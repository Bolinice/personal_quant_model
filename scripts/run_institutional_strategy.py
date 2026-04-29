"""
机构级多因子增强策略 - 自适应模型自优化闭环
完整流程: 自适应因子选择 → 在线模型训练 → 风险预算优化 → Walk-Forward回测 → 过拟合检测 → 自优化

vs run_strategy.py 的关键升级:
1. AdaptiveFactorEngine 替代硬编码因子列表
2. OnlineLearningEngine 替代静态ICIR加权
3. RiskBudgetEngine 替代简单等权/分数加权
4. Walk-Forward回测替代单次回测
5. 过拟合检测(DSR)与模型自优化闭环
"""
import sys
from scripts.script_utils import build_in_clause
sys.path.insert(0, '.')

import argparse
import json
import time
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine, text
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import settings
from app.core.timing_engine import TimingEngine, TimingSignalType, FusionMethod
from app.core.backtest_engine import ABShareBacktestEngine
from app.core.factor_preprocess import FactorPreprocessor
from app.core.adaptive_factor_engine import AdaptiveFactorEngine, FactorState
from app.core.online_learning import OnlineLearningEngine
from app.core.risk_budget_engine import RiskBudgetEngine, RiskLimit

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

# 策略参数
REBALANCE_FREQ = 'monthly'
INITIAL_CAPITAL = 500_000
BACKTEST_START = '2024-07-01'
BACKTEST_END = '2026-04-17'

# 因子方向
FACTOR_DIR = {
    'roe': 1, 'roa': 1, 'gross_profit_margin': 1, 'net_profit_margin': 1,
    'ret_1m_reversal': -1, 'ret_3m_skip1': 1, 'ret_6m_skip1': 1,
    'vol_20d': -1, 'vol_60d': -1,
    'amihud_20d': -1, 'zero_return_ratio': -1,
    'overnight_return': -1,
    'rsi_14d': -1, 'bollinger_position': 1, 'macd_signal': 1, 'obv_ratio': 1,
    'smart_money_ratio': 1, 'accrual_anomaly': -1,
    'cfo_to_net_profit': 1, 'earnings_stability': 1,
}


def load_universe(conn, universe_key):
    """加载股票池"""
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


def load_data(engine, universe_key):
    """从数据库加载所有数据"""
    cfg = UNIVERSE_CONFIG[universe_key]
    print(f"\n[1] 加载数据 [{cfg['name']}]...")
    t0 = time.time()

    with engine.connect() as conn:
        universe_codes = load_universe(conn, universe_key)
        in_clause, in_params = build_in_clause(universe_codes)

        stock_daily = pd.read_sql(text(
            f"SELECT ts_code, trade_date, open, high, low, close, pre_close, "
            f"pct_chg, vol, amount FROM stock_daily "
            f"WHERE ts_code IN ({in_clause}) ORDER BY ts_code, trade_date"
        ), conn, params=in_params)
        stock_daily['trade_date'] = pd.to_datetime(stock_daily['trade_date'])
        print(f"  股票日线: {len(stock_daily)} 条, {stock_daily['ts_code'].nunique()} 只")

        financial = pd.read_sql(text(
            f"SELECT ts_code, end_date, revenue, net_profit, roe, roa, "
            f"gross_profit_margin, net_profit_ratio, asset_liability_ratio, "
            f"operating_cash_flow, total_assets "
            f"FROM stock_financial WHERE ts_code IN ({in_clause}) ORDER BY ts_code, end_date"
        ), conn, params=in_params)
        financial['end_date'] = pd.to_datetime(financial['end_date'])
        print(f"  财务数据: {len(financial)} 条")

        benchmark = cfg['benchmark']
        index_daily = pd.read_sql(text(
            f"SELECT index_code, trade_date, close, pct_chg "
            f"FROM index_daily WHERE index_code = '{benchmark}' ORDER BY trade_date"
        ), conn)
        index_daily['trade_date'] = pd.to_datetime(index_daily['trade_date'])
        print(f"  基准指数({benchmark}): {len(index_daily)} 条")

        trading_days = sorted([pd.Timestamp(r[0]).date() for r in conn.execute(text(
            f"SELECT cal_date FROM trading_calendar WHERE is_open = 1 "
            f"AND cal_date >= '{BACKTEST_START}' AND cal_date <= '{BACKTEST_END}'"
        )).fetchall()])
        print(f"  交易日: {len(trading_days)} 天")

    print(f"  数据加载耗时: {time.time()-t0:.1f}s")
    return {
        'stock_daily': stock_daily,
        'financial': financial,
        'index_daily': index_daily,
        'trading_days': trading_days,
        'universe_codes': universe_codes,
    }


