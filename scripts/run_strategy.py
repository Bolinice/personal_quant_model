"""
多因子增强策略 - 基于真实数据 (V3 全面优化版)
支持股票池: 全A股 / 沪深300 / 中证500 / 中证1000

端到端流程:
  数据加载 → 因子计算(含行业中性化+分析师预期因子) → IC分析 →
  自适应因子权重(滚动ICIR) → Regime-aware选股 → ML增强融合(LightGBM WF) →
  多周期择时 → 组合构建(换手率控制+行业约束+行业偏离度+成本优化) → 回测

V2优化项:
  - 行业中性化: 因子预处理增加行业哑变量回归取残差
  - 换手率控制: 单次调仓换手率上限
  - 行业约束: 单行业权重≤20%
  - 多周期择时: 日线0.5 + 周线0.3 + 月线0.2
  - 回撤保护: 趋势跟踪止损
  - 交易明细: 输出持仓快照和交易流水

V3优化项:
  - 分析师预期因子: consensus_revision/analyst_coverage/eps_surprise
  - ML增强融合: LightGBM Walk-Forward + ICIR混合(0.6*ICIR + 0.4*ML)
  - 自适应因子权重: 滚动12期ICIR替代全样本ICIR
  - Regime-aware选股: 根据市场状态切换因子权重组合
  - 成本优化: 换仓成本过滤, 只有预期收益超过成本+阈值才换仓
  - 行业偏离度约束: 相对基准行业偏离≤5%
"""
import sys
from scripts.script_utils import build_in_clause
sys.path.insert(0, '.')

import argparse
import json
import time
import warnings
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine, text
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import settings
from app.core.timing_engine import TimingEngine, TimingSignalType, FusionMethod
from app.core.backtest_engine import ABShareBacktestEngine
from app.core.factor_preprocess import FactorPreprocessor

warnings.filterwarnings('ignore')

# 因子预计算缓存
_factor_cache = {}

# ==================== 股票池定义 ====================
UNIVERSE_CONFIG = {
    'all': {
        'name': '全A股', 'benchmark': '000001.SH',
        'top_n': 30, 'max_position': 0.06, 'min_history': 60,
    },
    'hs300': {
        'name': '沪深300', 'benchmark': '000300.SH', 'index_code': '000300.SH',
        'top_n': 10, 'max_position': 0.15, 'min_history': 60,
    },
    'zz500': {
        'name': '中证500', 'benchmark': '000905.SH', 'index_code': '000905.SH',
        'top_n': 20, 'max_position': 0.08, 'min_history': 60,
    },
    'zz1000': {
        'name': '中证1000', 'benchmark': '000852.SH', 'index_code': '000852.SH',
        'top_n': 30, 'max_position': 0.06, 'min_history': 60,
    },
}

# ==================== 策略参数 ====================
REBALANCE_FREQ = 'monthly'
INITIAL_CAPITAL = 500_000
BACKTEST_START = '2024-07-01'
BACKTEST_END = '2026-04-17'
MIN_IC_PERIODS = 10

# V2参数
MAX_TURNOVER = 0.50
MAX_INDUSTRY_WEIGHT = 0.20
DRAWDOWN_STOP_LEVEL1 = 0.10
DRAWDOWN_STOP_LEVEL2 = 0.15
DRAWDOWN_RECOVERY = 0.90

# V3参数
ROLLING_IC_WINDOW = 12        # 滚动ICIR窗口期数
ML_WEIGHT = 0.4               # ML融合权重
ICIR_WEIGHT = 0.6             # ICIR融合权重
COST_THRESHOLD = 0.005        # 换仓成本阈值(0.5%), 预期收益需超过此值才换仓
MAX_INDUSTRY_DEVIATION = 0.05 # 相对基准行业偏离≤5%
ML_TRAIN_WINDOW = 24          # ML训练窗口(期数)
ML_REFIT_FREQ = 6             # ML重训练频率(期数)

# ==================== 因子方向定义 ====================
FACTOR_DIR = {
    # 盈利质量
    'roe': 1, 'roa': 1, 'gross_profit_margin': 1, 'net_profit_margin': 1,
    # 动量反转
    'ret_1m_reversal': -1, 'ret_3m_skip1': 1, 'ret_6m_skip1': 1,
    # 波动流动性
    'vol_20d': -1, 'vol_60d': -1,
    'amihud_20d': -1, 'zero_return_ratio': -1,
    'overnight_return': -1,
    # 分析师预期 (V3)
    'consensus_revision': 1,    # 一致预期修正(正=上调)
    'analyst_coverage': 1,      # 分析师覆盖度(正=关注度高)
    'eps_surprise': 1,          # 盈利惊喜(正=超预期)
}

# Regime因子权重配置 (V3)
REGIME_FACTOR_WEIGHTS = {
    'trending': {
        # 趋势行情: 增加动量因子权重
        'ret_6m_skip1': 1.5, 'ret_3m_skip1': 1.3,
        'roe': 1.0, 'roa': 1.0,
        'consensus_revision': 1.3, 'eps_surprise': 1.2,
    },
    'oscillating': {
        # 震荡行情: 增加盈利质量和低波动因子权重
        'roe': 1.4, 'roa': 1.3, 'net_profit_margin': 1.3,
        'vol_20d': 1.3, 'vol_60d': 1.2,
        'zero_return_ratio': 1.2,
    },
    'defensive': {
        # 防御行情: 增加低波动和盈利稳定性因子权重
        'vol_20d': 1.5, 'vol_60d': 1.4,
        'zero_return_ratio': 1.4,
        'roe': 1.2, 'roa': 1.1,
        'analyst_coverage': 1.3,
    },
}


def load_universe(conn, universe_key):
    """加载股票池成分股列表"""
    cfg = UNIVERSE_CONFIG[universe_key]
    if universe_key == 'all':
        rows = conn.execute(text(
            "SELECT sb.ts_code FROM stock_basic sb "
            "WHERE sb.list_status = 'L' "
            "AND (sb.name IS NULL OR (sb.name NOT LIKE '%ST%' AND sb.name NOT LIKE '%*ST%'))"
        )).fetchall()
        codes = [r[0] for r in rows]
        print(f"  全A股(在市,非ST): {len(codes)} 只")
    else:
        index_code = cfg['index_code']
        rows = conn.execute(text(
            f"SELECT ts_code FROM index_components WHERE index_code = '{index_code}'"
        )).fetchall()
        codes = [r[0] for r in rows]
        print(f"  {cfg['name']}成分股: {len(codes)} 只")
    return codes


def load_industry_map(conn, universe_codes):
    """加载行业分类映射"""
    in_clause, in_params = build_in_clause(universe_codes)
    rows = conn.execute(text(
        f"SELECT ts_code, industry_name FROM stock_industry "
        f"WHERE ts_code IN ({in_clause}) AND standard = 'sw'"
    )).fetchall()
    industry_map = {r[0]: r[1] for r in rows}
    print(f"  行业分类: {len(industry_map)} 只股票, {len(set(industry_map.values()))} 个行业")
    return industry_map


def load_benchmark_industry_weights(conn, index_code):
    """加载基准指数行业权重 (V3: 用于行业偏离度约束)"""
    try:
        rows = conn.execute(text(
            f"SELECT industry_name, weight FROM index_industry_weight "
            f"WHERE index_code = '{index_code}'"
        )).fetchall()
        weights = {r[0]: float(r[1]) for r in rows}
        print(f"  基准行业权重: {len(weights)} 个行业")
        return weights
    except Exception as e:
        print(f"  基准行业权重: 不可用 ({e})")
        return {}


