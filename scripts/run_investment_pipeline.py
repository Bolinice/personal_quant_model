#!/usr/bin/env python
"""
端到端投资决策流水线
从Tushare高并发获取数据 → 写入数据库 → 加载到内存 → 跑出投资决策

完整流程:
  数据同步 → 数据加载 → 股票池构建 → 因子计算 → Alpha模块打分
  → Regime检测 → 信号融合 → 组合优化 → 择时信号 → 输出投资决策
"""
import sys
sys.path.insert(0, '.')

import argparse
import json
import time
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine, text

from app.core.config import settings


# ==================== Step 1: 数据同步 ====================

def step1_sync_data(trade_date: str, start_date: str, end_date: str,
                    max_workers: int = 8):
    """高并发Tushare数据同步"""
    print("\n" + "=" * 60)
    print("Step 1: 高并发Tushare数据同步")
    print("=" * 60)

    from app.core.data_sync import ConcurrentDataSyncer

    syncer = ConcurrentDataSyncer(
        token=settings.TUSHARE_TOKEN,
        max_workers=max_workers,
    )

    t0 = time.time()
    results = syncer.sync_all(
        trade_date=trade_date,
        start_date=start_date,
        end_date=end_date,
    )
    elapsed = time.time() - t0

    total = sum(results.values())
    print(f"\n  同步完成: {total} 行, 耗时 {elapsed:.1f}s")
    for k, v in results.items():
        print(f"    {k}: {v}")

    return results


# ==================== Step 2: 数据加载 ====================

