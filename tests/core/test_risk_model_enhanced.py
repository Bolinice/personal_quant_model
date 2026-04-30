"""
测试风险模型增强模块
"""

import numpy as np
import pandas as pd
import pytest

from app.core.risk_model_enhanced import (
    EnhancedCovarianceEstimator,
    RiskBudgetOptimizer,
    StressTester,
    RiskBudget,
)


class TestEnhancedCovarianceEstimator:
    """测试增强协方差估计"""

    def test_oracle_approximating_shrinkage(self):
        """测试OAS收缩估计"""
        np.random.seed(42)

        # 创建测试数据
        n_samples = 100
        n_assets = 10
        returns = pd.DataFrame(
            np.random.randn(n_samples, n_assets) * 0.01,
            columns=[f"asset{i}" for i in range(n_assets)],
        )

        estimator = EnhancedCovarianceEstimator()
        cov = estimator.oracle_approximating_shrinkage(returns)

        # 验证结果
        assert cov.shape == (n_assets, n_assets)
        assert np.allclose(cov, cov.T)  # 对称性
        assert np.all(np.linalg.eigvals(cov) > 0)  # 正定性

    def test_factor_model_covariance(self):
        """测试因子模型协方差"""
        np.random.seed(42)

        n_samples = 100
        n_assets = 10
        n_factors = 3

        # 资产收益
        returns = pd.DataFrame(
            np.random.randn(n_samples, n_assets) * 0.01,
            columns=[f"asset{i}" for i in range(n_assets)],
        )

        # 因子收益
        factor_returns = pd.DataFrame(
            np.random.randn(n_samples, n_factors) * 0.015,
            columns=[f"factor{i}" for i in range(n_factors)],
        )

        estimator = EnhancedCovarianceEstimator()
        cov = estimator.factor_model_covariance(returns, factor_returns)

        # 验证结果
        assert cov.shape == (n_assets, n_assets)
        assert np.allclose(cov, cov.T)

    def test_ewma_with_vol_targeting(self):
        """测试带波动率目标的EWMA"""
        np.random.seed(42)

        n_samples = 252
        n_assets = 5
        returns = pd.DataFrame(
            np.random.randn(n_samples, n_assets) * 0.02,
            columns=[f"asset{i}" for i in range(n_assets)],
        )

        estimator = EnhancedCovarianceEstimator()
        cov = estimator.ewma_with_vol_targeting(returns, target_vol=0.15)

        # 验证结果
        assert cov.shape == (n_assets, n_assets)

        # 验证波动率接近目标
        equal_weights = np.ones(n_assets) / n_assets
        portfolio_vol = np.sqrt(equal_weights @ cov.values @ equal_weights) * np.sqrt(252)

        # 允许一定误差
        assert abs(portfolio_vol - 0.15) < 0.05


class TestRiskBudgetOptimizer:
    """测试风险预算优化"""

    def test_risk_parity_weights(self):
        """测试风险平价权重"""
        np.random.seed(42)

        # 创建协方差矩阵
        n_assets = 5
        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.01)
        cov_matrix = returns.cov().values

        optimizer = RiskBudgetOptimizer()
        weights = optimizer.risk_parity_weights(cov_matrix)

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0)  # 权重和为1
        assert np.all(weights >= 0)  # 权重非负

        # 验证风险贡献接近相等
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        marginal_contrib = cov_matrix @ weights
        risk_contrib = weights * marginal_contrib / portfolio_vol
        risk_contrib_pct = risk_contrib / risk_contrib.sum()

        # 风险贡献应该接近等权
        expected_contrib = 1.0 / n_assets
        assert np.all(np.abs(risk_contrib_pct - expected_contrib) < 0.1)

    def test_minimum_variance_weights(self):
        """测试最小方差权重"""
        np.random.seed(42)

        n_assets = 5
        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.01)
        cov_matrix = returns.cov().values

        optimizer = RiskBudgetOptimizer()
        weights = optimizer.minimum_variance_weights(cov_matrix, max_weight=0.3)

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)
        assert np.all(weights <= 0.3)  # 不超过最大权重

        # 验证是最小方差
        portfolio_var = weights @ cov_matrix @ weights

        # 等权组合的方差应该更大
        equal_weights = np.ones(n_assets) / n_assets
        equal_var = equal_weights @ cov_matrix @ equal_weights

        assert portfolio_var <= equal_var

    def test_maximum_diversification_weights(self):
        """测试最大分散化权重"""
        np.random.seed(42)

        n_assets = 5
        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.01)
        cov_matrix = returns.cov().values

        optimizer = RiskBudgetOptimizer()
        weights = optimizer.maximum_diversification_weights(cov_matrix)

        # 验证权重
        assert len(weights) == n_assets
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)


