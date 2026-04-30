"""
测试回测引擎性能优化模块
"""

import numpy as np
import pandas as pd
import pytest

from app.core.backtest_performance import (
    VectorizedBacktestEngine,
    ParallelBacktestRunner,
    BacktestCache,
)


class TestVectorizedNAVCalculation:
    """测试向量化净值计算"""

    def test_calc_nav_vectorized(self):
        """测试向量化净值计算"""
        # 创建测试数据
        dates = pd.date_range("2023-01-01", periods=10, freq="D")
        stocks = ["stock1", "stock2", "stock3"]

        # 持仓矩阵（股数）
        positions_df = pd.DataFrame(
            np.random.randint(0, 1000, size=(10, 3)),
            index=dates,
            columns=stocks,
        )

        # 价格矩阵
        prices_df = pd.DataFrame(
            np.random.uniform(10, 50, size=(10, 3)),
            index=dates,
            columns=stocks,
        )

        # 现金序列
        cash_series = pd.Series(
            np.random.uniform(10000, 50000, size=10),
            index=dates,
        )

        initial_capital = 100000.0

        # 向量化计算
        engine = VectorizedBacktestEngine()
        result = engine.calc_nav_vectorized(positions_df, prices_df, cash_series, initial_capital)

        # 验证结果
        assert len(result) == 10
        assert "nav" in result.columns
        assert "total_value" in result.columns
        assert "cash" in result.columns
        assert "position_value" in result.columns

        # 验证净值计算正确性
        assert (result["total_value"] == result["cash"] + result["position_value"]).all()
        assert (result["nav"] == result["total_value"] / initial_capital).all()

    def test_calc_returns_vectorized(self):
        """测试向量化收益率计算"""
        # 创建净值序列
        dates = pd.date_range("2023-01-01", periods=10, freq="D")
        nav_series = pd.Series([1.0, 1.02, 1.01, 1.05, 1.03, 1.08, 1.10, 1.09, 1.12, 1.15], index=dates)

        engine = VectorizedBacktestEngine()
        result = engine.calc_returns_vectorized(nav_series)

        # 验证结果
        assert len(result) == 10
        assert "daily_return" in result.columns
        assert "cumulative_return" in result.columns

        # 验证第一天收益率为0
        assert result["daily_return"].iloc[0] == 0

        # 验证累计收益率
        assert abs(result["cumulative_return"].iloc[-1] - 0.15) < 0.01


class TestVectorizedPositionUpdate:
    """测试向量化持仓更新"""

    def test_update_positions_vectorized(self):
        """测试向量化持仓更新"""
        stocks = ["stock1", "stock2", "stock3"]

        # 当前持仓
        current_positions = pd.Series([100, 200, 0], index=stocks)

        # 目标权重
        target_weights = pd.Series([0.3, 0.4, 0.3], index=stocks)

        # 价格
        prices = pd.Series([10.0, 20.0, 15.0], index=stocks)

        total_value = 100000.0

        engine = VectorizedBacktestEngine()
        target_shares, buy_shares, sell_shares = engine.update_positions_vectorized(
            current_positions, target_weights, prices, total_value
        )

        # 验证结果
        assert len(target_shares) == 3
        assert len(buy_shares) == 3
        assert len(sell_shares) == 3

        # 验证交易单位（100股）
        assert all(target_shares % 100 == 0)

        # 验证买卖数量
        assert (buy_shares >= 0).all()
        assert (sell_shares >= 0).all()


class TestVectorizedCostCalculation:
    """测试向量化成本计算"""

    def test_calc_transaction_costs_vectorized(self):
        """测试向量化交易成本计算"""
        stocks = ["stock1", "stock2", "stock3"]

        # 交易金额
        trade_amounts = pd.Series([10000, 20000, 15000], index=stocks)

        # 交易方向（1=买入，-1=卖出）
        trade_directions = pd.Series([1, -1, 1], index=stocks)

        engine = VectorizedBacktestEngine()
        result = engine.calc_transaction_costs_vectorized(trade_amounts, trade_directions)

        # 验证结果
        assert len(result) == 3
        assert "commission" in result.columns
        assert "stamp_tax" in result.columns
        assert "slippage" in result.columns
        assert "total_cost" in result.columns

        # 验证印花税只在卖出时收取
        assert result.loc["stock1", "stamp_tax"] == 0  # 买入
        assert result.loc["stock2", "stamp_tax"] > 0  # 卖出
        assert result.loc["stock3", "stamp_tax"] == 0  # 买入


class TestVectorizedMetrics:
    """测试向量化指标计算"""

    def test_calc_metrics_vectorized(self):
        """测试向量化指标计算"""
        # 创建收益率序列
        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.01 + 0.0005)  # 年化约12.6%

        engine = VectorizedBacktestEngine()
        metrics = engine.calc_metrics_vectorized(returns)

        # 验证指标
        assert "total_return" in metrics
        assert "annual_return" in metrics
        assert "volatility" in metrics
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "calmar_ratio" in metrics
        assert "win_rate" in metrics

        # 验证指标合理性
        assert -1 < metrics["total_return"] < 2
        assert -1 < metrics["annual_return"] < 2
        assert 0 < metrics["volatility"] < 1
        assert metrics["max_drawdown"] <= 0
        assert 0 <= metrics["win_rate"] <= 1

    def test_calc_metrics_with_benchmark(self):
        """测试带基准的指标计算"""
        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.01 + 0.0005)
        benchmark_returns = pd.Series(np.random.randn(252) * 0.01 + 0.0003)

        engine = VectorizedBacktestEngine()
        metrics = engine.calc_metrics_vectorized(returns, benchmark_returns)

        # 验证超额收益指标
        assert "tracking_error" in metrics
        assert "information_ratio" in metrics
        assert "excess_return" in metrics


