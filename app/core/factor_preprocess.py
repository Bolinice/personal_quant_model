"""
因子预处理模块
实现缺失值处理、去极值、标准化、中性化等功能
"""
from typing import List, Optional, Dict, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, with_db
from app.core.logging import logger


class FactorPreprocessor:
    """因子预处理器"""

    def __init__(self):
        pass

    # ==================== 缺失值处理 ====================

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
        """用行业均值填充缺失值"""
        result = df[value_col].copy()
        for industry in df[industry_col].unique():
            mask = df[industry_col] == industry
            industry_mean = df.loc[mask, value_col].mean()
            result.loc[mask & df[value_col].isna()] = industry_mean
        return result

    # ==================== 去极值 ====================

    def winsorize_mad(self, series: pd.Series, n_mad: float = 3.0) -> pd.Series:
        """
        MAD方法去极值（Median Absolute Deviation）
        比标准差更稳健

        Args:
            series: 因子值序列
            n_mad: MAD倍数，默认3倍

        Returns:
            处理后的序列
        """
        median = series.median()
        mad = np.median(np.abs(series - median))

        if mad == 0:
            return series

        upper_bound = median + n_mad * mad
        lower_bound = median - n_mad * mad

        return series.clip(lower_bound, upper_bound)

    def winsorize_quantile(self, series: pd.Series, lower: float = 0.025, upper: float = 0.975) -> pd.Series:
        """
        分位数去极值

        Args:
            series: 因子值序列
            lower: 下分位数，默认2.5%
            upper: 上分位数，默认97.5%

        Returns:
            处理后的序列
        """
        lower_bound = series.quantile(lower)
        upper_bound = series.quantile(upper)

        return series.clip(lower_bound, upper_bound)

    def winsorize_sigma(self, series: pd.Series, n_sigma: float = 3.0) -> pd.Series:
        """
        标准差去极值

        Args:
            series: 因子值序列
            n_sigma: 标准差倍数

        Returns:
            处理后的序列
        """
        mean = series.mean()
        std = series.std()

        if std == 0:
            return series

        upper_bound = mean + n_sigma * std
        lower_bound = mean - n_sigma * std

        return series.clip(lower_bound, upper_bound)

    # ==================== 标准化 ====================

    def standardize_zscore(self, series: pd.Series) -> pd.Series:
        """
        Z-score标准化
        (x - mean) / std
        """
        mean = series.mean()
        std = series.std()

        if std == 0:
            return series - mean

        return (series - mean) / std

    def standardize_rank(self, series: pd.Series) -> pd.Series:
        """
        排名标准化
        将因子值转换为排名百分比 [0, 1]
        """
        return series.rank(pct=True)

    def standardize_minmax(self, series: pd.Series, min_val: float = 0, max_val: float = 1) -> pd.Series:
        """
        Min-Max标准化
        将因子值缩放到 [min_val, max_val] 区间
        """
        s_min = series.min()
        s_max = series.max()

        if s_max == s_min:
            return pd.Series([0.5] * len(series), index=series.index)

        normalized = (series - s_min) / (s_max - s_min)
        return normalized * (max_val - min_val) + min_val

    # ==================== 中性化 ====================

    def neutralize_industry(self, df: pd.DataFrame, value_col: str, industry_col: str) -> pd.Series:
        """
        行业中性化
        对每个行业内的因子值进行标准化，消除行业差异

        Args:
            df: 包含因子值和行业信息的数据框
            value_col: 因子值列名
            industry_col: 行业列名

        Returns:
            中性化后的因子值
        """
        result = pd.Series(index=df.index, dtype=float)

        for industry in df[industry_col].unique():
            mask = df[industry_col] == industry
            industry_values = df.loc[mask, value_col]
            result.loc[mask] = self.standardize_zscore(industry_values)

        return result

    def neutralize_market_cap(self, df: pd.DataFrame, value_col: str, cap_col: str) -> pd.Series:
        """
        市值中性化
        通过回归去除市值影响

        Args:
            df: 包含因子值和市值的数据框
            value_col: 因子值列名
            cap_col: 市值列名

        Returns:
            中性化后的因子值（残差）
        """
        # 对市值取对数
        log_cap = np.log(df[cap_col])

        # 线性回归
        slope, intercept, _, _, _ = stats.linregress(log_cap, df[value_col])

        # 计算残差
        residuals = df[value_col] - (slope * log_cap + intercept)

        return residuals

    def neutralize_industry_and_cap(self, df: pd.DataFrame, value_col: str,
                                    industry_col: str, cap_col: str) -> pd.Series:
        """
        行业和市值双重中性化

        Args:
            df: 数据框
            value_col: 因子值列名
            industry_col: 行业列名
            cap_col: 市值列名

        Returns:
            中性化后的因子值
        """
        # 先做行业中性化
        industry_neutral = self.neutralize_industry(df, value_col, industry_col)

        # 再做市值中性化
        df_temp = df.copy()
        df_temp['industry_neutral'] = industry_neutral

        return self.neutralize_market_cap(df_temp, 'industry_neutral', cap_col)

    # ==================== 完整预处理流程 ====================

    def preprocess(self, series: pd.Series,
                   fill_method: str = 'mean',
                   winsorize_method: str = 'mad',
                   winsorize_param: float = 3.0,
                   standardize_method: str = 'zscore') -> pd.Series:
        """
        完整的因子预处理流程

        Args:
            series: 原始因子值
            fill_method: 缺失值填充方法 ('mean', 'median', 'zero')
            winsorize_method: 去极值方法 ('mad', 'quantile', 'sigma')
            winsorize_param: 去极值参数
            standardize_method: 标准化方法 ('zscore', 'rank', 'minmax')

        Returns:
            预处理后的因子值
        """
        # 1. 缺失值处理
        if fill_method == 'mean':
            series = self.fill_missing_mean(series)
        elif fill_method == 'median':
            series = self.fill_missing_median(series)
        elif fill_method == 'zero':
            series = self.fill_missing_zero(series)

        # 2. 去极值
        if winsorize_method == 'mad':
            series = self.winsorize_mad(series, winsorize_param)
        elif winsorize_method == 'quantile':
            series = self.winsorize_quantile(series, 1 - winsorize_param, winsorize_param)
        elif winsorize_method == 'sigma':
            series = self.winsorize_sigma(series, winsorize_param)

        # 3. 标准化
        if standardize_method == 'zscore':
            series = self.standardize_zscore(series)
        elif standardize_method == 'rank':
            series = self.standardize_rank(series)
        elif standardize_method == 'minmax':
            series = self.standardize_minmax(series)

        return series

    def preprocess_dataframe(self, df: pd.DataFrame, factor_cols: List[str],
                            industry_col: str = None, cap_col: str = None,
                            neutralize: bool = False) -> pd.DataFrame:
        """
        批量预处理多个因子

        Args:
            df: 包含因子值的数据框
            factor_cols: 因子列名列表
            industry_col: 行业列名（用于中性化）
            cap_col: 市值列名（用于中性化）
            neutralize: 是否进行中性化

        Returns:
            预处理后的数据框
        """
        result = df.copy()

        for col in factor_cols:
            # 基硎预处理
            result[col] = self.preprocess(df[col])

            # 中性化
            if neutralize:
                if industry_col and cap_col:
                    result[col] = self.neutralize_industry_and_cap(result, col, industry_col, cap_col)
                elif industry_col:
                    result[col] = self.neutralize_industry(result, col, industry_col)
                elif cap_col:
                    result[col] = self.neutralize_market_cap(result, col, cap_col)

        return result