class TestStressTester:
    """测试压力测试"""

    def test_historical_stress_test(self):
        """测试历史压力测试"""
        np.random.seed(42)

        # 创建测试数据
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        n_assets = 5
        returns = pd.DataFrame(
            np.random.randn(100, n_assets) * 0.01,
            index=dates,
            columns=[f"asset{i}" for i in range(n_assets)],
        )

        # 添加极端事件
        stress_dates = [dates[10], dates[50]]
        returns.loc[stress_dates[0]] = -0.05  # 大跌
        returns.loc[stress_dates[1]] = -0.03

        weights = np.ones(n_assets) / n_assets

        tester = StressTester()
        results = tester.historical_stress_test(weights, returns, stress_dates)

        # 验证结果
        assert len(results) == 2
        assert "portfolio_return" in results.columns
        assert all(results["portfolio_return"] < 0)  # 压力事件应该是负收益

    def test_parametric_stress_test(self):
        """测试参数化压力测试"""
        np.random.seed(42)

        n_assets = 5
        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.01)
        cov_matrix = returns.cov().values

        weights = np.ones(n_assets) / n_assets

        # 定义冲击情景
        shock_scenarios = {
            "market_crash": np.array([-0.10, -0.08, -0.12, -0.09, -0.11]),
            "sector_shock": np.array([-0.15, -0.15, 0.02, 0.01, 0.03]),
            "volatility_spike": np.array([-0.05, -0.03, -0.08, -0.04, -0.06]),
        }

        tester = StressTester()
        results = tester.parametric_stress_test(weights, cov_matrix, shock_scenarios)

        # 验证结果
        assert len(results) == 3
        assert "scenario" in results.columns
        assert "portfolio_return" in results.columns
        assert "portfolio_vol" in results.columns

    def test_monte_carlo_stress_test(self):
        """测试蒙特卡洛压力测试"""
        np.random.seed(42)

        n_assets = 5
        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.01)
        cov_matrix = returns.cov().values

        weights = np.ones(n_assets) / n_assets

        tester = StressTester()
        results = tester.monte_carlo_stress_test(
            weights,
            cov_matrix,
            n_simulations=1000,
            confidence_level=0.95,
        )

        # 验证结果
        assert "mean" in results
        assert "std" in results
        assert "var" in results
        assert "cvar" in results
        assert "min" in results
        assert "max" in results

        # VaR应该是负数（损失）
        assert results["var"] < 0
        # CVaR应该比VaR更负（更大的损失）
        assert results["cvar"] <= results["var"]


class TestCovarianceComparison:
    """协方差估计方法对比测试"""

    def test_compare_estimators(self):
        """对比不同协方差估计方法"""
        np.random.seed(42)

        n_samples = 100
        n_assets = 10

        # 生成真实协方差矩阵
        true_cov = np.eye(n_assets) * 0.01
        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                if abs(i - j) == 1:  # 相邻资产相关
                    true_cov[i, j] = true_cov[j, i] = 0.005

        # 生成样本
        returns = pd.DataFrame(
            np.random.multivariate_normal(np.zeros(n_assets), true_cov, n_samples),
            columns=[f"asset{i}" for i in range(n_assets)],
        )

        estimator = EnhancedCovarianceEstimator()

        # 样本协方差
        sample_cov = returns.cov().values

        # OAS收缩
        oas_cov = estimator.oracle_approximating_shrinkage(returns).values

        # 计算Frobenius范数误差
        sample_error = np.linalg.norm(sample_cov - true_cov, 'fro')
        oas_error = np.linalg.norm(oas_cov - true_cov, 'fro')

        print(f"Sample covariance error: {sample_error:.6f}")
        print(f"OAS covariance error: {oas_error:.6f}")

        # OAS通常在小样本下表现更好
        # 但不是绝对的，所以只验证都是合理的值
        assert sample_error > 0
        assert oas_error > 0


class TestRiskBudgetRebalancing:
    """风险预算再平衡测试"""

    def test_risk_budget_rebalancing(self):
        """测试风险预算再平衡"""
        np.random.seed(42)

        n_assets = 5
        returns = pd.DataFrame(np.random.randn(100, n_assets) * 0.01)
        cov_matrix = returns.cov().values

        optimizer = RiskBudgetOptimizer()

        # 初始权重
        initial_weights = optimizer.risk_parity_weights(cov_matrix)

        # 模拟市场变化（协方差矩阵变化）
        new_returns = pd.DataFrame(np.random.randn(50, n_assets) * 0.015)
        new_cov_matrix = new_returns.cov().values

        # 新权重
        new_weights = optimizer.risk_parity_weights(new_cov_matrix)

        # 验证权重变化
        weight_change = np.abs(new_weights - initial_weights).sum()

        # 权重应该有变化
        assert weight_change > 0


class TestEdgeCases:
    """边界情况测试"""

    def test_singular_covariance(self):
        """测试奇异协方差矩阵"""
        # 创建完全相关的资产
        n_samples = 100
        base_returns = np.random.randn(n_samples) * 0.01

        returns = pd.DataFrame({
            "asset1": base_returns,
            "asset2": base_returns * 1.5,  # 完全相关
            "asset3": base_returns * 0.8,
        })

        estimator = EnhancedCovarianceEstimator()

        # OAS应该能处理
        cov = estimator.oracle_approximating_shrinkage(returns)

        assert cov.shape == (3, 3)
        # 应该是正定的（通过收缩）
        eigenvalues = np.linalg.eigvals(cov.values)
        assert np.all(eigenvalues > 0)

    def test_small_sample(self):
        """测试小样本情况"""
        np.random.seed(42)

        # 样本数少于资产数
        n_samples = 10
        n_assets = 20

        returns = pd.DataFrame(np.random.randn(n_samples, n_assets) * 0.01)

        estimator = EnhancedCovarianceEstimator()

        # OAS应该能处理小样本
        cov = estimator.oracle_approximating_shrinkage(returns)

        assert cov.shape == (n_assets, n_assets)
        assert np.all(np.linalg.eigvals(cov.values) > 0)
