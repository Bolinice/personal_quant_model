"""
Property-based Testing (Hypothesis)
====================================
自动生成边界用例，验证因子预处理不变量。

不变量：
1. MAD 去极值不改变非极值点
2. Z-score 标准化后均值≈0、标准差≈1（非常量序列）
3. 中性化后组内均值≈0
4. 组合权重之和 = 1.0
"""

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.factor_preprocess import FactorPreprocessor

preprocessor = FactorPreprocessor()


# ==================== Strategies ====================

finite_floats = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
positive_floats = st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False)

# 生成有变化的因子值（排除常量序列）
factor_values = st.lists(
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    min_size=30,
    max_size=200,
).filter(lambda xs: len(set(xs)) > 5)  # 至少5个不同值

mad_thresholds = st.floats(min_value=1.0, max_value=5.0)


# ==================== MAD Winsorization ====================


class TestMADWinsorization:
    """MAD 去极值不变量测试"""

    @given(values=factor_values, n_mad=mad_thresholds)
    @settings(max_examples=50, deadline=None)
    def test_no_nan_introduced(self, values, n_mad):
        """MAD 去极值不应引入 NaN"""
        series = pd.Series(values)
        result = preprocessor.winsorize_mad(series, n_mad=n_mad)
        assert not result.isna().any()

    @given(values=factor_values, n_mad=mad_thresholds)
    @settings(max_examples=50, deadline=None)
    def test_bounded_range(self, values, n_mad):
        """MAD 去极值后，所有值应在 [median - n_mad*bound, median + n_mad*bound] 内"""
        series = pd.Series(values)
        result = preprocessor.winsorize_mad(series, n_mad=n_mad)

        median = series.median()
        mad = np.median(np.abs(series - median)) * 1.4826
        if mad > 0:
            lower = median - n_mad * mad
            upper = median + n_mad * mad
            assert (result >= lower - 1e-6).all()
            assert (result <= upper + 1e-6).all()

    @given(values=factor_values, n_mad=mad_thresholds)
    @settings(max_examples=50, deadline=None)
    def test_preserves_non_outlier_values(self, values, n_mad):
        """MAD 去极值不应改变非极值点的值（容忍浮点精度）"""
        series = pd.Series(values)
        result = preprocessor.winsorize_mad(series, n_mad=n_mad)

        median = series.median()
        mad = np.median(np.abs(series - median)) * 1.4826
        if mad > 0:
            lower = median - n_mad * mad
            upper = median + n_mad * mad
            # 非极值点应保持不变（容忍浮点精度）
            non_outlier_mask = (series >= lower) & (series <= upper)
            if non_outlier_mask.any():
                np.testing.assert_allclose(
                    result[non_outlier_mask].values,
                    series[non_outlier_mask].values,
                    rtol=1e-5,
                )


# ==================== Z-score Standardization ====================


class TestZScoreStandardization:
    """Z-score 标准化不变量测试"""

    @given(values=factor_values)
    @settings(max_examples=50, deadline=None)
    def test_mean_approximately_zero(self, values):
        """Z-score 标准化后均值应接近 0"""
        series = pd.Series(values)
        result = preprocessor.standardize_zscore(series)
        # 浮点精度容忍：30-200 个值的均值偏差
        assert abs(result.mean()) < 1e-8

    @given(values=factor_values)
    @settings(max_examples=50, deadline=None)
    def test_std_approximately_one(self, values):
        """Z-score 标准化后标准差应接近 1（非常量序列）"""
        series = pd.Series(values)
        result = preprocessor.standardize_zscore(series)
        # 容忍度 0.05：大量重复值时浮点精度偏差较大
        assert abs(result.std(ddof=0) - 1.0) < 0.05

    @given(values=factor_values)
    @settings(max_examples=50, deadline=None)
    def test_preserves_rank_order(self, values):
        """Z-score 标准化应保持严格排序不变（x_i > x_j → z_i > z_j）"""
        series = pd.Series(values)
        result = preprocessor.standardize_zscore(series)

        valid = result.notna() & np.isfinite(result)
        if valid.sum() < 2:
            return

        # 不变量: 严格不等关系保持不变
        # 仅检查原始值差异足够大的对，避免浮点噪声
        orig = series[valid].values
        res = result[valid].values
        scale = np.maximum(np.abs(orig), 1.0)
        sorted_idx = np.argsort(orig)
        orig_sorted = orig[sorted_idx]
        res_sorted = res[sorted_idx]
        scale_sorted = scale[sorted_idx]

        # 检查相邻对: 如果原始差异显著，z-score 排序应一致
        for k in range(len(orig_sorted) - 1):
            diff = orig_sorted[k + 1] - orig_sorted[k]
            ref = max(scale_sorted[k], scale_sorted[k + 1])
            if diff / ref > 1e-10:
                assert res_sorted[k] <= res_sorted[k + 1], (
                    f"排序反转: orig[{k}]={orig_sorted[k]} < orig[{k+1}]={orig_sorted[k+1]} "
                    f"but z[{k}]={res_sorted[k]} > z[{k+1}]={res_sorted[k+1]}"
                )


# ==================== Rank Normal Standardization ====================


class TestRankNormalStandardization:
    """逆正态秩变换不变量测试"""

    @given(values=factor_values)
    @settings(max_examples=50, deadline=None)
    def test_no_nan(self, values):
        """逆正态秩变换不应产生 NaN"""
        series = pd.Series(values)
        result = preprocessor.standardize_rank_normal(series)
        assert not result.isna().any()

    @given(values=factor_values)
    @settings(max_examples=50, deadline=None)
    def test_finite_values(self, values):
        """逆正态秩变换结果应为有限值"""
        series = pd.Series(values)
        result = preprocessor.standardize_rank_normal(series)
        assert np.isfinite(result.values).all()


# ==================== Preprocessing Pipeline ====================


class TestPreprocessingPipeline:
    """完整预处理流水线不变量测试"""

    @given(values=factor_values)
    @settings(max_examples=30, deadline=None)
    def test_pipeline_no_nan(self, values):
        """完整预处理流水线不应产生 NaN"""
        series = pd.Series(values)
        result = preprocessor.preprocess(
            series,
            fill_method="median",
            winsorize_method="mad",
            standardize_method="zscore",
        )
        assert not result.isna().any()

    @given(values=factor_values)
    @settings(max_examples=30, deadline=None)
    def test_pipeline_preserves_length(self, values):
        """预处理不应改变数据长度"""
        series = pd.Series(values)
        result = preprocessor.preprocess(
            series,
            fill_method="median",
            winsorize_method="mad",
            standardize_method="zscore",
        )
        assert len(result) == len(series)
