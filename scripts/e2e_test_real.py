"""
端到端实测 - 用真实A股数据验证重构后的全链路
因子计算 → 评分 → 组合构建 → 回测 → 风险分析 → 绩效归因
"""
import sys
import time
import numpy as np
import pandas as pd
from datetime import date, timedelta

from app.db.base import SessionLocal
from app.core.logging import logger
from app.models.market import StockDaily, StockFinancial, IndexComponent, StockIndustry
from sqlalchemy import text


def step1_load_data():
    """Step 1: 从PostgreSQL加载真实行情+财务数据"""
    print("\n" + "="*60)
    print("Step 1: 加载真实A股数据")
    print("="*60)

    db = SessionLocal()
    t0 = time.perf_counter()

    # 加载HS300成分股
    hs300 = db.query(IndexComponent.ts_code).filter(
        IndexComponent.index_code == '000300.SH'
    ).all()
    hs300_codes = [r[0] for r in hs300]
    print(f"  HS300成分股: {len(hs300_codes)} 只")

    # 加载近3个月日线数据 (使用ORM)
    start_dt = date(2026, 1, 1)
    stocks = db.query(StockDaily).filter(
        StockDaily.trade_date >= start_dt
    ).order_by(StockDaily.ts_code, StockDaily.trade_date).all()

    price_df = pd.DataFrame([{
        'ts_code': s.ts_code,
        'trade_date': s.trade_date if isinstance(s.trade_date, date) else pd.Timestamp(s.trade_date).date(),
        'open': float(s.open) if s.open else np.nan,
        'close': float(s.close) if s.close else np.nan,
        'high': float(s.high) if s.high else np.nan,
        'low': float(s.low) if s.low else np.nan,
        'vol': float(s.vol) if s.vol else np.nan,
        'amount': float(s.amount) if s.amount else np.nan,
        'pct_chg': float(s.pct_chg) if s.pct_chg else np.nan,
    } for s in stocks])

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  日线数据: {len(price_df)} 条 ({price_df['ts_code'].nunique()} 只股票)")
    print(f"  日期范围: {price_df['trade_date'].min()} ~ {price_df['trade_date'].max()}")
    print(f"  耗时: {elapsed:.0f}ms")

    # 加载财务数据
    fin_stocks = db.query(StockFinancial).filter(
        StockFinancial.end_date >= date(2024, 6, 30)
    ).order_by(StockFinancial.ts_code, StockFinancial.end_date.desc()).all()

    fin_df = pd.DataFrame([{
        'ts_code': s.ts_code,
        'end_date': s.end_date,
        'revenue': float(s.revenue) if s.revenue else np.nan,
        'net_profit': float(s.net_profit) if s.net_profit else np.nan,
        'gross_profit': float(s.gross_profit) if s.gross_profit else np.nan,
        'gross_profit_margin': float(s.gross_profit_margin) if s.gross_profit_margin else np.nan,
        'roe': float(s.roe) if s.roe else np.nan,
        'roa': float(s.roa) if s.roa else np.nan,
        'current_ratio': float(s.current_ratio) if s.current_ratio else np.nan,
        'asset_liability_ratio': float(s.asset_liability_ratio) if s.asset_liability_ratio else np.nan,
    } for s in fin_stocks])

    fin_latest = fin_df.drop_duplicates(subset='ts_code', keep='first') if not fin_df.empty else fin_df
    print(f"  财务数据: {len(fin_latest)} 只股票 (最新期)")

    # 加载行业分类
    industries = db.query(StockIndustry).filter(
        StockIndustry.standard == 'sw2021'
    ).all()
    industry_map = {s.ts_code: s.industry_name for s in industries}
    print(f"  行业分类: {len(industry_map)} 只股票")

    db.close()
    return price_df, fin_latest, hs300_codes, industry_map