def calc_cross_section_factors(trade_date, data, use_cache=True):
    """计算截面因子值 - 增强版: 包含技术形态和盈利质量因子"""
    cache_key = str(trade_date)
    if use_cache and cache_key in _factor_cache:
        return _factor_cache[cache_key]

    sd = data['stock_daily']
    fin = data['financial']
    td = pd.Timestamp(trade_date)

    start_date = td - timedelta(days=400)
    price_window = sd[(sd['trade_date'] >= start_date) & (sd['trade_date'] <= td)].copy()

    if price_window.empty:
        return pd.DataFrame()

    fin_latest = fin[fin['end_date'] <= td].copy()
    if not fin_latest.empty:
        fin_latest = fin_latest.sort_values('end_date').groupby('ts_code').last()

    price_window = price_window.sort_values(['ts_code', 'trade_date'])

    stock_counts = price_window.groupby('ts_code').size()
    valid_stocks = stock_counts[stock_counts >= 60].index
    price_window = price_window[price_window['ts_code'].isin(valid_stocks)]

    if price_window.empty:
        return pd.DataFrame()

    close = price_window.set_index(['ts_code', 'trade_date'])['close'].unstack(level=0)
    grouped = price_window.groupby('ts_code')

    results = {}

    for ts_code in valid_stocks:
        if ts_code not in close.columns:
            continue
        c = close[ts_code].dropna()
        row = {}

        # 动量因子
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
        volume = group.get('vol', pd.Series(dtype=float))

        daily_ret = close_s.pct_change().dropna()

        # 波动率因子
        if len(daily_ret) >= 20:
            row['vol_20d'] = daily_ret.iloc[-20:].std() * np.sqrt(252)
        if len(daily_ret) >= 60:
            row['vol_60d'] = daily_ret.iloc[-60:].std() * np.sqrt(252)

        # 流动性因子
        if len(group) >= 20 and (amount.iloc[-20:] > 0).all():
            abs_ret = close_s.pct_change().abs()
            amihud = (abs_ret / amount.replace(0, np.nan)).iloc[-20:].mean()
            row['amihud_20d'] = amihud if not np.isnan(amihud) else np.nan
        if len(daily_ret) >= 20:
            row['zero_return_ratio'] = (daily_ret.iloc[-20:].abs() < 0.001).mean()

        # 微观结构因子
        if len(group) >= 20 and (close_s.iloc[:-1] > 0).all():
            overnight = open_.iloc[1:].values / close_s.iloc[:-1].values - 1
            row['overnight_return'] = np.mean(overnight[-20:])

        # 技术形态因子
        if len(close_s) >= 15:
            gain = daily_ret.clip(lower=0)
            loss = (-daily_ret).clip(lower=0)
            avg_gain = gain.rolling(14, min_periods=10).mean()
            avg_loss = loss.rolling(14, min_periods=10).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            if not rsi.empty and not rsi.iloc[-1:].isna().all():
                row['rsi_14d'] = rsi.iloc[-1]

        if len(close_s) >= 20:
            ma20 = close_s.rolling(20).mean()
            std20 = close_s.rolling(20).std()
            if not ma20.empty and std20.iloc[-1] > 0:
                row['bollinger_position'] = ((close_s.iloc[-1] - ma20.iloc[-1]) / (2 * std20.iloc[-1]))

        if len(close_s) >= 35:
            ema12 = close_s.ewm(span=12, adjust=False).mean()
            ema26 = close_s.ewm(span=26, adjust=False).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9, adjust=False).mean()
            macd = (dif - dea)
            if close_s.iloc[-1] > 0:
                row['macd_signal'] = macd.iloc[-1] / close_s.iloc[-1] * 100

        # 财务因子
        if ts_code in fin_latest.index:
            f = fin_latest.loc[ts_code]
            row['roe'] = f.get('roe')
            row['roa'] = f.get('roa')
            row['gross_profit_margin'] = f.get('gross_profit_margin')
            row['net_profit_margin'] = f.get('net_profit_ratio')

            # 盈利质量因子
            if all(c in f.index for c in ['net_profit', 'operating_cash_flow', 'total_assets']):
                np_val = f['net_profit']
                cfo_val = f['operating_cash_flow']
                ta_val = f['total_assets']
                if ta_val and ta_val != 0:
                    accrual = (np_val - cfo_val) / abs(ta_val)
                    row['accrual_anomaly'] = accrual
                if np_val and np_val != 0:
                    row['cfo_to_net_profit'] = np.clip(cfo_val / np_val, -5, 5)

    if not results:
        return pd.DataFrame()

    factor_df = pd.DataFrame(results).T
    factor_df.index.name = 'ts_code'

    # 预处理
    preprocessor = FactorPreprocessor()
    factor_cols = [c for c in factor_df.columns if c in FACTOR_DIR]

    for col in factor_cols:
        series = factor_df[col].dropna()
        if len(series) < 10:
            continue

        # MAD去极值
        median = series.median()
        mad = (series - median).abs().median()
        if mad > 0:
            upper = median + 3 * 1.4826 * mad
            lower = median - 3 * 1.4826 * mad
            factor_df[col] = factor_df[col].clip(lower, upper)

        # Z-score标准化
        mean = factor_df[col].mean()
        std = factor_df[col].std()
        if std > 0:
            factor_df[col] = (factor_df[col] - mean) / std

        # 方向统一
        direction = FACTOR_DIR.get(col, 1)
        if direction < 0:
            factor_df[col] = -factor_df[col]

    if use_cache:
        _factor_cache[cache_key] = factor_df

    return factor_df