def step2_load_data(engine, universe_key: str = 'hs300'):
    """从数据库加载所有需要的数据"""
    print("\n" + "=" * 60)
    print("Step 2: 加载数据")
    print("=" * 60)

    t0 = time.time()

    UNIVERSE_CONFIG = {
        'hs300': {'name': '沪深300', 'benchmark': '000300.SH', 'index_code': '000300.SH'},
        'zz500': {'name': '中证500', 'benchmark': '000905.SH', 'index_code': '000905.SH'},
        'zz1000': {'name': '中证1000', 'benchmark': '000852.SH', 'index_code': '000852.SH'},
        'all': {'name': '全A股', 'benchmark': '000001.SH'},
    }
    cfg = UNIVERSE_CONFIG.get(universe_key, UNIVERSE_CONFIG['hs300'])

    with engine.connect() as conn:
        # 股票池
        if universe_key == 'all':
            codes = [r[0] for r in conn.execute(text(
                "SELECT ts_code FROM stock_basic WHERE list_status='L' "
                "AND (name IS NULL OR (name NOT LIKE '%ST%' AND name NOT LIKE '%*ST%'))"
            )).fetchall()]
        else:
            codes = [r[0] for r in conn.execute(text(
                f"SELECT ts_code FROM index_components WHERE index_code = '{cfg['index_code']}'"
            )).fetchall()]
        print(f"  股票池 [{cfg['name']}]: {len(codes)} 只")

        if not codes:
            print("  错误: 股票池为空，请先同步数据")
            return None

        codes_str = ','.join(f"'{c}'" for c in codes)

        # 股票日线
        stock_daily = pd.read_sql(text(
            f"SELECT ts_code, trade_date, open, high, low, close, pre_close, "
            f"pct_chg, vol, amount FROM stock_daily "
            f"WHERE ts_code IN ({codes_str}) ORDER BY ts_code, trade_date"
        ), conn)
        stock_daily['trade_date'] = pd.to_datetime(stock_daily['trade_date'])
        print(f"  股票日线: {len(stock_daily)} 条, {stock_daily['ts_code'].nunique()} 只")

        # 财务数据 (独立连接)
        financial = pd.DataFrame()
        try:
            with engine.connect() as conn2:
                financial = pd.read_sql(text(
                    f"SELECT ts_code, end_date, ann_date, roe, roa, "
                    f"gross_profit_margin, net_profit_ratio, current_ratio, debt_to_assets, "
                    f"eps, bvps, pe_ttm, pb, ps_ttm, dividend_yield, "
                    f"revenue, net_profit, operating_cash_flow, total_assets, "
                    f"total_equity, current_assets, current_liabilities "
                    f"FROM stock_financial WHERE ts_code IN ({codes_str}) ORDER BY ts_code, end_date"
                ), conn2)
            if not financial.empty:
                financial['end_date'] = pd.to_datetime(financial['end_date'])
                if 'ann_date' in financial.columns:
                    financial['ann_date'] = pd.to_datetime(financial['ann_date'])
                # Rename net_profit_ratio → net_profit_margin for FactorCalculator
                if 'net_profit_ratio' in financial.columns:
                    financial = financial.rename(columns={'net_profit_ratio': 'net_profit_margin'})
            print(f"  财务数据: {len(financial)} 条")
        except Exception as e:
            print(f"  财务数据: 跳过 ({str(e)[:80]})")

        # 每日基本面 (独立连接) - 包含turnover_rate供流动性因子使用
        daily_basic = pd.DataFrame()
        try:
            with engine.connect() as conn3:
                daily_basic = pd.read_sql(text(
                    f"SELECT ts_code, trade_date, close, turnover_rate, pe, pe_ttm, pb, "
                    f"ps_ttm, dv_ratio, total_mv, circ_mv "
                    f"FROM stock_daily_basic WHERE ts_code IN ({codes_str}) "
                    f"ORDER BY ts_code, trade_date"
                ), conn3)
            if not daily_basic.empty:
                daily_basic['trade_date'] = pd.to_datetime(daily_basic['trade_date'])
                # Rename total_mv → total_market_cap for FactorCalculator
                if 'total_mv' in daily_basic.columns:
                    daily_basic = daily_basic.rename(columns={'total_mv': 'total_market_cap'})
            print(f"  每日基本面: {len(daily_basic)} 条")
        except Exception as e:
            print(f"  每日基本面: 跳过 ({str(e)[:80]})")

        # 基准指数
        benchmark = cfg['benchmark']
        index_daily = pd.read_sql(text(
            f"SELECT index_code, trade_date, close, pct_chg "
            f"FROM index_daily WHERE index_code = '{benchmark}' ORDER BY trade_date"
        ), conn)
        index_daily['trade_date'] = pd.to_datetime(index_daily['trade_date'])
        print(f"  基准指数({benchmark}): {len(index_daily)} 条")

        # 股票基础信息 (供A股特有因子使用)
        stock_basic = pd.read_sql(text(
            f"SELECT ts_code, name, industry, list_date, list_status "
            f"FROM stock_basic WHERE ts_code IN ({codes_str})"
        ), conn)
        print(f"  股票基础: {len(stock_basic)} 条")

        # 行业分类 (独立连接)
        industry_df = pd.DataFrame()
        try:
            with engine.connect() as conn4:
                industry_df = pd.read_sql(text(
                    f"SELECT ts_code, industry FROM stock_industry WHERE ts_code IN ({codes_str})"
                ), conn4)
            print(f"  行业分类: {len(industry_df)} 条")
        except Exception:
            pass

        # 北向资金 (独立连接)
        northbound = pd.DataFrame()
        try:
            with engine.connect() as conn5:
                northbound = pd.read_sql(text(
                    f"SELECT ts_code, trade_date, north_net_buy, north_buy, north_sell "
                    f"FROM stock_northbound WHERE ts_code IN ({codes_str}) "
                    f"ORDER BY ts_code, trade_date"
                ), conn5)
            if not northbound.empty:
                northbound['trade_date'] = pd.to_datetime(northbound['trade_date'])
                # Fill north_net_buy from north_buy - north_sell if null
                mask = northbound['north_net_buy'].isna() & northbound['north_buy'].notna() & northbound['north_sell'].notna()
                northbound.loc[mask, 'north_net_buy'] = northbound.loc[mask, 'north_buy'] - northbound.loc[mask, 'north_sell']
            print(f"  北向资金: {len(northbound)} 条")
        except Exception:
            pass

        # 资金流向 (独立连接)
        money_flow = pd.DataFrame()
        try:
            with engine.connect() as conn6:
                money_flow = pd.read_sql(text(
                    f"SELECT ts_code, trade_date, smart_net_inflow, smart_net_pct "
                    f"FROM stock_money_flow WHERE ts_code IN ({codes_str}) "
                    f"ORDER BY ts_code, trade_date"
                ), conn6)
            if not money_flow.empty:
                money_flow['trade_date'] = pd.to_datetime(money_flow['trade_date'])
            print(f"  资金流向: {len(money_flow)} 条")
        except Exception:
            pass

        # 融资融券 (独立连接)
        margin = pd.DataFrame()
        try:
            with engine.connect() as conn7:
                margin = pd.read_sql(text(
                    f"SELECT ts_code, trade_date, margin_buy, margin_balance "
                    f"FROM stock_margin WHERE ts_code IN ({codes_str}) "
                    f"ORDER BY ts_code, trade_date"
                ), conn7)
            if not margin.empty:
                margin['trade_date'] = pd.to_datetime(margin['trade_date'])
            print(f"  融资融券: {len(margin)} 条")
        except Exception:
            pass

        # 涨跌停状态 (独立连接, 供A股特有因子使用)
        stock_status = pd.DataFrame()
        try:
            with engine.connect() as conn8:
                stock_status = pd.read_sql(text(
                    f"SELECT ts_code, trade_date, is_limit_up, is_limit_down "
                    f"FROM stock_status_daily WHERE ts_code IN ({codes_str}) "
                    f"ORDER BY ts_code, trade_date"
                ), conn8)
            if not stock_status.empty:
                stock_status['trade_date'] = pd.to_datetime(stock_status['trade_date'])
            print(f"  涨跌停: {len(stock_status)} 条")
        except Exception:
            pass

    print(f"  数据加载耗时: {time.time()-t0:.1f}s")
    return {
        'stock_daily': stock_daily,
        'financial': financial,
        'daily_basic': daily_basic,
        'index_daily': index_daily,
        'stock_basic': stock_basic,
        'industry_df': industry_df,
        'northbound': northbound,
        'money_flow': money_flow,
        'margin': margin,
        'stock_status': stock_status,
        'universe_codes': codes,
        'config': cfg,
    }