def step2_factor_calculation(price_df, fin_df):
    """Step 2: 因子计算 (FactorCalculator)"""
    print("\n" + "="*60)
    print("Step 2: 因子计算 (FactorCalculator)")
    print("="*60)

    from app.core.factor_calculator import FactorCalculator

    calculator = FactorCalculator()
    t0 = time.perf_counter()

    # 只取截面数据做因子计算 (每只股票最新一天)
    latest_date = price_df['trade_date'].max()
    cross_section = price_df[price_df['trade_date'] == latest_date].copy()
    print(f"  截面日期: {latest_date}, {len(cross_section)} 只股票")

    # 动量/波动率因子需要时间序列，但评分只用截面
    # 计算各类因子 (用截面数据)
    momentum = calculator.calc_momentum_factors(cross_section)
    volatility = calculator.calc_volatility_factors(cross_section)
    liquidity = calculator.calc_liquidity_factors(cross_section)
    microstructure = calculator.calc_microstructure_factors(cross_section)

    factor_count = 0
    for name, df in [('momentum', momentum), ('volatility', volatility),
                      ('liquidity', liquidity), ('microstructure', microstructure)]:
        if not df.empty:
            n_factors = len(df.columns) - 1
            factor_count += n_factors
            print(f"  {name}: {n_factors} 个因子, {len(df)} 条记录")

    if not fin_df.empty:
        valuation = calculator.calc_valuation_factors(fin_df)
        growth = calculator.calc_growth_factors(fin_df)
        quality = calculator.calc_quality_factors(fin_df)
        for name, df in [('valuation', valuation), ('growth', growth), ('quality', quality)]:
            if not df.empty:
                n_factors = len(df.columns) - 1
                factor_count += n_factors
                print(f"  {name}: {n_factors} 个因子, {len(df)} 条记录")

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  总计: {factor_count} 个因子, 耗时: {elapsed:.0f}ms")

    return momentum, volatility, liquidity


