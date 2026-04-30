"""
高级组合优化算法模块
提供最新的组合优化方法和算法
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy import optimize

from app.core.logging import logger

if TYPE_CHECKING:
    pass


@dataclass
class OptimizationConstraints:
    """优化约束配置"""

    max_position: float = 0.10  # 单个资产最大权重
    min_position: float = 0.0  # 单个资产最小权重
    max_turnover: float = 0.5  # 最大换手率
    max_sector_weight: float = 0.30  # 单个行业最大权重
    target_num_holdings: int | None = None  # 目标持仓数量


class AdvancedPortfolioOptimizer:
    """
    高级组合优化器

    实现最新的组合优化算法
    """

    def __init__(self, constraints: OptimizationConstraints | None = None):
        self.constraints = constraints or OptimizationConstraints()

    # ==================== 1. 条件风险价值优化（CVaR） ====================

    def cvar_optimize(
        self,
        returns_scenarios: np.ndarray,
        confidence_level: float = 0.95,
        max_weight: float = 0.3,
    ) -> np.ndarray:
        """
        CVaR优化（条件风险价值）

        最小化尾部风险

        Args:
            returns_scenarios: 收益情景矩阵 (n_scenarios x n_assets)
            confidence_level: 置信水平
            max_weight: 单个资产最大权重

        Returns:
            最优权重
        """
        n_scenarios, n_assets = returns_scenarios.shape

        # CVaR优化的线性规划形式
        # 变量：[w1, ..., wn, VaR, u1, ..., um]
        # 其中 ui = max(0, -r_i'w - VaR)

        from scipy.optimize import linprog

        # 目标函数：min VaR + 1/(1-α)*m * sum(ui)
        alpha = 1 - confidence_level
        c = np.zeros(n_assets + 1 + n_scenarios)
        c[n_assets] = 1  # VaR系数
        c[n_assets + 1 :] = 1 / (alpha * n_scenarios)  # ui系数

        # 不等式约束：ui >= -r_i'w - VaR
        # 即：r_i'w + VaR + ui >= 0
        A_ub = np.zeros((n_scenarios, n_assets + 1 + n_scenarios))
        A_ub[:, :n_assets] = returns_scenarios
        A_ub[:, n_assets] = 1
        A_ub[:, n_assets + 1 :] = np.eye(n_scenarios)
        b_ub = np.zeros(n_scenarios)

        # 等式约束：sum(w) = 1
        A_eq = np.zeros((1, n_assets + 1 + n_scenarios))
        A_eq[0, :n_assets] = 1
        b_eq = np.array([1.0])

        # 边界：0 <= w <= max_weight, VaR无界，ui >= 0
        bounds = [(0, max_weight) for _ in range(n_assets)]
        bounds.append((None, None))  # VaR
        bounds.extend([(0, None) for _ in range(n_scenarios)])  # ui

        # 求解
        result = linprog(c, A_ub=-A_ub, b_ub=-b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

        if result.success:
            weights = result.x[:n_assets]
            logger.info(f"CVaR optimization converged, CVaR={result.fun:.4f}")
            return weights
        else:
            logger.warning(f"CVaR optimization failed: {result.message}")
            return np.ones(n_assets) / n_assets

    # ==================== 2. 最大夏普比率优化 ====================

    def max_sharpe_optimize(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        risk_free_rate: float = 0.03,
        max_weight: float = 0.3,
    ) -> np.ndarray:
        """
        最大夏普比率优化

        Args:
            expected_returns: 期望收益向量
            cov_matrix: 协方差矩阵
            risk_free_rate: 无风险利率
            max_weight: 单个资产最大权重

        Returns:
            最优权重
        """
        n_assets = len(expected_returns)

        # 目标函数：最大化夏普比率 = 最小化 -SR
        def objective(w):
            portfolio_return = w @ expected_returns
            portfolio_vol = np.sqrt(w @ cov_matrix @ w)
            sharpe = (portfolio_return - risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0
            return -sharpe

        # 约束
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        bounds = [(0, max_weight) for _ in range(n_assets)]

        # 初始权重
        w0 = np.ones(n_assets) / n_assets

        # 优化
        result = optimize.minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        if result.success:
            logger.info(f"Max Sharpe optimization converged, Sharpe={-result.fun:.4f}")
            return result.x
        else:
            logger.warning(f"Max Sharpe optimization failed: {result.message}")
            return w0

    # ==================== 3. 等权重风险贡献（ERC） ====================

    def equal_risk_contribution(
        self,
        cov_matrix: np.ndarray,
        max_weight: float = 0.3,
    ) -> np.ndarray:
        """
        等权重风险贡献（ERC）

        使每个资产的风险贡献相等

        Args:
            cov_matrix: 协方差矩阵
            max_weight: 单个资产最大权重

        Returns:
            最优权重
        """
        n_assets = cov_matrix.shape[0]

        # 目标函数：最小化风险贡献的方差
        def objective(w):
            portfolio_vol = np.sqrt(w @ cov_matrix @ w)
            marginal_contrib = cov_matrix @ w
            risk_contrib = w * marginal_contrib / portfolio_vol if portfolio_vol > 0 else np.zeros(n_assets)

            # 风险贡献的方差
            target_contrib = portfolio_vol / n_assets
            return np.sum((risk_contrib - target_contrib) ** 2)

        # 约束
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        bounds = [(0, max_weight) for _ in range(n_assets)]

        w0 = np.ones(n_assets) / n_assets

        result = optimize.minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else w0

    # ==================== 4. 最大去相关优化 ====================

    def max_decorrelation_optimize(
        self,
        corr_matrix: np.ndarray,
        max_weight: float = 0.3,
    ) -> np.ndarray:
        """
        最大去相关优化

        最小化组合内部相关性

        Args:
            corr_matrix: 相关系数矩阵
            max_weight: 单个资产最大权重

        Returns:
            最优权重
        """
        n_assets = corr_matrix.shape[0]

        # 目标函数：最小化加权平均相关性
        def objective(w):
            # 组合的平均相关性
            weighted_corr = 0
            for i in range(n_assets):
                for j in range(n_assets):
                    if i != j:
                        weighted_corr += w[i] * w[j] * corr_matrix[i, j]
            return weighted_corr

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        bounds = [(0, max_weight) for _ in range(n_assets)]

        w0 = np.ones(n_assets) / n_assets

        result = optimize.minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else w0

    # ==================== 5. 稳健优化（Robust Optimization） ====================

    def robust_optimize(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        uncertainty_set: float = 0.05,
        risk_aversion: float = 1.0,
        max_weight: float = 0.3,
    ) -> np.ndarray:
        """
        稳健优化

        考虑参数不确定性的优化

        Args:
            expected_returns: 期望收益向量
            cov_matrix: 协方差矩阵
            uncertainty_set: 不确定性集合大小
            risk_aversion: 风险厌恶系数
            max_weight: 单个资产最大权重

        Returns:
            最优权重
        """
        n_assets = len(expected_returns)

        # 稳健优化：最坏情况下的最优化
        # min_w max_δ [w'(μ-δ) - λ/2 * w'Σw]
        # 其中 ||δ|| <= ε

        # 简化为：min_w [w'μ - ε||w|| - λ/2 * w'Σw]
        def objective(w):
            portfolio_return = w @ expected_returns
            uncertainty_penalty = uncertainty_set * np.linalg.norm(w, 1)  # L1范数
            portfolio_risk = risk_aversion / 2 * w @ cov_matrix @ w
            return -portfolio_return + uncertainty_penalty + portfolio_risk

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        bounds = [(0, max_weight) for _ in range(n_assets)]

        w0 = np.ones(n_assets) / n_assets

        result = optimize.minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else w0

    # ==================== 6. 分层聚类组合（Hierarchical Clustering） ====================

    def hierarchical_clustering_portfolio(
        self,
        returns: pd.DataFrame,
        n_clusters: int = 5,
    ) -> pd.Series:
        """
        分层聚类组合

        将资产聚类，然后在类内和类间分配权重

        Args:
            returns: 收益率矩阵
            n_clusters: 聚类数量

        Returns:
            权重Series
        """
        try:
            from sklearn.cluster import AgglomerativeClustering

            # 计算相关系数矩阵
            corr_matrix = returns.corr()

            # 距离矩阵 = 1 - |相关系数|
            distance_matrix = 1 - np.abs(corr_matrix.values)

            # 层次聚类
            clustering = AgglomerativeClustering(
                n_clusters=n_clusters,
                metric="precomputed",
                linkage="average",
            )

            labels = clustering.fit_predict(distance_matrix)

            # 计算每个聚类的权重（等权）
            cluster_weights = {}
            for cluster_id in range(n_clusters):
                cluster_assets = returns.columns[labels == cluster_id]
                n_assets_in_cluster = len(cluster_assets)

                # 聚类权重 = 1/n_clusters
                # 聚类内资产权重 = cluster_weight / n_assets_in_cluster
                for asset in cluster_assets:
                    cluster_weights[asset] = 1.0 / (n_clusters * n_assets_in_cluster)

            weights = pd.Series(cluster_weights)
            weights = weights / weights.sum()  # 归一化

            logger.info(f"Hierarchical clustering: {n_clusters} clusters")

            return weights

        except ImportError:
            logger.warning("sklearn not available, using equal weights")
            return pd.Series(1.0 / len(returns.columns), index=returns.columns)

    # ==================== 7. 最小跟踪误差优化 ====================

    def min_tracking_error_optimize(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        benchmark_weights: np.ndarray,
        max_tracking_error: float = 0.05,
        max_weight: float = 0.3,
    ) -> np.ndarray:
        """
        最小跟踪误差优化

        在跟踪误差约束下最大化超额收益

        Args:
            expected_returns: 期望收益向量
            cov_matrix: 协方差矩阵
            benchmark_weights: 基准权重
            max_tracking_error: 最大跟踪误差
            max_weight: 单个资产最大权重

        Returns:
            最优权重
        """
        n_assets = len(expected_returns)

        # 目标函数：最大化超额收益
        def objective(w):
            excess_return = (w - benchmark_weights) @ expected_returns
            return -excess_return

        # 约束：跟踪误差 <= max_tracking_error
        def tracking_error_constraint(w):
            active_weights = w - benchmark_weights
            te = np.sqrt(active_weights @ cov_matrix @ active_weights)
            return max_tracking_error - te

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "ineq", "fun": tracking_error_constraint},
        ]

        bounds = [(0, max_weight) for _ in range(n_assets)]

        w0 = benchmark_weights.copy()

        result = optimize.minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else benchmark_weights

    # ==================== 8. 最大信息比率优化 ====================

    def max_information_ratio_optimize(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        benchmark_weights: np.ndarray,
        max_weight: float = 0.3,
    ) -> np.ndarray:
        """
        最大信息比率优化

        最大化 IR = E[超额收益] / 跟踪误差

        Args:
            expected_returns: 期望收益向量
            cov_matrix: 协方差矩阵
            benchmark_weights: 基准权重
            max_weight: 单个资产最大权重

        Returns:
            最优权重
        """
        n_assets = len(expected_returns)

        # 目标函数：最大化信息比率
        def objective(w):
            active_weights = w - benchmark_weights
            excess_return = active_weights @ expected_returns
            tracking_error = np.sqrt(active_weights @ cov_matrix @ active_weights)
            ir = excess_return / tracking_error if tracking_error > 0 else 0
            return -ir

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        bounds = [(0, max_weight) for _ in range(n_assets)]

        w0 = benchmark_weights.copy()

        result = optimize.minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else benchmark_weights


# ==================== 辅助函数 ====================


def compare_optimization_methods(
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    methods: list[str] = None,
) -> pd.DataFrame:
    """
    对比不同优化方法

    Args:
        expected_returns: 期望收益向量
        cov_matrix: 协方差矩阵
        methods: 要对比的方法列表

    Returns:
        对比结果DataFrame
    """
    if methods is None:
        methods = ["equal_weight", "min_variance", "max_sharpe", "risk_parity"]

    optimizer = AdvancedPortfolioOptimizer()
    results = []

    n_assets = len(expected_returns)

    for method in methods:
        if method == "equal_weight":
            weights = np.ones(n_assets) / n_assets
        elif method == "min_variance":
            # 最小方差
            def obj(w):
                return w @ cov_matrix @ w

            constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
            bounds = [(0, 1) for _ in range(n_assets)]
            result = optimize.minimize(obj, np.ones(n_assets) / n_assets, method="SLSQP", bounds=bounds, constraints=constraints)
            weights = result.x if result.success else np.ones(n_assets) / n_assets
        elif method == "max_sharpe":
            weights = optimizer.max_sharpe_optimize(expected_returns, cov_matrix)
        elif method == "risk_parity":
            weights = optimizer.equal_risk_contribution(cov_matrix)
        else:
            continue

        # 计算指标
        portfolio_return = weights @ expected_returns
        portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
        sharpe = portfolio_return / portfolio_vol if portfolio_vol > 0 else 0

        results.append(
            {
                "method": method,
                "return": portfolio_return,
                "volatility": portfolio_vol,
                "sharpe_ratio": sharpe,
                "max_weight": weights.max(),
                "min_weight": weights.min(),
                "n_holdings": (weights > 0.01).sum(),
            }
        )

    return pd.DataFrame(results)
