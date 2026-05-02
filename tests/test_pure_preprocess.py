"""
测试 app/core/pure/preprocess.py 中的纯函数
"""

import numpy as np
import pandas as pd
import pytest

from app.core.pure.preprocess import (
    align_direction,
    check_coverage,
    cross_sectional_residual,
    fill_missing_industry_mean,
    fill_missing_mean,
    fill_missing_median,
    fill_missing_zero,
    neutralize_industry,
    neutralize_market_cap,
    sanitize_dataframe,
    sanitize_series,
    standardize_minmax,
    standardize_rank,
    standardize_rank_normal,
    standardize_rank_zscore,
    standardize_robust_zscore,
    standardize_zscore,
    winsorize_mad,
    winsorize_quantile,
    winsorize_sigma,
)


class TestSanitize:
    """测试数据清洗函数"""

    def test_sanitize_series_removes_inf(self):
        series = pd.Series([1, 2, np.inf, 4, -np.inf])
        result = sanitize_series(series)
        assert result.isna().sum() == 2
        assert result.iloc[0] == 1
        assert result.iloc[1] == 2
        assert pd.isna(result.iloc[2])
        assert result.iloc[3] == 4
        assert pd.isna(result.iloc[4])

    def test_sanitize_dataframe_removes_inf(self):
        df = pd.DataFrame({"a": [1, np.inf, 3], "b": [4, 5, -np.inf]})
        result = sanitize_dataframe(df)
        assert result["a"].isna().sum() == 1
        assert result["b"].isna().sum() == 1

    def test_sanitize_series_no_modification(self):
        series = pd.Series([1, 2, 3, 4, 5])
        result = sanitize_series(series)
        pd.testing.assert_series_equal(result, series)


class TestFillMissing:
    """测试缺失值填充函数"""

    def test_fill_missing_mean(self):
        series = pd.Series([1, 2, np.nan, 4, 5])
        result = fill_missing_mean(series)
        assert result.iloc[2] == 3.0  # (1+2+4+5)/4 = 3

    def test_fill_missing_median(self):
        series = pd.Series([1, 2, np.nan, 4, 5])
        result = fill_missing_median(series)
        assert result.iloc[2] == 3.0  # median of [1,2,4,5]

    def test_fill_missing_zero(self):
        series = pd.Series([1, 2, np.nan, 4, 5])
        result = fill_missing_zero(series)
        assert result.iloc[2] == 0.0

    def test_fill_missing_industry_mean(self):
        df = pd.DataFrame({
            "value": [1, 2, np.nan, 4, 5, np.nan],
            "industry": ["A", "A", "A", "B", "B", "B"],
        })
        result = fill_missing_industry_mean(df, "value", "industry")
        assert result.iloc[2] == 1.5  # mean of A: (1+2)/2
        assert result.iloc[5] == 4.5  # mean of B: (4+5)/2

    def test_check_coverage(self):
        series = pd.Series([1, 2, 3, np.nan, 5])
        passed, coverage = check_coverage(series, min_coverage=0.8)
        assert passed == True
        assert coverage == 0.8

        passed, coverage = check_coverage(series, min_coverage=0.9)
        assert passed == False
        assert coverage == 0.8


class TestWinsorize:
    """测试去极值函数"""

    def test_winsorize_mad(self):
        series = pd.Series([1, 2, 3, 4, 5, 100])  # 100 是极值
        result = winsorize_mad(series, n_mad=3.0)
        assert result.iloc[-1] < 100  # 极值被压缩

    def test_winsorize_quantile(self):
        series = pd.Series(range(100))
        result = winsorize_quantile(series, lower=0.05, upper=0.95)
        assert result.min() >= 4  # 5th percentile
        assert result.max() <= 95  # 95th percentile

    def test_winsorize_sigma(self):
        series = pd.Series([1, 2, 3, 4, 5, 100])
        result = winsorize_sigma(series, n_sigma=2.0)  # 使用更严格的阈值
        assert result.iloc[-1] < 100  # 极值被压缩

    def test_winsorize_mad_constant_series(self):
        series = pd.Series([5, 5, 5, 5, 5])
        result = winsorize_mad(series)
        pd.testing.assert_series_equal(result, series)

    def test_winsorize_small_series(self):
        series = pd.Series([1, 2])
        result = winsorize_mad(series)
        pd.testing.assert_series_equal(result, series)


