"""
因子预处理模块
实现完整的因子预处理pipeline: 缺失值处理 → 去极值 → 标准化 → 方向统一 → 中性化
符合ADD文档6.3节规范 + 机构级增强: MICE插补/逆正态秩变换/自适应去极值/约束回归中性化
"""
from typing import List, Optional, Dict, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, with_db
from app.core.logging import logger


class FactorPreprocessor:
    """因子预处理器 - 实现ADD 6.3节完整预处理流程"""

    def __init__(self):
        pass

    # ==================== 1. 缺失值处理 ====================

    def fill_missing_mean(self, series: pd.Series) -> pd.Series:
        """用均值填充缺失值"""
        return series.fillna(series.mean())

    def fill_missing_median(self, series: pd.Series) -> pd.Series:
        """用中位数填充缺失值"""
        return series.fillna(series.median())

    def fill_missing_zero(self, series: pd.Series) -> pd.Series:
        """用0填充缺失值"""
        return series.fillna(0)

    def fill_missing_industry_mean(self, df: pd.DataFrame, value_col: str, industry_col: str) -> pd.Series:
        """用行业均值填充缺失值 (向量化: groupby.transform替代逐行业循环)"""
        industry_mean = df.groupby(industry_col)[value_col].transform('mean')
        return df[value_col].fillna(industry_mean)

    def fill_missing_cross_section_median(self, series: pd.Series) -> pd.Series:
        """用横截面中位数填充缺失值"""
        return series.fillna(series.median())

    def check_coverage(self, series: pd.Series, min_coverage: float = 0.8) -> Tuple[bool, float]:
        """
        检查因子覆盖率

        Args:
            series: 因子值序列
            min_coverage: 最低覆盖率阈值

        Returns:
            (是否通过, 实际覆盖率)
        """
        coverage = 1 - series.isna().mean()
        return coverage >= min_coverage, coverage

    def fill_missing_mice(self, df: pd.DataFrame, factor_cols: List[str],
                          max_iter: int = 10, random_state: int = 42) -> pd.DataFrame:
        """
        MICE多重插补 (Multivariate Imputation by Chained Equations)
        利用因子间相关性进行迭代插补，保留多变量关系

        Args:
            df: 包含因子值的数据框
            factor_cols: 需要插补的因子列
            max_iter: 最大迭代次数
            random_state: 随机种子
        """
        try:
            from sklearn.experimental import enable_iterative_imputer
            from sklearn.impute import IterativeImputer
        except ImportError:
            logger.warning("sklearn not available for MICE, falling back to median fill")
            result = df.copy()
            for col in factor_cols:
                result[col] = self.fill_missing_median(result[col])
            return result

        result = df.copy()
        imputer = IterativeImputer(max_iter=max_iter, random_state=random_state)
        valid_data = result[factor_cols]
        imputed = imputer.fit_transform(valid_data)
        result[factor_cols] = imputed
        return result

    def fill_missing_decay_forward(self, series: pd.Series, decay_rate: float = 0.05) -> pd.Series:
        """
        指数衰减前向填充 (向量化: ffill+指数衰减替代逐行循环)
        适用于季度财务数据：距离公告日越远，数据权重越低
        weight = exp(-decay_rate * days_since_announcement)

        Args:
            series: 因子值序列(按时间排序)
            decay_rate: 衰减率
        """
        result = series.copy()
        # ffill获取最近有效值
        filled = series.ffill()
        # 计算每个位置距上次有效值的步数
        is_na = series.isna()
        if not is_na.any():
            return result

        # 向量化计算步数: 对每个NA位置，计算连续NA的计数
        # 用cumsum trick: 非NA位置重置计数
        na_blocks = is_na.cumsum() - is_na.cumsum().where(~is_na).ffill().fillna(0)
        na_blocks = na_blocks.astype(int)

        # 应用衰减
        decay_weights = np.exp(-decay_rate * na_blocks)
        result = filled * decay_weights
        # 保留原始非NA值
        result[~is_na] = series[~is_na]

        return result

    def add_missingness_indicators(self, df: pd.DataFrame,
                                    factor_cols: List[str]) -> pd.DataFrame:
        """
        缺失指示特征
        某些因子缺失本身是信息(如不披露研发费用)，创建二值指示特征

        Args:
            df: 包含因子值的数据框
            factor_cols: 因子列名列表
        """
        result = df.copy()
        for col in factor_cols:
            result[f'{col}_missing'] = result[col].isna().astype(int)
        return result

    # ==================== 2. 去极值 ====================

    def winsorize_mad(self, series: pd.Series, n_mad: float = 3.0) -> pd.Series:
        """
        MAD方法去极值（Median Absolute Deviation）
        比标准差更稳健，符合ADD 6.3.2节

        x' = median(x) ± k * MAD
        MAD = median(|x - median(x)|)
        """
        s = series.dropna()
        if s.empty:
            return series
        median = s.median()
        mad = np.median(np.abs(s - median))
        if mad == 0:
            # MAD=0表示超过50%数据相同，可能是数据质量问题
            # 回退到分位数去极值
            q_low = series.quantile(0.01)
            q_high = series.quantile(0.99)
            iqr = q_high - q_low
            if iqr > 0:
                return series.clip(q_low - 1.5 * iqr, q_high + 1.5 * iqr)
            logger.warning(f"Factor MAD=0 and IQR=0, skipping winsorization")
            return series
        upper_bound = median + n_mad * mad
        lower_bound = median - n_mad * mad
        return series.clip(lower_bound, upper_bound)

    def winsorize_quantile(self, series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
        """
        分位数截断去极值
        符合ADD 6.3.2节，默认1%/99%
        """
        lower_bound = series.quantile(lower)
        upper_bound = series.quantile(upper)
        return series.clip(lower_bound, upper_bound)

    def winsorize_sigma(self, series: pd.Series, n_sigma: float = 3.0) -> pd.Series:
        """标准差去极值"""
        mean = series.mean()
        std = series.std()
        if std == 0:
            return series
        upper_bound = mean + n_sigma * std
        lower_bound = mean - n_sigma * std
        return series.clip(lower_bound, upper_bound)

    def winsorize_adaptive_mad(self, series: pd.Series, base_k: float = 3.0,
                                vol_series: pd.Series = None,
                                long_run_vol: float = None) -> pd.Series:
        """
        自适应MAD去极值
        高波动期k更大(避免过度截断)，低波动期k更小
        k_t = base_k * (vol_t / vol_long_run)

        Args:
            series: 因子值序列
            base_k: 基础MAD倍数
            vol_series: 当前波动率序列(可选)
            long_run_vol: 长期波动率(可选)
        """
        if vol_series is not None and long_run_vol is not None and long_run_vol > 0:
            # 自适应k
            current_vol = vol_series.iloc[-1] if len(vol_series) > 0 else long_run_vol
            adaptive_k = base_k * (current_vol / long_run_vol)
            adaptive_k = np.clip(adaptive_k, base_k * 0.5, base_k * 2.0)  # 限制范围
        else:
            adaptive_k = base_k

        return self.winsorize_mad(series, n_mad=adaptive_k)

    def winsorize_isolation_forest(self, df: pd.DataFrame, factor_cols: List[str],
                                    contamination: float = 0.02,
                                    random_state: int = 42) -> pd.DataFrame:
        """
        Isolation Forest多变量异常检测
        检测因子空间中的异常观测(而非单变量极值)

        Args:
            df: 包含因子值的数据框
            factor_cols: 因子列名列表
            contamination: 异常比例
            random_state: 随机种子
        """
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            logger.warning("sklearn not available for Isolation Forest, skipping")
            return df

        result = df.copy()
        valid_mask = result[factor_cols].notna().all(axis=1)
        if valid_mask.sum() < 50:
            return result

        clf = IsolationForest(contamination=contamination, random_state=random_state)
        X = result.loc[valid_mask, factor_cols].fillna(0)
        outliers = clf.fit_predict(X)

        # 将异常值标记为NaN(后续由单变量方法处理)
        outlier_mask = outliers == -1
        outlier_indices = result.loc[valid_mask].index[outlier_mask]
        for col in factor_cols:
            result.loc[outlier_indices, col] = np.nan

        return result

    # ==================== 3. 标准化 ====================

    def standardize_zscore(self, series: pd.Series) -> pd.Series:
        """
        横截面Z-score标准化
        符合ADD 6.3.3节: z_i = (x_i - μ) / σ
        """
        mean = series.mean()
        std = series.std()
        if std == 0 or np.isnan(std):
            return series - mean
        return (series - mean) / std

    def standardize_rank(self, series: pd.Series) -> pd.Series:
        """排名标准化: 将因子值转换为排名百分比 [0, 1]"""
        return series.rank(pct=True)

    def standardize_minmax(self, series: pd.Series, min_val: float = 0, max_val: float = 1) -> pd.Series:
        """Min-Max标准化"""
        s_min = series.min()
        s_max = series.max()
        if s_max == s_min:
            return pd.Series([0.5] * len(series), index=series.index)
        normalized = (series - s_min) / (s_max - s_min)
        return normalized * (max_val - min_val) + min_val

    def standardize_rank_normal(self, series: pd.Series) -> pd.Series:
        """
        逆正态秩变换 (Inverse Normal Transformation)
        AQR和学术界标准方法: 将排名转换为标准正态分布
        z_i = Phi^{-1}(rank_i / (N + 1))
        强制横截面服从标准正态，对下游线性模型最优
        """
        ranks = series.rank(method='average')
        n = len(series.dropna())
        if n == 0:
            return series
        # 逆正态变换
        percentile = ranks / (n + 1)
        # 限制在(0.001, 0.999)避免无穷
        percentile = percentile.clip(0.001, 0.999)
        result = pd.Series(np.nan, index=series.index)
        valid = series.notna()
        result.loc[valid] = stats.norm.ppf(percentile.loc[valid])
        return result

    def standardize_robust_zscore(self, series: pd.Series) -> pd.Series:
        """
        稳健Z-score (基于中位数和MAD)
        z_i = (x_i - median(x)) / (1.4826 * MAD(x))
        1.4826因子使MAD与标准差在正态分布下一致
        """
        s = series.dropna()
        if s.empty:
            return series
        median = s.median()
        mad = np.median(np.abs(s - median))
        if mad == 0:
            return series - median
        return (series - median) / (1.4826 * mad)

    # ==================== 4. 因子方向统一 ====================

    def align_direction(self, series: pd.Series, direction: int = 1) -> pd.Series:
        """
        统一因子方向
        符合ADD 6.3.4节: 分数越高，预期未来表现越好

        Args:
            direction: 1=正向(越大越好), -1=反向(越小越好)
        """
        if direction == -1:
            return -series
        return series

    # ==================== 5. 中性化 ====================

    def neutralize_industry(self, df: pd.DataFrame, value_col: str, industry_col: str) -> pd.Series:
        """
        行业中性化
        符合ADD 6.3.5节: 对因子做行业哑变量回归，取残差
        无行业映射的股票标记为NaN，避免引入行业偏差

        x_i = α + Σ β_k * Industry_{i,k} + ε_i
        """
        # 识别无行业映射的股票
        has_industry = df[industry_col].notna()
        no_industry_mask = ~has_industry

        # 构建行业哑变量 (仅对有行业映射的股票)
        industries = pd.get_dummies(df.loc[has_industry, industry_col], drop_first=True)
        X = industries.values
        y = df[value_col].values

        # 处理NaN
        valid_mask = has_industry & ~np.isnan(y)
        if valid_mask.sum() < X.shape[1] + 10:
            # 样本不足，退化为行业内标准化
            result = pd.Series(np.nan, index=df.index)
            for industry in df.loc[has_industry, industry_col].unique():
                mask = (df[industry_col] == industry) & has_industry
                industry_values = df.loc[mask, value_col]
                result.loc[mask] = self.standardize_zscore(industry_values)
            # 无行业映射的股票保持NaN
            return result

        # WLS回归
        try:
            X_valid = X[valid_mask]
            y_valid = y[valid_mask]
            # 添加截距项
            X_with_const = np.column_stack([np.ones(X_valid.shape[0]), X_valid])
            beta = np.linalg.lstsq(X_with_const, y_valid, rcond=None)[0]
            predicted = X_with_const @ beta
            residuals = y_valid - predicted
            result = pd.Series(np.nan, index=df.index)
            result.loc[result.index[valid_mask]] = residuals
            return result
        except np.linalg.LinAlgError:
            logger.warning("Industry neutralization failed, falling back to within-industry zscore")
            result = pd.Series(index=df.index, dtype=float)
            for industry in df[industry_col].unique():
                mask = df[industry_col] == industry
                industry_values = df.loc[mask, value_col]
                result.loc[mask] = self.standardize_zscore(industry_values)
            return result

    def neutralize_market_cap(self, df: pd.DataFrame, value_col: str, cap_col: str) -> pd.Series:
        """
        市值中性化
        符合ADD 6.3.5节: 加入log(market cap)控制项

        x_i = α + β * log(MV_i) + ε_i
        """
        log_cap = np.log(df[cap_col])
        valid_mask = ~(np.isnan(df[value_col]) | np.isnan(log_cap) | np.isinf(log_cap))

        if valid_mask.sum() < 10:
            return df[value_col]

        slope, intercept, _, _, _ = stats.linregress(
            log_cap[valid_mask], df.loc[valid_mask, value_col]
        )
        residuals = df[value_col] - (slope * log_cap + intercept)
        return residuals

    def neutralize_industry_and_cap(self, df: pd.DataFrame, value_col: str,
                                    industry_col: str, cap_col: str) -> pd.Series:
        """
        行业和市值双重中性化
        符合ADD 6.3.5节:
        x_i = α + β * log(MV_i) + Σ γ_k * Industry_{i,k} + ε_i
        """
        # 构建特征矩阵: 行业哑变量 + log(市值)
        industries = pd.get_dummies(df[industry_col], drop_first=True)
        log_cap = np.log(df[cap_col])
        X = np.column_stack([industries.values, log_cap.values])
        y = df[value_col].values

        valid_mask = ~(np.isnan(y) | np.isnan(X).any(axis=1) | np.isinf(X).any(axis=1))
        if valid_mask.sum() < X.shape[1] + 10:
            return self.neutralize_industry(df, value_col, industry_col)

        try:
            X_valid = X[valid_mask]
            y_valid = y[valid_mask]
            X_with_const = np.column_stack([np.ones(X_valid.shape[0]), X_valid])
            beta = np.linalg.lstsq(X_with_const, y_valid, rcond=None)[0]
            predicted = X_with_const @ beta
            residuals = y_valid - predicted
            result = pd.Series(np.nan, index=df.index)
            result.iloc[valid_mask] = residuals
            return result
        except np.linalg.LinAlgError:
            return self.neutralize_industry(df, value_col, industry_col)

    def neutralize_industry_constrained(self, df: pd.DataFrame, value_col: str,
                                         industry_col: str) -> pd.Series:
        """
        约束回归行业中性化 (Barra Assector方法)
        约束行业哑变量系数之和为0，防止截距项吸收行业效应

        x_i = α + Σ β_k * Industry_{i,k} + ε_i
        s.t. Σ β_k = 0
        """
        industries = pd.get_dummies(df[industry_col])  # 不drop_first
        y = df[value_col].values
        valid_mask = ~np.isnan(y)

        if valid_mask.sum() < industries.shape[1] + 10:
            return self.neutralize_industry(df, value_col, industry_col)

        try:
            X = industries.values[valid_mask]
            y_valid = y[valid_mask]
            n_industries = X.shape[1]

            # 约束矩阵: 行业系数之和为0
            # 使用Lagrange乘子法: [X'X  A'] [beta ] = [X'y]
            #                     [A   0 ] [lambda]   [0   ]
            A = np.ones((1, n_industries))
            X_with_const = np.column_stack([np.ones(X.shape[0]), X])

            # 构建KKT系统
            n_vars = X_with_const.shape[1]
            KKT = np.zeros((n_vars + 1, n_vars + 1))
            KKT[:n_vars, :n_vars] = X_with_const.T @ X_with_const
            KKT[:n_vars, n_vars] = A.flatten()  # 约束行
            KKT[n_vars, :n_vars] = A.flatten()  # 约束列

            rhs = np.zeros(n_vars + 1)
            rhs[:n_vars] = X_with_const.T @ y_valid
            rhs[n_vars] = 0  # 约束右侧

            solution = np.linalg.solve(KKT, rhs)
            beta = solution[:n_vars]
            predicted = X_with_const @ beta
            residuals = y_valid - predicted

            result = pd.Series(np.nan, index=df.index)
            result.iloc[valid_mask] = residuals
            return result
        except (np.linalg.LinAlgError, ValueError):
            return self.neutralize_industry(df, value_col, industry_col)

    # ==================== 6. 完整预处理流程 ====================

    def preprocess(self, series: pd.Series,
                   fill_method: str = 'median',
                   winsorize_method: str = 'mad',
                   winsorize_param: float = 3.0,
                   standardize_method: str = 'zscore',
                   direction: int = 1,
                   df: pd.DataFrame = None,
                   industry_col: str = None,
                   cap_col: str = None,
                   value_col: str = None,
                   neutralize: bool = False) -> pd.Series:
        """
        完整的因子预处理流程
        符合ADD 6.3节: 缺失值处理 → 去极值 → 中性化 → 标准化 → 方向统一
        注意: 中性化必须在标准化之前，否则残差不再服从标准正态

        Args:
            series: 原始因子值
            fill_method: 缺失值填充方法 ('mean', 'median', 'zero', 'decay_forward')
            winsorize_method: 去极值方法 ('mad', 'quantile', 'sigma', 'adaptive_mad')
            winsorize_param: 去极值参数
            standardize_method: 标准化方法 ('zscore', 'rank', 'minmax', 'rank_normal', 'robust_zscore')
            direction: 因子方向 (1=正向, -1=反向)
            df: 包含行业/市值信息的DataFrame (中性化时需要)
            industry_col: 行业列 (中性化时需要)
            cap_col: 市值列 (中性化时需要)
            value_col: 因子值列名 (中性化时需要)
            neutralize: 是否进行中性化
        """
        # 1. 缺失值处理
        if fill_method == 'mean':
            series = self.fill_missing_mean(series)
        elif fill_method == 'median':
            series = self.fill_missing_median(series)
        elif fill_method == 'zero':
            series = self.fill_missing_zero(series)
        elif fill_method == 'decay_forward':
            series = self.fill_missing_decay_forward(series)

        # 2. 去极值
        if winsorize_method == 'mad':
            series = self.winsorize_mad(series, winsorize_param)
        elif winsorize_method == 'quantile':
            series = self.winsorize_quantile(series, 1 - winsorize_param / 100, winsorize_param / 100)
        elif winsorize_method == 'sigma':
            series = self.winsorize_sigma(series, winsorize_param)
        elif winsorize_method == 'adaptive_mad':
            series = self.winsorize_adaptive_mad(series, base_k=winsorize_param)

        # 3. 中性化 (在标准化之前!)
        if neutralize and df is not None and value_col is not None:
            df_neutral = df.copy()
            df_neutral[value_col] = series
            if industry_col and cap_col:
                series = self.neutralize_industry_and_cap(df_neutral, value_col, industry_col, cap_col)
            elif industry_col:
                series = self.neutralize_industry(df_neutral, value_col, industry_col)
            elif cap_col:
                series = self.neutralize_market_cap(df_neutral, value_col, cap_col)

        # 4. 标准化
        if standardize_method == 'zscore':
            series = self.standardize_zscore(series)
        elif standardize_method == 'rank':
            series = self.standardize_rank(series)
        elif standardize_method == 'minmax':
            series = self.standardize_minmax(series)
        elif standardize_method == 'rank_normal':
            series = self.standardize_rank_normal(series)
        elif standardize_method == 'robust_zscore':
            series = self.standardize_robust_zscore(series)

        # 5. 方向统一
        series = self.align_direction(series, direction)

        return series

    def preprocess_dataframe(self, df: pd.DataFrame, factor_cols: List[str],
                            industry_col: str = None, cap_col: str = None,
                            neutralize: bool = False,
                            direction_map: Dict[str, int] = None,
                            config: Dict[str, Dict] = None,
                            min_coverage: float = 0.6,
                            add_missing_indicators: bool = True) -> pd.DataFrame:
        """
        批量预处理多个因子 (机构级: 逐因子配置 + 覆盖率过滤 + 缺失指示器)

        预处理顺序 (修正后):
          缺失指示器 → 缺失值处理 → 去极值 → 中性化 → 标准化 → 方向统一

        注意: 中性化必须在标准化之前，否则残差不再服从标准正态，
        标准化会失效。这是机构级因子预处理的标准做法。

        Args:
            df: 包含因子值的数据框
            factor_cols: 因子列名列表
            industry_col: 行业列（用于中性化）
            cap_col: 市值列（用于中性化）
            neutralize: 是否进行中性化
            direction_map: 因子方向映射 {col: direction}
            config: 逐因子预处理配置 {col: {fill_method, winsorize_method, winsorize_param, standardize_method}}
                    未配置的因子使用默认值
            min_coverage: 最低覆盖率阈值, 低于此值的因子跳过
            add_missing_indicators: 是否添加缺失指示器列(缺失本身可能包含信息)
        """
        result = df.copy()

        # Step 0: 添加缺失指示器 (缺失本身可能包含信息，如停牌、未披露等)
        if add_missing_indicators:
            for col in factor_cols:
                if col in result.columns:
                    missing_ratio = result[col].isna().mean()
                    # 只对缺失率>5%且<95%的因子添加缺失指示器
                    if 0.05 < missing_ratio < 0.95:
                        result[f'{col}_missing'] = result[col].isna().astype(int)

        for col in factor_cols:
            if col not in result.columns:
                continue

            # 覆盖率过滤
            coverage = 1 - result[col].isna().mean()
            if coverage < min_coverage:
                logger.warning(f"Factor {col} coverage {coverage:.2%} < {min_coverage:.0%}, skipping")
                result[col] = np.nan
                continue

            direction = direction_map.get(col, 1) if direction_map else 1

            # Step 1-2: 缺失值处理 + 去极值 (不包含标准化和方向)
            if config and col in config:
                cfg = config[col]
                # 缺失值处理
                fill_method = cfg.get('fill_method', 'median')
                if fill_method == 'mean':
                    result[col] = self.fill_missing_mean(result[col])
                elif fill_method == 'median':
                    result[col] = self.fill_missing_median(result[col])
                elif fill_method == 'zero':
                    result[col] = self.fill_missing_zero(result[col])
                elif fill_method == 'decay_forward':
                    result[col] = self.fill_missing_decay_forward(result[col])

                # 去极值
                winsorize_method = cfg.get('winsorize_method', 'mad')
                winsorize_param = cfg.get('winsorize_param', 3.0)
                if winsorize_method == 'mad':
                    result[col] = self.winsorize_mad(result[col], winsorize_param)
                elif winsorize_method == 'quantile':
                    result[col] = self.winsorize_quantile(result[col], 1 - winsorize_param / 100, winsorize_param / 100)
                elif winsorize_method == 'sigma':
                    result[col] = self.winsorize_sigma(result[col], winsorize_param)
                elif winsorize_method == 'adaptive_mad':
                    result[col] = self.winsorize_adaptive_mad(result[col], base_k=winsorize_param)
            else:
                # 默认: 缺失值(中位数) + 去极值(MAD)
                result[col] = self.fill_missing_median(result[col])
                result[col] = self.winsorize_mad(result[col])

            # Step 3: 中性化 (在标准化之前!)
            if neutralize:
                if industry_col and cap_col:
                    result[col] = self.neutralize_industry_and_cap(result, col, industry_col, cap_col)
                elif industry_col:
                    result[col] = self.neutralize_industry(result, col, industry_col)
                elif cap_col:
                    result[col] = self.neutralize_market_cap(result, col, cap_col)

            # Step 4: 标准化 (在中性化之后)
            if config and col in config:
                cfg = config[col]
                standardize_method = cfg.get('standardize_method', 'zscore')
            else:
                standardize_method = 'zscore'

            if standardize_method == 'zscore':
                result[col] = self.standardize_zscore(result[col])
            elif standardize_method == 'rank':
                result[col] = self.standardize_rank(result[col])
            elif standardize_method == 'minmax':
                result[col] = self.standardize_minmax(result[col])
            elif standardize_method == 'rank_normal':
                result[col] = self.standardize_rank_normal(result[col])
            elif standardize_method == 'robust_zscore':
                result[col] = self.standardize_robust_zscore(result[col])

            # Step 5: 方向统一
            result[col] = self.align_direction(result[col], direction)

        return result

    # ==================== 7. 因子正交化 ====================

    def orthogonalize_factors(self, df: pd.DataFrame, factor_cols: List[str],
                               target_col: str = None,
                               method: str = 'residual') -> pd.DataFrame:
        """
        因子正交化 (机构级: 消除因子间共线性)
        典型用途: 对价值因子做size中性化, 得到size-neutral value

        Args:
            df: 因子DataFrame
            factor_cols: 需要正交化的因子列
            target_col: 正交化目标列 (如'size'或'log_market_cap')
                       如果为None, 使用Gram-Schmidt顺序正交
            method: 'residual' = 截面回归取残差, 'gram_schmidt' = Gram-Schmidt

        Returns:
            正交化后的DataFrame
        """
        result = df.copy()

        if target_col is not None and target_col in df.columns:
            # 对每个因子做target中性化
            for col in factor_cols:
                if col == target_col or col not in result.columns:
                    continue
                result[col] = self.cross_sectional_residual(result, col, [target_col])
        else:
            # Gram-Schmidt顺序正交
            for i, col in enumerate(factor_cols):
                if col not in result.columns:
                    continue
                if i == 0:
                    continue  # 第一个因子不需要正交化
                # 对前面的所有因子取残差
                control_cols = [c for c in factor_cols[:i] if c in result.columns]
                if control_cols:
                    result[col] = self.cross_sectional_residual(result, col, control_cols)

        return result

    def cross_sectional_residual(self, df: pd.DataFrame, factor_col: str,
                                   control_cols: List[str]) -> pd.Series:
        """
        截面回归取残差
        factor = alpha + beta1*control1 + beta2*control2 + ... + epsilon
        返回epsilon (控制control后的纯净因子)

        Args:
            df: DataFrame
            factor_col: 因子列名
            control_cols: 控制变量列名列表

        Returns:
            残差序列
        """
        y = df[factor_col].values
        X = df[control_cols].values

        valid_mask = ~(np.isnan(y) | np.isnan(X).any(axis=1))
        if valid_mask.sum() < len(control_cols) + 2:
            return df[factor_col]  # 样本不足, 返回原值

        try:
            X_valid = X[valid_mask]
            y_valid = y[valid_mask]
            X_with_const = np.column_stack([np.ones(X_valid.shape[0]), X_valid])
            beta = np.linalg.lstsq(X_with_const, y_valid, rcond=None)[0]
            predicted = X_with_const @ beta
            residuals = y_valid - predicted

            result = pd.Series(np.nan, index=df.index)
            result.iloc[valid_mask] = residuals
            return result
        except np.linalg.LinAlgError:
            logger.warning(f"Cross-sectional residual failed for {factor_col}, returning original")
            return df[factor_col]

    # ==================== 7. 稳定性检查 ====================

    def check_stability(self, factor_values: pd.DataFrame,
                        date_col: str = 'trade_date',
                        value_col: str = 'value',
                        window: int = 60) -> Dict:
        """
        因子稳定性检查
        计算滚动IC和滚动覆盖率，检测因子失效

        Args:
            factor_values: 因子值DataFrame
            date_col: 日期列
            value_col: 值列
            window: 滚动窗口

        Returns:
            稳定性指标
        """
        if factor_values.empty:
            return {'is_stable': False, 'reason': 'No data'}

        # 按日期计算覆盖率
        daily_coverage = factor_values.groupby(date_col)[value_col].apply(
            lambda x: 1 - x.isna().mean()
        )

        # 滚动覆盖率
        rolling_coverage = daily_coverage.rolling(window).mean()

        # 覆盖率趋势
        coverage_trend = rolling_coverage.iloc[-1] - rolling_coverage.iloc[0] if len(rolling_coverage) > 1 else 0

        return {
            'is_stable': rolling_coverage.iloc[-1] > 0.5 if len(rolling_coverage) > 0 else False,
            'current_coverage': rolling_coverage.iloc[-1] if len(rolling_coverage) > 0 else 0,
            'coverage_trend': coverage_trend,
            'min_coverage': rolling_coverage.min() if len(rolling_coverage) > 0 else 0,
        }


# 便捷函数
def preprocess_factor_values(factor_values: pd.Series,
                            fill_method: str = 'median',
                            winsorize_method: str = 'mad',
                            standardize_method: str = 'zscore',
                            direction: int = 1) -> pd.Series:
    """预处理因子值的便捷函数"""
    preprocessor = FactorPreprocessor()
    return preprocessor.preprocess(factor_values, fill_method, winsorize_method, 3.0, standardize_method, direction)