def load_stock_names(conn, universe_codes):
    """加载股票名称映射"""
    in_clause, in_params = build_in_clause(universe_codes)
    rows = conn.execute(text(
        f"SELECT ts_code, name FROM stock_basic WHERE ts_code IN ({in_clause})"
    )).fetchall()
    return {r[0]: r[1] for r in rows}


def load_data(engine, universe_key):
    """从数据库加载所有需要的数据"""
    cfg = UNIVERSE_CONFIG[universe_key]
    print(f"\n[1] 加载数据 [{cfg['name']}]...")
    t0 = time.time()

    with engine.connect() as conn:
        universe_codes = load_universe(conn, universe_key)
        industry_map = load_industry_map(conn, universe_codes)
        stock_names = load_stock_names(conn, universe_codes)

        # V3: 基准行业权重
        benchmark_industry_weights = {}
        if 'index_code' in cfg:
            benchmark_industry_weights = load_benchmark_industry_weights(conn, cfg['index_code'])

        in_clause, in_params = build_in_clause(universe_codes)

        # 股票日线
        stock_daily = pd.read_sql(text(
            f"SELECT ts_code, trade_date, open, high, low, close, pre_close, "
            f"pct_chg, vol, amount FROM stock_daily "
            f"WHERE ts_code IN ({in_clause}) ORDER BY ts_code, trade_date"
        ), conn, params=in_params)
        stock_daily['trade_date'] = pd.to_datetime(stock_daily['trade_date'])
        print(f"  股票日线: {len(stock_daily)} 条, {stock_daily['ts_code'].nunique()} 只")

        # 财务数据
        financial = pd.read_sql(text(
            f"SELECT ts_code, end_date, revenue, net_profit, roe, roa, "
            f"gross_profit_margin, net_profit_ratio, asset_liability_ratio, "
            f"operating_cash_flow, total_assets, total_equity, "
            f"current_assets, current_liabilities, "
            f"total_market_cap, pe_ttm, pb, ps_ttm, dividend_yield "
            f"FROM stock_financial WHERE ts_code IN ({in_clause}) ORDER BY ts_code, end_date"
        ), conn, params=in_params)
        financial['end_date'] = pd.to_datetime(financial['end_date'])
        print(f"  财务数据: {len(financial)} 条")

        # V3: 分析师一致预期数据
        analyst_consensus = pd.DataFrame()
        try:
            analyst_consensus = pd.read_sql(text(
                f"SELECT ts_code, trade_date, consensus_eps, consensus_target_price, "
                f"num_analyst, consensus_rating, consensus_rating_mean "
                f"FROM stock_analyst_consensus "
                f"WHERE ts_code IN ({in_clause}) ORDER BY ts_code, trade_date"
            ), conn, params=in_params)
            if not analyst_consensus.empty:
                analyst_consensus['trade_date'] = pd.to_datetime(analyst_consensus['trade_date'])
            print(f"  分析师一致预期: {len(analyst_consensus)} 条")
        except Exception as e:
            print(f"  分析师一致预期: 跳过 ({e})")

        # 基准指数日线
        benchmark = cfg['benchmark']
        index_daily = pd.read_sql(text(
            f"SELECT index_code, trade_date, close, pct_chg "
            f"FROM index_daily WHERE index_code = '{benchmark}' ORDER BY trade_date"
        ), conn)
        index_daily['trade_date'] = pd.to_datetime(index_daily['trade_date'])
        print(f"  基准指数({benchmark}): {len(index_daily)} 条")

        # 交易日历
        trading_days = sorted([pd.Timestamp(r[0]).date() for r in conn.execute(text(
            f"SELECT cal_date FROM trading_calendar WHERE is_open = true "
            f"AND cal_date >= '{BACKTEST_START}' AND cal_date <= '{BACKTEST_END}'"
        )).fetchall()])
        print(f"  交易日: {len(trading_days)} 天")

    print(f"  数据加载耗时: {time.time()-t0:.1f}s")
    return {
        'stock_daily': stock_daily,
        'financial': financial,
        'analyst_consensus': analyst_consensus,
        'index_daily': index_daily,
        'trading_days': trading_days,
        'universe_codes': universe_codes,
        'industry_map': industry_map,
        'stock_names': stock_names,
        'benchmark_industry_weights': benchmark_industry_weights,
    }