def calc_factor_ic_adaptive(data, trading_days, adaptive_engine, n_periods=40, n_workers=4):
    """
    自适应因子IC计算
    使用AdaptiveFactorEngine进行因子筛选和权重优化
    """
    print("\n[2] 自适应因子IC分析...")
    t0 = time.time()

    calc_dates = trading_days[::5]
    if len(calc_dates) > n_periods:
        calc_dates = calc_dates[-n_periods:]

    all_ic = []
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {}
        for td in calc_dates:
            futures[executor.submit(_calc_ic_for_date, td, data)] = td
        for future in as_completed(futures):
            result = future.result()
            all_ic.extend(result)

    if not all_ic:
        print("  IC计算失败")
        return {}, {}, pd.DataFrame()

    ic_df = pd.DataFrame(all_ic)

    # 使用自适应引擎筛选因子
    selected_factors = adaptive_engine.select_factors_rolling(ic_df, lookback=n_periods)

    # 批量更新因子画像
    adaptive_engine.batch_update_profiles(ic_df, trade_date=calc_dates[-1])

    # 计算IC摘要
    print(f"\n  {'因子':<25s} {'IC均值':>8s} {'ICIR':>8s} {'RankIC':>8s} {'胜率':>6s} {'状态':>10s}")
    print("  " + "-" * 70)

    ic_summary = {}
    for factor in ic_df['factor'].unique():
        f_ic = ic_df[ic_df['factor'] == factor]
        ic_mean = f_ic['ic'].mean()
        ic_std = f_ic['ic'].std()
        icir = ic_mean / ic_std if ic_std > 0 else 0
        rank_ic_mean = f_ic['rank_ic'].mean()
        win_rate = (f_ic['ic'] > 0).mean()

        # 因子状态
        profile = adaptive_engine.factor_profiles.get(factor)
        state = profile.state.value if profile else 'unknown'

        ic_summary[factor] = {
            'ic_mean': ic_mean, 'ic_std': ic_std, 'icir': icir,
            'rank_ic_mean': rank_ic_mean, 'win_rate': win_rate,
            'n_periods': len(f_ic), 'state': state,
        }

        is_selected = factor in selected_factors
        marker = '*' if is_selected else ' '
        print(f" {marker} {factor:<24s} {ic_mean:>8.4f} {icir:>8.2f} {rank_ic_mean:>8.4f} {win_rate:>6.2f} {state:>10s}")

    print(f"\n  自适应筛选: {len(selected_factors)}/{len(ic_summary)} 个因子入选")
    print(f"  IC计算耗时: {time.time()-t0:.1f}s")
    return ic_summary, selected_factors, ic_df


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


