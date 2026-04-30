"""
风险模型增强模块
提供高级协方差估计、风险预算、压力测试等功能
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy import optimize, stats

from app.core.logging import logger

if TYPE_CHECKING:
    from datetime import date


@dataclass
class RiskBudget:
    """风险预算配置"""

    target_volatility: float = 0.15  # 目标波动率
    max_component_risk: float = 0.05  # 单个成分最大风险贡献
    rebalance_threshold: float = 0.02  # 再平衡阈值


class EnhancedCovarianceEstimator:
    """
    增强协方差估计器

    提供多种高级协方差估计方法
    """

    def __init__(self):
        pass

    # ==================== 1. 收缩估计器 ====================

    def oracle_approximating_shrinkage(self, returns: pd.DataFrame) -> pd.DataFrame:
        """
        Oracle近似收缩估计器（OAS）

        相比Ledoit-Wolf，OAS在小样本下表现更好

        Args:
            returns: 收益率矩阵 (T x N)

        Returns:
            收缩后的协方差矩阵
        """
        X = returns.values
        T, N = X.shape

        # 样本协方差
        S = np.cov(X, rowvar=False, ddof=1)

        # 计算收缩强度
        trace_S = np.trace(S)
        trace_S2 = np.trace(S @ S)

        # OAS收缩系数
        rho = min(
            ((1 - 2 / N) * trace_S2 + trace_S**2) / ((T + 1 - 2 / N) * (trace_S2 - trace_S**2 / N)),
            1.0,
        )

        # 收缩目标：对角矩阵
        F = (trace_S / N) * np.eye(N)

        # 收缩估计
        shrunk = (1 - rho) * S + rho * F

        return pd.DataFrame(shrunk, index=returns.columns, columns=returns.columns)

    def graphical_lasso(
        self,
        returns: pd.DataFrame,
        alpha: float = 0.01,
        max_iter: int = 100,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        图形化Lasso（稀疏逆协方差估计）

        适用于高维数据，估计稀疏的精度矩阵（逆协方差）

        Args:
            returns: 收益率矩阵
            alpha: 正则化参数（越大越稀疏）
            max_iter: 最大迭代次数

        Returns:
            (协方差矩阵, 精度矩阵)
        """
        try:
            from sklearn.covariance import GraphicalLassoCV

            # 使用交叉验证自动选择alpha
            model = GraphicalLassoCV(alphas=10, max_iter=max_iter, cv=5)
            model.fit(returns.values)

            cov = pd.DataFrame(model.covariance_, index=returns.columns, columns=returns.columns)

            precision = pd.DataFrame(model.precision_, index=returns.columns, columns=returns.columns)

            logger.info(f"Graphical Lasso: selected alpha={model.alpha_:.4f}")

            return cov, precision

        except ImportError:
            logger.warning("sklearn not available, falling back to sample covariance")
            cov = returns.cov()
            precision = pd.DataFrame(
                np.linalg.pinv(cov.values),
                index=returns.columns,
                columns=returns.columns,
            )
            return cov, precision

    def minimum_covariance_determinant(
        self,
        returns: pd.DataFrame,
        support_fraction: float = 0.8,
    ) -> pd.DataFrame:
        """
        最小协方差行列式（MCD）

        鲁棒协方差估计，对异常值不敏感

        Args:
            returns: 收益率矩阵
            support_fraction: 支持集比例

        Returns:
            鲁棒协方差矩阵
        """
        try:
            from sklearn.covariance import MinCovDet

            mcd = MinCovDet(support_fraction=support_fraction, random_state=42)
            mcd.fit(returns.values)

            cov = pd.DataFrame(mcd.covariance_, index=returns.columns, columns=returns.columns)

            logger.info(f"MCD: support fraction={support_fraction}")

            return cov

        except ImportError:
            logger.warning("sklearn not available, falling back to sample covariance")
            return returns.cov()

    # ==================== 2. 因子模型协方差 ====================

    def factor_model_covariance(
        self,
        returns: pd.DataFrame,
        factor_returns: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        因子模型协方差估计

        Σ = B * F * B' + D

        其中：
        - B: 因子载荷矩阵
        - F: 因子协方差矩阵
        - D: 特质风险对角矩阵

        Args:
            returns: 资产收益率矩阵 (T x N)
            factor_returns: 因子收益率矩阵 (T x K)

        Returns:
            协方差矩阵
        """
        # 估计因子载荷（回归）
        betas = []
        residuals = []

        for col in returns.columns:
            y = returns[col].values
            X = factor_returns.values

            # 添加截距
            X_with_const = np.column_stack([np.ones(len(X)), X])

            # OLS回归
            beta = np.linalg.lstsq(X_with_const, y, rcond=None)[0]
            betas.append(beta[1:])  # 去掉截距

            # 残差
            y_pred = X_with_const @ beta
            residuals.append(y - y_pred)

        # 因子载荷矩阵 (N x K)
        B = np.array(betas)

        # 因子协方差矩阵 (K x K)
        F = factor_returns.cov().values

        # 特质风险（残差方差）
        D = np.diag([np.var(r) for r in residuals])

        # 协方差矩阵
        cov = B @ F @ B.T + D

        return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)

    # ==================== 3. 动态协方差模型 ====================

    def ewma_with_vol_targeting(
        self,
        returns: pd.DataFrame,
        target_vol: float = 0.15,
        halflife: int = 60,
    ) -> pd.DataFrame:
        """
        带波动率目标的EWMA协方差

        动态调整协方差矩阵，使组合波动率接近目标

        Args:
            returns: 收益率矩阵
            target_vol: 目标波动率（年化）
            halflife: EWMA半衰期

        Returns:
            调整后的协方差矩阵
        """
        # EWMA协方差
        ewm_cov = returns.ewm(halflife=halflife).cov()

        # 取最后一个时间截面
        if isinstance(ewm_cov.index, pd.MultiIndex):
            last_date = ewm_cov.index.get_level_values(0)[-1]
            cov = ewm_cov.loc[last_date]
        else:
            cov = ewm_cov

        # 当前波动率
        equal_weights = np.ones(len(returns.columns)) / len(returns.columns)
        current_vol = np.sqrt(equal_weights @ cov.values @ equal_weights) * np.sqrt(252)

        # 波动率调整因子
        vol_adjustment = (target_vol / current_vol) ** 2 if current_vol > 0 else 1.0

        # 调整协方差矩阵
        adjusted_cov = cov * vol_adjustment

        logger.info(f"Vol targeting: current={current_vol:.2%}, target={target_vol:.2%}, adjustment={vol_adjustment:.2f}")

        return adjusted_cov


class RiskBudgetOptimizer:
    """
    风险预算优化器

    实现风险平价、风险预算等组合优化方法
    """

    def __init__(self, risk_budget: RiskBudget | None = None):
        self.risk_budget = risk_budget or RiskBudget()

    def risk_parity_weights(
        self,
        cov_matrix: np.ndarray,
        risk_budgets: np.ndarray | None = None,
    ) -> np.ndarray:
        """
        风险平价权重

        使每个资产的风险贡献相等（或按指定比例）

        Args:
            cov_matrix: 协方差矩阵 (N x N)
            risk_budgets: 风险预算 (N,)，默认为等权

        Returns:
            权重向量 (N,)
        """
        N = cov_matrix.shape[0]

        if risk_budgets is None:
            risk_budgets = np.ones(N) / N

        # 目标函数：最小化风险贡献与目标的偏差
        def objective(w):
            portfolio_vol = np.sqrt(w @ cov_matrix @ w)
            marginal_contrib = cov_matrix @ w
            risk_contrib = w * marginal_contrib / portfolio_vol if portfolio_vol > 0 else np.zeros(N)

            # 归一化风险贡献
            risk_contrib_pct = risk_contrib / risk_contrib.sum() if risk_contrib.sum() > 0 else np.ones(N) / N

            # 偏差平方和
            return np.sum((risk_contrib_pct - risk_budgets) ** 2)

        # 约束：权重和为1，权重非负
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        bounds = [(0, 1) for _ in range(N)]

        # 初始权重：等权
        w0 = np.ones(N) / N

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
            weights = result.x
            logger.info(f"Risk parity optimization converged: {result.message}")
        else:
            logger.warning(f"Risk parity optimization failed: {result.message}, using equal weights")
            weights = w0

        return weights

    def minimum_variance_weights(
        self,
        cov_matrix: np.ndarray,
        max_weight: float = 0.3,
    ) -> np.ndarray:
        """
        最小方差权重

        Args:
            cov_matrix: 协方差矩阵
            max_weight: 单个资产最大权重

        Returns:
            权重向量
        """
        N = cov_matrix.shape[0]

        # 目标函数：最小化组合方差
        def objective(w):
            return w @ cov_matrix @ w

        # 约束
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        bounds = [(0, max_weight) for _ in range(N)]

        # 初始权重
        w0 = np.ones(N) / N

        # 优化
        result = optimize.minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else w0

    def maximum_diversification_weights(
        self,
        cov_matrix: np.ndarray,
        expected_returns: np.ndarray | None = None,
    ) -> np.ndarray:
        """
        最大分散化权重

        最大化分散化比率：DR = (w' σ) / sqrt(w' Σ w)

        Args:
            cov_matrix: 协方差矩阵
            expected_returns: 预期收益（可选）

        Returns:
            权重向量
        """
        N = cov_matrix.shape[0]

        # 资产波动率
        volatilities = np.sqrt(np.diag(cov_matrix))

        # 目标函数：最大化分散化比率 = 最小化负分散化比率
        def objective(w):
            portfolio_vol = np.sqrt(w @ cov_matrix @ w)
            weighted_vol = w @ volatilities
            return -weighted_vol / portfolio_vol if portfolio_vol > 0 else 0

        # 约束
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        bounds = [(0, 1) for _ in range(N)]

        w0 = np.ones(N) / N

        result = optimize.minimize(
            objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        return result.x if result.success else w0


class StressTester:
    """
    压力测试器

    模拟极端市场情景下的组合表现
    """

    def __init__(self):
        pass

    def historical_stress_test(
        self,
        weights: np.ndarray,
        returns: pd.DataFrame,
        stress_dates: list[date],
    ) -> pd.DataFrame:
        """
        历史压力测试

        使用历史极端事件测试组合

        Args:
            weights: 组合权重
            returns: 收益率矩阵
            stress_dates: 压力事件日期列表

        Returns:
            压力测试结果DataFrame
        """
        results = []

        for stress_date in stress_dates:
            if stress_date in returns.index:
                stress_returns = returns.loc[stress_date]
                portfolio_return = weights @ stress_returns.values

                results.append(
                    {
                        "date": stress_date,
                        "portfolio_return": portfolio_return,
                        "scenario": "historical",
                    }
                )

        return pd.DataFrame(results)

    def parametric_stress_test(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        shock_scenarios: dict[str, np.ndarray],
    ) -> pd.DataFrame:
        """
        参数化压力测试

        基于假设的冲击情景测试组合

        Args:
            weights: 组合权重
            cov_matrix: 协方差矩阵
            shock_scenarios: 冲击情景字典 {scenario_name: shock_vector}

        Returns:
            压力测试结果DataFrame
        """
        results = []

        for scenario_name, shock in shock_scenarios.items():
            # 组合收益 = 权重 @ 冲击
            portfolio_return = weights @ shock

            # 组合波动率
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)

            results.append(
                {
                    "scenario": scenario_name,
                    "portfolio_return": portfolio_return,
                    "portfolio_vol": portfolio_vol,
                    "sharpe_ratio": portfolio_return / portfolio_vol if portfolio_vol > 0 else 0,
                }
            )

        return pd.DataFrame(results)

    def monte_carlo_stress_test(
        self,
        weights: np.ndarray,
        cov_matrix: np.ndarray,
        n_simulations: int = 10000,
        confidence_level: float = 0.99,
    ) -> dict:
        """
        蒙特卡洛压力测试

        模拟大量随机情景

        Args:
            weights: 组合权重
            cov_matrix: 协方差矩阵
            n_simulations: 模拟次数
            confidence_level: 置信水平

        Returns:
            压力测试结果字典
        """
        # 生成随机收益
        mean = np.zeros(len(weights))
        simulated_returns = np.random.multivariate_normal(mean, cov_matrix, n_simulations)

        # 组合收益
        portfolio_returns = simulated_returns @ weights

        # 统计
        var = np.percentile(portfolio_returns, (1 - confidence_level) * 100)
        cvar = portfolio_returns[portfolio_returns <= var].mean()

        return {
            "mean": portfolio_returns.mean(),
            "std": portfolio_returns.std(),
            "var": var,
            "cvar": cvar,
            "min": portfolio_returns.min(),
            "max": portfolio_returns.max(),
            "confidence_level": confidence_level,
        }


# ==================== 辅助函数 ====================


def rolling_covariance_forecast(
    returns: pd.DataFrame,
    window: int = 60,
    method: str = "ewma",
) -> pd.DataFrame:
    """
    滚动协方差预测

    Args:
        returns: 收益率矩阵
        window: 滚动窗口
        method: 估计方法 ('sample', 'ewma', 'ledoit_wolf')

    Returns:
        协方差预测序列
    """
    forecasts = []

    for i in range(window, len(returns)):
        window_returns = returns.iloc[i - window : i]

        if method == "sample":
            cov = window_returns.cov()
        elif method == "ewma":
            cov = window_returns.ewm(halflife=window // 2).cov().iloc[-len(window_returns.columns) :]
        else:
            cov = window_returns.cov()

        forecasts.append(cov)

    return forecasts
