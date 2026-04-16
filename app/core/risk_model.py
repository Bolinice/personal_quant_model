"""
Barra风格风险模型
实现因子暴露矩阵构建、截面回归、协方差矩阵估计、风险分解
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats
from app.core.logging import logger


class BarraRiskModel:
    """
    Barra风格风险模型

    收益分解: r = X*f + ε
    - X: 因子暴露矩阵 (N×K), N=股票数, K=因子数
    - f: 因子收益率 (K×1)
    - ε: 特质收益 (N×1)

    协方差矩阵: Σ = X * Σ_f * X' + D
    - Σ_f: 因子协方差矩阵 (K×K)
    - D: 特质方差矩阵 (N×N), 对角阵
    """

    # 风格因子定义
    STYLE_FACTORS = ['size', 'momentum', 'volatility', 'turnover', 'value', 'growth', 'quality']

    def __init__(self, half_life_factor: int = 90, half_life_specific: int = 60,
                 newey_west_lag: int = 2):
        """
        Args:
            half_life_factor: 因子协方差EWMA半衰期(天)
            half_life_specific: 特质方差EWMA半衰期(天)
            newey_west_lag: Newey-West调整的最大滞后期
        """
        self.half_life_factor = half_life_factor
        self.half_life_specific = half_life_specific
        self.newey_west_lag = newey_west_lag

        # 模型结果缓存
        self.factor_exposure = None   # 因子暴露矩阵
        self.factor_returns = None    # 因子收益率时间序列
        self.factor_cov = None        # 因子协方差矩阵
        self.specific_var = None      # 特质方差
        self.cov_matrix = None        # 完整协方差矩阵
        self.residuals = None         # 特质收益

    # ==================== 因子暴露矩阵构建 ====================

    def build_factor_exposure(self, returns_df: pd.DataFrame,
                              style_data: pd.DataFrame,
                              industry_data: pd.Series) -> pd.DataFrame:
        """
        构建因子暴露矩阵

        Args:
            returns_df: 收益率数据, columns=[trade_date, ts_code, pct_chg]
            style_data: 风格因子数据, index=ts_code, columns=风格因子名
            industry_data: 行业数据, index=ts_code, values=行业名

        Returns:
            因子暴露矩阵 DataFrame, index=ts_code, columns=因子名
        """
        stocks = style_data.index.tolist()
        industries = industry_data.reindex(stocks)

        # 1. 行业因子: 哑变量编码
        unique_industries = sorted(industries.dropna().unique())
        industry_cols = []
        industry_exposure = pd.DataFrame(0, index=stocks, columns=unique_industries)

        for stock in stocks:
            ind = industries.get(stock)
            if ind and ind in unique_industries:
                industry_exposure.loc[stock, ind] = 1

        # 去掉最后一列(避免共线性)，用最后一列作为基准
        if len(unique_industries) > 1:
            industry_exposure = industry_exposure.iloc[:, :-1]
        industry_cols = industry_exposure.columns.tolist()

        # 2. 风格因子: 标准化 + 行业中性化
        style_exposure = pd.DataFrame(index=stocks)
        available_styles = [s for s in self.STYLE_FACTORS if s in style_data.columns]

        for style in available_styles:
            values = style_data[style].reindex(stocks)
            # MAD去极值
            values = self._winsorize_mad(values)
            # Z-score标准化
            values = self._zscore(values)
            style_exposure[style] = values

        # 3. 合并因子暴露矩阵
        exposure = pd.concat([industry_exposure, style_exposure], axis=1)

        # 去掉全为NaN的行
        exposure = exposure.dropna(how='all')

        self.factor_exposure = exposure
        logger.info(f"Built factor exposure matrix: {exposure.shape[0]} stocks × {exposure.shape[1]} factors "
                    f"({len(industry_cols)} industry + {len(available_styles)} style)")

        return exposure

    # ==================== 截面回归 ====================

    def fit_factor_returns(self, returns: pd.Series,
                           exposure: pd.DataFrame = None,
                           weights: pd.Series = None) -> Dict:
        """
        截面回归求因子收益率 (WLS)

        r = X*f + ε
        f = (X'WX)^{-1} * X'Wr

        Args:
            returns: 当期收益率, index=ts_code
            exposure: 因子暴露矩阵, 默认用self.factor_exposure
            weights: 回归权重(市值加权), index=ts_code

        Returns:
            {'factor_returns': pd.Series, 'residuals': pd.Series}
        """
        if exposure is None:
            exposure = self.factor_exposure

        if exposure is None:
            raise ValueError("No factor exposure matrix available")

        # 对齐数据
        common_stocks = returns.index.intersection(exposure.index)
        # 去重
        common_stocks = common_stocks[~common_stocks.duplicated()]
        returns = returns[~returns.index.duplicated(keep='first')]
        exposure = exposure[~exposure.index.duplicated(keep='first')]
        if len(common_stocks) < exposure.shape[1] + 10:
            logger.warning(f"Too few stocks for regression: {len(common_stocks)}")
            return {'factor_returns': pd.Series(), 'residuals': returns}

        r = returns.reindex(common_stocks)
        X = exposure.reindex(common_stocks)

        # 填充NaN
        X = X.fillna(0)
        r = r.fillna(0)

        # 构建权重矩阵 (默认等权)
        if weights is not None:
            w = weights.reindex(common_stocks).fillna(1.0)
            w = np.sqrt(w.abs())  # sqrt(市值) 作为WLS权重
        else:
            w = pd.Series(1.0, index=common_stocks)

        # WLS回归: f = (X'WX)^{-1} * X'Wr
        W = np.diag(w.values)
        XW = X.values.T @ W

        try:
            XtWX = XW @ W @ X.values
            XtWr = XW @ W @ r.values

            # 求解
            f = np.linalg.solve(XtWX, XtWr)
            factor_returns = pd.Series(f, index=X.columns)

            # 计算残差
            predicted = X.values @ f
            residuals = r.values - predicted
            residuals = pd.Series(residuals, index=common_stocks)

        except np.linalg.LinAlgError:
            logger.warning("Singular matrix in factor return regression, using pseudo-inverse")
            XtWX = XW @ W @ X.values
            XtWr = XW @ W @ r.values
            f = np.linalg.lstsq(XtWX, XtWr, rcond=None)[0]
            factor_returns = pd.Series(f, index=X.columns)
            predicted = X.values @ f
            residuals = pd.Series(r.values - predicted, index=common_stocks)

        return {
            'factor_returns': factor_returns,
            'residuals': residuals
        }

    def fit_factor_returns_series(self, returns_df: pd.DataFrame,
                                  exposure_df: pd.DataFrame = None,
                                  market_caps: pd.Series = None) -> pd.DataFrame:
        """
        对每个交易日做截面回归，得到因子收益率时间序列

        Args:
            returns_df: 收益率数据, columns=[trade_date, ts_code, pct_chg]
            exposure_df: 因子暴露矩阵(每期), index=ts_code
            market_caps: 市值数据, index=ts_code

        Returns:
            因子收益率时间序列 DataFrame
        """
        dates = sorted(returns_df['trade_date'].unique())
        all_factor_returns = []
        all_residuals = []

        for date in dates:
            # 当期收益率
            day_returns = returns_df[returns_df['trade_date'] == date].set_index('ts_code')['pct_chg'] / 100

            if len(day_returns) < 20:
                continue

            # 截面回归
            result = self.fit_factor_returns(day_returns, exposure_df, market_caps)

            if not result['factor_returns'].empty:
                fr = result['factor_returns']
                fr.name = date
                all_factor_returns.append(fr)

                res = result['residuals']
                res.name = date
                all_residuals.append(res)

        if not all_factor_returns:
            return pd.DataFrame()

        self.factor_returns = pd.DataFrame(all_factor_returns)
        self.residuals = all_residuals

        logger.info(f"Fitted factor returns for {len(self.factor_returns)} periods, "
                    f"{self.factor_returns.shape[1]} factors")

        return self.factor_returns

    # ==================== 协方差矩阵估计 ====================

    def estimate_factor_cov(self, factor_returns: pd.DataFrame = None) -> pd.DataFrame:
        """
        估计因子协方差矩阵 (EWMA + Newey-West调整)

        Args:
            factor_returns: 因子收益率时间序列

        Returns:
            因子协方差矩阵 DataFrame
        """
        if factor_returns is None:
            factor_returns = self.factor_returns

        if factor_returns is None or factor_returns.empty:
            raise ValueError("No factor returns available")

        # EWMA权重
        n_periods = len(factor_returns)
        decay = 1 - 0.5 ** (1 / self.half_life_factor)
        weights = np.array([(1 - decay) ** i for i in range(n_periods)])
        weights = weights[::-1]  # 最近的权重最大
        weights = weights / weights.sum()

        # 加权协方差
        K = factor_returns.shape[1]
        cov = np.zeros((K, K))

        for t in range(n_periods):
            r_t = factor_returns.iloc[t].values
            cov += weights[t] * np.outer(r_t, r_t)

        # Newey-West调整 (修正自相关)
        for lag in range(1, min(self.newey_west_lag + 1, n_periods)):
            gamma = np.zeros((K, K))
            for t in range(lag, n_periods):
                r_t = factor_returns.iloc[t].values
                r_t_lag = factor_returns.iloc[t - lag].values
                gamma += weights[t] * (np.outer(r_t, r_t_lag) + np.outer(r_t_lag, r_t))

            # Newey-West权重: 1 - lag/(L+1)
            nw_weight = 1 - lag / (self.newey_west_lag + 1)
            cov += nw_weight * gamma / 2

        # 确保正定
        cov = self._ensure_positive_definite(cov)

        self.factor_cov = pd.DataFrame(cov, index=factor_returns.columns,
                                        columns=factor_returns.columns)

        logger.info(f"Estimated factor covariance matrix: {K}×{K}")
        return self.factor_cov

    def estimate_specific_var(self, residuals: List[pd.Series] = None) -> pd.Series:
        """
        估计特质方差 (对角阵)

        Args:
            residuals: 特质收益时间序列列表

        Returns:
            特质方差 Series, index=ts_code
        """
        if residuals is None:
            residuals = self.residuals

        if not residuals:
            raise ValueError("No residuals available")

        # 合并所有期的残差
        all_residuals = pd.DataFrame(residuals).T

        # EWMA估计每只股票的特质方差
        n_periods = len(residuals)
        decay = 1 - 0.5 ** (1 / self.half_life_specific)
        weights = np.array([(1 - decay) ** i for i in range(n_periods)])
        weights = weights[::-1]
        weights = weights / weights.sum()

        specific_var = pd.Series(0.0, index=all_residuals.index)

        for t, res in enumerate(residuals):
            for stock in res.index:
                if stock in specific_var.index:
                    specific_var[stock] += weights[t] * res[stock] ** 2

        # 下限保护: 至少为全市场均值的5%
        mean_var = specific_var[specific_var > 0].mean()
        specific_var = specific_var.clip(lower=mean_var * 0.05)

        self.specific_var = specific_var
        logger.info(f"Estimated specific variance for {len(specific_var)} stocks")

        return specific_var

    def estimate_cov_matrix(self, exposure: pd.DataFrame = None,
                           factor_cov: pd.DataFrame = None,
                           specific_var: pd.Series = None) -> pd.DataFrame:
        """
        估计完整协方差矩阵

        Σ = X * Σ_f * X' + D

        Args:
            exposure: 因子暴露矩阵
            factor_cov: 因子协方差矩阵
            specific_var: 特质方差

        Returns:
            协方差矩阵 DataFrame
        """
        if exposure is None:
            exposure = self.factor_exposure
        if factor_cov is None:
            factor_cov = self.factor_cov
        if specific_var is None:
            specific_var = self.specific_var

        if any(x is None for x in [exposure, factor_cov, specific_var]):
            raise ValueError("Missing required inputs for covariance estimation")

        # 对齐股票
        common_stocks = exposure.index.intersection(specific_var.index)
        X = exposure.reindex(common_stocks).fillna(0).values
        Sigma_f = factor_cov.values
        D = np.diag(specific_var.reindex(common_stocks).fillna(specific_var.mean()).values)

        # Σ = X * Σ_f * X' + D
        Sigma = X @ Sigma_f @ X.T + D

        # 确保正定
        Sigma = self._ensure_positive_definite(Sigma)

        self.cov_matrix = pd.DataFrame(Sigma, index=common_stocks, columns=common_stocks)

        logger.info(f"Estimated covariance matrix: {len(common_stocks)}×{len(common_stocks)}")
        return self.cov_matrix

    # ==================== 风险分解 ====================

    def risk_decompose(self, weights: pd.Series,
                       exposure: pd.DataFrame = None,
                       factor_cov: pd.DataFrame = None,
                       specific_var: pd.Series = None) -> Dict:
        """
        风险分解: 总风险 = 行业风险 + 风格风险 + 特质风险

        Args:
            weights: 组合权重, index=ts_code

        Returns:
            风险分解结果
        """
        if exposure is None:
            exposure = self.factor_exposure
        if factor_cov is None:
            factor_cov = self.factor_cov
        if specific_var is None:
            specific_var = self.specific_var

        if any(x is None for x in [exposure, factor_cov, specific_var]):
            raise ValueError("Missing required inputs for risk decomposition")

        # 对齐
        common = weights.index.intersection(exposure.index).intersection(specific_var.index)
        w = weights.reindex(common).fillna(0).values
        X = exposure.reindex(common).fillna(0).values
        Sigma_f = factor_cov.values
        D = np.diag(specific_var.reindex(common).fillna(specific_var.mean()).values)

        # 组合因子暴露
        x_port = w @ X  # (K,)

        # 因子风险 = x_port' * Σ_f * x_port
        factor_risk = x_port @ Sigma_f @ x_port

        # 特质风险 = w' * D * w
        specific_risk = w @ D @ w

        # 总风险
        total_risk = factor_risk + specific_risk

        # 分解行业和风格风险
        industry_cols = [c for c in exposure.columns if c not in self.STYLE_FACTORS]
        style_cols = [c for c in exposure.columns if c in self.STYLE_FACTORS]

        industry_idx = [exposure.columns.get_loc(c) for c in industry_cols if c in exposure.columns]
        style_idx = [exposure.columns.get_loc(c) for c in style_cols if c in exposure.columns]

        # 行业风险
        if industry_idx:
            x_ind = x_port[industry_idx]
            Sigma_f_ind = Sigma_f[np.ix_(industry_idx, industry_idx)]
            industry_risk = x_ind @ Sigma_f_ind @ x_ind
        else:
            industry_risk = 0

        # 风格风险
        if style_idx:
            x_style = x_port[style_idx]
            Sigma_f_style = Sigma_f[np.ix_(style_idx, style_idx)]
            style_risk = x_style @ Sigma_f_style @ x_style
        else:
            style_risk = 0

        return {
            'total_risk': total_risk,
            'total_vol': np.sqrt(total_risk),
            'factor_risk': factor_risk,
            'industry_risk': industry_risk,
            'style_risk': style_risk,
            'specific_risk': specific_risk,
            'industry_pct': industry_risk / total_risk if total_risk > 0 else 0,
            'style_pct': style_risk / total_risk if total_risk > 0 else 0,
            'specific_pct': specific_risk / total_risk if total_risk > 0 else 0,
        }

    def calc_marginal_risk_contribution(self, weights: pd.Series,
                                         cov_matrix: pd.DataFrame = None) -> pd.Series:
        """
        计算边际风险贡献 (MRC)

        MRC_i = (Σ * w)_i / σ_p

        Args:
            weights: 组合权重
            cov_matrix: 协方差矩阵

        Returns:
            边际风险贡献 Series
        """
        if cov_matrix is None:
            cov_matrix = self.cov_matrix

        if cov_matrix is None:
            raise ValueError("No covariance matrix available")

        common = weights.index.intersection(cov_matrix.index)
        w = weights.reindex(common).fillna(0).values
        Sigma = cov_matrix.loc[common, common].values

        # 组合风险
        port_var = w @ Sigma @ w
        port_vol = np.sqrt(port_var) if port_var > 0 else 1e-8

        # 边际风险贡献
        mrc = (Sigma @ w) / port_vol

        # 风险贡献 = w * MRC
        rc = w * mrc

        return pd.Series(rc, index=common)

    def calc_portfolio_risk(self, weights: pd.Series,
                            cov_matrix: pd.DataFrame = None) -> Dict:
        """
        计算组合风险

        Args:
            weights: 组合权重

        Returns:
            组合风险指标
        """
        if cov_matrix is None:
            cov_matrix = self.cov_matrix

        if cov_matrix is None:
            raise ValueError("No covariance matrix available")

        common = weights.index.intersection(cov_matrix.index)
        w = weights.reindex(common).fillna(0).values
        Sigma = cov_matrix.loc[common, common].values

        port_var = w @ Sigma @ w
        port_vol = np.sqrt(port_var)

        # 风险贡献
        rc = self.calc_marginal_risk_contribution(weights, cov_matrix)

        return {
            'variance': port_var,
            'volatility': port_vol,
            'annual_volatility': port_vol * np.sqrt(252),
            'risk_contributions': rc,
        }

    # ==================== 辅助方法 ====================

    def _winsorize_mad(self, series: pd.Series, n_mad: float = 3.0) -> pd.Series:
        """MAD去极值"""
        s = series.dropna()
        if s.empty:
            return series
        median = s.median()
        mad = np.median(np.abs(s - median))
        if mad == 0:
            return series
        upper = median + n_mad * mad
        lower = median - n_mad * mad
        return series.clip(lower, upper)

    def _zscore(self, series: pd.Series) -> pd.Series:
        """Z-score标准化"""
        mean = series.mean()
        std = series.std()
        if std == 0 or np.isnan(std):
            return series - mean
        return (series - mean) / std

    def _ensure_positive_definite(self, matrix: np.ndarray, min_eigenvalue: float = 1e-8) -> np.ndarray:
        """确保矩阵正定"""
        eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        if np.all(eigenvalues > min_eigenvalue):
            return matrix

        # 修正负特征值
        eigenvalues = np.maximum(eigenvalues, min_eigenvalue)
        return eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
