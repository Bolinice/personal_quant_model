#!/usr/bin/env python
"""
量化策略运行示例
演示完整的策略运行流程
"""
import sys
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, '.')


def run_factor_calculation_example():
    """因子计算示例"""
    print("\n" + "=" * 50)
    print("1. 因子计算示例")
    print("=" * 50)

    from app.core.factor_engine import FactorEngine
    from app.db.base import SessionLocal

    db = SessionLocal()
    engine = FactorEngine(db)

    # 计算单只股票的因子
    ts_code = "600000.SH"
    trade_date = "2023-12-29"

    print(f"\n计算 {ts_code} 在 {trade_date} 的因子值:")

    factors_to_calc = ['ROE', 'PE_TTM', 'MOM_20D', 'VOL_20D']

    for factor_code in factors_to_calc:
        try:
            value = engine.calculate_factor(factor_code, ts_code, trade_date)
            print(f"  {factor_code}: {value:.4f}" if value else f"  {factor_code}: N/A")
        except Exception as e:
            print(f"  {factor_code}: Error - {e}")

    db.close()


def run_factor_preprocess_example():
    """因子预处理示例"""
    print("\n" + "=" * 50)
    print("2. 因子预处理示例")
    print("=" * 50)

    import pandas as pd
    import numpy as np
    from app.core.factor_preprocess import FactorPreprocessor

    # 生成模拟因子值
    np.random.seed(42)
    factor_values = pd.Series(np.random.normal(0, 1, 100))

    # 添加一些缺失值和极值
    factor_values.iloc[10] = 10  # 极大值
    factor_values.iloc[20] = -10  # 极小值
    factor_values.iloc[30:35] = np.nan  # 缺失值

    preprocessor = FactorPreprocessor()

    print("\n原始数据统计:")
    print(f"  均值: {factor_values.mean():.4f}")
    print(f"  标准差: {factor_values.std():.4f}")
    print(f"  缺失值: {factor_values.isna().sum()}")

    # 预处理
    processed = preprocessor.preprocess(factor_values)

    print("\n预处理后统计:")
    print(f"  均值: {processed.mean():.4f}")
    print(f"  标准差: {processed.std():.4f}")
    print(f"  缺失值: {processed.isna().sum()}")


def run_factor_analysis_example():
    """因子分析示例"""
    print("\n" + "=" * 50)
    print("3. 因子分析示例")
    print("=" * 50)

    import pandas as pd
    import numpy as np
    from app.core.factor_analyzer import FactorAnalyzer

    np.random.seed(42)

    # 生成模拟数据
    n_stocks = 100
    n_days = 50

    dates = pd.date_range('2023-01-01', periods=n_days, freq='D')

    # 因子值和收益率
    factor_values = pd.Series(np.random.normal(0, 1, n_stocks), index=range(n_stocks))
    returns = pd.Series(np.random.normal(0.001, 0.02, n_stocks), index=range(n_stocks))

    analyzer = FactorAnalyzer()

    # 计算IC
    ic = analyzer.calc_ic(factor_values, returns)
    rank_ic = analyzer.calc_rank_ic(factor_values, returns)

    print(f"\nIC分析结果:")
    print(f"  IC: {ic:.4f}")
    print(f"  Rank IC: {rank_ic:.4f}")

    # 分组收益
    group_returns, long_short = analyzer.calc_group_returns(factor_values, returns, n_groups=10)

    print(f"\n分组收益:")
    for i, ret in enumerate(group_returns):
        print(f"  第{i+1}组: {ret*100:.2f}%")
    print(f"  多空收益: {long_short*100:.2f}%")


def run_model_scoring_example():
    """模型评分示例"""
    print("\n" + "=" * 50)
    print("4. 模型评分示例")
    print("=" * 50)

    import pandas as pd
    import numpy as np
    from app.core.model_scorer import MultiFactorScorer

    np.random.seed(42)

    # 模拟因子得分矩阵
    n_stocks = 100
    factor_names = ['ROE', 'PE_TTM', 'MOM_20D', 'VOL_20D', 'LIQUIDITY']

    factor_scores = pd.DataFrame(
        np.random.normal(0, 1, (n_stocks, len(factor_names))),
        columns=factor_names,
        index=[f"stock_{i}" for i in range(n_stocks)]
    )

    scorer = MultiFactorScorer()

    # 等权加权
    equal_weight_score = scorer.equal_weight(factor_scores)

    print("\n等权加权综合评分 (Top 10):")
    top_10 = equal_weight_score.nlargest(10)
    for stock, score in top_10.items():
        print(f"  {stock}: {score:.4f}")

    # 人工权重
    weights = {
        'ROE': 0.3,
        'PE_TTM': 0.2,
        'MOM_20D': 0.2,
        'VOL_20D': 0.15,
        'LIQUIDITY': 0.15
    }

    manual_weight_score = scorer.manual_weight(factor_scores, weights)

    print("\n人工权重综合评分 (Top 10):")
    top_10 = manual_weight_score.nlargest(10)
    for stock, score in top_10.items():
        print(f"  {stock}: {score:.4f}")