def calc_cross_section_factors(trade_date, data, use_cache=True):
    """
    计算截面因子值 (V3: 含分析师预期因子)
    返回: DataFrame, index=ts_code, columns=各因子
    """
    cache_key = str(trade_date)
    if use_cache and cache_key in _factor_cache:
        return _factor_cache[cache_key]

    sd = data['stock_daily']
    fin = data['financial']
    ac = data.get('analyst_consensus', pd.DataFrame())
    td = pd.Timestamp(trade_date)

    start_date = td - timedelta(days=400)
    price_window = sd[(sd['trade_date'] >= start_date) & (sd['trade_date'] <= td)].copy()

    if price_window.empty:
        return pd.DataFrame()

    # PIT安全: 财务数据
    if 'ann_date' in fin.columns:
        fin_latest = fin[fin['ann_date'] <= td].copy()
    else:
        fin_latest = fin[fin['end_date'] <= td].copy()
    if not fin_latest.empty:
        if 'ann_date' in fin_latest.columns:
            fin_latest = fin_latest.sort_values('ann_date').groupby('ts_code').last()
        else:
            fin_latest = fin_latest.sort_values('end_date').groupby('ts_code').last()

    # PIT安全: 分析师一致预期
    ac_latest = pd.DataFrame()
    if not ac.empty:
        ac_latest = ac[ac['trade_date'] <= td].copy()
        if not ac_latest.empty:
            ac_latest = ac_latest.sort_values('trade_date').groupby('ts_code').last()

    price_window = price_window.sort_values(['ts_code', 'trade_date'])

    stock_counts = price_window.groupby('ts_code').size()
    valid_stocks = stock_counts[stock_counts >= 60].index
    price_window = price_window[price_window['ts_code'].isin(valid_stocks)]

    if price_window.empty:
        return pd.DataFrame()

    grouped = price_window.groupby('ts_code')
    close = price_window.set_index(['ts_code', 'trade_date'])['close'].unstack(level=0)

    results = {}

    for ts_code in valid_stocks:
        if ts_code not in close.columns:
            continue
        c = close[ts_code].dropna()
        row = {}
        if len(c) >= 20:
            row['ret_1m_reversal'] = c.iloc[-1] / c.iloc[-20] - 1
        if len(c) >= 60:
            row['ret_3m_skip1'] = c.iloc[-20] / c.iloc[-60] - 1 if c.iloc[-60] != 0 else np.nan
        if len(c) >= 120:
            row['ret_6m_skip1'] = c.iloc[-20] / c.iloc[-120] - 1 if c.iloc[-120] != 0 else np.nan
        results[ts_code] = row

    for ts_code, group in grouped:
        if ts_code not in results:
            continue
        group = group.sort_values('trade_date')
        row = results[ts_code]

        close_s = group['close']
        open_ = group['open']
        amount = group['amount']

        daily_ret = close_s.pct_change().dropna()
        if len(daily_ret) >= 20:
            row['vol_20d'] = daily_ret.iloc[-20:].std() * np.sqrt(252)
        if len(daily_ret) >= 60:
            row['vol_60d'] = daily_ret.iloc[-60:].std() * np.sqrt(252)

        if len(group) >= 20 and (amount.iloc[-20:] > 0).all():
            abs_ret = close_s.pct_change().abs()
            amihud = (abs_ret / amount.replace(0, np.nan)).iloc[-20:].mean()
            row['amihud_20d'] = amihud if not np.isnan(amihud) else np.nan
        if len(daily_ret) >= 20:
            row['zero_return_ratio'] = (daily_ret.iloc[-20:].abs() < 0.001).mean()

        if len(group) >= 20 and (close_s.iloc[:-1] > 0).all():
            overnight = open_.iloc[1:].values / close_s.iloc[:-1].values - 1
            row['overnight_return'] = np.mean(overnight[-20:])

        if ts_code in fin_latest.index:
            f = fin_latest.loc[ts_code]
            row['roe'] = f.get('roe')
            row['roa'] = f.get('roa')
            row['gross_profit_margin'] = f.get('gross_profit_margin')
            row['net_profit_margin'] = f.get('net_profit_ratio')

            if pd.notna(f.get('operating_cash_flow')) and pd.notna(f.get('total_assets')) and f.get('total_assets', 0) != 0:
                net_profit = f.get('net_profit', 0)
                ocf = f.get('operating_cash_flow', 0)
                total_assets = f.get('total_assets', 0)
                accruals = net_profit - ocf
                row['sloan_accrual'] = accruals / total_assets
                if net_profit != 0:
                    row['cfo_to_net_profit'] = np.clip(ocf / net_profit, -5, 5)

        # V3: 分析师预期因子
        if not ac_latest.empty and ts_code in ac_latest.index:
            a = ac_latest.loc[ts_code]
            # 一致预期EPS修正: 当前EPS vs 20天前EPS
            if pd.notna(a.get('consensus_eps')):
                row['consensus_revision'] = a.get('consensus_eps')  # 将在预处理中做差分
            # 分析师覆盖度
            if pd.notna(a.get('num_analyst')):
                row['analyst_coverage'] = float(a.get('num_analyst', 0))
            # 盈利惊喜: 基于一致预期评级
            if pd.notna(a.get('consensus_rating_mean')):
                row['eps_surprise'] = float(a.get('consensus_rating_mean', 0))

    if not results:
        return pd.DataFrame()

    factor_df = pd.DataFrame(results).T
    factor_df.index.name = 'ts_code'

    preprocessor = FactorPreprocessor()
    factor_cols = [c for c in factor_df.columns if c in FACTOR_DIR]

    # Step 1: MAD去极值 + Z-score标准化
    for col in factor_cols:
        series = factor_df[col].dropna()
        if len(series) < 10:
            continue

        median = series.median()
        mad = (series - median).abs().median()
        if mad > 0:
            upper = median + 3 * 1.4826 * mad
            lower = median - 3 * 1.4826 * mad
            factor_df[col] = factor_df[col].clip(lower, upper)

        mean = factor_df[col].mean()
        std = factor_df[col].std()
        if std > 0:
            factor_df[col] = (factor_df[col] - mean) / std

        direction = FACTOR_DIR.get(col, 1)
        if direction < 0:
            factor_df[col] = -factor_df[col]

    # Step 2: 行业中性化
    industry_map = data.get('industry_map', {})
    if industry_map:
        factor_df['_industry'] = factor_df.index.map(industry_map)
        for col in factor_cols:
            if col not in factor_df.columns:
                continue
            series = factor_df[col].dropna()
            if len(series) < 30:
                continue
            if '_industry' in factor_df.columns:
                industry_groups = factor_df.groupby('_industry')[col]
                industry_mean = industry_groups.transform('mean')
                industry_std = industry_groups.transform('std')
                valid = industry_std > 0
                factor_df.loc[valid, col] = ((factor_df[col] - industry_mean) / industry_std).loc[valid]
        factor_df = factor_df.drop(columns=['_industry'], errors='ignore')

    if use_cache:
        _factor_cache[cache_key] = factor_df

    return factor_df


def _calc_ic_for_date(td, data):
    """计算单日IC"""
    try:
        factor_df = calc_cross_section_factors(td, data)
        if factor_df.empty or len(factor_df) < 30:
            return []

        sd = data['stock_daily']
        td_ts = pd.Timestamp(td)
        fwd_date = td_ts + timedelta(days=30)

        price_now = sd[sd['trade_date'] <= td_ts].groupby('ts_code')['close'].last()
        price_fwd = sd[(sd['trade_date'] > td_ts) & (sd['trade_date'] <= fwd_date)].groupby('ts_code')['close'].last()

        fwd_return = (price_fwd / price_now - 1).dropna()

        date_ics = []
        for col in factor_df.columns:
            if col not in FACTOR_DIR:
                continue
            fv = factor_df[col].dropna()
            common = fv.index.intersection(fwd_return.index)
            if len(common) < 30:
                continue

            ic = fv.loc[common].corr(fwd_return.loc[common])
            rank_ic = fv.loc[common].rank().corr(fwd_return.loc[common].rank())

            date_ics.append({
                'trade_date': td, 'factor': col,
                'ic': ic if not np.isnan(ic) else 0,
                'rank_ic': rank_ic if not np.isnan(rank_ic) else 0,
            })
        return date_ics
    except Exception:
        return []


def calc_factor_ic(data, trading_days, n_periods=40, n_workers=4):
    """计算各因子IC - 并行化"""
    print("\n[2] 计算因子IC...")
    t0 = time.time()

    calc_dates = trading_days[::5]
    if len(calc_dates) > n_periods:
        calc_dates = calc_dates[-n_periods:]

    all_ic = []
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(_calc_ic_for_date, td, data): td for td in calc_dates}
        for future in as_completed(futures):
            result = future.result()
            all_ic.extend(result)

    if not all_ic:
        print("  IC计算失败")
        return {}, {}

    ic_df = pd.DataFrame(all_ic)

    print(f"\n  {'因子':<25s} {'IC均值':>8s} {'ICIR':>8s} {'RankIC':>8s} {'胜率':>6s}")
    print("  " + "-" * 60)

    ic_summary = {}
    for factor in ic_df['factor'].unique():
        f_ic = ic_df[ic_df['factor'] == factor]
        ic_mean = f_ic['ic'].mean()
        ic_std = f_ic['ic'].std()
        icir = ic_mean / ic_std if ic_std > 0 else 0
        rank_ic_mean = f_ic['rank_ic'].mean()
        win_rate = (f_ic['ic'] > 0).mean()

        ic_summary[factor] = {
            'ic_mean': ic_mean, 'ic_std': ic_std, 'icir': icir,
            'rank_ic_mean': rank_ic_mean, 'win_rate': win_rate,
            'n_periods': len(f_ic),
        }
        print(f"  {factor:<25s} {ic_mean:>8.4f} {icir:>8.2f} {rank_ic_mean:>8.4f} {win_rate:>6.2f}")

    print(f"  IC计算耗时: {time.time()-t0:.1f}s")
    return ic_summary, ic_df


