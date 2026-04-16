"""
组合优化器
基于风险模型的均值方差优化、风险平价优化、最小方差组合
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy.optimize import minimize
from app.core.logging import logger


class PortfolioOptimizer:
    """组合优化器"""

    def __init__(self):
        pass

    # ==================== 均值方差优化 ====================

    def mean_variance_optimize(self, expected_returns: pd.Series,
                                cov_matrix: pd.DataFrame,
                                risk_aversion: float = 1.0,
                                max_position: float = 0.10,
                                min_position: float = 0.0,
                                industry_data: pd.Series = None,
                                max_industry_weight: float = 0.30,
                                long_only: bool = True) -> pd.Series:
        """
        均值方差优化

        max: w'μ - λ/2 * w'Σw
        s.t.: w'1 = 1, w >= 0

        Args:
            expected_returns: 期望收益, index=ts_code
            cov_matrix: 协方差矩阵
            risk_aversion: 风险厌恶系数 λ
            max_position: 单只股票最大权重
            min_position: 单只股票最小权重
            industry_data: 行业数据
            max_industry_weight: 单个行业最大权重
            long_only: 是否仅做多

        Returns:
            最优权重 Series
        """
        # 对齐数据
        common = expected_returns.index.intersection(cov_matrix.index)
        n = len(common)

        if n < 2:
            logger.warning("Too few assets for optimization")
            return pd.Series(1.0 / n, index=common) if n > 0 else pd.Series()

        mu = expected_returns.reindex(common).values
        Sigma = cov_matrix.loc[common, common].values

        # 目标函数: min -w'μ + λ/2 * w'Σw
        def objective(w):
            return -w @ mu + risk_aversion / 2 * w @ Sigma @ w

        def gradient(w):
            return -mu + risk_aversion * Sigma @ w

        # 约束
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]

        # 权重边界
        if long_only:
            bounds = [(min_position, max_position) for _ in range(n)]
        else:
            bounds = [(-max_position, max_position) for _ in range(n)]

        # 行业约束
        if industry_data is not None:
            ind = industry_data.reindex(common)
            for industry in ind.unique():
                if pd.isna(industry):
                    continue
                idx = np.where(ind.values == industry)[0]
                if len(idx) > 0:
                    constraints.append({
                        'type': 'ineq',
                        'fun': lambda w, idx=idx: max_industry_weight - np.sum(w[idx])
                    })

        # 初始值: 等权
        w0 = np.ones(n) / n

        # 优化
        result = minimize(
            objective, w0,
            method='SLSQP',
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 500, 'ftol': 1e-10}
        )

        if not result.success:
            logger.warning(f"Optimization did not converge: {result.message}")
            # 回退到等权
            weights = pd.Series(1.0 / n, index=common)
        else:
            weights = pd.Series(result.x, index=common)
            # 清理微小权重
            weights[weights < 1e-4] = 0
            if weights.sum() > 0:
                weights = weights / weights.sum()

        return weights

    # ==================== 风险平价优化 ====================

    def risk_parity_optimize(self, cov_matrix: pd.DataFrame,
                             max_position: float = 0.10,
                             target_risk: Optional[pd.Series] = None) -> pd.Series:
        """
        风险平价优化

        每个资产的风险贡献相等: w_i * (Σw)_i / (w'Σw) = 1/N

        Args:
            cov_matrix: 协方差矩阵
            max_position: 单只股票最大权重
            target_risk: 目标风险比例, 默认等风险贡献

        Returns:
            最优权重 Series
        """
        stocks = cov_matrix.index
        n = len(stocks)
        Sigma = cov_matrix.values

        if target_risk is None:
            target_risk = np.ones(n) / n
        else:
            target_risk = target_risk.reindex(stocks).values
            target_risk = target_risk / target_risk.sum()

        # 目标函数: 最小化风险贡献与目标的偏差
        def objective(w):
            port_var = w @ Sigma @ w
            if port_var <= 0:
                return 1e10
            mrc = Sigma @ w  # 边际风险贡献
            rc = w * mrc     # 风险贡献
            rc_pct = rc / port_var  # 风险贡献占比
            return np.sum((rc_pct - target_risk) ** 2)

        # 约束
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
        bounds = [(0, max_position) for _ in range(n)]

        # 初始值: 按波动率倒数加权
        vols = np.sqrt(np.diag(Sigma))
        inv_vol = 1.0 / vols
        w0 = inv_vol / inv_vol.sum()

        result = minimize(
            objective, w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 500, 'ftol': 1e-12}
        )

        if not result.success:
            logger.warning(f"Risk parity optimization did not converge: {result.message}")
            weights = pd.Series(w0, index=stocks)
        else:
            weights = pd.Series(result.x, index=stocks)
            weights[weights < 1e-4] = 0
            if weights.sum() > 0:
                weights = weights / weights.sum()

        return weights

    # ==================== 最小方差组合 ====================

    def min_variance_optimize(self, cov_matrix: pd.DataFrame,
                              max_position: float = 0.10,
                              industry_data: pd.Series = None,
                              max_industry_weight: float = 0.30) -> pd.Series:
        """
        最小方差组合

        min: w'Σw
        s.t.: w'1 = 1, w >= 0

        Args:
            cov_matrix: 协方差矩阵
            max_position: 单只股票最大权重
            industry_data: 行业数据
            max_industry_weight: 单个行业最大权重

        Returns:
            最优权重 Series
        """
        stocks = cov_matrix.index
        n = len(stocks)
        Sigma = cov_matrix.values

        def objective(w):
            return w @ Sigma @ w

        def gradient(w):
            return 2 * Sigma @ w

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
        bounds = [(0, max_position) for _ in range(n)]

        # 行业约束
        if industry_data is not None:
            ind = industry_data.reindex(stocks)
            for industry in ind.unique():
                if pd.isna(industry):
                    continue
                idx = np.where(ind.values == industry)[0]
                if len(idx) > 0:
                    constraints.append({
                        'type': 'ineq',
                        'fun': lambda w, idx=idx: max_industry_weight - np.sum(w[idx])
                    })

        w0 = np.ones(n) / n

        result = minimize(
            objective, w0,
            method='SLSQP',
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 500, 'ftol': 1e-10}
        )

        if not result.success:
            logger.warning(f"Min variance optimization did not converge: {result.message}")
            weights = pd.Series(1.0 / n, index=stocks)
        else:
            weights = pd.Series(result.x, index=stocks)
            weights[weights < 1e-4] = 0
            if weights.sum() > 0:
                weights = weights / weights.sum()

        return weights

    # ==================== 最大去相关组合 ====================

    def max_decorrelation_optimize(self, cov_matrix: pd.DataFrame,
                                   max_position: float = 0.10) -> pd.Series:
        """
        最大去相关组合

        最小化组合内资产间的平均相关系数

        Args:
            cov_matrix: 协方差矩阵
            max_position: 单只股票最大权重

        Returns:
            最优权重 Series
        """
        stocks = cov_matrix.index
        n = len(stocks)
        Sigma = cov_matrix.values

        # 构建去相关矩阵: C = D^{-1/2} * Σ * D^{-1/2}
        vols = np.sqrt(np.diag(Sigma))
        D_inv_half = np.diag(1.0 / vols)
        C = D_inv_half @ Sigma @ D_inv_half

        def objective(w):
            return w @ C @ w

        def gradient(w):
            return 2 * C @ w

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
        bounds = [(0, max_position) for _ in range(n)]

        w0 = np.ones(n) / n

        result = minimize(
            objective, w0,
            method='SLSQP',
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 500, 'ftol': 1e-10}
        )

        if not result.success:
            logger.warning(f"Max decorrelation optimization did not converge: {result.message}")
            weights = pd.Series(1.0 / n, index=stocks)
        else:
            weights = pd.Series(result.x, index=stocks)
            weights[weights < 1e-4] = 0
            if weights.sum() > 0:
                weights = weights / weights.sum()

        return weights

    # ==================== 优化结果分析 ====================

    def analyze_optimization(self, weights: pd.Series,
                              expected_returns: pd.Series,
                              cov_matrix: pd.DataFrame,
                              risk_free_rate: float = 0.03) -> Dict:
        """
        分析优化结果

        Args:
            weights: 优化后的权重
            expected_returns: 期望收益
            cov_matrix: 协方差矩阵
            risk_free_rate: 无风险利率

        Returns:
            优化结果分析
        """
        common = weights.index.intersection(expected_returns.index).intersection(cov_matrix.index)
        w = weights.reindex(common).fillna(0).values
        mu = expected_returns.reindex(common).values
        Sigma = cov_matrix.loc[common, common].values

        # 组合期望收益 (输入已经是年化收益)
        annual_return = w @ mu

        # 组合风险
        port_var = w @ Sigma @ w
        port_vol = np.sqrt(port_var)

        # 年化波动率 (输入协方差是日频)
        annual_vol = port_vol * np.sqrt(252)

        # 夏普比率
        sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0

        # 风险贡献
        mrc = Sigma @ w
        rc = w * mrc
        rc_pct = rc / port_var if port_var > 0 else rc

        # 有效持仓数
        effective_n = 1 / np.sum(w ** 2)

        return {
            'expected_return': annual_return,
            'volatility': annual_vol,
            'sharpe_ratio': sharpe,
            'effective_positions': effective_n,
            'max_weight': weights.max(),
            'min_weight': weights[weights > 0].min() if (weights > 0).any() else 0,
            'non_zero_positions': (weights > 1e-4).sum(),
            'risk_contributions': pd.Series(rc_pct, index=common),
        }