def run_timing_signal_example():
    """择时信号示例"""
    print("\n" + "=" * 50)
    print("5. 择时信号示例")
    print("=" * 50)

    import pandas as pd
    import numpy as np
    from app.core.timing_engine import TimingSignalCalculator

    np.random.seed(42)

    # 模拟价格序列
    n_days = 100
    dates = pd.date_range('2023-01-01', periods=n_days, freq='D')
    prices = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0.001, 0.02, n_days))), index=dates)
    returns = prices.pct_change()

    calculator = TimingSignalCalculator()

    # 均线择时
    ma_signal = calculator.ma_signal(prices, short_period=5, long_period=20)

    print("\n均线择时信号 (最近5天):")
    for date, signal in ma_signal.tail(5).items():
        signal_str = "多头" if signal > 0 else "空头" if signal < 0 else "中性"
        print(f"  {date.strftime('%Y-%m-%d')}: {signal_str}")

    # 波动率择时
    vol = calculator.calc_volatility(returns, period=20)
    vol_signal = calculator.volatility_signal(vol)

    print(f"\n当前波动率: {vol.iloc[-1]:.4f}")
    print(f"波动率信号: {'低波动-加仓' if vol_signal.iloc[-1] > 0 else '高波动-降仓' if vol_signal.iloc[-1] < 0 else '中性'}")


def run_portfolio_build_example():
    """组合构建示例"""
    print("\n" + "=" * 50)
    print("6. 组合构建示例")
    print("=" * 50)

    import pandas as pd
    import numpy as np
    from app.core.portfolio_builder import PortfolioBuilder

    np.random.seed(42)

    # 模拟评分数据
    n_stocks = 100
    scores = pd.Series(np.random.normal(0, 1, n_stocks),
                      index=[f"stock_{i}" for i in range(n_stocks)])

    # 模拟行业数据
    industries = ['银行', '医药', '科技', '消费', '制造']
    industry_data = pd.Series(
        np.random.choice(industries, n_stocks),
        index=scores.index
    )

    builder = PortfolioBuilder()

    # Top N选股
    selected = builder.select_top_n(scores, n=20)
    print(f"\nTop 20 选股结果: {selected[:5]}...")

    # 等权组合
    weights = builder.equal_weight(selected)
    print(f"\n等权组合权重: {weights.iloc[0]:.4f} (每只股票)")

    # 带行业约束选股
    constrained = builder.select_with_constraints(scores, industry_data, max_per_industry=3, n=20)
    print(f"\n带行业约束选股结果: {constrained[:5]}...")

    # 检查行业分布
    selected_industries = industry_data[constrained].value_counts()
    print("\n行业分布:")
    for ind, count in selected_industries.items():
        print(f"  {ind}: {count}只")


def run_performance_analysis_example():
    """绩效分析示例"""
    print("\n" + "=" * 50)
    print("7. 绩效分析示例")
    print("=" * 50)

    import pandas as pd
    import numpy as np
    from app.core.performance_analyzer import PerformanceAnalyzer

    np.random.seed(42)

    # 模拟净值序列
    n_days = 252  # 一年
    dates = pd.date_range('2023-01-01', periods=n_days, freq='D')
    returns = pd.Series(np.random.normal(0.001, 0.02, n_days), index=dates)
    nav = (1 + returns).cumprod()

    analyzer = PerformanceAnalyzer()

    # 完整绩效分析
    metrics = analyzer.analyze_performance(nav)

    print("\n绩效指标:")
    print(f"  总收益率: {metrics['total_return']*100:.2f}%")
    print(f"  年化收益率: {metrics['annual_return']*100:.2f}%")
    print(f"  年化波动率: {metrics['volatility']*100:.2f}%")
    print(f"  最大回撤: {metrics['max_drawdown']*100:.2f}%")
    print(f"  夏普比率: {metrics['sharpe_ratio']:.2f}")
    print(f"  索提诺比率: {metrics['sortino_ratio']:.2f}")
    print(f"  卡玛比率: {metrics['calmar_ratio']:.2f}")
    print(f"  胜率: {metrics['win_rate']*100:.2f}%")
    print(f"  盈亏比: {metrics['profit_loss_ratio']:.2f}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  A股多因子增强策略平台 - 运行示例")
    print("=" * 60)

    try:
        # 1. 因子计算
        run_factor_calculation_example()

        # 2. 因子预处理
        run_factor_preprocess_example()

        # 3. 因子分析
        run_factor_analysis_example()

        # 4. 模型评分
        run_model_scoring_example()

        # 5. 择时信号
        run_timing_signal_example()

        # 6. 组合构建
        run_portfolio_build_example()

        # 7. 绩效分析
        run_performance_analysis_example()

    except Exception as e:
        print(f"\n运行出错: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("  示例运行完成！")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