class FactorNormalizer:
    """因子方向统一化"""

    def __init__(self):
        pass

    def align_direction(self, series: pd.Series, direction: str = 'desc') -> pd.Series:
        """
        统一因子方向

        Args:
            series: 因子值
            direction: 期望方向 ('desc' 表示越大越好，'asc' 表示越小越好)

        Returns:
            调整方向后的因子值
        """
        if direction == 'asc':
            # 越小越好，取负
            return -series
        return series

    def align_to_benchmark(self, factor_values: pd.Series, benchmark_values: pd.Series) -> pd.Series:
        """
        对齐到基准方向
        确保因子与基准收益正相关
        """
        correlation = factor_values.corr(benchmark_values)

        if correlation < 0:
            return -factor_values
        return factor_values


# 便捷函数
def preprocess_factor_values(factor_values: pd.Series,
                            fill_method: str = 'mean',
                            winsorize_method: str = 'mad',
                            standardize_method: str = 'zscore') -> pd.Series:
    """
    预处理因子值的便捷函数

    Args:
        factor_values: 因子值序列
        fill_method: 缺失值填充方法
        winsorize_method: 去极值方法
        standardize_method: 标准化方法

    Returns:
        预处理后的因子值
    """
    preprocessor = FactorPreprocessor()
    return preprocessor.preprocess(factor_values, fill_method, winsorize_method, 3.0, standardize_method)