# ==================== Step 3: 因子计算 ====================

def step3_calc_factors(trade_date, data):
    """计算全量69因子 — 复用FactorCalculator"""
    print("\n" + "=" * 60)
    print("Step 3: 因子计算")
    print("=" * 60)

    t0 = time.time()
    td = pd.Timestamp(trade_date)

    from app.core.factor_calculator import FactorCalculator, FACTOR_GROUPS, FACTOR_DIRECTIONS
    calculator = FactorCalculator()

    # 准备price_df: 截取500天窗口, 合并turnover_rate
    sd = data['stock_daily']
    start_date = td - timedelta(days=500)
    price_df = sd[(sd['trade_date'] >= start_date) & (sd['trade_date'] <= td)].copy()
    price_df = price_df.sort_values(['ts_code', 'trade_date'])

    # 过滤数据不足60天的股票
    stock_counts = price_df.groupby('ts_code').size()
    valid_stocks = stock_counts[stock_counts >= 60].index
    price_df = price_df[price_df['ts_code'].isin(valid_stocks)]

    if price_df.empty:
        print("  错误: 无有效行情数据")
        return pd.DataFrame()

    # 合并turnover_rate到price_df (流动性因子需要)
    db = data.get('daily_basic')
    if db is not None and not db.empty:
        db_subset = db[db['trade_date'] <= td][['ts_code', 'trade_date', 'turnover_rate']].copy()
        price_df = price_df.merge(db_subset, on=['ts_code', 'trade_date'], how='left')

    # 准备financial_df: PIT过滤
    financial_df = data.get('financial', pd.DataFrame())
    if not financial_df.empty and 'ann_date' in financial_df.columns:
        financial_df = financial_df[financial_df['ann_date'] <= td].copy()

    # 准备northbound_df
    northbound_df = data.get('northbound', pd.DataFrame())

    # 准备money_flow_df
    money_flow_df = data.get('money_flow', pd.DataFrame())

    # 准备margin_df
    margin_df = data.get('margin', pd.DataFrame())

    # 准备stock_basic_df
    stock_basic_df = data.get('stock_basic', pd.DataFrame())
    if not stock_basic_df.empty and 'list_date' in stock_basic_df.columns:
        stock_basic_df['list_date'] = pd.to_datetime(stock_basic_df['list_date'])

    # 准备stock_status_df (涨跌停)
    stock_status_df = data.get('stock_status', pd.DataFrame())

    # 调用FactorCalculator计算全部因子
    factor_df = calculator.calc_all_factors(
        financial_df=financial_df,
        price_df=price_df,
        neutralize=False,  # 不做行业中性化(截面数据)
        northbound_df=northbound_df,
        money_flow_df=money_flow_df,
        margin_df=margin_df,
        stock_basic_df=stock_basic_df,
        stock_status_df=stock_status_df,
        daily_basic_df=data.get('daily_basic', pd.DataFrame()),
        trade_date=td,
    )

    if factor_df.empty:
        print("  错误: 因子计算结果为空")
        return pd.DataFrame()

    # 设置index为ts_code (FactorCalculator输出security_id列)
    if 'security_id' in factor_df.columns:
        factor_df = factor_df.set_index('security_id')
        factor_df.index.name = 'ts_code'

    # 因子覆盖率报告
    factor_cols = [c for c in factor_df.columns
                   if c in FACTOR_DIRECTIONS and not c.endswith('_missing')]
    coverage = factor_df[factor_cols].notna().mean()
    high_cov = (coverage > 0.5).sum()
    n_stocks = len(factor_df)

    print(f"  因子数: {len(factor_cols)}, 股票数: {n_stocks}")
    print(f"  高覆盖因子(>50%): {high_cov}/{len(factor_cols)}")

    # 按因子组打印
    for group_name, group_info in FACTOR_GROUPS.items():
        group_factors = [f for f in group_info['factors'] if f in factor_cols]
        if not group_factors:
            continue
        group_cov = {f: coverage.get(f, 0) for f in group_factors if coverage.get(f, 0) > 0}
        if group_cov:
            print(f"  [{group_info['name']}] {len(group_cov)}/{len(group_factors)} 有数据")
            for f, cov in sorted(group_cov.items(), key=lambda x: -x[1]):
                print(f"    {f}: {cov:.0%}")

    print(f"  因子计算耗时: {time.time()-t0:.1f}s")
    return factor_df