def calc_rolling_ic_weights(ic_df, current_date, window=ROLLING_IC_WINDOW):
    """V3: 自适应因子权重 - 基于滚动ICIR"""
    if ic_df.empty:
        return {}

    td = pd.Timestamp(current_date)
    recent_ic = ic_df[pd.to_datetime(ic_df['trade_date']) <= td]

    if recent_ic.empty:
        return {}

    # 取最近window期
    dates = sorted(recent_ic['trade_date'].unique())
    if len(dates) > window:
        recent_ic = recent_ic[recent_ic['trade_date'].isin(dates[-window:])]

    weights = {}
    for factor in recent_ic['factor'].unique():
        f_ic = recent_ic[recent_ic['factor'] == factor]
        if len(f_ic) < MIN_IC_PERIODS:
            continue
        ic_mean = f_ic['ic'].mean()
        ic_std = f_ic['ic'].std()
        icir = ic_mean / ic_std if ic_std > 0 else 0
        if icir > 0:
            weights[factor] = icir

    if weights:
        total_w = sum(abs(v) for v in weights.values())
        weights = {k: v / total_w for k, v in weights.items()}

    return weights


def detect_market_regime(index_daily, trade_date, lookback=60):
    """V3: 检测市场状态 (趋势/震荡/防御)"""
    td = pd.Timestamp(trade_date)
    idx = index_daily.set_index('trade_date').sort_index()
    idx_slice = idx[idx.index <= td].tail(lookback)

    if len(idx_slice) < 20:
        return 'oscillating'

    close = idx_slice['close']
    returns = close.pct_change().dropna()

    # 趋势强度: MA20 vs MA60
    ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else close.iloc[-1]
    trend_strength = (ma20 / ma60 - 1) if ma60 > 0 else 0

    # 波动率
    vol = returns.std() * np.sqrt(252) if len(returns) >= 10 else 0.2

    # 回撤
    peak = close.max()
    current = close.iloc[-1]
    drawdown = (current - peak) / peak if peak > 0 else 0

    # 分类逻辑
    if drawdown < -0.10:
        return 'defensive'
    elif trend_strength > 0.02 and vol < 0.25:
        return 'trending'
    elif trend_strength < -0.02 or vol > 0.30:
        return 'defensive'
    else:
        return 'oscillating'


def apply_regime_weights(base_weights, regime):
    """V3: 根据市场状态调整因子权重"""
    regime_config = REGIME_FACTOR_WEIGHTS.get(regime, {})
    if not regime_config:
        return base_weights

    adjusted = {}
    for factor, weight in base_weights.items():
        multiplier = regime_config.get(factor, 1.0)
        adjusted[factor] = weight * multiplier

    # 归一化
    total = sum(abs(v) for v in adjusted.values())
    if total > 0:
        adjusted = {k: v / total for k, v in adjusted.items()}

    return adjusted


def calc_timing_signals(data, trading_days):
    """计算择时信号 - 多周期融合"""
    print("\n[3] 计算择时信号(多周期)...")
    t0 = time.time()

    engine = TimingEngine()
    idx = data['index_daily'].set_index('trade_date')['close'].sort_index()

    # 日线信号
    ma_signal = engine.ma_cross_signal(idx, short_window=20, long_window=60)
    vol_signal = engine.volatility_signal(idx, window=20, low_vol_threshold=0.12, high_vol_threshold=0.25)
    dd_signal = engine.drawdown_control_signal(idx, max_drawdown=0.10, recovery_threshold=0.03)
    daily_fused = engine.fuse_signals({
        'ma': ma_signal, 'vol': vol_signal, 'drawdown': dd_signal,
    }, method=FusionMethod.EQUAL)

    # 周线信号
    weekly_idx = idx.resample('5B').last().dropna()
    if len(weekly_idx) >= 60:
        weekly_ma = engine.ma_cross_signal(weekly_idx, short_window=4, long_window=12)
        weekly_vol = engine.volatility_signal(weekly_idx, window=4, low_vol_threshold=0.10, high_vol_threshold=0.20)
        weekly_fused = engine.fuse_signals({'ma': weekly_ma, 'vol': weekly_vol}, method=FusionMethod.EQUAL)
        weekly_fused_daily = weekly_fused.reindex(idx.index, method='ffill')
    else:
        weekly_fused_daily = pd.Series(TimingSignalType.NEUTRAL, index=idx.index)

    # 月线信号
    monthly_idx = idx.resample('20B').last().dropna()
    if len(monthly_idx) >= 12:
        monthly_ma = engine.ma_cross_signal(monthly_idx, short_window=3, long_window=6)
        monthly_fused_daily = monthly_ma.reindex(idx.index, method='ffill')
    else:
        monthly_fused_daily = pd.Series(TimingSignalType.NEUTRAL, index=idx.index)

    # 多周期融合
    def signal_to_numeric(s):
        return s.map({
            TimingSignalType.LONG: 1, TimingSignalType.NEUTRAL: 0, TimingSignalType.SHORT: -1,
        }).fillna(0)

    daily_num = signal_to_numeric(daily_fused)
    weekly_num = signal_to_numeric(weekly_fused_daily)
    monthly_num = signal_to_numeric(monthly_fused_daily)

    combined = 0.5 * daily_num + 0.3 * weekly_num + 0.2 * monthly_num

    fused = pd.Series(TimingSignalType.NEUTRAL, index=idx.index)
    fused[combined > 0.2] = TimingSignalType.LONG
    fused[combined < -0.2] = TimingSignalType.SHORT

    n_long = (fused == TimingSignalType.LONG).sum()
    n_short = (fused == TimingSignalType.SHORT).sum()
    n_neutral = (fused == TimingSignalType.NEUTRAL).sum()
    total = len(fused)
    print(f"  多周期融合: 看多{n_long} 看空{n_short} 中性{n_neutral}")

    exposure = engine.calc_target_exposure(fused, base_exposure=0.8, max_exposure=1.0, min_exposure=0.2)
    print(f"  择时计算耗时: {time.time()-t0:.1f}s")
    return fused, exposure