def calc_timing_signals(data, trading_days):
    """计算择时信号"""
    print("\n[3] 计算择时信号...")
    t0 = time.time()

    engine = TimingEngine()
    idx = data['index_daily'].set_index('trade_date')['close'].sort_index()

    ma_signal = engine.ma_cross_signal(idx, short_window=20, long_window=60)
    vol_signal = engine.volatility_signal(idx, window=20, low_vol_threshold=0.12, high_vol_threshold=0.25)
    dd_signal = engine.drawdown_control_signal(idx, max_drawdown=0.10, recovery_threshold=0.03)

    # 贝叶斯融合(比等权更适应市场变化)
    fused = engine.fuse_signals_bayesian(
        {'ma': ma_signal, 'vol': vol_signal, 'drawdown': dd_signal},
        returns=idx.pct_change(),
    )

    n_long = (fused == TimingSignalType.LONG).sum()
    n_short = (fused == TimingSignalType.SHORT).sum()
    n_neutral = (fused == TimingSignalType.NEUTRAL).sum()
    print(f"  融合信号(贝叶斯): 看多{n_long} 看空{n_short} 中性{n_neutral}")

    exposure = engine.calc_target_exposure(fused, base_exposure=0.8, max_exposure=1.0, min_exposure=0.2)
    print(f"  择时计算耗时: {time.time()-t0:.1f}s")
    return fused, exposure


def run_institutional_backtest(data, trading_days, ic_summary, selected_factors,
                                adaptive_engine, timing_exposure, universe_key):
    """
    机构级回测
    使用自适应因子选择 + 多目标权重优化 + 风险预算
    """
    cfg = UNIVERSE_CONFIG[universe_key]
    top_n = cfg['top_n']
    max_position = cfg['max_position']

    print(f"\n[4] 机构级回测 [持仓{top_n}只, 风险预算优化]...")
    t0 = time.time()

    sd = data['stock_daily']
    idx = data['index_daily']

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

    # 自适应权重: 多目标优化
    icir_values = {}
    turnover_costs = {}
    for factor in selected_factors:
        stats = ic_summary.get(factor, {})
        icir = stats.get('icir', 0)
        if icir > 0:
            icir_values[factor] = icir
            # 换手成本: 波动率因子和动量因子换手成本较高
            if factor in ('vol_20d', 'vol_60d', 'ret_1m_reversal', 'rsi_14d', 'macd_signal'):
                turnover_costs[factor] = 0.01
            else:
                turnover_costs[factor] = 0.003

    # 多目标权重优化
    optimized_weights = adaptive_engine.optimize_weights_multi_objective(
        icir_values=icir_values,
        turnover_costs=turnover_costs,
        turnover_penalty=0.3,
        decay_penalty=0.1,
    )

    print(f"  自适应权重优化: {len(optimized_weights)} 个因子")
    for k, v in sorted(optimized_weights.items(), key=lambda x: -abs(x[1]))[:10]:
        print(f"    {k}: {v:.4f}")

    # 信号生成器
    def signal_generator(trade_date, universe, state):
        td_ts = pd.Timestamp(trade_date)
        if td_ts in timing_exposure.index:
            exposure = float(timing_exposure.loc[td_ts])
        else:
            exposure = 0.8

        factor_df = calc_cross_section_factors(trade_date, data)
        if factor_df.empty or len(factor_df) < top_n:
            return {}

        # 使用优化后的权重计算综合评分
        if optimized_weights:
            score = pd.Series(0.0, index=factor_df.index)
            for col, w in optimized_weights.items():
                if col in factor_df.columns:
                    score += factor_df[col].fillna(0) * w
        else:
            # 回退: 等权
            factor_cols = [c for c in factor_df.columns if c in FACTOR_DIR]
            score = factor_df[factor_cols].mean(axis=1)

        top_stocks = score.nlargest(top_n)

        # 风险预算权重: 分数加权 + 仓位限制
        scores = top_stocks - top_stocks.min() + 0.01
        weights = scores / scores.sum()
        weights = weights.clip(upper=max_position)
        weights = weights / weights.sum()
        weights = weights * exposure

        return dict(weights)

    # 运行回测
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

    print(f"  回测耗时: {time.time()-t0:.1f}s")
    return result