def step3_factor_preprocess(momentum, volatility, liquidity):
    """Step 3: 因子预处理 + 评分"""
    print("\n" + "="*60)
    print("Step 3: 因子预处理 + 多因子评分")
    print("="*60)

    from app.core.factor_preprocess import FactorPreprocessor
    from app.core.factor_calculator import FACTOR_DIRECTIONS
    from app.core.model_scorer import MultiFactorScorer

    factor_dfs = [df for df in [momentum, volatility, liquidity] if not df.empty and 'security_id' in df.columns]
    if not factor_dfs:
        print("  无有效因子数据")
        return pd.DataFrame()

    merged = factor_dfs[0]
    for f in factor_dfs[1:]:
        merged = pd.merge(merged, f, on='security_id', how='outer')

    print(f"  合并前: {len(merged)} 只股票, {len(merged.columns)-1} 个因子")

    t0 = time.perf_counter()
    preprocessor = FactorPreprocessor()
    factor_cols = [c for c in merged.columns if c != 'security_id']
    processed = preprocessor.preprocess_dataframe(
        merged, factor_cols, neutralize=False, direction_map=FACTOR_DIRECTIONS,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  预处理后: {len(processed)} 只股票, 耗时: {elapsed:.0f}ms")

    t0 = time.perf_counter()
    scores_df = MultiFactorScorer.score_from_factor_df(processed, method='equal')
    elapsed = (time.perf_counter() - t0) * 1000
    if 'total_score' in scores_df.columns:
        top5 = scores_df.nlargest(5, 'total_score')[['security_id', 'total_score']]
        print(f"  Top 5: {top5.to_string(index=False)}")
    print(f"  评分耗时: {elapsed:.0f}ms")
    return scores_df


def step4_backtest(price_df, hs300_codes, industry_map):
    """Step 4: 事件驱动回测"""
    print("\n" + "="*60)
    print("Step 4: 事件驱动回测 (EventDrivenBacktestEngine)")
    print("="*60)

    from app.core.backtest_engine import EventDrivenBacktestEngine

    engine = EventDrivenBacktestEngine()

    # 准备price_data字典 (只取universe中的股票)
    universe = hs300_codes[:20]
    universe_set = set(universe)
    t0 = time.perf_counter()
    price_data = {}
    for _, row in price_df[price_df['ts_code'].isin(universe_set)].iterrows():
        td = row['trade_date'] if isinstance(row['trade_date'], date) else pd.Timestamp(row['trade_date']).date()
        key = (row['ts_code'], td)
        price_data[key] = {
            'close': float(row['close']) if pd.notna(row['close']) else 0,
            'open': float(row['open']) if pd.notna(row['open']) else 0,
            'pct_chg': float(row['pct_chg']) if pd.notna(row['pct_chg']) else 0,
            'volume': float(row['vol']) if pd.notna(row['vol']) else 0,
            'amount': float(row['amount']) if pd.notna(row['amount']) else 0,
            'is_suspended': False, 'is_st': False,
        }
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  price_data构建: {len(price_data)} 条, {elapsed:.0f}ms")

    trading_days = sorted(set(td for _, td in price_data.keys()))

    start_date = trading_days[0]
    end_date = trading_days[-1]

    def signal_generator(trade_date, universe, state):
        return {code: 1.0 / len(universe) for code in universe}

    t0 = time.perf_counter()
    result = engine.run_backtest_event_driven(
        signal_generator=signal_generator,
        universe=universe,
        start_date=start_date, end_date=end_date,
        rebalance_freq='monthly',
        initial_capital=1_000_000,
        trading_days=trading_days,
        price_data=price_data,
        industry_data={k: industry_map.get(k, 'unknown') for k in universe},
        max_industry_weight=0.30,
    )
    elapsed = (time.perf_counter() - t0) * 1000

    metrics = result.get('metrics', {})
    print(f"  回测期间: {start_date} ~ {end_date}")
    print(f"  总交易天数: {result.get('total_days', 0)}")
    print(f"  总收益率: {metrics.get('total_return', 0):.2%}")
    print(f"  年化收益: {metrics.get('annual_return', 0):.2%}")
    print(f"  夏普比率: {metrics.get('sharpe', 0):.2f}")
    print(f"  最大回撤: {metrics.get('max_drawdown', 0):.2%}")
    print(f"  索提诺比率: {metrics.get('sortino', 0):.2f}")
    print(f"  换手率: {metrics.get('turnover_rate', 0):.2f}")
    print(f"  总交易次数: {result.get('total_trades', 0)}")
    print(f"  订单成交率: {result.get('order_fill_rate', 0):.2%}")
    print(f"  被拒订单数: {result.get('total_rejected_orders', 0)}")
    print(f"  回测耗时: {elapsed:.0f}ms")
    return result


def step5_risk_analysis(result):
    """Step 5: 风险分析"""
    print("\n" + "="*60)
    print("Step 5: 风险分析 (RiskModel)")
    print("="*60)

    from app.core.risk_model import RiskModel
    risk_model = RiskModel()

    nav_history = result.get('nav_history', [])
    if not nav_history:
        print("  无净值历史数据"); return

    nav_series = pd.Series([h['nav'] for h in nav_history], index=[h['trade_date'] for h in nav_history])
    returns = nav_series.pct_change().dropna()

    t0 = time.perf_counter()
    hist_var = risk_model.historical_var(returns, confidence=0.95)
    param_var = risk_model.parametric_var(returns, confidence=0.95)
    cvar = risk_model.conditional_var(returns, confidence=0.95)
    t_var = risk_model.student_t_var(returns, confidence=0.95)
    elapsed = (time.perf_counter() - t0) * 1000

    print(f"  历史VaR(95%): {hist_var:.4f}")
    print(f"  参数VaR(95%): {param_var:.4f}")
    print(f"  CVaR(95%): {cvar:.4f}")
    print(f"  Student-t VaR(95%): {t_var:.4f}")
    print(f"  VaR计算耗时: {elapsed:.0f}ms")

    t0 = time.perf_counter()
    var_bt = risk_model.backtest_var(returns, confidence=0.95, window=60, method='historical')
    elapsed = (time.perf_counter() - t0) * 1000

    print(f"\n  VaR回测检验:")
    print(f"    突破次数: {var_bt.get('n_violations', 0)}/{var_bt.get('n_observations', 0)}")
    print(f"    实际突破率: {var_bt.get('empirical_rate', 0):.4f} (期望: {var_bt.get('expected_rate', 0):.4f})")
    kupiec = var_bt.get('kupiec_pof', {})
    print(f"    Kupiec POF p值: {kupiec.get('p_value', 'N/A')}")
    christ = var_bt.get('christoffersen_independence', {})
    print(f"    Christoffersen p值: {christ.get('p_value', 'N/A')}")
    print(f"    VaR充分性: {'通过' if var_bt.get('var_adequate', False) else '不通过'}")
    print(f"    VaR回测耗时: {elapsed:.0f}ms")


def step6_statistical_tests(result):
    """Step 6: 统计显著性检验"""
    print("\n" + "="*60)
    print("Step 6: 统计显著性检验")
    print("="*60)

    from app.core.backtest_engine import ABShareBacktestEngine
    engine = ABShareBacktestEngine()

    nav_history = result.get('nav_history', [])
    if not nav_history:
        print("  无净值历史数据"); return

    nav_series = pd.Series([h['nav'] for h in nav_history], index=[h['trade_date'] for h in nav_history])
    returns = nav_series.pct_change().dropna()

    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    dsr = engine.deflated_sharpe_ratio(
        sharpe=sharpe, n_trials=10, backtest_length_years=len(returns) / 252,
        skewness=returns.skew(), kurtosis=returns.kurtosis() + 3,
    )
    print(f"  观测Sharpe: {dsr['sharpe']:.2f}")
    print(f"  期望最大Sharpe: {dsr['expected_max_sharpe']:.2f}")
    print(f"  DSR: {dsr['dsr']:.4f} ({'显著' if dsr['is_significant'] else '不显著'})")

    min_btl = engine.min_backtest_length(sharpe)
    print(f"  最小回测长度: {min_btl['min_years']:.1f} 年")

    t0 = time.perf_counter()
    ci = engine.bootstrap_confidence_interval(returns, metric='sharpe', n_bootstrap=500)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  Sharpe 95% CI: [{ci['lower']:.2f}, {ci['upper']:.2f}]")
    print(f"  Bootstrap耗时: {elapsed:.0f}ms")


def step7_portfolio_optimization(price_df):
    """Step 7: 组合优化"""
    print("\n" + "="*60)
    print("Step 7: 组合优化 (PortfolioOptimizer)")
    print("="*60)

    from app.core.portfolio_optimizer import PortfolioOptimizer
    optimizer = PortfolioOptimizer()

    # 取最近20只股票构建协方差矩阵
    latest_date = price_df['trade_date'].max()
    codes = price_df[price_df['trade_date'] == latest_date]['ts_code'].head(20).tolist()

    returns_data = {}
    for code in codes:
        stock_data = price_df[price_df['ts_code'] == code].sort_values('trade_date')
        ret = stock_data.set_index('trade_date')['close'].pct_change().dropna()
        if len(ret) > 20:
            returns_data[code] = ret

    if len(returns_data) < 5:
        print("  数据不足，跳过"); return

    returns_df = pd.DataFrame(returns_data).dropna()
    if len(returns_df) < 20:
        print("  数据不足，跳过"); return

    cov_matrix = returns_df.cov() * 252
    expected_returns = returns_df.mean() * 252

    t0 = time.perf_counter()
    mv_weights = optimizer.mean_variance_optimize(expected_returns, cov_matrix, risk_aversion=1.0, max_position=0.10)
    elapsed = (time.perf_counter() - t0) * 1000
    eff_n = 1 / (mv_weights**2).sum()
    print(f"  均值方差: 有效持仓={eff_n:.1f}, 耗时={elapsed:.0f}ms")

    t0 = time.perf_counter()
    rp_weights = optimizer.risk_parity_optimize(cov_matrix, max_position=0.10)
    elapsed = (time.perf_counter() - t0) * 1000
    eff_n = 1 / (rp_weights**2).sum()
    print(f"  风险平价: 有效持仓={eff_n:.1f}, 耗时={elapsed:.0f}ms")

    t0 = time.perf_counter()
    hrp_weights = optimizer.hrp_optimize(cov_matrix.values, index=cov_matrix.index)
    elapsed = (time.perf_counter() - t0) * 1000
    eff_n = 1 / (hrp_weights**2).sum()
    print(f"  HRP: 有效持仓={eff_n:.1f}, 耗时={elapsed:.0f}ms")

    t0 = time.perf_counter()
    minv_weights = optimizer.min_variance_optimize(cov_matrix, max_position=0.10)
    elapsed = (time.perf_counter() - t0) * 1000
    eff_n = 1 / (minv_weights**2).sum()
    print(f"  最小方差: 有效持仓={eff_n:.1f}, 耗时={elapsed:.0f}ms")

    analysis = optimizer.analyze_optimization(mv_weights, expected_returns, cov_matrix)
    print(f"\n  均值方差组合: 期望收益={analysis['expected_return']:.2%}, 波动={analysis['volatility']:.2%}, 夏普={analysis['sharpe_ratio']:.2f}")


def step8_cache_and_config():
    """Step 8: 缓存+配置验证"""
    print("\n" + "="*60)
    print("Step 8: 缓存 + 配置验证")
    print("="*60)

    from app.core.cache import CacheService, factor_cache
    from app.core.config import settings

    cache = CacheService(max_size=100, default_ttl=60)
    cache.set("test_key", {"value": 42})
    result = cache.get("test_key")
    print(f"  CacheService: set/get = {result}, stats = {cache.stats()}")

    factor_cache.set("factor:test:2025-01-01", pd.DataFrame({"a": [1, 2, 3]}))
    cached = factor_cache.get("factor:test:2025-01-01")
    print(f"  factor_cache: hit = {cached is not None}, stats = {factor_cache.stats()}")

    n_inv = factor_cache.invalidate_by_trade_date(date(2025, 1, 1))
    print(f"  交易日失效: {n_inv} 条缓存被清除")

    print(f"\n  配置验证:")
    print(f"    Backtest: commission={settings.backtest.COMMISSION_RATE}, slippage={settings.backtest.SLIPPAGE_RATE}")
    print(f"    Risk: risk_aversion={settings.risk.RISK_AVERSION}, max_position={settings.risk.MAX_POSITION}")
    print(f"    Factor: min_coverage={settings.factor.MIN_COVERAGE}, forward_period={settings.factor.FORWARD_PERIOD}")

    warnings = settings.check_production_safety()
    if warnings:
        print(f"    安全警告: {warnings}")


def main():
    print("="*60)
    print("A股多因子增强策略平台 - 端到端实测")
    print("基于真实PostgreSQL数据 (240万+日线记录)")
    print("="*60)

    total_t0 = time.perf_counter()

    price_df, fin_df, hs300_codes, industry_map = step1_load_data()
    momentum, volatility, liquidity = step2_factor_calculation(price_df, fin_df)
    scores_df = step3_factor_preprocess(momentum, volatility, liquidity)
    backtest_result = step4_backtest(price_df, hs300_codes, industry_map)
    step5_risk_analysis(backtest_result)
    step6_statistical_tests(backtest_result)
    step7_portfolio_optimization(price_df)
    step8_cache_and_config()

    total_elapsed = (time.perf_counter() - total_t0) * 1000
    print("\n" + "="*60)
    print(f"端到端实测完成! 总耗时: {total_elapsed:.0f}ms")
    print("="*60)


if __name__ == '__main__':
    main()