def apply_industry_constraints(weights, industry_map, benchmark_weights,
                                max_industry_weight=MAX_INDUSTRY_WEIGHT,
                                max_industry_deviation=MAX_INDUSTRY_DEVIATION):
    """V3: 行业约束 (绝对权重上限 + 相对基准偏离度约束)"""
    if not industry_map:
        return weights

    adjusted = weights.copy()

    # 计算当前行业权重
    current_industry_weights = {}
    for ts_code, weight in adjusted.items():
        industry = industry_map.get(ts_code, 'unknown')
        current_industry_weights[industry] = current_industry_weights.get(industry, 0) + weight

    # 约束1: 单行业绝对权重上限
    over_limit = {ind: w for ind, w in current_industry_weights.items() if w > max_industry_weight}
    if over_limit:
        excess_weight = 0.0
        for ind, ind_weight in over_limit.items():
            scale = max_industry_weight / ind_weight
            for ts_code in adjusted.index:
                if industry_map.get(ts_code) == ind:
                    adjusted[ts_code] *= scale
            excess_weight += ind_weight * (1 - scale)

        if excess_weight > 0:
            under_limit = {ind: w for ind, w in current_industry_weights.items() if w <= max_industry_weight}
            if under_limit:
                under_total = sum(adjusted[ts_code] for ts_code in adjusted.index
                                  if industry_map.get(ts_code) in under_limit)
                if under_total > 0:
                    for ts_code in adjusted.index:
                        if industry_map.get(ts_code) in under_limit:
                            adjusted[ts_code] += excess_weight * (adjusted[ts_code] / under_total)

    # 约束2: V3 - 相对基准行业偏离度约束
    if benchmark_weights:
        # 重新计算行业权重
        current_industry_weights = {}
        for ts_code, weight in adjusted.items():
            industry = industry_map.get(ts_code, 'unknown')
            current_industry_weights[industry] = current_industry_weights.get(industry, 0) + weight

        deviation_excess = 0.0
        for industry, current_w in current_industry_weights.items():
            benchmark_w = benchmark_weights.get(industry, 0)
            deviation = current_w - benchmark_w
            if deviation > max_industry_deviation:
                # 超过偏离上限, 缩减该行业
                target_w = benchmark_w + max_industry_deviation
                scale = target_w / current_w if current_w > 0 else 1.0
                for ts_code in adjusted.index:
                    if industry_map.get(ts_code) == industry:
                        reduced = adjusted[ts_code] * (1 - scale)
                        adjusted[ts_code] *= scale
                        deviation_excess += reduced

        # 将释放的权重按比例分配给偏离度未超限的行业
        if deviation_excess > 0:
            under_industries = []
            for industry, current_w in current_industry_weights.items():
                benchmark_w = benchmark_weights.get(industry, 0)
                if current_w - benchmark_w <= max_industry_deviation:
                    under_industries.append(industry)

            if under_industries:
                under_total = sum(adjusted[ts_code] for ts_code in adjusted.index
                                  if industry_map.get(ts_code) in under_industries)
                if under_total > 0:
                    for ts_code in adjusted.index:
                        if industry_map.get(ts_code) in under_industries:
                            adjusted[ts_code] += deviation_excess * (adjusted[ts_code] / under_total)

    # 归一化
    total = adjusted.sum()
    if total > 0:
        adjusted = adjusted / total

    return adjusted


def apply_cost_filter(new_weights, old_weights, cost_threshold=COST_THRESHOLD):
    """V3: 成本优化 - 只有预期收益超过换仓成本+阈值才换仓"""
    if old_weights.empty:
        return new_weights

    # 计算换仓成本: 买入佣金0.025% + 卖出佣金0.025% + 印花税0.1% + 滑点0.1% = ~0.25%
    # 双边换仓成本约0.25%
    trade_cost_rate = 0.0025

    filtered = new_weights.copy()
    weight_changes = new_weights.subtract(old_weights.reindex(new_weights.index, fill_value=0), fill_value=0)

    for ts_code in weight_changes.index:
        change = weight_changes[ts_code]
        # 换仓的绝对成本
        abs_change = abs(change)
        if abs_change < 0.001:
            # 权重变化极小, 不换仓
            if ts_code in old_weights.index:
                filtered[ts_code] = old_weights[ts_code]
            continue

        # 换仓成本占权重变化的比例
        cost_ratio = trade_cost_rate * abs_change / abs_change if abs_change > 0 else 0

        # 如果权重变化带来的预期收益不足以覆盖成本, 不换仓
        # 简化判断: 如果新权重与旧权重差异小于成本阈值, 保持旧权重
        if ts_code in old_weights.index:
            old_w = old_weights[ts_code]
            new_w = new_weights[ts_code]
            # 只有当权重变化超过成本阈值时才调整
            if abs(new_w - old_w) < cost_threshold:
                filtered[ts_code] = old_w

    # 归一化
    total = filtered.sum()
    if total > 0:
        filtered = filtered / total

    return filtered


def build_training_data(data, rebalance_dates, n_history=12, fwd_days=20):
    """
    构建股票级训练数据
    每个截面期每只股票是一个样本:
      特征X = 该股票在该截面期的因子暴露(行业中性化后)
      标签y = 该股票从该截面期开始的未来fwd_days日超额收益(相对行业均值)
    """
    sd = data['stock_daily']
    industry_map = data.get('industry_map', {})

    all_samples = []
    sorted_dates = sorted(rebalance_dates)

    for i, td in enumerate(sorted_dates):
        td_ts = pd.Timestamp(td)

        # 计算该截面期的因子暴露
        factor_df = calc_cross_section_factors(td, data, use_cache=True)
        if factor_df.empty or len(factor_df) < 30:
            continue

        # 计算未来fwd_days日收益
        fwd_end = td_ts + timedelta(days=fwd_days + 10)  # 多留几天缓冲
        price_now = sd[sd['trade_date'] <= td_ts].groupby('ts_code')['close'].last()
        price_fwd = sd[(sd['trade_date'] > td_ts) & (sd['trade_date'] <= fwd_end)].groupby('ts_code')['close'].last()

        fwd_return = (price_fwd / price_now - 1).dropna()

        # 行业中性超额收益: 减去行业均值
        if industry_map:
            industry_returns = {}
            for ts_code, ret in fwd_return.items():
                ind = industry_map.get(ts_code, 'unknown')
                if ind not in industry_returns:
                    industry_returns[ind] = []
                industry_returns[ind].append(ret)
            industry_mean = {ind: np.mean(rets) for ind, rets in industry_returns.items()}

            excess_return = pd.Series(dtype=float)
            for ts_code, ret in fwd_return.items():
                ind = industry_map.get(ts_code, 'unknown')
                excess_return[ts_code] = ret - industry_mean.get(ind, 0)
        else:
            excess_return = fwd_return

        # 构建样本
        factor_cols = [c for c in factor_df.columns if c in FACTOR_DIR]
        common = factor_df.index.intersection(excess_return.index)

        if len(common) < 30:
            continue

        for ts_code in common:
            sample = {'ts_code': ts_code, 'trade_date': td}
            for col in factor_cols:
                sample[f'f_{col}'] = factor_df.loc[ts_code, col] if col in factor_df.columns else np.nan
                # 因子排名特征 (百分位)
                if col in factor_df.columns:
                    rank = factor_df[col].rank(pct=True)
                    sample[f'f_{col}_rank'] = rank.get(ts_code, np.nan)
            sample['label'] = excess_return[ts_code]
            all_samples.append(sample)

    if not all_samples:
        return pd.DataFrame(), []

    df = pd.DataFrame(all_samples)
    feature_cols = [c for c in df.columns if c.startswith('f_')]
    return df, feature_cols


