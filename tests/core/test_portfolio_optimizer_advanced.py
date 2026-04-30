"""
测试高级组合优化算法
"""

import numpy as np
import pandas as pd

from app.core.portfolio_optimizer_advanced import (
    AdvancedPortfolioOptimizer,
    OptimizationConstraints,
    compare_optimization_methods,
)


class TestCVaROptimization:
    """测试CVaR优化"""

    def test_cvar_optimize(self):
        """测试CVaR优化"""
        np.random.seed(42)

        # 生成收益情景
        n_scenarios = 1000
        n_assets = 5
        returns_scenarios = np.random.randn(n_scenarios, n_assets) * 0.01

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.cvar_optimize(returns_scenarios, confidence_level=0.95)

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0, atol=0.01)
        assert np.all(weights >= 0)


class TestMaxSharpeOptimization:
    """测试最大夏普比率优化"""

    def test_max_sharpe_optimize(self):
        """测试最大夏普比率优化"""
        np.random.seed(42)

        n_assets = 5
        expected_returns = np.array([0.10, 0.12, 0.08, 0.15, 0.11])

        # 生成协方差矩阵
        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.02)
        cov_matrix = returns.cov().values

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.max_sharpe_optimize(expected_returns, cov_matrix)

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)

        # 计算夏普比率
        portfolio_return = weights @ expected_returns
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        sharpe = (portfolio_return - 0.03) / portfolio_vol

        # 夏普比率应该是正的
        assert sharpe > 0


class TestEqualRiskContribution:
    """测试等权重风险贡献"""

    def test_equal_risk_contribution(self):
        """测试ERC优化"""
        np.random.seed(42)

        n_assets = 5
        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.01)
        cov_matrix = returns.cov().values

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.equal_risk_contribution(cov_matrix)

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)

        # 验证风险贡献接近相等
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        marginal_contrib = cov_matrix @ weights
        risk_contrib = weights * marginal_contrib / portfolio_vol

        # 风险贡献的标准差应该很小
        assert risk_contrib.std() < risk_contrib.mean() * 0.5


class TestMaxDecorrelation:
    """测试最大去相关优化"""

    def test_max_decorrelation_optimize(self):
        """测试最大去相关优化"""
        np.random.seed(42)

        n_assets = 5
        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.01)
        corr_matrix = returns.corr().values

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.max_decorrelation_optimize(corr_matrix)

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)


class TestRobustOptimization:
    """测试稳健优化"""

    def test_robust_optimize(self):
        """测试稳健优化"""
        np.random.seed(42)

        n_assets = 5
        expected_returns = np.array([0.10, 0.12, 0.08, 0.15, 0.11])

        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.02)
        cov_matrix = returns.cov().values

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.robust_optimize(
            expected_returns,
            cov_matrix,
            uncertainty_set=0.05,
        )

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)


class TestTrackingErrorOptimization:
    """测试跟踪误差优化"""

    def test_min_tracking_error_optimize(self):
        """测试最小跟踪误差优化"""
        np.random.seed(42)

        n_assets = 5
        expected_returns = np.array([0.10, 0.12, 0.08, 0.15, 0.11])
        benchmark_weights = np.array([0.2, 0.2, 0.2, 0.2, 0.2])

        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.02)
        cov_matrix = returns.cov().values

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.min_tracking_error_optimize(
            expected_returns,
            cov_matrix,
            benchmark_weights,
            max_tracking_error=0.05,
        )

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)

        # 验证跟踪误差
        active_weights = weights - benchmark_weights
        te = np.sqrt(active_weights @ cov_matrix @ active_weights)
        assert te <= 0.05 + 1e-6  # 允许小误差

    def test_max_information_ratio_optimize(self):
        """测试最大信息比率优化"""
        np.random.seed(42)

        n_assets = 5
        expected_returns = np.array([0.10, 0.12, 0.08, 0.15, 0.11])
        benchmark_weights = np.array([0.2, 0.2, 0.2, 0.2, 0.2])

        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.02)
        cov_matrix = returns.cov().values

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.max_information_ratio_optimize(
            expected_returns,
            cov_matrix,
            benchmark_weights,
        )

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)


class TestHierarchicalClustering:
    """测试分层聚类组合"""

    def test_hierarchical_clustering_portfolio(self):
        """测试分层聚类组合"""
        np.random.seed(42)

        n_samples = 100
        n_assets = 10
        returns = pd.DataFrame(
            np.random.randn(n_samples, n_assets) * 0.01,
            columns=[f"asset{i}" for i in range(n_assets)],
        )

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.hierarchical_clustering_portfolio(returns, n_clusters=3)

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)


class TestCompareOptimizationMethods:
    """测试优化方法对比"""

    def test_compare_optimization_methods(self):
        """测试对比不同优化方法"""
        np.random.seed(42)

        n_assets = 5
        expected_returns = np.array([0.10, 0.12, 0.08, 0.15, 0.11])

        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.02)
        cov_matrix = returns.cov().values

        results = compare_optimization_methods(
            expected_returns,
            cov_matrix,
            methods=["equal_weight", "min_variance", "max_sharpe", "risk_parity"],
        )

        # 验证结果
        assert len(results) == 4
        assert "method" in results.columns
        assert "return" in results.columns
        assert "volatility" in results.columns
        assert "sharpe_ratio" in results.columns

        # 所有方法都应该有正的收益
        assert all(results["return"] > 0)


class TestOptimizationConstraints:
    """测试优化约束"""

    def test_constraints_initialization(self):
        """测试约束初始化"""
        constraints = OptimizationConstraints(
            max_position=0.15,
            min_position=0.01,
            max_turnover=0.3,
        )

        assert constraints.max_position == 0.15
        assert constraints.min_position == 0.01
        assert constraints.max_turnover == 0.3


class TestEdgeCases:
    """边界情况测试"""

    def test_single_asset(self):
        """测试单个资产"""
        expected_returns = np.array([0.10])
        cov_matrix = np.array([[0.04]])

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.max_sharpe_optimize(expected_returns, cov_matrix)

        # 单个资产应该全部配置
        assert np.allclose(weights, [1.0])

    def test_negative_returns(self):
        """测试负收益"""
        np.random.seed(42)

        n_assets = 5
        expected_returns = np.array([-0.05, -0.02, -0.08, -0.01, -0.03])

        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.02)
        cov_matrix = returns.cov().values

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.max_sharpe_optimize(expected_returns, cov_matrix)

        # 即使收益为负，权重和仍应为1
        assert np.allclose(weights.sum(), 1.0)

    def test_highly_correlated_assets(self):
        """测试高度相关的资产"""
        np.random.seed(42)

        # 创建高度相关的资产
        n_samples = 100
        base_returns = np.random.randn(n_samples) * 0.01

        returns = pd.DataFrame({
            "asset1": base_returns,
            "asset2": base_returns * 1.2 + np.random.randn(n_samples) * 0.001,
            "asset3": base_returns * 0.8 + np.random.randn(n_samples) * 0.001,
        })

        corr_matrix = returns.corr().values

        optimizer = AdvancedPortfolioOptimizer()
        weights = optimizer.max_decorrelation_optimize(corr_matrix)

        # 应该能处理高相关性
        assert len(weights) == 3
        assert np.allclose(weights.sum(), 1.0)