class TestStandardize:
    """测试标准化函数"""

    def test_standardize_zscore(self):
        series = pd.Series([1, 2, 3, 4, 5])
        result = standardize_zscore(series)
        assert abs(result.mean()) < 1e-10  # 均值接近0
        assert abs(result.std() - 1.0) < 1e-10  # 标准差接近1

    def test_standardize_rank(self):
        series = pd.Series([10, 20, 30, 40, 50])
        result = standardize_rank(series)
        assert result.min() == 0.0
        assert result.max() == 1.0

    def test_standardize_rank_zscore(self):
        series = pd.Series([10, 20, 30, 40, 50])
        result = standardize_rank_zscore(series)
        assert abs(result.mean()) < 1e-10

    def test_standardize_minmax(self):
        series = pd.Series([1, 2, 3, 4, 5])
        result = standardize_minmax(series, min_val=0, max_val=1)
        assert result.min() == 0.0
        assert result.max() == 1.0

    def test_standardize_rank_normal(self):
        series = pd.Series([1, 2, 3, 4, 5])
        result = standardize_rank_normal(series)
        # 结果应该近似服从标准正态分布
        assert abs(result.mean()) < 0.5
        assert 0.5 < result.std() < 1.5

    def test_standardize_robust_zscore(self):
        series = pd.Series([1, 2, 3, 4, 5, 100])  # 包含极值
        result = standardize_robust_zscore(series)
        # 使用中位数和MAD，对极值更稳健
        assert abs(result.median()) < 1.0

    def test_standardize_constant_series(self):
        series = pd.Series([5, 5, 5, 5, 5])
        result = standardize_zscore(series)
        assert (result == 0.0).all()


class TestAlignDirection:
    """测试方向统一函数"""

    def test_align_direction_positive(self):
        series = pd.Series([1, 2, 3, 4, 5])
        result = align_direction(series, direction=1)
        pd.testing.assert_series_equal(result, series)

    def test_align_direction_negative(self):
        series = pd.Series([1, 2, 3, 4, 5])
        result = align_direction(series, direction=-1)
        expected = pd.Series([-1, -2, -3, -4, -5])
        pd.testing.assert_series_equal(result, expected)


class TestNeutralize:
    """测试中性化函数"""

    def test_neutralize_industry(self):
        df = pd.DataFrame({
            "value": [1, 2, 3, 4, 5, 6],
            "industry": ["A", "A", "A", "B", "B", "B"],
        })
        result = neutralize_industry(df, "value", "industry")
        # 行业A均值: 2, 行业B均值: 5
        assert abs(result.iloc[0] - (-1)) < 1e-10  # 1 - 2 = -1
        assert abs(result.iloc[1] - 0) < 1e-10  # 2 - 2 = 0
        assert abs(result.iloc[2] - 1) < 1e-10  # 3 - 2 = 1
        assert abs(result.iloc[3] - (-1)) < 1e-10  # 4 - 5 = -1

    def test_neutralize_market_cap(self):
        df = pd.DataFrame({
            "value": [1.5, 2.3, 2.8, 4.2, 5.1, 3.7, 4.8, 2.1, 5.5, 3.2, 4.0, 2.9],
            "cap": [10, 20, 30, 40, 50, 25, 45, 15, 55, 22, 38, 28],
        })
        result = neutralize_market_cap(df, "value", "cap")
        # 线性回归后残差均值应接近0
        assert abs(result.mean()) < 0.1

    def test_cross_sectional_residual(self):
        df = pd.DataFrame({
            "factor": [1.2, 2.5, 2.9, 4.1, 5.3, 3.5, 4.7, 2.2, 5.1, 3.3, 4.2, 3.0],
            "control1": [10, 20, 30, 40, 50, 25, 45, 15, 55, 22, 38, 28],
            "control2": [5, 10, 15, 20, 25, 12, 22, 8, 27, 11, 19, 14],
        })
        result = cross_sectional_residual(df, "factor", ["control1", "control2"])
        # 残差均值应接近0
        assert abs(result.mean()) < 0.1

    def test_cross_sectional_residual_insufficient_data(self):
        df = pd.DataFrame({
            "factor": [1, 2],
            "control1": [10, 20],
        })
        result = cross_sectional_residual(df, "factor", ["control1"])
        # 数据不足，返回原序列
        pd.testing.assert_series_equal(result, df["factor"])


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_series(self):
        series = pd.Series([], dtype=float)
        assert fill_missing_mean(series).empty
        assert standardize_zscore(series).empty

    def test_all_nan_series(self):
        series = pd.Series([np.nan, np.nan, np.nan])
        result = fill_missing_mean(series)
        assert result.isna().all()

    def test_single_value_series(self):
        series = pd.Series([5.0])
        result = standardize_zscore(series)
        assert len(result) == 1

    def test_two_value_series(self):
        series = pd.Series([1.0, 2.0])
        result = standardize_zscore(series)
        assert len(result) == 2
        assert abs(result.mean()) < 1e-10
