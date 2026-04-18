"""
风险模型模块
实现ADD 10节: Barra风格因子风险模型、协方差估计、风险分解、VaR/CVaR
机构级增强: DCC-GARCH时变协方差、PCA混合风险模型、Mean-CVaR组合优化、Copula尾部模型
"""
from typing import List, Optional, Dict, Tuple
import numpy as np
import pandas as pd
from scipy import linalg, stats as sp_stats
from app.core.logging import logger


class RiskModel:
    """风险模型 - 符合ADD 10节"""

    # Barra风格因子定义 (ADD 10.1节)
    BARRA_FACTORS = [
        'beta', 'book_to_price', 'earnings_yield', 'growth',
        'leverage', 'liquidity', 'momentum', 'non_linear_size',
        'residual_volatility', 'size',
    ]

    def __init__(self):
        pass

    # ==================== 1. 协方差矩阵估计 (ADD 10.2节) ====================

    def sample_covariance(self, returns: pd.DataFrame) -> pd.DataFrame:
        """
        样本协方差矩阵
        Σ = (1/T) * R'R
        """
        return returns.cov()

    def ledoit_wolf_shrinkage(self, returns: pd.DataFrame,
                              shrinkage_target: str = 'identity') -> pd.DataFrame:
        """
        Ledoit-Wolf压缩估计 (ADD 10.2.1节)
        Σ_shrunk = α * F + (1-α) * S

        Args:
            returns: 收益率矩阵
            shrinkage_target: 压缩目标 ('identity', 'diagonal', 'single_factor')
        """
        S = returns.cov().values  # 样本协方差
        n = S.shape[0]
        T = len(returns)

        if shrinkage_target == 'identity':
            # 目标: 缩放后的单位矩阵
            F = np.trace(S) / n * np.eye(n)
        elif shrinkage_target == 'diagonal':
            # 目标: 对角矩阵
            F = np.diag(np.diag(S))
        elif shrinkage_target == 'single_factor':
            # 目标: 单因子模型
            market_returns = returns.mean(axis=1)
            betas = returns.covwith(market_returns) / market_returns.var() if hasattr(returns, 'covwith') else np.ones(n)
            var_market = market_returns.var()
            F = np.outer(betas, betas) * var_market + np.diag(np.diag(S) - betas**2 * var_market)
            F = np.maximum(F, 1e-10)  # 确保正定
        else:
            F = np.trace(S) / n * np.eye(n)

        # 计算最优压缩系数
        alpha = self._calc_optimal_shrinkage(returns.values, S, F, T)

        # 压缩估计
        shrunk = alpha * F + (1 - alpha) * S

        # 确保正定
        shrunk = self._ensure_positive_definite(shrunk)

        return pd.DataFrame(shrunk, index=returns.columns, columns=returns.columns)

    def _calc_optimal_shrinkage(self, X: np.ndarray, S: np.ndarray,
                                F: np.ndarray, T: int) -> float:
        """计算最优压缩系数"""
        n = S.shape[0]

        # 计算样本协方差的方差
        sum_sq = 0
        for t in range(T):
            x_t = X[t] - X.mean(axis=0)
            sum_sq += np.sum((np.outer(x_t, x_t) - S) ** 2)
        var_S = sum_sq / (T ** 2)

        # 计算目标与样本的差异
        diff_sq = np.sum((F - S) ** 2)

        if diff_sq == 0:
            return 0.0

        alpha = min(var_S / diff_sq, 1.0)
        return alpha

    def _ensure_positive_definite(self, matrix: np.ndarray) -> np.ndarray:
        """确保矩阵正定"""
        try:
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)
            eigenvalues = np.maximum(eigenvalues, 1e-10)
            return eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
        except np.linalg.LinAlgError:
            return matrix

    def ewma_covariance(self, returns: pd.DataFrame,
                        halflife: int = 60) -> pd.DataFrame:
        """
        指数加权移动平均协方差 (EWMA)
        近期数据权重更大
        """
        return returns.ewm(halflife=halflife).cov().iloc[-len(returns.columns):]

    def dcc_garch_covariance(self, returns: pd.DataFrame,
                              alpha: float = 0.02, beta: float = 0.95,
                              halflife: int = 60) -> pd.DataFrame:
        """
        DCC-GARCH时变协方差 (Dynamic Conditional Correlation)
        捕捉危机期间相关性上升的现象，比静态EWMA更准确

        Args:
            returns: 收益率矩阵 (T x N)
            alpha: DCC动态参数
            beta: DCC持久性参数
            halflife: 单变量GARCH半衰期
        """
        T, N = returns.shape
        if T < 30 or N < 2:
            return self.ewma_covariance(returns, halflife)

        # Step 1: 单变量GARCH(1,1)估计波动率
        omega_garch = 0.01  # 长期方差权重
        alpha_garch = 0.05
        beta_garch = 0.90

        conditional_vols = np.zeros((T, N))
        for j in range(N):
            r = returns.iloc[:, j].values
            var = np.zeros(T)
            var[0] = r.var() if len(r) > 1 else 0.01
            for t in range(1, T):
                var[t] = omega_garch * var[0] + alpha_garch * r[t-1]**2 + beta_garch * var[t-1]
                var[t] = max(var[t], 1e-10)
            conditional_vols[:, j] = np.sqrt(var)

        # Step 2: 标准化残差
        std_residuals = returns.values / conditional_vols

        # Step 3: DCC动态相关矩阵
        # Q_t = (1-a-b) * S + a * eps_{t-1}*eps_{t-1}' + b * Q_{t-1}
        S = np.corrcoef(std_residuals.T)  # 无条件相关矩阵
        Q = S.copy()
        Q_bar = S.copy()

        for t in range(1, T):
            eps = std_residuals[t-1].reshape(-1, 1)
            Q = (1 - alpha - beta) * Q_bar + alpha * (eps @ eps.T) + beta * Q
            # 确保正定
            eigvals, eigvecs = np.linalg.eigh(Q)
            eigvals = np.maximum(eigvals, 1e-10)
            Q = eigvecs @ np.diag(eigvals) @ eigvecs.T

        # Step 4: 相关系数矩阵 R = diag(Q)^{-1/2} * Q * diag(Q)^{-1/2}
        diag_Q = np.diag(Q)
        diag_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(diag_Q, 1e-10)))
        R = diag_inv_sqrt @ Q @ diag_inv_sqrt

        # Step 5: 协方差矩阵 = diag(sigma) * R * diag(sigma)
        current_vols = conditional_vols[-1]
        D = np.diag(current_vols)
        cov = D @ R @ D

        return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)

    def pca_hybrid_covariance(self, returns: pd.DataFrame,
                               n_pca_factors: int = 10,
                               shrinkage: float = 0.5) -> pd.DataFrame:
        """
        PCA混合风险模型
        结构化部分(PCA因子) + 特质部分(对角残差)
        比纯样本协方差更稳定，比纯Barra更灵活

        Args:
            returns: 收益率矩阵
            n_pca_factors: PCA因子数量
            shrinkage: 特质方差压缩系数
        """
        T, N = returns.shape
        if T < N + 10:
            return self.ledoit_wolf_shrinkage(returns)

        # PCA分解
        sample_cov = returns.cov().values
        eigenvalues, eigenvectors = np.linalg.eigh(sample_cov)

        # 降序排列
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]

        # 结构化部分: 前K个主成分
        K = min(n_pca_factors, N)
        factor_loadings = eigenvectors[:, :K]
        factor_cov = np.diag(eigenvalues[:K])
        structured = factor_loadings @ factor_cov @ factor_loadings.T

        # 特质部分: 残差方差
        idio_var = np.diag(sample_cov) - np.diag(structured)
        idio_var = np.maximum(idio_var, 1e-10)  # 确保正

        # 混合协方差
        hybrid = structured + np.diag(idio_var)

        # 确保正定
        hybrid = self._ensure_positive_definite(hybrid)

        return pd.DataFrame(hybrid, index=returns.columns, columns=returns.columns)

    # ==================== 2. Barra风险模型 (ADD 10.1节) ====================

    def barra_factor_exposure(self, stock_data: pd.DataFrame) -> pd.DataFrame:
        """
        计算Barra因子暴露度 (ADD 10.1节)
        """
        exposures = pd.DataFrame(index=stock_data.index)

        # Size: log(总市值)
        if 'total_market_cap' in stock_data.columns:
            exposures['size'] = np.log(stock_data['total_market_cap'])
        elif 'market_cap' in stock_data.columns:
            exposures['size'] = np.log(stock_data['market_cap'])

        # Beta: 相对市场的Beta
        if 'beta' in stock_data.columns:
            exposures['beta'] = stock_data['beta']

        # Book-to-Price: BP
        if 'bp' in stock_data.columns:
            exposures['book_to_price'] = stock_data['bp']

        # Earnings Yield: EP
        if 'ep_ttm' in stock_data.columns:
            exposures['earnings_yield'] = stock_data['ep_ttm']

        # Growth: 营收增速
        if 'yoy_revenue' in stock_data.columns:
            exposures['growth'] = stock_data['yoy_revenue']

        # Leverage: 资产负债率
        if 'asset_liability_ratio' in stock_data.columns:
            exposures['leverage'] = stock_data['asset_liability_ratio']

        # Liquidity: 换手率
        if 'turnover_20d' in stock_data.columns:
            exposures['liquidity'] = stock_data['turnover_20d']

        # Momentum: 过去12个月收益
        if 'ret_12m' in stock_data.columns:
            exposures['momentum'] = stock_data['ret_12m']

        # Residual Volatility
        if 'idio_vol' in stock_data.columns:
            exposures['residual_volatility'] = stock_data['idio_vol']
        elif 'vol_60d' in stock_data.columns:
            exposures['residual_volatility'] = stock_data['vol_60d']

        # Non-linear Size: size^2
        if 'size' in exposures.columns:
            exposures['non_linear_size'] = exposures['size'] ** 2

        return exposures

    def barra_factor_return(self, returns: pd.DataFrame,
                            exposures: pd.DataFrame) -> pd.Series:
        """
        计算因子收益 (ADD 10.1节)
        r = X * f + u
        f = (X'X)^{-1} X' r
        """
        # 对齐
        common = returns.index.intersection(exposures.index)
        if len(common) == 0:
            return pd.Series()

        X = exposures.loc[common].values
        r = returns.loc[common].values

        # 截面回归
        try:
            f = np.linalg.lstsq(X, r, rcond=None)[0]
            return pd.Series(f, index=exposures.columns)
        except np.linalg.LinAlgError:
            return pd.Series()

    def barra_decompose_risk(self, exposures: pd.DataFrame,
                             factor_cov: pd.DataFrame,
                             idio_var: pd.Series) -> Dict:
        """
        风险分解 (ADD 10.3节)
        总风险 = 因子风险 + 特质风险

        σ²_i = b_i' Σ_f b_i + σ²_ε_i
        """
        X = exposures.values
        F = factor_cov.values

        # 因子风险
        factor_risk = np.diag(X @ F @ X.T)
        # 特质风险
        idio_risk = idio_var.values if isinstance(idio_var, pd.Series) else idio_var
        # 总风险
        total_risk = factor_risk + idio_risk

        return {
            'factor_risk': factor_risk,
            'idiosyncratic_risk': idio_risk,
            'total_risk': total_risk,
            'factor_risk_pct': factor_risk / total_risk if np.any(total_risk > 0) else None,
        }

    # ==================== 3. VaR和CVaR (ADD 10.4节) ====================

    def historical_var(self, returns: pd.Series,
                       confidence: float = 0.95,
                       window: int = 252) -> float:
        """
        历史模拟法VaR (ADD 10.4节)
        """
        if len(returns) < window:
            window = len(returns)
        recent_returns = returns.iloc[-window:]
        return -np.percentile(recent_returns, (1 - confidence) * 100)

    def parametric_var(self, returns: pd.Series,
                       confidence: float = 0.95) -> float:
        """
        参数法VaR (ADD 10.4节)
        VaR = -μ - z_α * σ
        """
        from scipy.stats import norm
        mu = returns.mean()
        sigma = returns.std()
        z = norm.ppf(confidence)
        return -(mu - z * sigma)

    def conditional_var(self, returns: pd.Series,
                        confidence: float = 0.95) -> float:
        """
        CVaR/ES (ADD 10.4节)
        E[-R | R < -VaR]
        """
        var = self.historical_var(returns, confidence)
        tail_returns = returns[returns < -var]
        if len(tail_returns) == 0:
            return var
        return -tail_returns.mean()

    def monte_carlo_var(self, returns: pd.Series,
                        confidence: float = 0.95,
                        n_simulations: int = 10000,
                        horizon: int = 1) -> float:
        """
        蒙特卡洛VaR
        """
        from scipy.stats import norm
        mu = returns.mean()
        sigma = returns.std()

        simulated = np.random.normal(mu, sigma, (n_simulations, horizon))
        simulated_returns = simulated.sum(axis=1)

        return -np.percentile(simulated_returns, (1 - confidence) * 100)

    def student_t_var(self, returns: pd.Series,
                      confidence: float = 0.95,
                      df: float = None) -> float:
        """
        Student-t分布VaR
        比正态分布更好地捕捉厚尾特征

        Args:
            returns: 收益率序列
            confidence: 置信水平
            df: 自由度(不提供则自动估计)
        """
        if df is None:
            # 用矩估计法估计自由度
            kurt = returns.kurtosis()
            if kurt > 0:
                df = 6.0 / kurt + 4  # 超额峰度 = 6/(df-4)
                df = max(df, 4.5)  # 至少4.5自由度
            else:
                df = 30.0  # 接近正态

        mu = returns.mean()
        sigma = returns.std()
        t_quantile = sp_stats.t.ppf(1 - confidence, df=df)
        # Student-t的VaR缩放因子
        scale = sigma * np.sqrt((df - 2) / df)
        return -(mu + t_quantile * scale)

    def copula_tail_dependence(self, returns_a: pd.Series, returns_b: pd.Series,
                                threshold: float = 0.05) -> Dict[str, float]:
        """
        Copula尾部依赖估计
        衡量两个资产在极端情况下的共同运动程度
        相关性在尾部会被低估，尾部依赖更准确

        Args:
            returns_a: 资产A收益率
            returns_b: 资产B收益率
            threshold: 尾部阈值
        """
        common_idx = returns_a.index.intersection(returns_b.index)
        a = returns_a.loc[common_idx]
        b = returns_b.loc[common_idx]

        # 下尾依赖: P(Y < F_Y^{-1}(u) | X < F_X^{-1}(u))
        a_rank = a.rank(pct=True)
        b_rank = b.rank(pct=True)
        n = len(a)

        # 下尾(左尾)
        both_lower = ((a_rank <= threshold) & (b_rank <= threshold)).sum()
        a_lower = (a_rank <= threshold).sum()
        lower_tail_dep = both_lower / a_lower if a_lower > 0 else 0

        # 上尾(右尾)
        both_upper = ((a_rank >= 1 - threshold) & (b_rank >= 1 - threshold)).sum()
        a_upper = (a_rank >= 1 - threshold).sum()
        upper_tail_dep = both_upper / a_upper if a_upper > 0 else 0

        return {
            'lower_tail_dependence': round(lower_tail_dep, 4),
            'upper_tail_dependence': round(upper_tail_dep, 4),
            'asymmetry': round(lower_tail_dep - upper_tail_dep, 4),  # A股通常下尾>上尾
        }

    def mean_cvar_optimization(self, expected_returns: np.ndarray,
                                cov_matrix: np.ndarray,
                                confidence: float = 0.95,
                                risk_aversion: float = 1.0,
                                max_weight: float = 0.05,
                                min_weight: float = 0.0,
                                long_only: bool = True) -> Dict:
        """
        Mean-CVaR组合优化 (Rockafellar-Uryasev 2000)
        直接优化尾部风险而非方差，对非正态分布更稳健

        min  -w'*mu + lambda * CVaR_alpha(w)
        s.t. w >= 0, sum(w) = 1, w_i <= w_max

        Args:
            expected_returns: 预期收益向量
            cov_matrix: 协方差矩阵
            confidence: CVaR置信水平
            risk_aversion: 风险厌恶系数
            max_weight: 单一资产最大权重
            min_weight: 单一资产最小权重
            long_only: 是否仅做多

        Returns:
            优化结果 {weights, cvar, expected_return, ...}
        """
        try:
            import cvxpy as cp
        except ImportError:
            logger.warning("cvxpy not available, falling back to mean-variance")
            return self._mean_variance_fallback(expected_returns, cov_matrix, max_weight)

        N = len(expected_returns)
        w = cp.Variable(N)
        xi = cp.Variable()  # VaR辅助变量

        # 使用Cholesky分解生成场景
        L = np.linalg.cholesky(self._ensure_positive_definite(cov_matrix))
        n_scenarios = 1000
        Z = np.random.randn(n_scenarios, N)
        scenarios = Z @ L.T + expected_returns.reshape(1, -1)

        # CVaR线性化: CVaR = xi + 1/((1-alpha)*T) * sum(max(0, -r_t'*w - xi))
        losses = -scenarios @ w  # 场景损失
        slack = cp.Variable(n_scenarios)  # 辅助变量: slack >= max(0, loss - xi)

        # 目标函数
        cvar_term = xi + (1.0 / ((1 - confidence) * n_scenarios)) * cp.sum(slack)
        objective = cp.Minimize(-expected_returns @ w + risk_aversion * cvar_term)

        # 约束
        constraints = [
            cp.sum(w) == 1,
            slack >= 0,
            slack >= losses - xi,  # slack >= max(0, loss - xi)
        ]

        if long_only:
            constraints.append(w >= min_weight)
        constraints.append(w <= max_weight)

        # 求解
        problem = cp.Problem(objective, constraints)
        try:
            problem.solve(solver=cp.ECOS, max_iters=500)
        except cp.SolverError:
            problem.solve(solver=cp.SCS, max_iters=2000)

        if problem.status not in ['optimal', 'optimal_inaccurate']:
            return self._mean_variance_fallback(expected_returns, cov_matrix, max_weight)

        weights = w.value
        if weights is None:
            return self._mean_variance_fallback(expected_returns, cov_matrix, max_weight)

        # 清理微小权重
        weights = np.maximum(weights, 0)
        weights = weights / weights.sum()

        return {
            'weights': weights,
            'expected_return': float(expected_returns @ weights),
            'cvar': float(xi.value + (1.0 / ((1 - confidence) * n_scenarios)) * np.sum(np.maximum(0, -scenarios @ weights - xi.value))),
            'var': float(xi.value),
            'portfolio_vol': float(np.sqrt(weights @ cov_matrix @ weights)),
            'status': problem.status,
        }

    def _mean_variance_fallback(self, expected_returns: np.ndarray,
                                 cov_matrix: np.ndarray,
                                 max_weight: float) -> Dict:
        """均值-方差优化回退方案"""
        N = len(expected_returns)
        try:
            inv_cov = np.linalg.inv(cov_matrix)
            raw_weights = inv_cov @ expected_returns
            raw_weights = np.maximum(raw_weights, 0)
            if raw_weights.sum() > 0:
                weights = raw_weights / raw_weights.sum()
                weights = np.minimum(weights, max_weight)
                weights = weights / weights.sum()
            else:
                weights = np.ones(N) / N
        except np.linalg.LinAlgError:
            weights = np.ones(N) / N

        return {
            'weights': weights,
            'expected_return': float(expected_returns @ weights),
            'portfolio_vol': float(np.sqrt(weights @ cov_matrix @ weights)),
            'status': 'fallback',
        }

    def liquidity_adjusted_var(self, returns: pd.Series,
                                position_size: float,
                                daily_volume: float,
                                spread: float = 0.001,
                                confidence: float = 0.95) -> Dict[str, float]:
        """
        流动性调整VaR (LVaR)
        标准VaR + 流动性成本

        LVaR = VaR + 0.5*spread + lambda*sqrt(position_size/daily_volume)

        Args:
            returns: 收益率序列
            position_size: 持仓金额
            daily_volume: 日均成交额
            spread: 买卖价差
            confidence: 置信水平
        """
        var = self.parametric_var(returns, confidence)

        # 价差成本
        spread_cost = 0.5 * spread

        # 市场冲击成本 (Almgren-Chriss简化)
        participation_rate = position_size / daily_volume if daily_volume > 0 else 0
        impact_cost = 0.1 * np.sqrt(max(participation_rate, 0))  # 平方根法则

        lvar = var + spread_cost + impact_cost

        return {
            'var': round(var, 6),
            'spread_cost': round(spread_cost, 6),
            'impact_cost': round(impact_cost, 6),
            'lvar': round(lvar, 6),
            'participation_rate': round(participation_rate, 4),
        }

    # ==================== 4. 组合风险计算 ====================

    def portfolio_var(self, weights: np.ndarray,
                      cov_matrix: np.ndarray) -> float:
        """组合方差: w'Σw"""
        return weights @ cov_matrix @ weights

    def portfolio_volatility(self, weights: np.ndarray,
                             cov_matrix: np.ndarray) -> float:
        """组合波动率"""
        return np.sqrt(self.portfolio_var(weights, cov_matrix))

    def marginal_risk_contribution(self, weights: np.ndarray,
                                   cov_matrix: np.ndarray) -> np.ndarray:
        """
        边际风险贡献 (MRC)
        MRC_i = (Σw)_i / σ_p
        """
        portfolio_vol = self.portfolio_volatility(weights, cov_matrix)
        if portfolio_vol == 0:
            return np.zeros(len(weights))
        return (cov_matrix @ weights) / portfolio_vol

    def risk_contribution(self, weights: np.ndarray,
                          cov_matrix: np.ndarray) -> np.ndarray:
        """
        风险贡献 (RC)
        RC_i = w_i * MRC_i
        """
        mrc = self.marginal_risk_contribution(weights, cov_matrix)
        return weights * mrc

    def risk_contribution_pct(self, weights: np.ndarray,
                              cov_matrix: np.ndarray) -> np.ndarray:
        """风险贡献百分比"""
        rc = self.risk_contribution(weights, cov_matrix)
        total = rc.sum()
        if total == 0:
            return np.zeros(len(weights))
        return rc / total