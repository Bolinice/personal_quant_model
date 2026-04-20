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
from app.core.logging import logger, log_execution_time
from sqlalchemy import text


def step1_load_data():
    """Step 1: 从PostgreSQL加载真实行情+财务数据"""
    print("\n" + "="*60)
    print("Step 1: 加载真实A股数据")
    print("="*60)

    db = SessionLocal()
    t0 = time.perf_counter()

    # 加载HS300成分股
    hs300 = db.execute(text("""
        SELECT ts_code FROM index_components
        WHERE index_code = '000300.SH'
    """)).fetchall()
    hs300_codes = [r[0] for r in hs300]
    print(f"  HS300成分股: {len(hs300_codes)} 只")

    # 加载近3个月日线数据 (缩小范围加速)
    price_df = db.execute(text("""
        SELECT ts_code, trade_date, open, close, high, low,
               vol, amount, pct_chg
        FROM stock_daily
        WHERE trade_date >= '2026-01-01'
        ORDER BY ts_code, trade_date
    """)).fetchall()

    price_df = pd.DataFrame(price_df, columns=[
        'ts_code', 'trade_date', 'open', 'close', 'high', 'low',
        'vol', 'amount', 'pct_chg'
    ])
    # 数值转换
    for col in ['open', 'close', 'high', 'low', 'vol', 'amount', 'pct_chg']:
        price_df[col] = pd.to_numeric(price_df[col], errors='coerce')

    # 计算换手率 (用amount/close估算)
    price_df['turnover_rate'] = (price_df['amount'] / (price_df['close'] * price_df['vol']).replace(0, np.nan)).fillna(0)

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  日线数据: {len(price_df)} 条 ({price_df['ts_code'].nunique()} 只股票)")
    print(f"  日期范围: {price_df['trade_date'].min()} ~ {price_df['trade_date'].max()}")
    print(f"  耗时: {elapsed:.0f}ms")

    # 加载财务数据
    fin_df = db.execute(text("""
        SELECT ts_code, end_date, revenue, net_profit,
               gross_profit, gross_profit_margin,
               roe, roa, current_ratio, asset_liability_ratio
        FROM stock_financial
        WHERE end_date >= '2024-06-30'
        ORDER BY ts_code, end_date DESC
    """)).fetchall()

    fin_df = pd.DataFrame(fin_df, columns=[
        'ts_code', 'end_date', 'revenue', 'net_profit',
        'gross_profit', 'gross_profit_margin',
        'roe', 'roa', 'current_ratio', 'asset_liability_ratio'
    ])
    for col in fin_df.columns:
        if col not in ['ts_code', 'end_date']:
            fin_df[col] = pd.to_numeric(fin_df[col], errors='coerce')

    # 取每只股票最新一期财务数据
    fin_latest = fin_df.drop_duplicates(subset='ts_code', keep='first')
    print(f"  财务数据: {len(fin_latest)} 只股票 (最新期)")

    # 加载行业分类
    industry_df = db.execute(text("""
        SELECT ts_code, industry_name
        FROM stock_industry
        WHERE standard = 'sw2021'
    """)).fetchall()
    industry_map = {r[0]: r[1] for r in industry_df}
    print(f"  行业分类: {len(industry_map)} 只股票")

    db.close()

    return price_df, fin_latest, hs300_codes, industry_map