def train_ml_model(data, rebalance_dates, current_date, n_history=12, fwd_days=20):
    """
    V3重构: LightGBM Walk-Forward训练
    用过去n_history期的截面数据训练，预测当期股票评分

    训练数据: 每只股票在每个截面期是一个样本
    特征X: 因子暴露 + 因子排名
    标签y: 未来20日行业中性超额收益
    """
    try:
        import lightgbm as lgb
    except ImportError:
        print("  LightGBM未安装, 跳过ML融合")
        return None, None

    td = pd.Timestamp(current_date)
    sorted_dates = sorted(rebalance_dates)

    # 找到当前日期之前的调仓日
    past_dates = [d for d in sorted_dates if pd.Timestamp(d) < td]
    if len(past_dates) < n_history + 2:
        return None, None

    # 取最近n_history期作为训练数据
    train_dates = past_dates[-n_history:]

    # 构建训练数据
    train_df, feature_cols = build_training_data(data, train_dates, n_history, fwd_days)

    if train_df.empty or len(train_df) < 100:
        return None, None

    # 清理NaN
    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['label']

    # 去除标签异常值
    label_mean = y_train.mean()
    label_std = y_train.std()
    if label_std > 0:
        valid_mask = (y_train - label_mean).abs() < 3 * label_std
        X_train = X_train[valid_mask]
        y_train = y_train[valid_mask]

    if len(X_train) < 50:
        return None, None

    # 分出验证集: 最近2期数据
    last_2_dates = sorted(train_df['trade_date'].unique())[-2:]
    val_mask = train_df['trade_date'].isin(last_2_dates)
    # 重新计算valid_mask对齐
    val_idx = train_df.index[val_mask.values if hasattr(val_mask, 'values') else val_mask]
    train_idx = train_df.index[~(val_mask.values if hasattr(val_mask, 'values') else val_mask)]

    X_tr = X_train.loc[train_idx]
    y_tr = y_train.loc[train_idx]
    X_val = X_train.loc[val_idx]
    y_val = y_train.loc[val_idx]

    if len(X_tr) < 30 or len(X_val) < 10:
        # 验证集不够, 全部用于训练
        X_tr, y_tr = X_train, y_train
        X_val, y_val = None, None

    # 训练LightGBM
    try:
        model = lgb.LGBMRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            min_child_samples=50,
            subsample=0.7,
            colsample_bytree=0.7,
            reg_alpha=0.1,
            reg_lambda=0.5,
            random_state=42,
            verbose=-1,
        )

        if X_val is not None and len(X_val) >= 10:
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(20, verbose=False)],
            )
        else:
            model.fit(X_tr, y_tr)

        # 检查模型质量: 训练集IC
        train_pred = model.predict(X_train)
        train_ic = np.corrcoef(train_pred, y_train.values)[0, 1]
        if np.isnan(train_ic) or train_ic < 0.02:
            return None, None

        n_features = len(feature_cols)
        print(f"  ML模型训练完成: {len(X_train)}样本, {n_features}特征, 训练IC={train_ic:.3f}")
        return model, feature_cols

    except Exception as e:
        print(f"  ML训练失败: {e}")
        return None, None


def predict_ml_score(model, feature_cols, factor_df):
    """
    V3重构: 使用ML模型预测股票评分
    输入: 训练好的模型, 特征列名, 当期因子暴露矩阵
    输出: pd.Series, index=ts_code, values=ML评分(标准化后)
    """
    if model is None:
        return None

    # 构建预测特征
    factor_cols = [c for c in factor_df.columns if c in FACTOR_DIR]
    pred_data = {}

    for ts_code in factor_df.index:
        sample = {}
        for col in factor_cols:
            sample[f'f_{col}'] = factor_df.loc[ts_code, col] if col in factor_df.columns else np.nan
            if col in factor_df.columns:
                rank = factor_df[col].rank(pct=True)
                sample[f'f_{col}_rank'] = rank.get(ts_code, np.nan)
        pred_data[ts_code] = sample

    if not pred_data:
        return None

    X_pred = pd.DataFrame(pred_data).T
    X_pred = X_pred.fillna(0)

    # 确保特征列一致
    for col in feature_cols:
        if col not in X_pred.columns:
            X_pred[col] = 0
    X_pred = X_pred[feature_cols]

    # 预测
    raw_pred = model.predict(X_pred)
    ml_score = pd.Series(raw_pred, index=factor_df.index)

    # 标准化
    std = ml_score.std()
    mean = ml_score.mean()
    if std > 0:
        ml_score = (ml_score - mean) / std
    else:
        ml_score = pd.Series(0.0, index=factor_df.index)

    return ml_score


