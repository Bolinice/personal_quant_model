"""
风险模型模块
实现ADD 10节: Barra风格因子风险模型、协方差估计、风险分解、VaR/CVaR
机构级增强: DCC-GARCH时变协方差、PCA混合风险模型、Mean-CVaR组合优化、Copula尾部模型
"""

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from app.core.logging import logger


class RiskModel:
    """风险模型 - 符合ADD 10节"""

    # Barra USE4风格因子定义 (ADD 10.1节)
    # 行业因子由单独的行业分类处理，此处仅列风格因子
    BARRA_FACTORS = [
        "beta",  # 系统性风险暴露：个股对市场的敏感度
        "book_to_price",  # 价值因子：BP越高越偏价值风格
        "earnings_yield",  # 盈利因子：EP_TTM，高EP即低PE，价值维度补充
        "growth",  # 成长因子：营收同比增速
        "leverage",  # 杠杆因子：资产负债率，高杠杆放大尾部风险
        "liquidity",  # 流动性因子：20日换手率，低流动性股票有流动性溢价
        "momentum",  # 动量因子：跳月12月动量，跳月避免短期反转污染
        "non_linear_size",  # 规模非线性因子：size的立方项，捕捉大小盘风格切换的非对称效应
        "residual_volatility",  # 残差波动率因子：剥离市场后的特质波动，高波动股票长期收益偏低
        "size",  # 规模因子：log(总市值)，对数变换使市值分布近似正态
    ]

    def __init__(self) -> None:
        pass

    # ==================== 1. 协方差矩阵估计 (ADD 10.2节) ====================

    def sample_covariance(self, returns: pd.DataFrame) -> pd.DataFrame:
        """
        样本协方差矩阵
        Σ = (1/T) * R'R
        """
        return returns.cov()

    def ledoit_wolf_shrinkage(self, returns: pd.DataFrame, shrinkage_target: str = "identity") -> pd.DataFrame:
        """
        Ledoit-Wolf压缩估计 (ADD 10.2.1节)
        Σ_shrunk = α * F + (1-α) * S

        Args:
            returns: 收益率矩阵
            shrinkage_target: 压缩目标 ('identity', 'diagonal', 'single_factor')
        """
        S = returns.cov(ddof=0).values  # 有偏协方差(ddof=0): 与外积x_t*x_t'一致
        # Ledoit-Wolf公式要求一致的估计器: 外积使用ddof=0(1/T), cov也必须用ddof=0
        # pandas默认cov(ddof=1)使用无偏估计(1/(T-1)), 与外积不一致, 导致alpha偏小
        n: int = S.shape[0]
        T: int = len(returns)

        if shrinkage_target == "identity":
            # 目标: 缩放后的单位矩阵
            F = np.trace(S) / n * np.eye(n)
        elif shrinkage_target == "diagonal":
            # 目标: 对角矩阵 — 假设资产间无条件相关，仅保留方差
            F = np.diag(np.diag(S))
        elif shrinkage_target == "single_factor":
            # 目标: 单因子模型 — 用市场因子解释共同运动，残差作为特质方差
            market_returns = returns.mean(axis=1)
            var_market = market_returns.var()
            betas = returns.apply(lambda x: x.cov(market_returns)) / var_market if var_market > 0 else np.ones(n)
            F = np.outer(betas, betas) * var_market + np.diag(np.diag(S) - betas**2 * var_market)
            F = self._ensure_positive_definite(F)  # 单因子模型可能产生负的特质方差，需强制正定
        else:
            F = np.trace(S) / n * np.eye(n)

        # 计算最优压缩系数
        alpha = self._calc_optimal_shrinkage(returns.values, S, F, T)

        # 压缩估计
        shrunk = alpha * F + (1 - alpha) * S

        # 确保正定
        shrunk = self._ensure_positive_definite(shrunk)

        return pd.DataFrame(shrunk, index=returns.columns, columns=returns.columns)

    def _calc_optimal_shrinkage(self, X: np.ndarray, S: np.ndarray, F: np.ndarray, T: int) -> float:
        """计算最优压缩系数"""
        n = S.shape[0]

        # Large N fallback: vectorized (T, N, N) tensor consumes too much memory
        # when N > 100 (e.g., N=500 => 125M elements). Use loop-based approach.
        # N>100时向量化路径内存爆炸，切换逐时间步循环
        var_S = self._calc_var_S_loop(X, S, T, n) if n > 100 else self._calc_var_S_vectorized(X, S, T, n)

        # 计算目标与样本的差异
        diff_sq = np.sum((F - S) ** 2)

        if diff_sq == 0:
            return 0.0

        # alpha越接近1，越依赖结构化目标F；样本量不足时alpha自动升高
        return min(var_S / diff_sq, 1.0)

    def _calc_var_S_vectorized(self, X: np.ndarray, S: np.ndarray, T: int, n: int) -> float:
        """向量化计算 var_S: 适用于 N <= 100"""
        X_centered = X - X.mean(axis=0)  # (T, N)
        # outer products: (T, N, 1) * (T, 1, N) -> (T, N, N)
        outer_prods = X_centered[:, :, np.newaxis] * X_centered[:, np.newaxis, :]  # (T, N, N)
        diffs = outer_prods - S[np.newaxis, :, :]  # (T, N, N)
        return np.sum(diffs**2) / (T**2)

    def _calc_var_S_loop(self, X: np.ndarray, S: np.ndarray, T: int, n: int) -> float:
        """
        循环计算 var_S: 适用于 N > 100, 避免创建 (T, N, N) 大张量
        var_S = (1/T^2) * sum_t || x_t x_t' - S ||_F^2
        展开: sum of (x_t_i * x_t_j - S_ij)^2 for each (i,j) pair, summed over t
        等价于: (1/T^2) * [sum_t sum_i sum_j (x_ti * x_tj - S_ij)^2]
        """
        X_centered = X - X.mean(axis=0)  # (T, N)
        total = 0.0
        for t in range(T):
            x_t = X_centered[t]  # (N,)
            # outer product - S, then Frobenius norm squared
            diff = np.outer(x_t, x_t) - S
            total += np.sum(diff**2)
        return total / (T**2)

    def _ensure_positive_definite(self, matrix: np.ndarray) -> np.ndarray:
        """确保矩阵正定"""
        try:
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)
            # 将负/近零特征值提升到1e-10，避免后续求逆时数值溢出
            eigenvalues = np.maximum(eigenvalues, 1e-10)
            return eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
        except np.linalg.LinAlgError:
            return matrix

    def ewma_covariance(self, returns: pd.DataFrame, halflife: int = 60) -> pd.DataFrame:
        """
        指数加权移动平均协方差 (EWMA)
        近期数据权重更大
        halflife=60对应衰减因子≈0.9885，与RiskMetrics标准(λ=0.94, halflife≈17)相比
        更平滑，适合A股中低频策略减少交易噪音
        """
        ewm_result = returns.ewm(halflife=halflife).cov()
        # pandas ewm().cov()返回MultiIndex (date, asset), 取最后一个时间截面
        if isinstance(ewm_result.index, pd.MultiIndex):
            last_date = ewm_result.index.get_level_values(0)[-1]
            cov_matrix = ewm_result.loc[last_date].values
        else:
            # 单时间点情况
            cov_matrix = ewm_result.values
        cov_matrix = self._ensure_positive_definite(cov_matrix)
        return pd.DataFrame(cov_matrix, index=returns.columns, columns=returns.columns)

    def dcc_garch_covariance(
        self,
        returns: pd.DataFrame,
        alpha: float | None = None,
        beta: float | None = None,
        halflife: int = 60,
        use_mle: bool = True,
    ) -> pd.DataFrame:
        """
        DCC-GARCH时变协方差 (机构级: MLE估计参数)
        捕捉危机期间相关性上升的现象，比静态EWMA更准确

        Args:
            returns: 收益率矩阵 (T x N)
            alpha: DCC动态参数 (None则自动估计)
            beta: DCC持久性参数 (None则自动估计)
            halflife: 单变量GARCH半衰期
            use_mle: 是否使用MLE估计GARCH参数 (True=arch包, False=硬编码)
        """
        T, N = returns.shape
        # 数据不足时回退EWMA：GARCH参数估计至少需要30个观测点
        if T < 30 or N < 2:
            logger.info("DCC-GARCH: insufficient data, falling back to EWMA", extra={"T": T, "N": N})
            return self.ewma_covariance(returns, halflife)

        # Step 1: 单变量GARCH(1,1)估计波动率
        conditional_vols = np.zeros((T, N))

        if use_mle:
            # 机构级: 用arch包做MLE估计
            try:
                from arch.univariate import GARCH, ConstantMean, Normal

                for j in range(N):
                    r = returns.iloc[:, j].dropna()
                    if len(r) < 30:
                        conditional_vols[:, j] = r.std()
                        continue
                    am = ConstantMean(r.values * 100)  # 缩放避免数值问题：收益率量级过小会导致GARCH优化器不收敛
                    am.volatility = GARCH(p=1, o=0, q=1)
                    am.distribution = Normal()
                    try:
                        res = am.fit(disp="off", show_warning=False)
                        cond_vol = res.conditional_volatility / 100  # 还原缩放
                        # 对齐长度
                        if len(cond_vol) == T:
                            conditional_vols[:, j] = cond_vol
                        elif len(cond_vol) > T:
                            conditional_vols[:, j] = cond_vol[-T:]
                        else:
                            conditional_vols[: len(cond_vol), j] = cond_vol
                            conditional_vols[len(cond_vol) :, j] = cond_vol[-1]
                    except Exception:
                        # MLE失败, 回退到EWMA
                        conditional_vols[:, j] = (
                            r.rolling(20, min_periods=10).std().values[-T:] if len(r) >= 20 else r.std()
                        )
            except ImportError:
                logger.warning("arch package not available, using hardcoded GARCH params")
                conditional_vols = self._garch_hardcoded(returns, T, N)
        else:
            conditional_vols = self._garch_hardcoded(returns, T, N)

        # 确保无零值
        conditional_vols = np.maximum(conditional_vols, 1e-8)

        # Step 2: 标准化残差
        std_residuals = returns.values / conditional_vols

        # Step 3: DCC参数估计
        if alpha is None or beta is None:
            # 网格搜索最大化DCC对数似然
            alpha, beta = self._dcc_grid_search(std_residuals, T)

        # Step 4: DCC动态相关矩阵
        S = np.corrcoef(std_residuals.T)
        Q = S.copy()
        Q_bar = S.copy()

        for t in range(1, T):
            eps = std_residuals[t - 1].reshape(-1, 1)
            Q = (1 - alpha - beta) * Q_bar + alpha * (eps @ eps.T) + beta * Q
            eigvals, eigvecs = np.linalg.eigh(Q)
            eigvals = np.maximum(eigvals, 1e-10)
            Q = eigvecs @ np.diag(eigvals) @ eigvecs.T

        # Step 5: 相关系数矩阵
        diag_Q = np.diag(Q)
        diag_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(diag_Q, 1e-10)))
        R = diag_inv_sqrt @ Q @ diag_inv_sqrt

        # Step 6: 协方差矩阵
        current_vols = conditional_vols[-1]
        D = np.diag(current_vols)
        cov = D @ R @ D

        logger.info(
            "DCC-GARCH covariance estimated", extra={"T": T, "N": N, "alpha": alpha, "beta": beta, "use_mle": use_mle}
        )

        return pd.DataFrame(cov, index=returns.columns, columns=returns.columns)

    def _garch_hardcoded(self, returns: pd.DataFrame, T: int, N: int) -> np.ndarray:
        """硬编码GARCH参数(回退方案)"""
        # 典型A股GARCH参数：alpha+beta=0.95表示波动率持久性较强
        # omega*var[0]使长期方差回归到样本方差水平
        omega_garch = 0.01
        alpha_garch = 0.05  # 残差平方对条件方差的冲击
        beta_garch = 0.90  # 条件方差的自回归系数

        conditional_vols = np.zeros((T, N))
        for j in range(N):
            r = returns.iloc[:, j].values
            var = np.zeros(T)
            var[0] = r.var() if len(r) > 1 else 0.01
            for t in range(1, T):
                var[t] = omega_garch * var[0] + alpha_garch * r[t - 1] ** 2 + beta_garch * var[t - 1]
                var[t] = max(var[t], 1e-10)
            conditional_vols[:, j] = np.sqrt(var)
        return conditional_vols

    def _dcc_grid_search(self, std_residuals: np.ndarray, T: int) -> tuple[float, float]:
        """
        DCC参数网格搜索
        最大化DCC对数似然: L = -0.5 * Σ [log(det(R_t)) + eps_t' * R_t^{-1} * eps_t]
        """
        # 初始值取DCC文献典型范围：alpha小(新闻冲击弱)，beta大(相关性持久)
        best_alpha, best_beta = 0.02, 0.95
        best_ll = -np.inf

        S = np.corrcoef(std_residuals.T)

        # 网格: alpha in [0.01, 0.05], beta in [0.90, 0.98]
        # alpha+beta<1是DCC平稳性条件，超出则时变相关矩阵发散
        for a in np.arange(0.01, 0.06, 0.01):
            for b in np.arange(0.90, 0.99, 0.02):
                if a + b >= 1.0:
                    continue

                Q = S.copy()
                ll = 0.0
                valid = True

                for t in range(1, T):
                    eps = std_residuals[t - 1].reshape(-1, 1)
                    Q = (1 - a - b) * S + a * (eps @ eps.T) + b * Q

                    # 确保正定
                    eigvals, eigvecs = np.linalg.eigh(Q)
                    eigvals = np.maximum(eigvals, 1e-10)
                    Q = eigvecs @ np.diag(eigvals) @ eigvecs.T

                    # R_t
                    diag_Q = np.diag(Q)
                    diag_inv_sqrt = np.diag(1.0 / np.sqrt(np.maximum(diag_Q, 1e-10)))
                    R_t = diag_inv_sqrt @ Q @ diag_inv_sqrt

                    try:
                        det_R = np.linalg.det(R_t)
                        if det_R <= 0:
                            valid = False
                            break
                        R_inv = np.linalg.inv(R_t)
                        eps_t = std_residuals[t]
                        ll += -0.5 * (np.log(det_R) + eps_t @ R_inv @ eps_t)
                    except np.linalg.LinAlgError:
                        valid = False
                        break

                    # 早停: 如果当前平均每步对数似然已低于best的平均每步对数似然
                    # 且已过1/4时间步，跳过 (使用平均而非累计，消除时间步数的影响)
                    if best_ll > -np.inf and t > T // 4:
                        avg_ll = ll / t
                        best_avg_ll = best_ll / (T - 1)  # best_ll是完整遍历的累计值
                        if avg_ll < best_avg_ll:
                            valid = False
                            break

                if valid and ll > best_ll:
                    best_ll = ll
                    best_alpha = a
                    best_beta = b

        return best_alpha, best_beta

    def pca_hybrid_covariance(
        self, returns: pd.DataFrame, n_pca_factors: int = 10, shrinkage: float = 0.5
    ) -> pd.DataFrame:
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
        # T<N时样本协方差奇异，直接用LW压缩避免过拟合
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
        idio_var = np.maximum(idio_var, 1e-10)  # PCA可能过度解释方差导致残差为负，截断为正值

        # 混合协方差
        hybrid = structured + np.diag(idio_var)

        # 确保正定
        hybrid = self._ensure_positive_definite(hybrid)

        return pd.DataFrame(hybrid, index=returns.columns, columns=returns.columns)

    # ==================== 2. Barra风险模型 (ADD 10.1节) ====================

    def barra_factor_exposure(self, stock_data: pd.DataFrame) -> pd.DataFrame:
        """
        计算Barra因子暴露度 (机构级: 从原始数据计算)
        ADD 10.1节 + Barra USE4标准

        Args:
            stock_data: 需包含 total_market_cap/market_cap, bp, ep_ttm, yoy_revenue,
                        turnover_20d, ret_12m_skip1, vol_60d, asset_liability_ratio
        """
        exposures = pd.DataFrame(index=stock_data.index)

        # Size: log(总市值) — Barra标准，对数变换压缩市值量级差异(大盘股可达小盘股万倍)
        cap_col = "total_market_cap" if "total_market_cap" in stock_data.columns else "market_cap"
        if cap_col in stock_data.columns:
            exposures["size"] = np.log(stock_data[cap_col].clip(lower=1))

        # Non-linear Size: (size - mean_size)^3 — Barra USE4标准(立方, 非平方)
        # 立方项捕捉大小盘风格切换的非对称性：大→小的切换比小→大更剧烈
        if "size" in exposures.columns:
            mean_size = exposures["size"].mean()
            exposures["non_linear_size"] = (exposures["size"] - mean_size) ** 3

        # Beta: 相对市场的Beta (优先从250日回归计算)
        if "beta" in stock_data.columns:
            exposures["beta"] = stock_data["beta"]

        # Book-to-Price: BP
        if "bp" in stock_data.columns:
            exposures["book_to_price"] = stock_data["bp"]

        # Earnings Yield: EP
        if "ep_ttm" in stock_data.columns:
            exposures["earnings_yield"] = stock_data["ep_ttm"]

        # Growth: 营收增速
        if "yoy_revenue" in stock_data.columns:
            exposures["growth"] = stock_data["yoy_revenue"]

        # Leverage: 资产负债率
        if "asset_liability_ratio" in stock_data.columns:
            exposures["leverage"] = stock_data["asset_liability_ratio"]

        # Liquidity: 换手率
        if "turnover_20d" in stock_data.columns:
            exposures["liquidity"] = stock_data["turnover_20d"]

        # Momentum: 跳月12月动量
        # 跳过最近1个月避免短期反转效应污染中期动量信号(A股1个月反转显著)
        if "ret_12m_skip1" in stock_data.columns:
            exposures["momentum"] = stock_data["ret_12m_skip1"]
        elif "ret_12m" in stock_data.columns:
            exposures["momentum"] = stock_data["ret_12m"]

        # Residual Volatility: 优先用剥离市场后的特质波动率
        # 特质波动率高(低波动异象)的股票长期收益偏低，与beta因子含义不同
        if "idio_vol" in stock_data.columns:
            exposures["residual_volatility"] = stock_data["idio_vol"]
        elif "vol_60d" in stock_data.columns:
            exposures["residual_volatility"] = stock_data["vol_60d"]

        return exposures

    def barra_factor_return(
        self, returns: pd.DataFrame, exposures: pd.DataFrame, market_cap: pd.Series | None = None
    ) -> pd.Series:
        """
        计算因子收益 (机构级: WLS截面回归)
        Barra标准: 权重 = sqrt(市值), 大市值股票因子收益估计更精确
        r = X * f + u, WLS: (X'WX)f = X'Wr

        Args:
            returns: 截面收益率 Series
            exposures: 因子暴露度 DataFrame
            market_cap: 市值序列 (用于WLS权重)
        """
        common = returns.index.intersection(exposures.index)
        if len(common) == 0:
            logger.warning("Barra factor return: no common indices between returns and exposures")
            return pd.Series()

        X = exposures.loc[common].values
        r = returns.loc[common].values

        # WLS权重 = sqrt(市值)
        # Barra标准：大市值股票定价更有效，给予更高权重提升因子收益估计精度
        # 用sqrt而非线性权重，避免超级大盘股(如贵州茅台)完全主导回归
        if market_cap is not None:
            w = np.sqrt(market_cap.reindex(common).fillna(market_cap.median()).values)
            W = np.diag(w)
        else:
            W = np.eye(len(common))

        # WLS: (X'WX)f = X'Wr
        try:
            XW = X.T @ W
            XtWX = XW @ W @ X
            XtWr = XW @ W @ r
            f = np.linalg.solve(XtWX, XtWr)
            logger.info(
                "Barra factor return computed via WLS",
                extra={
                    "n_stocks": len(common),
                    "n_factors": len(exposures.columns),
                    "method": "WLS",
                    "has_market_cap": market_cap is not None,
                },
            )
            return pd.Series(f, index=exposures.columns)
        except np.linalg.LinAlgError:
            # 回退到OLS
            try:
                f = np.linalg.lstsq(X, r, rcond=None)[0]
                logger.info(
                    "Barra factor return computed via OLS fallback",
                    extra={"n_stocks": len(common), "n_factors": len(exposures.columns), "method": "OLS_fallback"},
                )
                return pd.Series(f, index=exposures.columns)
            except np.linalg.LinAlgError:
                logger.warning("Barra factor return: both WLS and OLS failed, returning empty Series")
                return pd.Series()

    def estimate_factor_covariance(
        self, factor_returns_df: pd.DataFrame, halflife: int = 168, eigenvalue_clip_pct: float = 0.05
    ) -> pd.DataFrame:
        """
        估计因子协方差矩阵 (机构级: EWMA + 特征值裁剪)
        Barra标准: halflife=168交易日(约8个月)，比特质方差半衰期更长
        因为因子收益时间序列更短且噪声更大，需要更长的记忆窗口

        Args:
            factor_returns_df: 因子收益时间序列 (T x K)
            halflife: EWMA半衰期
            eigenvalue_clip_pct: 特征值裁剪比例 (防止近零特征值导致逆矩阵不稳定)

        Returns:
            因子协方差矩阵 (K x K)
        """
        if factor_returns_df.empty:
            return pd.DataFrame()

        # EWMA协方差
        # decay=1-exp(-ln2/halflife)将半衰期转换为pandas ewm的alpha参数
        # halflife=168对应衰减因子λ≈0.9959，约8个月的历史数据贡献一半权重
        decay = 1 - np.exp(-np.log(2) / halflife)
        ewm_result = factor_returns_df.ewm(alpha=decay).cov()

        # pandas ewm().cov()返回MultiIndex (date, asset), 取最后一个时间截面
        if isinstance(ewm_result.index, pd.MultiIndex):
            last_date = ewm_result.index.get_level_values(0)[-1]
            cov = ewm_result.loc[last_date].values
        else:
            cov = ewm_result.values

        # 特征值裁剪：近零特征值会导致逆矩阵数值爆炸，在组合优化中产生极端权重
        # 阈值设为最大特征值的5%，足够小不影响正常结构，但能消除数值不稳定
        try:
            eigenvalues, eigenvectors = np.linalg.eigh(cov)
            max_eigenvalue = eigenvalues.max()
            clip_threshold = max_eigenvalue * eigenvalue_clip_pct
            eigenvalues = np.maximum(eigenvalues, clip_threshold)
            cov = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
        except np.linalg.LinAlgError:
            pass

        return pd.DataFrame(cov, index=factor_returns_df.columns, columns=factor_returns_df.columns)

    def estimate_idiosyncratic_variance(
        self, stock_returns: pd.DataFrame, factor_returns: pd.DataFrame, exposures: pd.DataFrame, halflife: int = 84
    ) -> pd.Series:
        """
        估计特质方差 (机构级: 从残差估计, 分行业EWMA)
        Barra标准: halflife=84交易日(约4个月)，短于因子协方差半衰期
        因为个股特质波动变化比因子收益变化更快，需要更灵敏的响应

        Args:
            stock_returns: 股票收益 (T x N)
            factor_returns: 因子收益 (T x K)
            exposures: 因子暴露度 (N x K)
            halflife: EWMA半衰期

        Returns:
            特质方差序列 (N,)
        """
        # 计算残差: u = r - X*f
        try:
            predicted = exposures.values @ factor_returns.T.values
            residuals = stock_returns.T.values - predicted
        except (ValueError, np.linalg.LinAlgError):
            return pd.Series(np.nan, index=exposures.index)

        # EWMA方差
        decay = 1 - np.exp(-np.log(2) / halflife)
        residual_df = pd.DataFrame(residuals.T, index=stock_returns.index, columns=exposures.index)
        idio_var = residual_df.ewm(alpha=decay).var().iloc[-1]

        return idio_var.clip(lower=1e-10)

    def barra_decompose_risk(
        self, exposures: pd.DataFrame, factor_cov: pd.DataFrame, idio_var: pd.Series
    ) -> dict[str, Any]:
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
            "factor_risk": factor_risk,
            "idiosyncratic_risk": idio_risk,
            "total_risk": total_risk,
            "factor_risk_pct": factor_risk / total_risk if np.any(total_risk > 0) else None,
        }

    # ==================== 3. VaR和CVaR (ADD 10.4节) ====================

    def historical_var(self, returns: pd.Series, confidence: float = 0.95, window: int = 252) -> float:
        """
        历史模拟法VaR (ADD 10.4节)
        """
        if len(returns) < window:
            window = len(returns)
        recent_returns = returns.iloc[-window:]
        return -np.percentile(recent_returns, (1 - confidence) * 100)

    def parametric_var(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """
        参数法VaR (ADD 10.4节)
        VaR = -μ - z_α * σ
        """
        from scipy.stats import norm

        mu = returns.mean()
        sigma = returns.std()
        z = norm.ppf(confidence)
        return -(mu - z * sigma)

    def conditional_var(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """
        CVaR/ES (ADD 10.4节)
        E[-R | R < -VaR]
        """
        var = self.historical_var(returns, confidence)
        tail_returns = returns[returns < -var]
        if len(tail_returns) == 0:
            return var
        return -tail_returns.mean()

    def monte_carlo_var(
        self, returns: pd.Series, confidence: float = 0.95, n_simulations: int = 10000, horizon: int = 1
    ) -> float:
        """
        蒙特卡洛VaR
        """
        mu = returns.mean()
        sigma = returns.std()

        simulated = np.random.normal(mu, sigma, (n_simulations, horizon))
        simulated_returns = simulated.sum(axis=1)

        return -np.percentile(simulated_returns, (1 - confidence) * 100)

    def student_t_var(self, returns: pd.Series, confidence: float = 0.95, df: float | None = None) -> float:
        """
        Student-t分布VaR
        比正态分布更好地捕捉厚尾特征
        A股收益率峰度显著高于正态分布，用t分布可避免VaR低估

        Args:
            returns: 收益率序列
            confidence: 置信水平
            df: 自由度(不提供则自动估计)
        """
        if df is None:
            # 用矩估计法估计自由度
            kurt = returns.kurtosis()
            if kurt > 0:
                df = 6.0 / kurt + 4  # 超额峰度 = 6/(df-4)，反解自由度
                df = max(df, 4.5)  # 至少4.5自由度 — 低于4时t分布方差无定义
            else:
                df = 30.0  # 峰度接近0时t分布退化为正态

        mu = returns.mean()
        sigma = returns.std()
        t_quantile = sp_stats.t.ppf(1 - confidence, df=df)
        # Student-t的VaR缩放因子：调整t分布比正态更宽的分布到等方差尺度
        scale = sigma * np.sqrt((df - 2) / df)
        return -(mu + t_quantile * scale)

    def copula_tail_dependence(
        self, returns_a: pd.Series, returns_b: pd.Series, threshold: float = 0.05
    ) -> dict[str, float]:
        """
        Copula尾部依赖估计
        衡量两个资产在极端情况下的共同运动程度
        线性相关系数只度量线性关系且对尾部不敏感，
        危机期间相关性系统性上升(相关性突变)，尾部依赖能直接捕捉这一现象

        Args:
            returns_a: 资产A收益率
            returns_b: 资产B收益率
            threshold: 尾部阈值 — 0.05对应最极端5%的观测，兼顾样本量和尾部敏感性
        """
        common_idx = returns_a.index.intersection(returns_b.index)
        a = returns_a.loc[common_idx]
        b = returns_b.loc[common_idx]

        # 下尾依赖: P(Y < F_Y^{-1}(u) | X < F_X^{-1}(u))
        a_rank = a.rank(pct=True)
        b_rank = b.rank(pct=True)

        # 下尾(左尾)
        both_lower = ((a_rank <= threshold) & (b_rank <= threshold)).sum()
        a_lower = (a_rank <= threshold).sum()
        lower_tail_dep = both_lower / a_lower if a_lower > 0 else 0

        # 上尾(右尾)
        both_upper = ((a_rank >= 1 - threshold) & (b_rank >= 1 - threshold)).sum()
        a_upper = (a_rank >= 1 - threshold).sum()
        upper_tail_dep = both_upper / a_upper if a_upper > 0 else 0

        return {
            "lower_tail_dependence": round(lower_tail_dep, 4),
            "upper_tail_dependence": round(upper_tail_dep, 4),
            "asymmetry": round(lower_tail_dep - upper_tail_dep, 4),  # A股通常下尾>上尾：暴跌时同跌强于暴涨时同涨
        }

    def liquidity_adjusted_var(
        self,
        returns: pd.Series,
        position_size: float,
        daily_volume: float,
        spread: float = 0.001,  # A股典型买卖价差约10bp
        confidence: float = 0.95,
    ) -> dict[str, float]:
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
        impact_cost = 0.1 * np.sqrt(max(participation_rate, 0))  # 平方根法则：冲击成本与参与率的平方根成正比

        lvar = var + spread_cost + impact_cost

        return {
            "var": round(var, 6),
            "spread_cost": round(spread_cost, 6),
            "impact_cost": round(impact_cost, 6),
            "lvar": round(lvar, 6),
            "participation_rate": round(participation_rate, 4),
        }

    # ==================== 4. 组合风险计算 ====================

    def portfolio_var(self, weights: np.ndarray, cov_matrix: np.ndarray) -> float:
        """组合方差: w'Σw"""
        return weights @ cov_matrix @ weights

    def portfolio_volatility(self, weights: np.ndarray, cov_matrix: np.ndarray) -> float:
        """组合波动率"""
        return np.sqrt(self.portfolio_var(weights, cov_matrix))

    def marginal_risk_contribution(self, weights: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """
        边际风险贡献 (MRC)
        MRC_i = (Σw)_i / σ_p
        """
        portfolio_vol = self.portfolio_volatility(weights, cov_matrix)
        if portfolio_vol == 0:
            return np.zeros(len(weights))
        return (cov_matrix @ weights) / portfolio_vol

    def risk_contribution(self, weights: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """
        风险贡献 (RC)
        RC_i = w_i * MRC_i
        """
        mrc = self.marginal_risk_contribution(weights, cov_matrix)
        return weights * mrc

    def risk_contribution_pct(self, weights: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """风险贡献百分比"""
        rc = self.risk_contribution(weights, cov_matrix)
        total = rc.sum()
        if total == 0:
            return np.zeros(len(weights))
        return rc / total

    # ==================== 5. VaR回测 (突破率检验) ====================

    def backtest_var(
        self, returns: pd.Series, confidence: float = 0.95, window: int = 252, method: str = "historical"
    ) -> dict[str, Any]:
        """
        VaR回测: 滚动VaR+突破率统计+Kupiec POF检验+Christoffersen独立性检验

        Args:
            returns: 收益率序列 (时间索引)
            confidence: VaR置信水平
            window: 滚动窗口长度
            method: VaR方法 ('historical', 'parametric')

        Returns:
            突破率统计、Kupiec检验、Christoffersen检验结果
        """
        T: int = len(returns)
        if window + 10 > T:
            return {"error": "Insufficient data for VaR backtest"}

        var_series = pd.Series(np.nan, index=returns.index)
        violations = pd.Series(0, index=returns.index)

        for t in range(window, T):
            hist = returns.iloc[t - window : t]
            if method == "historical":
                var_t: float = -np.percentile(hist, (1 - confidence) * 100)
            else:
                var_t = -(hist.mean() - sp_stats.norm.ppf(confidence) * hist.std())

            var_series.iloc[t] = var_t
            # 突破: 实际损失 > VaR (即 return < -VaR)
            if returns.iloc[t] < -var_t:
                violations.iloc[t] = 1

        # 有效突破统计 (去掉NaN)
        valid = ~var_series.isna()
        n_violations: int = violations[valid].sum()
        n_total: int = valid.sum()
        empirical_rate: float = n_violations / n_total if n_total > 0 else 0
        expected_rate: float = 1 - confidence

        # Kupiec POF检验 (比例失效检验)
        kupiec: dict[str, Any] = self._kupiec_pof_test(n_violations, n_total, expected_rate)

        # Christoffersen独立性检验
        christoffersen: dict[str, Any] = self._christoffersen_independence_test(violations[valid])

        logger.info(
            "VaR backtest completed",
            extra={
                "n_violations": int(n_violations),
                "n_total": int(n_total),
                "empirical_rate": round(empirical_rate, 4),
                "expected_rate": round(expected_rate, 4),
                "method": method,
                "confidence": confidence,
                "var_adequate": kupiec["p_value"] > 0.05 and christoffersen["p_value"] > 0.05,
            },
        )

        return {
            "n_violations": int(n_violations),
            "n_observations": int(n_total),
            "expected_violations": round(expected_rate * n_total, 1),
            "empirical_rate": round(empirical_rate, 4),
            "expected_rate": round(expected_rate, 4),
            "kupiec_pof": kupiec,
            "christoffersen_independence": christoffersen,
            "var_adequate": kupiec["p_value"] > 0.05
            and christoffersen["p_value"] > 0.05,  # 两检验均不拒绝才认为VaR模型充分
        }

    def _kupiec_pof_test(self, n_violations: int, n_total: int, expected_rate: float) -> dict[str, Any]:
        """
        Kupiec比例失效检验 (POF)
        H0: 突破率 = 1 - confidence
        LR_POF = -2 * ln(p0^n0 * p1^n1) + 2 * ln(p_hat^n0 * (1-p_hat)^n1)
        """
        if n_total == 0 or n_violations == 0 or n_violations == n_total:
            return {"lr_stat": np.nan, "p_value": np.nan, "reject": None}

        p0: float = expected_rate
        p_hat: float = n_violations / n_total
        n1: int = n_violations
        n0: int = n_total - n_violations

        log_h0: float = n0 * np.log(1 - p0) + n1 * np.log(p0)
        log_h1: float = n0 * np.log(1 - p_hat) + n1 * np.log(p_hat)
        lr: float = -2 * (log_h0 - log_h1)

        from scipy.stats import chi2

        p_value: float = 1 - chi2.cdf(lr, df=1)

        logger.info(
            "Kupiec POF test completed",
            extra={
                "n_violations": n_violations,
                "n_total": n_total,
                "expected_rate": round(expected_rate, 4),
                "empirical_rate": round(p_hat, 4),
                "lr_stat": round(lr, 4),
                "p_value": round(p_value, 4),
                "reject": p_value < 0.05,
            },
        )

        return {
            "lr_stat": round(lr, 4),
            "p_value": round(p_value, 4),
            "reject": p_value < 0.05,
        }

    def _christoffersen_independence_test(self, violations: pd.Series) -> dict[str, Any]:
        """
        Christoffersen独立性检验
        检验突破是否独立 (非聚集)
        基于转移概率的似然比检验
        """
        v = violations.values
        n: int = len(v)
        if n < 10:
            return {"lr_stat": np.nan, "p_value": np.nan, "reject": None}

        # 计算转移计数
        n00: int = 0
        n01: int = 0
        n10: int = 0
        n11: int = 0
        for t in range(1, n):
            if v[t - 1] == 0 and v[t] == 0:
                n00 += 1
            elif v[t - 1] == 0 and v[t] == 1:
                n01 += 1
            elif v[t - 1] == 1 and v[t] == 0:
                n10 += 1
            else:
                n11 += 1

        # 无约束模型似然
        p01: float = n01 / (n00 + n01) if (n00 + n01) > 0 else 0
        p11: float = n11 / (n10 + n11) if (n10 + n11) > 0 else 0

        # 约束模型似然 (独立性: p01 = p11)
        n_v: int = v.sum()
        p: float = n_v / n if n > 0 else 0

        # 对数似然
        eps: float = 1e-10
        log_unconstrained: float = 0
        if n00 > 0:
            log_unconstrained += n00 * np.log(max(1 - p01, eps))
        if n01 > 0:
            log_unconstrained += n01 * np.log(max(p01, eps))
        if n10 > 0:
            log_unconstrained += n10 * np.log(max(1 - p11, eps))
        if n11 > 0:
            log_unconstrained += n11 * np.log(max(p11, eps))

        log_constrained: float = 0
        if (n - n_v) > 0:
            log_constrained += (n - n_v) * np.log(max(1 - p, eps))
        if n_v > 0:
            log_constrained += n_v * np.log(max(p, eps))

        lr: float = -2 * (log_constrained - log_unconstrained)
        lr = max(lr, 0)  # 数值保护：有限样本下似然比统计量理论上非负，浮点误差可能导致微小负值

        from scipy.stats import chi2

        p_value: float = 1 - chi2.cdf(lr, df=1)

        logger.info(
            "Christoffersen independence test completed",
            extra={
                "n_observations": n,
                "n_violations": int(n_v),
                "transition_01": round(p01, 4),
                "transition_11": round(p11, 4),
                "lr_stat": round(lr, 4),
                "p_value": round(p_value, 4),
                "reject": p_value < 0.05,
            },
        )

        return {
            "lr_stat": round(lr, 4),
            "p_value": round(p_value, 4),
            "reject": p_value < 0.05,
            "transition_01": round(p01, 4),
            "transition_11": round(p11, 4),
        }


# ==================== Newey-West 调整 ====================


def newey_west_se(series: pd.Series, max_lags: int | None = None, auto_lag_select: str = "bartlett") -> float:
    """
    Newey-West标准误 (机构级: 修正序列自相关导致的t统计量高估)
    IC序列通常有显著自相关，朴素t统计量会高估显著性
    不做NW调整可能导致因子IC显著性被虚增，误选无效因子

    Args:
        series: 时间序列 (如IC序列)
        max_lags: 最大滞后期数, None则自动选择
        auto_lag_select: 自动选择方法 'bartlett' = n^(1/3), 'newey_west' = floor(4*(T/100)^(2/9))

    Returns:
        Newey-West调整后的标准误
    """
    series = series.dropna()
    T = len(series)
    if T < 2:
        return np.nan

    mean = series.mean()
    gamma0 = ((series - mean) ** 2).mean()

    # 自动选择滞后期
    # Bartlett核取n^(1/3)是经典选择，平衡偏差与方差
    if max_lags is None:
        max_lags = int(T ** (1 / 3)) if auto_lag_select == "bartlett" else int(4 * (T / 100) ** (2 / 9))
        max_lags = max(1, max_lags)

    # Newey-West核权重 (Bartlett核)：线性衰减权重，lag越大权重越小
    # 乘以2是因为协方差项在方差公式中出现两次(对称性)
    nw_var = gamma0
    for lag in range(1, max_lags + 1):
        weight = 1 - lag / (max_lags + 1)
        gamma_lag = ((series.iloc[lag:].values - mean) * (series.iloc[:-lag].values - mean)).mean()
        nw_var += 2 * weight * gamma_lag

    return np.sqrt(max(nw_var, 0) / T)


def newey_west_tstat(series: pd.Series, max_lags: int | None = None) -> float:
    """
    Newey-West调整t统计量

    Args:
        series: 时间序列 (如IC序列)
        max_lags: 最大滞后期数

    Returns:
        NW调整t统计量
    """
    se = newey_west_se(series, max_lags)
    if se is None or se == 0 or np.isnan(se):
        return 0.0
    return series.mean() / se