def step2_factor_calculation(price_df, fin_df):
    """Step 2: 因子计算 (FactorCalculator)"""
    print("\n" + "="*60)
    print("Step 2: 因子计算 (FactorCalculator)")
    print("="*60)

    from app.core.factor_calculator import FactorCalculator, FACTOR_GROUPS

    calculator = FactorCalculator()
    t0 = time.perf_counter()

    # 取截面数据 (最近一个交易日)
    latest_date = price_df['trade_date'].max()
    cross_section = price_df[price_df['trade_date'] == latest_date].copy()
    print(f"  截面日期: {latest_date}, {len(cross_section)} 只股票")

    # 计算各类因子
    # 动量因子需要时间序列，取每只股票的时序数据
    # 为简化，用全量price_df计算
    momentum = calculator.calc_momentum_factors(price_df)
    volatility = calculator.calc_volatility_factors(price_df)
    liquidity = calculator.calc_liquidity_factors(price_df)
    microstructure = calculator.calc_microstructure_factors(price_df)

    factor_count = 0
    for name, df in [('momentum', momentum), ('volatility', volatility),
                      ('liquidity', liquidity), ('microstructure', microstructure)]:
        if not df.empty:
            n_factors = len(df.columns) - 1  # 减去security_id
            factor_count += n_factors
            print(f"  {name}: {n_factors} 个因子, {len(df)} 条记录")

    # 价值/成长/质量因子
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
    print(f"  总计: {factor_count} 个因子")
    print(f"  耗时: {elapsed:.0f}ms")

    return momentum, volatility, liquidity