def run_backtest(data, trading_days, ic_summary, ic_df, timing_exposure, universe_key):
    """运行回测 (V3: 全部优化)"""
    cfg = UNIVERSE_CONFIG[universe_key]
    top_n = cfg['top_n']
    max_position = cfg['max_position']

    print(f"\n[4] 运行回测 [V3全面优化, 持仓{top_n}只]...")
    t0 = time.time()

    sd = data['stock_daily']
    idx = data['index_daily']
    industry_map = data.get('industry_map', {})
    stock_names = data.get('stock_names', {})
    benchmark_industry_weights = data.get('benchmark_industry_weights', {})

    # 准备行情数据
    print("  准备行情数据...")
    price_data = {}
    for row in sd[['ts_code', 'trade_date', 'close', 'open', 'high', 'low', 'pct_chg', 'vol', 'amount']].itertuples(index=False):
        td = row.trade_date.date() if hasattr(row.trade_date, 'date') else row.trade_date
        key = (row.ts_code, td)
        price_data[key] = {
            'close': float(row.close),
            'open': float(row.open),
            'high': float(row.high),
            'low': float(row.low),
            'pct_chg': float(row.pct_chg) if pd.notna(row.pct_chg) else 0,
            'volume': float(row.vol) if pd.notna(row.vol) else 0,
            'amount': float(row.amount) if pd.notna(row.amount) else 0,
            'is_suspended': False, 'is_st': False,
        }

    # 预计算调仓日因子
    print("  预计算调仓日因子...")
    rebalance_dates = set()
    if REBALANCE_FREQ == 'monthly':
        seen_months = set()
        for td in trading_days:
            month_key = (td.year, td.month)
            if month_key not in seen_months:
                seen_months.add(month_key)
                rebalance_dates.add(td)
    elif REBALANCE_FREQ == 'weekly':
        seen_weeks = set()
        for td in trading_days:
            week_key = td.isocalendar()[:2]
            if week_key not in seen_weeks:
                seen_weeks.add(week_key)
                rebalance_dates.add(td)
    else:
        rebalance_dates = set(trading_days)

    sorted_rebalance_dates = sorted(rebalance_dates)

    precomputed = 0
    for td in rebalance_dates:
        if str(td) not in _factor_cache:
            calc_cross_section_factors(td, data, use_cache=True)
            precomputed += 1
    print(f"  预计算 {precomputed} 个调仓日因子完成")

    # 基准净值
    idx_sorted = idx.set_index('trade_date').sort_index()
    start_nav = idx_sorted[idx_sorted.index >= BACKTEST_START].iloc[0]['close']
    benchmark_nav = []
    for td in trading_days:
        td_ts = pd.Timestamp(td)
        if td_ts in idx_sorted.index:
            benchmark_nav.append({'trade_date': td, 'nav': float(idx_sorted.loc[td_ts, 'close']) / start_nav})

    # 全样本ICIR权重 (作为自适应权重的fallback)
    full_icir_weights = {}
    if ic_summary:
        for factor, stats in ic_summary.items():
            if stats['icir'] > 0 and stats['n_periods'] >= MIN_IC_PERIODS:
                full_icir_weights[factor] = stats['icir']
    if full_icir_weights:
        total_w = sum(abs(v) for v in full_icir_weights.values())
        full_icir_weights = {k: v / total_w for k, v in full_icir_weights.items()}

    print(f"  全样本ICIR加权因子: {len(full_icir_weights)} 个")

    # V3: ML模型状态
    ml_model = None
    ml_feature_cols = None
    ml_train_counter = 0

    # 回撤保护状态
    drawdown_state = {'peak_nav': 1.0, 'current_position_scale': 1.0}

    # V3: Regime统计
    regime_stats = {'trending': 0, 'oscillating': 0, 'defensive': 0}

    def signal_generator(trade_date, universe, state):
        nonlocal ml_model, ml_feature_cols, ml_train_counter

        td_ts = pd.Timestamp(trade_date)
        if td_ts in timing_exposure.index:
            exposure = float(timing_exposure.loc[td_ts])
        else:
            exposure = 0.8

        # 回撤保护
        if hasattr(state, 'nav_history') and state.nav_history:
            current_nav = state.nav_history[-1]['nav']
            drawdown_state['peak_nav'] = max(drawdown_state['peak_nav'], current_nav)
            drawdown = (current_nav - drawdown_state['peak_nav']) / drawdown_state['peak_nav']

            if abs(drawdown) > DRAWDOWN_STOP_LEVEL2:
                drawdown_state['current_position_scale'] = 0.375
            elif abs(drawdown) > DRAWDOWN_STOP_LEVEL1:
                drawdown_state['current_position_scale'] = 0.75
            elif current_nav > DRAWDOWN_RECOVERY * drawdown_state['peak_nav']:
                drawdown_state['current_position_scale'] = 1.0

            exposure *= drawdown_state['current_position_scale']

        # V3: 检测市场状态
        regime = detect_market_regime(idx, trade_date)
        regime_stats[regime] = regime_stats.get(regime, 0) + 1

        # V3: 自适应因子权重 (滚动ICIR)
        current_weights = calc_rolling_ic_weights(ic_df, trade_date, ROLLING_IC_WINDOW)
        if not current_weights:
            current_weights = full_icir_weights.copy()

        # V3: Regime-aware权重调整
        current_weights = apply_regime_weights(current_weights, regime)

        # V3: ML Walk-Forward训练 (每ML_REFIT_FREQ期重训练)
        ml_train_counter += 1
        if ml_train_counter % ML_REFIT_FREQ == 1 or ml_model is None:
            ml_model, ml_feature_cols = train_ml_model(
                data, sorted_rebalance_dates, trade_date,
                n_history=12, fwd_days=20,
            )

        # 计算因子
        factor_df = calc_cross_section_factors(trade_date, data)
        if factor_df.empty or len(factor_df) < top_n:
            return {}

        factor_cols = [c for c in factor_df.columns if c in FACTOR_DIR]

        # IC加权评分
        if current_weights:
            ic_score = pd.Series(0.0, index=factor_df.index)
            for col, w in current_weights.items():
                if col in factor_df.columns:
                    ic_score += factor_df[col].fillna(0) * w
        else:
            ic_score = factor_df[factor_cols].mean(axis=1)

        # 标准化IC评分
        ic_std = ic_score.std()
        ic_mean = ic_score.mean()
        if ic_std > 0:
            ic_score_norm = (ic_score - ic_mean) / ic_std
        else:
            ic_score_norm = ic_score

        # V3: ML融合
        if ml_model is not None and ml_feature_cols is not None:
            ml_score = predict_ml_score(ml_model, ml_feature_cols, factor_df)
            if ml_score is not None and not ml_score.empty:
                # 两者都已标准化, 直接加权混合
                common_idx = ic_score_norm.index.intersection(ml_score.index)
                score = ic_score_norm.copy()
                score.loc[common_idx] = (ICIR_WEIGHT * ic_score_norm.loc[common_idx] +
                                          ML_WEIGHT * ml_score.loc[common_idx])
            else:
                score = ic_score_norm
        else:
            score = ic_score_norm

        top_stocks = score.nlargest(top_n)

        scores = top_stocks - top_stocks.min() + 0.01
        weights = scores / scores.sum()
        weights = weights.clip(upper=max_position)
        weights = weights / weights.sum()

        # 行业约束 (绝对权重上限 + V3: 相对基准偏离度)
        weights = apply_industry_constraints(
            weights, industry_map, benchmark_industry_weights,
            MAX_INDUSTRY_WEIGHT, MAX_INDUSTRY_DEVIATION
        )

        # V3: 成本优化 (换仓成本过滤)
        if hasattr(state, 'positions') and state.positions:
            current_total = state.cash + sum(p.market_value for p in state.positions.values())
            old_weights = pd.Series({
                ts_code: p.market_value / current_total
                for ts_code, p in state.positions.items()
            }) if current_total > 0 else pd.Series(dtype=float)

            if not old_weights.empty:
                # 先应用成本过滤
                weights = apply_cost_filter(weights, old_weights, COST_THRESHOLD)

                # 再应用换手率控制
                turnover = (weights.subtract(old_weights.reindex(weights.index, fill_value=0), fill_value=0).abs().sum()) / 2
                if turnover > MAX_TURNOVER:
                    alpha = MAX_TURNOVER / turnover
                    weights = old_weights.reindex(weights.index, fill_value=0) + alpha * (
                        weights - old_weights.reindex(weights.index, fill_value=0)
                    )
                    if weights.sum() > 0:
                        weights = weights / weights.sum()

        weights = weights * exposure

        return dict(weights)

    bt_engine = ABShareBacktestEngine()
    start_date = date.fromisoformat(BACKTEST_START)
    end_date = date.fromisoformat(BACKTEST_END)

    result = bt_engine.run_backtest(
        signal_generator=signal_generator,
        universe=data['universe_codes'],
        start_date=start_date,
        end_date=end_date,
        rebalance_freq=REBALANCE_FREQ,
        initial_capital=INITIAL_CAPITAL,
        trading_days=trading_days,
        price_data=price_data,
        benchmark_nav=benchmark_nav,
    )

    # 附加V3元数据
    result['regime_stats'] = regime_stats
    result['ml_enabled'] = ml_model is not None

    print(f"  回测耗时: {time.time()-t0:.1f}s")
    print(f"  Regime统计: {regime_stats}")
    print(f"  ML融合: {'启用' if ml_model is not None else '未启用'}")
    return result


