"""
因子预处理纯函数 — 无副作用、无 IO、无日志依赖

所有函数接收 numpy/pandas 数据结构，返回计算结果。
不修改输入，不产生副作用，可独立测试。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# ==================== 数据清洗 ====================


def sanitize_series(series: pd.Series) -> pd.Series:
    """替换所有 Inf/-Inf 为 NaN

    Args:
        series: 输入序列

    Returns:
        清洗后的序列（返回副本）
    """
    result = series.copy()
    result = result.replace([np.inf, -np.inf], np.nan)
    return result


def sanitize_dataframe(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """替换所有 Inf/-Inf 为 NaN

    Args:
        df: 输入 DataFrame
        columns: 仅处理指定列，None 则处理所有数值列

    Returns:
        清洗后的 DataFrame（返回副本）
    """
    result = df.copy()
    numeric_cols = result.select_dtypes(include=[np.number]).columns
    target_cols = numeric_cols if columns is None else numeric_cols.intersection(columns)

    for col in target_cols:
        result[col] = result[col].replace([np.inf, -np.inf], np.nan)

    return result


# ==================== 缺失值处理 ====================


def fill_missing_mean(series: pd.Series) -> pd.Series:
    """用均值填充缺失值"""
    return series.fillna(series.mean())


def fill_missing_median(series: pd.Series) -> pd.Series:
    """用中位数填充缺失值"""
    return series.fillna(series.median())


def fill_missing_zero(series: pd.Series) -> pd.Series:
    """用0填充缺失值"""
    return series.fillna(0)


def fill_missing_industry_mean(df: pd.DataFrame, value_col: str, industry_col: str) -> pd.Series:
    """用行业均值填充缺失值

    Args:
        df: 包含因子值和行业列的 DataFrame
        value_col: 因子值列名
        industry_col: 行业列名

    Returns:
        填充后的序列
    """
    industry_mean = df.groupby(industry_col)[value_col].transform("mean")
    return df[value_col].fillna(industry_mean)


def check_coverage(series: pd.Series, min_coverage: float = 0.8) -> tuple[bool, float]:
    """检查因子覆盖率

    Args:
        series: 因子值序列
        min_coverage: 最低覆盖率阈值

    Returns:
        (是否通过, 实际覆盖率)
    """
    coverage = 1 - series.isna().mean()
    return coverage >= min_coverage, coverage


# ==================== 去极值 ====================


def winsorize_mad(series: pd.Series, n_mad: float = 3.0) -> pd.Series:
    """MAD去极值（中位数绝对偏差）

    Args:
        series: 输入序列
        n_mad: MAD倍数阈值

    Returns:
        去极值后的序列
    """
    valid = series.dropna()
    if len(valid) < 3:
        return series

    median = valid.median()
    mad = (valid - median).abs().median()

    if mad < 1e-10:
        return series

    # 1.4826 使 MAD 与正态分布标准差一致
    mad_adjusted = mad * 1.4826
    lower = median - n_mad * mad_adjusted
    upper = median + n_mad * mad_adjusted

    return series.clip(lower=lower, upper=upper)


def winsorize_quantile(series: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """分位数去极值

    Args:
        series: 输入序列
        lower: 下分位数
        upper: 上分位数

    Returns:
        去极值后的序列
    """
    valid = series.dropna()
    if len(valid) < 3:
        return series

    lower_bound = valid.quantile(lower)
    upper_bound = valid.quantile(upper)
    return series.clip(lower=lower_bound, upper=upper_bound)


def winsorize_sigma(series: pd.Series, n_sigma: float = 3.0) -> pd.Series:
    """3-sigma去极值

    Args:
        series: 输入序列
        n_sigma: 标准差倍数

    Returns:
        去极值后的序列
    """
    valid = series.dropna()
    if len(valid) < 2:
        return series

    mean = valid.mean()
    std = valid.std()

    if std < 1e-10:
        return series

    lower = mean - n_sigma * std
    upper = mean + n_sigma * std
    return series.clip(lower=lower, upper=upper)


# ==================== 标准化 ====================


def standardize_zscore(series: pd.Series) -> pd.Series:
    """Z-score标准化

    Args:
        series: 输入序列

    Returns:
        标准化后的序列
    """
    valid = series.dropna()
    if len(valid) < 2:
        return series

    mean = valid.mean()
    std = valid.std()

    if std < 1e-10 or pd.isna(std):
        return pd.Series(0.0, index=series.index)

    return (series - mean) / std


def standardize_rank(series: pd.Series) -> pd.Series:
    """排序标准化（归一化到[0, 1]）

    Args:
        series: 输入序列

    Returns:
        标准化后的序列
    """
    valid_count = series.notna().sum()
    if valid_count < 2:
        return series

    ranks = series.rank(method='average')
    return (ranks - 1) / (valid_count - 1)


def standardize_rank_zscore(series: pd.Series) -> pd.Series:
    """先排序再Z-score标准化

    Args:
        series: 输入序列

    Returns:
        标准化后的序列
    """
    ranks = series.rank(method='average')
    return standardize_zscore(ranks)


def standardize_minmax(series: pd.Series, min_val: float = 0, max_val: float = 1) -> pd.Series:
    """Min-Max标准化

    Args:
        series: 输入序列
        min_val: 目标最小值
        max_val: 目标最大值

    Returns:
        标准化后的序列
    """
    valid = series.dropna()
    if len(valid) < 2:
        return series

    data_min = valid.min()
    data_max = valid.max()

    if abs(data_max - data_min) < 1e-10:
        return pd.Series((min_val + max_val) / 2, index=series.index)

    normalized = (series - data_min) / (data_max - data_min)
    return normalized * (max_val - min_val) + min_val


def standardize_rank_normal(series: pd.Series) -> pd.Series:
    """逆正态秩变换（Rank Normal Transformation）

    将排序后的值映射到标准正态分布的分位数。

    Args:
        series: 输入序列

    Returns:
        标准化后的序列
    """
    valid_mask = series.notna()
    valid_count = valid_mask.sum()

    if valid_count < 2:
        return series

    result = series.astype(float).copy()
    ranks = series[valid_mask].rank(method='average')

    # 映射到 (0, 1) 区间，避免边界值
    percentiles = (ranks - 0.5) / valid_count

    # 使用标准正态分布的逆累积分布函数
    result.loc[valid_mask] = stats.norm.ppf(percentiles)

    return result


def standardize_robust_zscore(series: pd.Series) -> pd.Series:
    """稳健Z-score标准化（使用中位数和MAD）

    Args:
        series: 输入序列

    Returns:
        标准化后的序列
    """
    valid = series.dropna()
    if len(valid) < 2:
        return series

    median = valid.median()
    mad = (valid - median).abs().median()

    if mad < 1e-10:
        return pd.Series(0.0, index=series.index)

    # 1.4826 使 MAD 与正态分布标准差一致
    mad_adjusted = mad * 1.4826
    return (series - median) / mad_adjusted


# ==================== 方向统一 ====================


def align_direction(series: pd.Series, direction: int = 1) -> pd.Series:
    """统一因子方向

    Args:
        series: 输入序列
        direction: 1 表示正向（值越大越好），-1 表示反向（值越小越好）

    Returns:
        方向统一后的序列
    """
    if direction == -1:
        return -series
    return series


# ==================== 中性化 ====================


def neutralize_industry(df: pd.DataFrame, value_col: str, industry_col: str) -> pd.Series:
    """行业中性化（去除行业均值）

    Args:
        df: 包含因子值和行业列的 DataFrame
        value_col: 因子值列名
        industry_col: 行业列名

    Returns:
        中性化后的序列
    """
    industry_mean = df.groupby(industry_col)[value_col].transform("mean")
    return df[value_col] - industry_mean


def neutralize_market_cap(df: pd.DataFrame, value_col: str, cap_col: str) -> pd.Series:
    """市值中性化（线性回归残差）

    Args:
        df: 包含因子值和市值列的 DataFrame
        value_col: 因子值列名
        cap_col: 市值列名

    Returns:
        中性化后的序列
    """
    valid = df[[value_col, cap_col]].dropna()
    if len(valid) < 10:
        return df[value_col]

    X = valid[cap_col].values.reshape(-1, 1)
    y = valid[value_col].values

    # 简单线性回归
    X_mean = X.mean()
    y_mean = y.mean()

    numerator = ((X - X_mean) * (y - y_mean).reshape(-1, 1)).sum()
    denominator = ((X - X_mean) ** 2).sum()

    if abs(denominator) < 1e-10:
        return df[value_col]

    beta = numerator / denominator
    alpha = y_mean - beta * X_mean

    # 计算残差
    result = df[value_col].astype(float).copy()
    residuals = y - (alpha + beta * X.flatten())
    result.loc[valid.index] = residuals

    return result


def cross_sectional_residual(df: pd.DataFrame, factor_col: str, control_cols: list[str]) -> pd.Series:
    """横截面回归残差（多因子中性化）

    Args:
        df: 包含因子值和控制变量的 DataFrame
        factor_col: 因子值列名
        control_cols: 控制变量列名列表

    Returns:
        回归残差序列
    """
    cols = [factor_col] + control_cols
    valid = df[cols].dropna()

    if len(valid) < len(control_cols) + 5:
        return df[factor_col]

    X = valid[control_cols].values
    y = valid[factor_col].values

    # 添加截距项
    X_with_intercept = np.column_stack([np.ones(len(X)), X])

    # 最小二乘法
    try:
        beta = np.linalg.lstsq(X_with_intercept, y, rcond=None)[0]
        y_pred = X_with_intercept @ beta
        residuals = y - y_pred

        result = df[factor_col].astype(float).copy()
        result.loc[valid.index] = residuals
        return result
    except np.linalg.LinAlgError:
        return df[factor_col]