def step3_factor_preprocess(momentum, volatility, liquidity):
    """Step 3: 因子预处理 + 评分"""
    print("\n" + "="*60)
    print("Step 3: 因子预处理 + 多因子评分")
    print("="*60)

    from app.core.factor_preprocess import FactorPreprocessor
    from app.core.factor_calculator import FACTOR_DIRECTIONS
    from app.core.model_scorer import MultiFactorScorer

    # 合并因子
    factor_dfs = [df for df in [momentum, volatility, liquidity] if not df.empty and 'security_id' in df.columns]
    if not factor_dfs:
        print("  无有效因子数据")
        return pd.DataFrame()

    merged = factor_dfs[0]
    for f in factor_dfs[1:]:
        merged = pd.merge(merged, f, on='security_id', how='outer')

    print(f"  合并前: {len(merged)} 只股票, {len(merged.columns)-1} 个因子")

    # 预处理
    t0 = time.perf_counter()
    preprocessor = FactorPreprocessor()
    factor_cols = [c for c in merged.columns if c != 'security_id']
    processed = preprocessor.preprocess_dataframe(
        merged, factor_cols,
        neutralize=False,
        direction_map=FACTOR_DIRECTIONS,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  预处理后: {len(processed)} 只股票, {len(factor_cols)} 个因子")
    print(f"  预处理耗时: {elapsed:.0f}ms")

    # 评分
    t0 = time.perf_counter()
    scores_df = MultiFactorScorer.score_from_factor_df(
        processed, method='equal'
    )
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  评分完成: {len(scores_df)} 只股票")
    if 'total_score' in scores_df.columns:
        print(f"  Top 5: {scores_df.nlargest(5, 'total_score')[['security_id', 'total_score']].to_string(index=False)}")
    print(f"  评分耗时: {elapsed:.0f}ms")

    return scores_df


def step4_backtest(price_df, hs300_codes, industry_map):
    """Step 4: 事件驱动回测"""
    print("\n" + "="*60)
    print("Step 4: 事件驱动回测 (EventDrivenBacktestEngine)")
    print("="*60)

    from app.core.backtest_engine import EventDrivenBacktestEngine

    engine = EventDrivenBacktestEngine()

    # 准备price_data字典
    t0 = time.perf_counter()
    price_data = {}
    for _, row in price_df.iterrows():
        key = (row['ts_code'], row['trade_date'] if isinstance(row['trade_date'], date) else pd.Timestamp(row['trade_date']).date())
        price_data[key] = {
            'close': float(row['close']) if pd.notna(row['close']) else 0,
            'open': float(row['open']) if pd.notna(row['open']) else 0,
            'pct_chg': float(row['pct_chg']) if pd.notna(row['pct_chg']) else 0,
            'volume': float(row['vol']) if pd.notna(row['vol']) else 0,
            'amount': float(row['amount']) if pd.notna(row['amount']) else 0,
            'is_suspended': False,
            'is_st': False,
        }
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  price_data构建: {len(price_data)} 条, {elapsed:.0f}ms")

    # 取交易日列表
    trading_days = sorted(price_df['trade_date'].unique())
    trading_days = [d if isinstance(d, date) else pd.Timestamp(d).date() for d in trading_days]

    # 定义信号生成器: 等权持有HS300前20只
    universe = hs300_codes[:20]
    start_date = trading_days[0]
    end_date = trading_days[-1]

    def signal_generator(trade_date, universe, state):
        """简单等权信号"""
        return {code: 1.0 / len(universe) for code in universe}

    # 运行事件驱动回测
    t0 = time.perf_counter()
    result = engine.run_backtest_event_driven(
        signal_generator=signal_generator,
        universe=universe,
        start_date=start_date,
        end_date=end_date,
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

    # 从净值历史提取收益率
    nav_history = result.get('nav_history', [])
    if not nav_history:
        print("  无净值历史数据")
        return

    nav_series = pd.Series(
        [h['nav'] for h in nav_history],
        index=[h['trade_date'] for h in nav_history]
    )
    returns = nav_series.pct_change().dropna()

    # VaR分析
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

    # VaR回测检验
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
        print("  无净值历史数据")
        return

    nav_series = pd.Series(
        [h['nav'] for h in nav_history],
        index=[h['trade_date'] for h in nav_history]
    )
    returns = nav_series.pct_change().dropna()

    # 通胀夏普比率
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    dsr = engine.deflated_sharpe_ratio(
        sharpe=sharpe, n_trials=10,
        backtest_length_years=len(returns) / 252,
        skewness=returns.skew(),
        kurtosis=returns.kurtosis() + 3,
    )
    print(f"  观测Sharpe: {dsr['sharpe']:.2f}")
    print(f"  期望最大Sharpe: {dsr['expected_max_sharpe']:.2f}")
    print(f"  DSR: {dsr['dsr']:.4f} ({'显著' if dsr['is_significant'] else '不显著'})")

    # 最小回测长度
    min_btl = engine.min_backtest_length(sharpe)
    print(f"  最小回测长度: {min_btl['min_years']:.1f} 年")

    # Bootstrap置信区间
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

    # 取最近30只股票构建协方差矩阵
    latest_date = price_df['trade_date'].max()
    cross_section = price_df[price_df['trade_date'] == latest_date].head(30)

    # 计算收益率
    codes = cross_section['ts_code'].tolist()
    returns_data = {}
    for code in codes:
        stock_data = price_df[price_df['ts_code'] == code].sort_values('trade_date')
        ret = stock_data['close'].pct_change().dropna()
        if len(ret) > 20:
            returns_data[code] = ret

    if len(returns_data) < 5:
        print("  数据不足，跳过")
        return

    returns_df = pd.DataFrame(returns_data).dropna()
    if len(returns_df) < 20:
        print("  数据不足，跳过")
        return

    cov_matrix = returns_df.cov() * 252  # 年化
    expected_returns = returns_df.mean() * 252

    # 均值方差优化
    t0 = time.perf_counter()
    mv_weights = optimizer.mean_variance_optimize(
        expected_returns, cov_matrix,
        risk_aversion=1.0, max_position=0.10
    )
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  均值方差优化: {len(mv_weights)} 只, 有效持仓={1/(mv_weights**2).sum():.1f}, 耗时={elapsed:.0f}ms")

    # 风险平价
    t0 = time.perf_counter()
    rp_weights = optimizer.risk_parity_optimize(cov_matrix, max_position=0.10)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  风险平价优化: {len(rp_weights)} 只, 有效持仓={1/(rp_weights**2).sum():.1f}, 耗时={elapsed:.0f}ms")

    # HRP
    t0 = time.perf_counter()
    hrp_weights = optimizer.hrp_optimize(cov_matrix.values, index=cov_matrix.index)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  HRP层次风险平价: {len(hrp_weights)} 只, 有效持仓={1/(hrp_weights**2).sum():.1f}, 耗时={elapsed:.0f}ms")

    # 最小方差
    t0 = time.perf_counter()
    minv_weights = optimizer.min_variance_optimize(cov_matrix, max_position=0.10)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  最小方差优化: {len(minv_weights)} 只, 有效持仓={1/(minv_weights**2).sum():.1f}, 耗时={elapsed:.0f}ms")

    # 优化结果分析
    analysis = optimizer.analyze_optimization(mv_weights, expected_returns, cov_matrix)
    print(f"\n  均值方差组合分析:")
    print(f"    期望收益: {analysis['expected_return']:.2%}")
    print(f"    年化波动: {analysis['volatility']:.2%}")
    print(f"    夏普比率: {analysis['sharpe_ratio']:.2f}")
    print(f"    有效持仓: {analysis['effective_positions']:.1f}")


def step8_cache_and_config():
    """Step 8: 缓存+配置验证"""
    print("\n" + "="*60)
    print("Step 8: 缓存 + 配置验证")
    print("="*60)

    from app.core.cache import CacheService, TwoLevelCache, factor_cache
    from app.core.config import settings

    # 缓存测试
    cache = CacheService(max_size=100, default_ttl=60)
    cache.set("test_key", {"value": 42})
    result = cache.get("test_key")
    print(f"  CacheService: set/get = {result}, stats = {cache.stats()}")

    # 因子缓存
    factor_cache.set("factor:test:2025-01-01", pd.DataFrame({"a": [1, 2, 3]}))
    cached = factor_cache.get("factor:test:2025-01-01")
    print(f"  factor_cache: hit = {cached is not None}, stats = {factor_cache.stats()}")

    # 交易日失效
    n_invalidated = factor_cache.invalidate_by_trade_date(date(2025, 1, 1))
    print(f"  交易日失效: {n_invalidated} 条缓存被清除")

    # 配置
    print(f"\n  配置验证:")
    print(f"    BacktestConfig: commission={settings.backtest.COMMISSION_RATE}, slippage={settings.backtest.SLIPPAGE_RATE}")
    print(f"    RiskConfig: risk_aversion={settings.risk.RISK_AVERSION}, max_position={settings.risk.MAX_POSITION}")
    print(f"    FactorConfig: min_coverage={settings.factor.MIN_COVERAGE}, forward_period={settings.factor.FORWARD_PERIOD}")

    # 安全检查
    warnings = settings.check_production_safety()
    if warnings:
        print(f"    安全警告: {warnings}")


def main():
    print("="*60)
    print("A股多因子增强策略平台 - 端到端实测")
    print("基于真实PostgreSQL数据 (240万+日线记录)")
    print("="*60)

    total_t0 = time.perf_counter()

    # Step 1: 加载数据
    price_df, fin_df, hs300_codes, industry_map = step1_load_data()

    # Step 2: 因子计算
    momentum, volatility, liquidity = step2_factor_calculation(price_df, fin_df)

    # Step 3: 因子预处理+评分
    scores_df = step3_factor_preprocess(momentum, volatility, liquidity)

    # Step 4: 事件驱动回测
    backtest_result = step4_backtest(price_df, hs300_codes, industry_map)

    # Step 5: 风险分析
    step5_risk_analysis(backtest_result)

    # Step 6: 统计显著性检验
    step6_statistical_tests(backtest_result)

    # Step 7: 组合优化
    step7_portfolio_optimization(price_df)

    # Step 8: 缓存+配置
    step8_cache_and_config()

    total_elapsed = (time.perf_counter() - total_t0) * 1000
    print("\n" + "="*60)
    print(f"端到端实测完成! 总耗时: {total_elapsed:.0f}ms")
    print("="*60)


if __name__ == '__main__':
    main()