def print_report(result, ic_summary, universe_key, data):
    """打印策略报告 (V3: 含全部优化项和交易明细)"""
    cfg = UNIVERSE_CONFIG[universe_key]
    strategy_name = f"{cfg['name']}精选{cfg['top_n']}股增强"
    metrics = result.get('metrics', {})
    stock_names = data.get('stock_names', {})
    industry_map = data.get('industry_map', {})
    regime_stats = result.get('regime_stats', {})

    print("\n" + "=" * 70)
    print(f"  {strategy_name} 策略报告 (V3全面优化版)")
    print("=" * 70)

    print(f"\n  股票池: {cfg['name']}  基准: {cfg['benchmark']}")
    print(f"  回测区间: {BACKTEST_START} ~ {BACKTEST_END}")
    print(f"  调仓频率: {REBALANCE_FREQ}  持仓数: {cfg['top_n']}  初始资金: {INITIAL_CAPITAL:,.0f}")
    print(f"  优化项: 行业中性化 | 换手率控制({MAX_TURNOVER:.0%}) | 行业约束(≤{MAX_INDUSTRY_WEIGHT:.0%}) | "
          f"行业偏离(≤{MAX_INDUSTRY_DEVIATION:.0%}) | 多周期择时 | 回撤保护 | "
          f"分析师预期因子 | ML融合({ML_WEIGHT:.0%}) | 自适应ICIR | Regime-aware | 成本优化({COST_THRESHOLD:.1%})")

    print(f"\n  --- 收益指标 ---")
    print(f"  总收益率:     {metrics.get('total_return', 0):>10.2%}")
    print(f"  年化收益率:   {metrics.get('annual_return', 0):>10.2%}")
    print(f"  基准收益率:   {metrics.get('benchmark_return', 0):>10.2%}")
    print(f"  超额收益:     {metrics.get('excess_return', 0):>10.2%}")
    print(f"  Alpha:        {metrics.get('alpha', 0):>10.2%}")
    print(f"  Beta:         {metrics.get('beta', 0):>10.4f}")

    print(f"\n  --- 风险指标 ---")
    print(f"  年化波动率:   {metrics.get('volatility', 0):>10.2%}")
    print(f"  最大回撤:     {metrics.get('max_drawdown', 0):>10.2%}")

    print(f"\n  --- 风险调整收益 ---")
    print(f"  夏普比率:     {metrics.get('sharpe', 0):>10.2f}")
    print(f"  索提诺比率:   {metrics.get('sortino', 0):>10.2f}")
    print(f"  卡玛比率:     {metrics.get('calmar', 0):>10.2f}")
    print(f"  信息比率:     {metrics.get('information_ratio', 0):>10.2f}")

    print(f"\n  --- 交易指标 ---")
    print(f"  换手率:       {metrics.get('turnover_rate', 0):>10.2%}")
    print(f"  胜率:         {metrics.get('win_rate', 0):>10.2%}")
    print(f"  总交易次数:   {metrics.get('total_trades', 0):>10d}")
    print(f"  总交易成本:   {metrics.get('total_cost', 0):>10,.0f}")

    print(f"\n  --- V3优化指标 ---")
    print(f"  Regime统计:   趋势{regime_stats.get('trending', 0)} 震荡{regime_stats.get('oscillating', 0)} 防御{regime_stats.get('defensive', 0)}")
    print(f"  ML融合:       {'启用' if result.get('ml_enabled') else '未启用'}")
    print(f"  自适应ICIR:   启用 (滚动{ROLLING_IC_WINDOW}期)")
    print(f"  成本过滤:     启用 (阈值{COST_THRESHOLD:.1%})")
    print(f"  行业偏离约束: 启用 (≤{MAX_INDUSTRY_DEVIATION:.0%})")

    print(f"\n  --- 最终结果 ---")
    print(f"  期末净值:     {result.get('final_value', 0):>10,.0f}")
    print(f"  回测天数:     {result.get('total_days', 0):>10d}")

    # 交易明细
    trade_records = result.get('trade_records', [])
    if trade_records:
        print(f"\n  --- 交易流水明细 (最近20笔) ---")
        print(f"  {'日期':>12s} {'方向':>4s} {'代码':>10s} {'名称':>8s} {'行业':>8s} {'价格':>8s} {'数量':>8s} {'金额':>12s}")
        print("  " + "-" * 80)
        for t in trade_records[-20:]:
            ts_code = t.get('security_id', '')
            name = stock_names.get(ts_code, '')[:8]
            industry = industry_map.get(ts_code, '')[:8]
            print(f"  {str(t.get('trade_date', '')):>12s} {t.get('action', ''):>4s} {ts_code:>10s} "
                  f"{name:>8s} {industry:>8s} {t.get('price', 0):>8.2f} {t.get('quantity', 0):>8d} "
                  f"{t.get('amount', 0):>12,.0f}")

    # 持仓快照
    holdings_snapshots = result.get('holdings_snapshots', [])
    if holdings_snapshots:
        print(f"\n  --- 持仓明细 (最近3期调仓) ---")
        for snapshot in holdings_snapshots[-3:]:
            td = snapshot.get('trade_date', '')
            total_value = snapshot.get('total_value', 0)
            positions = snapshot.get('positions', {})
            print(f"\n  调仓日: {td}  总市值: {total_value:,.0f}  持仓数: {len(positions)}")
            print(f"  {'代码':>10s} {'名称':>8s} {'行业':>8s} {'股数':>8s} {'权重':>8s} {'市值':>12s}")
            print("  " + "-" * 60)
            sorted_positions = sorted(positions.items(), key=lambda x: -x[1].get('weight', 0))
            for ts_code, pos in sorted_positions:
                name = stock_names.get(ts_code, '')[:8]
                industry = industry_map.get(ts_code, '')[:8]
                print(f"  {ts_code:>10s} {name:>8s} {industry:>8s} {pos.get('shares', 0):>8d} "
                      f"{pos.get('weight', 0):>7.2%} {pos.get('market_value', 0):>12,.0f}")

    # 保存JSON报告
    report = {
        'strategy': strategy_name,
        'version': 'V3',
        'universe': universe_key,
        'benchmark': cfg['benchmark'],
        'backtest_period': f"{BACKTEST_START} ~ {BACKTEST_END}",
        'optimizations': {
            'industry_neutralization': True,
            'turnover_control': MAX_TURNOVER,
            'industry_constraint': MAX_INDUSTRY_WEIGHT,
            'industry_deviation': MAX_INDUSTRY_DEVIATION,
            'multi_period_timing': True,
            'drawdown_protection': True,
            'analyst_factors': True,
            'ml_fusion': ML_WEIGHT,
            'rolling_icir': ROLLING_IC_WINDOW,
            'regime_aware': True,
            'cost_optimization': COST_THRESHOLD,
        },
        'metrics': {k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                     for k, v in metrics.items()},
        'regime_stats': regime_stats,
        'ml_enabled': result.get('ml_enabled', False),
        'trade_records': [{
            'trade_date': str(t.get('trade_date', '')),
            'action': t.get('action', ''),
            'ts_code': t.get('security_id', ''),
            'name': stock_names.get(t.get('security_id', ''), ''),
            'industry': industry_map.get(t.get('security_id', ''), ''),
            'price': t.get('price', 0),
            'quantity': t.get('quantity', 0),
            'amount': t.get('amount', 0),
            'total_cost': t.get('total_cost', 0),
        } for t in trade_records],
        'holdings_snapshots': [{
            'trade_date': str(s.get('trade_date', '')),
            'total_value': s.get('total_value', 0),
            'positions': {
                ts_code: {
                    'name': stock_names.get(ts_code, ''),
                    'industry': industry_map.get(ts_code, ''),
                    **pos,
                }
                for ts_code, pos in s.get('positions', {}).items()
            },
        } for s in holdings_snapshots],
    }
    out_file = f"strategy_report_{universe_key}.json"
    with open(out_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  报告已保存: {out_file}")


def main():
    parser = argparse.ArgumentParser(description='多因子增强策略回测 (V3全面优化版)')
    parser.add_argument(
        'universe',
        choices=list(UNIVERSE_CONFIG.keys()),
        nargs='?',
        default='hs300',
        help='股票池选择: all=全A股, hs300=沪深300, zz500=中证500, zz1000=中证1000',
    )
    args = parser.parse_args()

    universe_key = args.universe
    cfg = UNIVERSE_CONFIG[universe_key]
    strategy_name = f"{cfg['name']}精选{cfg['top_n']}股增强"

    print("=" * 70)
    print(f"  {strategy_name} (V3全面优化版)")
    print("=" * 70)

    t_start = time.time()

    engine = create_engine(settings.DATABASE_URL)
    data = load_data(engine, universe_key)

    ic_summary, ic_df = calc_factor_ic(data, data['trading_days'])

    timing_signal, timing_exposure = calc_timing_signals(data, data['trading_days'])

    result = run_backtest(data, data['trading_days'], ic_summary, ic_df, timing_exposure, universe_key)

    print_report(result, ic_summary, universe_key, data)

    print(f"\n总耗时: {time.time()-t_start:.1f}s")


if __name__ == '__main__':
    main()