# ==================== Step 4: Alpha模块打分 ====================

def step4_alpha_scoring(factor_df):
    """Alpha模块打分 + 信号融合"""
    print("\n" + "=" * 60)
    print("Step 4: Alpha模块打分 + 信号融合")
    print("=" * 60)

    t0 = time.time()

    from app.core.alpha_modules import get_all_modules
    from app.core.ensemble import AlphaEnsemble

    modules = get_all_modules()
    ensemble = AlphaEnsemble(modules=modules)

    # 各模块打分
    module_scores = {}
    module_diagnostics = {}
    for module in modules:
        try:
            score = module.score(factor_df)
            if not score.empty:
                module_scores[module.name] = score
            diag = module.diagnostics(factor_df)
            module_diagnostics[module.name] = diag
        except Exception as e:
            print(f"  模块 {module.name} 失败: {e}")
            module_diagnostics[module.name] = {'error': str(e)}

    for name, s in module_scores.items():
        if not s.empty:
            print(f"  {name}: mean={s.mean():.3f}, std={s.std():.3f}, count={len(s)}")

    # 信号融合 (默认震荡市)
    from app.core.regime import REGIME_MEAN_REVERTING
    final_alpha, all_module_scores = ensemble.fuse(
        factor_df, regime=REGIME_MEAN_REVERTING
    )

    print(f"  融合alpha: mean={final_alpha.mean():.3f}, std={final_alpha.std():.3f}")
    print(f"  模块权重: {dict((k, round(v, 3)) for k, v in ensemble.weights.items())}")
    print(f"  Alpha打分耗时: {time.time()-t0:.1f}s")

    return final_alpha, module_scores, module_diagnostics, ensemble


# ==================== Step 5: Regime检测 ====================

def step5_regime_detection(data):
    """市场状态检测"""
    print("\n" + "=" * 60)
    print("Step 5: Regime检测")
    print("=" * 60)

    t0 = time.time()

    from app.core.regime import RegimeDetector

    detector = RegimeDetector()
    idx = data['index_daily']

    if idx.empty:
        print("  无指数数据，使用默认震荡市")
        return 'mean_reverting', {}

    market_data = idx.rename(columns={'index_code': 'ts_code'})
    regime_info = detector.detect_with_confidence(market_data)
    regime = regime_info.get('regime', 'mean_reverting')
    confidence = regime_info.get('confidence', (0.3))

    print(f"  Regime: {regime} (置信度: {confidence:.1%})")
    features = regime_info.get('features', {})
    for k, v in features.items():
        if isinstance(v, float):
            print(f"    {k}: {v:.4f}")

    print(f"  Regime检测耗时: {time.time()-t0:.1f}s")
    return regime, regime_info


# ==================== Step 6: 组合优化 ====================