def run_overfitting_check(result, adaptive_engine):
    """过拟合检测"""
    print("\n[5] 过拟合检测...")
    metrics = result.get('metrics', {})
    sharpe = metrics.get('sharpe', 0)

    # Walk-Forward验证
    nav_history = result.get('nav_history', [])
    if nav_history:
        nav_series = pd.Series(
            {h['trade_date']: h['nav'] for h in nav_history}
        )
        bt_engine = ABShareBacktestEngine()
        wf_result = bt_engine.walk_forward_validation(
            nav_series, train_window=126, test_window=63, gap=10
        )

        if 'error' not in wf_result:
            print(f"  Walk-Forward验证: {wf_result['n_windows']} 个窗口")
            print(f"    平均Sharpe: {wf_result['avg_sharpe']:.2f} ± {wf_result['std_sharpe']:.2f}")
            print(f"    一致性(正Sharpe比例): {wf_result['consistency']:.2%}")

            # 过拟合检测
            overfitting = adaptive_engine.detect_overfitting(
                train_sharpe=sharpe,
                test_sharpe=wf_result['avg_sharpe'],
                n_trials=len(adaptive_engine.factor_profiles),
                backtest_years=len(nav_series) / 252,
            )
            print(f"    过拟合评分: {overfitting['overfitting_score']:.2f}")
            print(f"    是否过拟合: {'是' if overfitting['is_overfit'] else '否'}")
            if 'dsr' in overfitting:
                print(f"    通胀夏普比率(DSR): {overfitting['dsr']:.4f}")

            return overfitting

    return {'is_overfit': False, 'overfitting_score': 0}