class TestBacktestCache:
    """测试回测缓存"""

    def test_cache_save_and_load(self):
        """测试缓存保存和加载"""
        cache_config = BacktestCache(enabled=True, cache_dir=".cache/test_backtest")
        engine = VectorizedBacktestEngine(cache_config)

        # 测试配置
        config = {"param1": 1, "param2": 2}
        result = {"sharpe": 1.5, "return": 0.2}

        # 保存缓存
        engine.save_cached_result(config, result)

        # 加载缓存
        cached_result = engine.get_cached_result(config)

        assert cached_result is not None
        assert cached_result["sharpe"] == 1.5
        assert cached_result["return"] == 0.2

        # 清理
        engine.clear_cache()

    def test_cache_disabled(self):
        """测试禁用缓存"""
        cache_config = BacktestCache(enabled=False)
        engine = VectorizedBacktestEngine(cache_config)

        config = {"param1": 1}
        result = {"sharpe": 1.5}

        # 保存缓存（应该不执行）
        engine.save_cached_result(config, result)

        # 加载缓存（应该返回None）
        cached_result = engine.get_cached_result(config)
        assert cached_result is None


class TestParallelBacktest:
    """测试并行回测"""

    def test_run_parallel(self):
        """测试并行运行多个回测"""

        def mock_backtest(config):
            """模拟回测函数"""
            import time

            time.sleep(0.1)  # 模拟计算时间
            return {"sharpe": config["param"] * 0.5, "config": config}

        configs = [{"param": i} for i in range(1, 5)]

        runner = ParallelBacktestRunner(max_workers=2)
        results = runner.run_parallel(mock_backtest, configs, show_progress=False)

        # 验证结果
        assert len(results) == 4
        assert all("sharpe" in r for r in results)

    def test_run_parameter_sweep(self):
        """测试参数扫描"""

        def mock_backtest(config):
            """模拟回测函数"""
            return {
                "sharpe": config["param1"] * config["param2"],
                "return": config["param1"] + config["param2"],
            }

        base_config = {"base": 1}
        param_grid = {"param1": [1, 2], "param2": [0.5, 1.0]}

        runner = ParallelBacktestRunner(max_workers=2)
        results_df = runner.run_parameter_sweep(mock_backtest, base_config, param_grid)

        # 验证结果
        assert len(results_df) == 4  # 2 * 2 = 4 组合
        assert "param1" in results_df.columns
        assert "param2" in results_df.columns
        assert "sharpe" in results_df.columns
        assert "return" in results_df.columns


class TestPerformanceComparison:
    """性能对比测试"""

    def test_vectorized_vs_loop(self):
        """对比向量化和循环的性能"""
        import time

        # 创建测试数据
        dates = pd.date_range("2023-01-01", periods=252, freq="D")
        stocks = [f"stock{i}" for i in range(50)]

        positions_df = pd.DataFrame(
            np.random.randint(0, 1000, size=(252, 50)),
            index=dates,
            columns=stocks,
        )

        prices_df = pd.DataFrame(
            np.random.uniform(10, 50, size=(252, 50)),
            index=dates,
            columns=stocks,
        )

        cash_series = pd.Series(np.random.uniform(10000, 50000, size=252), index=dates)

        initial_capital = 1000000.0

        # 向量化方法
        engine = VectorizedBacktestEngine()
        start = time.time()
        result_vectorized = engine.calc_nav_vectorized(positions_df, prices_df, cash_series, initial_capital)
        time_vectorized = time.time() - start

        # 循环方法（模拟）
        start = time.time()
        navs = []
        for i in range(len(dates)):
            position_value = (positions_df.iloc[i] * prices_df.iloc[i]).sum()
            total_value = position_value + cash_series.iloc[i]
            nav = total_value / initial_capital
            navs.append(nav)
        time_loop = time.time() - start

        # 验证结果一致
        assert np.allclose(result_vectorized["nav"].values, navs, rtol=1e-5)

        # 向量化应该更快
        print(f"Vectorized: {time_vectorized:.4f}s, Loop: {time_loop:.4f}s")
        print(f"Speedup: {time_loop / time_vectorized:.1f}x")

        # 通常向量化会快3-10倍
        assert time_vectorized < time_loop


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_data(self):
        """测试空数据"""
        engine = VectorizedBacktestEngine()

        # 空DataFrame
        positions_df = pd.DataFrame()
        prices_df = pd.DataFrame()
        cash_series = pd.Series(dtype=float)

        result = engine.calc_nav_vectorized(positions_df, prices_df, cash_series, 100000.0)

        assert len(result) == 0

    def test_zero_prices(self):
        """测试零价格"""
        dates = pd.date_range("2023-01-01", periods=5, freq="D")
        stocks = ["stock1", "stock2"]

        positions_df = pd.DataFrame([[100, 200], [100, 200], [100, 200], [100, 200], [100, 200]], index=dates, columns=stocks)

        # 包含零价格
        prices_df = pd.DataFrame([[10, 20], [10, 0], [10, 20], [0, 20], [10, 20]], index=dates, columns=stocks)

        cash_series = pd.Series([10000] * 5, index=dates)

        engine = VectorizedBacktestEngine()
        result = engine.calc_nav_vectorized(positions_df, prices_df, cash_series, 100000.0)

        # 应该能处理零价格
        assert len(result) == 5
        assert not result["nav"].isna().any()