def step6_portfolio_optimization(final_alpha, regime, data, ensemble):
    """组合优化"""
    print("\n" + "=" * 60)
    print("Step 6: 组合优化")
    print("=" * 60)

    t0 = time.time()

    from app.core.portfolio_optimizer import PortfolioOptimizer

    optimizer = PortfolioOptimizer()

    # 重新融合（使用检测到的regime）
    final_alpha_regime, _ = ensemble.fuse(
        data.get('_factor_df', pd.DataFrame()), regime=regime
    )

    # 使用regime调整后的alpha
    alpha = final_alpha_regime if not final_alpha_regime.empty else final_alpha

    # 行业数据
    industry_series = None
    industry_df = data.get('industry_df')
    if industry_df is not None and not industry_df.empty:
        industry_series = industry_df.set_index('ts_code')['industry']

    # 分数映射权重
    target_weights = optimizer.score_to_weight(
        scores=alpha,
        industry_data=industry_series,
        max_position=0.03,
    )

    n_positions = len(target_weights[target_weights > 0])
    max_weight = target_weights.max() if len(target_weights) > 0 else 0
    top5 = target_weights.nlargest(5)

    print(f"  持仓数: {n_positions}")
    print(f"  最大权重: {max_weight:.2%}")
    print(f"  Top 5:")
    for code, w in top5.items():
        name = ''
        sb = data.get('stock_basic')
        if sb is not None and not sb.empty:
            match = sb[sb['ts_code'] == code]
            if not match.empty:
                name = match.iloc[0].get('name', '')
        print(f"    {code} ({name}): {w:.2%}")

    print(f"  组合优化耗时: {time.time()-t0:.1f}s")
    return target_weights


# ==================== Step 7: 择时信号 ====================

def step7_timing_signals(data):
    """择时信号"""
    print("\n" + "=" * 60)
    print("Step 7: 择时信号")
    print("=" * 60)

    t0 = time.time()

    from app.core.timing_engine import TimingEngine, TimingSignalType, FusionMethod

    engine = TimingEngine()
    idx = data['index_daily']

    if idx.empty:
        print("  无指数数据，使用默认中性信号")
        return 'NEUTRAL', 0.8

    close = idx.set_index('trade_date')['close'].sort_index()

    ma_signal = engine.ma_cross_signal(close, short_window=20, long_window=60)
    vol_signal = engine.volatility_signal(close, window=20, low_vol_threshold=0.12, high_vol_threshold=0.25)
    dd_signal = engine.drawdown_control_signal(close, max_drawdown=0.10, recovery_threshold=0.03)

    fused = engine.fuse_signals({
        'ma': ma_signal, 'vol': vol_signal, 'drawdown': dd_signal,
    }, method=FusionMethod.EQUAL)

    latest_signal = fused.iloc[-1]
    exposure = engine.calc_target_exposure(fused, base_exposure=0.8, max_exposure=1.0, min_exposure=0.2)
    latest_exposure = float(exposure.iloc[-1])

    n_long = (fused == TimingSignalType.LONG).sum()
    n_short = (fused == TimingSignalType.SHORT).sum()
    n_neutral = (fused == TimingSignalType.NEUTRAL).sum()

    print(f"  融合信号: {latest_signal}")
    print(f"  目标仓位: {latest_exposure:.1%}")
    print(f"  信号分布: 看多{n_long} 看空{n_short} 中性{n_neutral}")
    print(f"  择时计算耗时: {time.time()-t0:.1f}s")

    return str(latest_signal), latest_exposure


# ==================== Step 8: 输出投资决策 ====================