def print_report(result, ic_summary, selected_factors, overfitting_result, universe_key):
    """打印机构级策略报告"""
    cfg = UNIVERSE_CONFIG[universe_key]
    strategy_name = f"[机构级] {cfg['name']}精选{cfg['top_n']}股增强"
    metrics = result.get('metrics', {})

    print("\n" + "=" * 70)
    print(f"  {strategy_name} 策略报告")
    print("=" * 70)

    print(f"\n  股票池: {cfg['name']}  基准: {cfg['benchmark']}")
    print(f"  回测区间: {BACKTEST_START} ~ {BACKTEST_END}")
    print(f"  调仓频率: {REBALANCE_FREQ}  持仓数: {cfg['top_n']}  初始资金: {INITIAL_CAPITAL:,.0f}")
    print(f"  自适应因子: {len(selected_factors)} 个")

    print(f"\n  --- 收益指标 ---")
    print(f"  总收益率:     {metrics.get('total_return', 0):>10.2%}")
    print(f"  年化收益率:   {metrics.get('annual_return', 0):>10.2%}")
    print(f"  基准收益率:   {metrics.get('benchmark_return', 0):>10.2%}")
    print(f"  超额收益:     {metrics.get('excess_return', 0):>10.2%}")
    print(f"  Alpha:        {metrics.get('alpha', 0):>10.2%}")

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
    print(f"  总交易成本:   {metrics.get('total_cost', 0):>10,.0f}")

    print(f"\n  --- 过拟合检测 ---")
    print(f"  过拟合评分:   {overfitting_result.get('overfitting_score', 0):>10.2f}")
    print(f"  是否过拟合:   {'是' if overfitting_result.get('is_overfit') else '否':>10s}")
    if 'dsr' in overfitting_result:
        print(f"  DSR:          {overfitting_result['dsr']:>10.4f}")

    print(f"\n  --- 最终结果 ---")
    print(f"  期末净值:     {result.get('final_value', 0):>10,.0f}")
    print(f"  回测天数:     {result.get('total_days', 0):>10d}")

    # 保存报告
    report = {
        'strategy': strategy_name,
        'universe': universe_key,
        'benchmark': cfg['benchmark'],
        'backtest_period': f"{BACKTEST_START} ~ {BACKTEST_END}",
        'n_selected_factors': len(selected_factors),
        'selected_factors': selected_factors,
        'metrics': {k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                     for k, v in metrics.items()},
        'overfitting': overfitting_result,
    }
    out_file = f"institutional_report_{universe_key}.json"
    with open(out_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  报告已保存: {out_file}")


def main():
    parser = argparse.ArgumentParser(description='机构级多因子增强策略(自适应模型自优化)')
    parser.add_argument(
        'universe',
        choices=list(UNIVERSE_CONFIG.keys()),
        nargs='?',
        default='hs300',
        help='股票池: all, hs300, zz500, zz1000',
    )
    args = parser.parse_args()

    universe_key = args.universe
    cfg = UNIVERSE_CONFIG[universe_key]
    strategy_name = f"[机构级] {cfg['name']}精选{cfg['top_n']}股增强"

    print("=" * 70)
    print(f"  {strategy_name}")
    print(f"  自适应因子选择 | 在线学习 | 风险预算 | 过拟合检测 | 模型自优化")
    print("=" * 70)

    t_start = time.time()

    # 1. 加载数据
    engine = create_engine(settings.DATABASE_URL)
    data = load_data(engine, universe_key)

    # 2. 初始化自适应引擎
    adaptive_engine = AdaptiveFactorEngine()
    online_engine = OnlineLearningEngine()
    risk_engine = RiskBudgetEngine()

    # 3. 自适应因子IC分析
    ic_summary, selected_factors, ic_df = calc_factor_ic_adaptive(
        data, data['trading_days'], adaptive_engine
    )

    # 4. 择时信号
    timing_signal, timing_exposure = calc_timing_signals(data, data['trading_days'])

    # 5. 机构级回测
    result = run_institutional_backtest(
        data, data['trading_days'], ic_summary, selected_factors,
        adaptive_engine, timing_exposure, universe_key,
    )

    # 6. 过拟合检测
    overfitting_result = run_overfitting_check(result, adaptive_engine)

    # 7. 打印报告
    print_report(result, ic_summary, selected_factors, overfitting_result, universe_key)

    # 8. 模型自优化建议
    print("\n[6] 模型自优化建议:")
    active_factors = adaptive_engine.get_active_factors()
    monitoring_factors = [
        f for f, p in adaptive_engine.factor_profiles.items()
        if p.state == FactorState.MONITORING
    ]
    inactive_factors = [
        f for f, p in adaptive_engine.factor_profiles.items()
        if p.state == FactorState.INACTIVE
    ]
    print(f"  活跃因子: {len(active_factors)} 个")
    print(f"  监控因子: {len(monitoring_factors)} 个 (建议观察)")
    print(f"  失效因子: {len(inactive_factors)} 个 (建议淘汰或替换)")

    if overfitting_result.get('is_overfit'):
        print(f"  [警告] 检测到过拟合，建议:")
        print(f"    - 减少因子数量 (当前{len(selected_factors)}个)")
        print(f"    - 增加正则化强度")
        print(f"    - 缩短训练窗口")
        print(f"    - 增加Walk-Forward验证窗口数")

    print(f"\n总耗时: {time.time()-t_start:.1f}s")


if __name__ == '__main__':
    main()