def step8_output_decision(trade_date, target_weights, regime, regime_info,
                          timing_signal, timing_exposure, module_scores,
                          module_diagnostics, ensemble, data):
    """输出投资决策JSON"""
    print("\n" + "=" * 60)
    print("Step 8: 输出投资决策")
    print("=" * 60)

    # 构建持仓列表
    positions = []
    positive_weights = target_weights[target_weights > 0].sort_values(ascending=False)
    stock_basic = data.get('stock_basic', pd.DataFrame())

    for ts_code, weight in positive_weights.items():
        name = ''
        industry = ''
        if not stock_basic.empty:
            match = stock_basic[stock_basic['ts_code'] == ts_code]
            if not match.empty:
                name = match.iloc[0].get('name', '')
                industry = match.iloc[0].get('industry', '')

        positions.append({
            'ts_code': ts_code,
            'name': name,
            'industry': industry,
            'weight': round(float(weight), 4),
            'weight_pct': f"{float(weight):.2%}",
        })

    # 模块诊断摘要
    module_summary = {}
    for name, diag in module_diagnostics.items():
        module_summary[name] = {
            'coverage': diag.get('coverage', 0),
            'available_factors': diag.get('available_factors', []),
            'missing_factors': diag.get('missing_factors', []),
        }

    decision = {
        'trade_date': str(trade_date),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'regime': {
            'status': regime,
            'confidence': regime_info.get('confidence', 0.3),
            'features': {k: round(v, 4) if isinstance(v, float) else v
                         for k, v in regime_info.get('features', {}).items()},
            'weight_adjustments': {k: round(v, 3) for k, v in regime_info.get('weight_adjustments', {}).items()},
        },
        'timing': {
            'signal': timing_signal,
            'target_exposure': round(timing_exposure, 3),
        },
        'portfolio': {
            'n_positions': len(positions),
            'max_weight': round(float(positive_weights.max()), 4) if len(positive_weights) > 0 else 0,
            'positions': positions[:50],  # Top 50
        },
        'alpha_modules': {
            'weights': {k: round(v, 3) for k, v in ensemble.weights.items()},
            'diagnostics': module_summary,
        },
    }

    # 保存JSON
    out_file = f"investment_decision_{trade_date}.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(decision, f, indent=2, ensure_ascii=False, default=str)

    print(f"  投资决策已保存: {out_file}")
    print(f"\n  === 投资决策摘要 ===")
    print(f"  交易日期: {trade_date}")
    print(f"  市场状态: {regime}")
    print(f"  择时信号: {timing_signal}, 目标仓位: {timing_exposure:.1%}")
    print(f"  持仓数量: {len(positions)}")
    print(f"  Top 10 持仓:")
    for p in positions[:10]:
        print(f"    {p['ts_code']} ({p['name']}) {p['weight_pct']}")

    return decision


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(description='端到端投资决策流水线')
    parser.add_argument(
        'universe', nargs='?', default='hs300',
        choices=['all', 'hs300', 'zz500', 'zz1000'],
        help='股票池: all=全A股, hs300=沪深300, zz500=中证500, zz1000=中证1000',
    )
    parser.add_argument('--sync', action='store_true', help='先从Tushare同步数据')
    parser.add_argument('--workers', type=int, default=8, help='并发线程数')
    parser.add_argument('--start-date', default=None, help='历史数据起始日期 YYYYMMDD')
    parser.add_argument('--end-date', default=None, help='历史数据结束日期 YYYYMMDD')
    args = parser.parse_args()

    now = datetime.now()
    trade_date = now.strftime('%Y%m%d')
    start_date = args.start_date or (now - timedelta(days=365)).strftime('%Y%m%d')
    end_date = args.end_date or trade_date

    print("=" * 60)
    print("  端到端投资决策流水线")
    print(f"  股票池: {args.universe}")
    print(f"  交易日期: {trade_date}")
    print(f"  数据范围: {start_date} ~ {end_date}")
    print("=" * 60)

    t_start = time.time()

    # Step 1: 数据同步（可选）
    if args.sync:
        step1_sync_data(trade_date, start_date, end_date, args.workers)

    # Step 2: 数据加载
    engine = create_engine(settings.DATABASE_URL)
    data = step2_load_data(engine, args.universe)
    if data is None:
        print("\n错误: 数据加载失败，请使用 --sync 先同步数据")
        return

    # Step 3: 因子计算
    factor_df = step3_calc_factors(trade_date, data)
    if factor_df.empty:
        print("\n错误: 因子计算失败")
        return
    data['_factor_df'] = factor_df  # 供后续使用

    # Step 4: Alpha模块打分
    final_alpha, module_scores, module_diagnostics, ensemble = step4_alpha_scoring(factor_df)

    # Step 5: Regime检测
    regime, regime_info = step5_regime_detection(data)

    # Step 6: 组合优化
    target_weights = step6_portfolio_optimization(final_alpha, regime, data, ensemble)

    # Step 7: 择时信号
    timing_signal, timing_exposure = step7_timing_signals(data)

    # Step 8: 输出投资决策
    decision = step8_output_decision(
        trade_date, target_weights, regime, regime_info,
        timing_signal, timing_exposure, module_scores,
        module_diagnostics, ensemble, data,
    )

    elapsed = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"  流水线完成! 总耗时: {elapsed:.1f}s")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
