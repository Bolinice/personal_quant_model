"""
测试因子正交化模块
"""

import numpy as np
import pandas as pd
import pytest

from app.core.factor_orthogonalization import (
    FactorOrthogonalizer,
    OrthogonalizationMethod,
)


class TestFactorCorrelation:
    """测试因子相关性分析"""

    def test_compute_factor_correlation(self):
        """测试计算因子相关性矩阵"""
        # 创建测试数据：3个因子，100个样本
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = factor1 + np.random.randn(n_samples) * 0.5  # 与factor1高相关
        factor3 = np.random.randn(n_samples)  # 独立因子

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
                "factor3": factor3,
            }
        )

        orthogonalizer = FactorOrthogonalizer()
        corr_matrix = orthogonalizer.compute_factor_correlation(factor_data, method="pearson")

        # 验证相关性矩阵形状
        assert corr_matrix.shape == (3, 3)

        # 验证对角线为1
        assert np.allclose(np.diag(corr_matrix), 1.0)

        # 验证factor1和factor2高相关
        assert abs(corr_matrix.loc["factor1", "factor2"]) > 0.7

        # 验证对称性
        assert np.allclose(corr_matrix, corr_matrix.T)

    def test_identify_redundant_factors(self):
        """测试识别冗余因子"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = factor1 + np.random.randn(n_samples) * 0.3  # 高相关
        factor3 = np.random.randn(n_samples)  # 独立

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
                "factor3": factor3,
            }
        )

        orthogonalizer = FactorOrthogonalizer()
        redundant_pairs = orthogonalizer.identify_redundant_factors(
            factor_data,
            corr_threshold=0.7,
        )

        # 应该识别出factor1和factor2是冗余的
        assert len(redundant_pairs) >= 1
        pair = redundant_pairs[0]
        assert {pair.factor1, pair.factor2} == {"factor1", "factor2"}
        assert pair.is_redundant is True

    def test_select_factors_by_ic(self):
        """测试根据IC选择因子"""
        redundant_pairs = [
            type(
                "FactorCorrelation",
                (),
                {
                    "factor1": "factor_a",
                    "factor2": "factor_b",
                    "pearson_corr": 0.8,
                    "spearman_corr": 0.75,
                    "ic_corr": 0.0,
                    "is_redundant": True,
                },
            )()
        ]

        ic_values = {
            "factor_a": 0.03,  # IC较低
            "factor_b": 0.05,  # IC较高
        }

        orthogonalizer = FactorOrthogonalizer()
        factors_to_remove = orthogonalizer.select_factors_by_ic(redundant_pairs, ic_values)

        # 应该剔除IC较低的factor_a
        assert "factor_a" in factors_to_remove
        assert "factor_b" not in factors_to_remove


class TestOrthogonalization:
    """测试因子正交化"""

    def test_gram_schmidt_orthogonalization(self):
        """测试Gram-Schmidt正交化"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = factor1 + np.random.randn(n_samples) * 0.5
        factor3 = np.random.randn(n_samples)

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
                "factor3": factor3,
            }
        )

        orthogonalizer = FactorOrthogonalizer()
        result = orthogonalizer.orthogonalize_gram_schmidt(factor_data)

        # 验证结果形状
        assert result.orthogonal_factors.shape == factor_data.shape

        # 验证正交性：相关性矩阵应该接近单位矩阵
        orthogonal_corr = result.orthogonal_factors.corr()
        off_diagonal = orthogonal_corr.values[~np.eye(3, dtype=bool)]

        # 非对角线元素应该接近0（允许一定误差）
        assert np.abs(off_diagonal).max() < 0.3

    def test_regression_orthogonalization(self):
        """测试回归残差法正交化"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = factor1 * 0.8 + np.random.randn(n_samples) * 0.5
        factor3 = np.random.randn(n_samples)

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
                "factor3": factor3,
            }
        )

        orthogonalizer = FactorOrthogonalizer()
        result = orthogonalizer.orthogonalize_regression(
            factor_data,
            base_factors=["factor1"],
        )

        # 验证结果形状
        assert result.orthogonal_factors.shape == factor_data.shape

        # 验证factor2和factor3与factor1的相关性降低
        original_corr = factor_data.corr().loc["factor2", "factor1"]
        orthogonal_corr = result.orthogonal_factors.corr().loc["factor2", "factor1"]

        assert abs(orthogonal_corr) < abs(original_corr)

    def test_pca_orthogonalization(self):
        """测试PCA正交化"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = factor1 + np.random.randn(n_samples) * 0.5
        factor3 = np.random.randn(n_samples)

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
                "factor3": factor3,
            }
        )

        orthogonalizer = FactorOrthogonalizer()
        result = orthogonalizer.orthogonalize_pca(factor_data, n_components=3)

        # 验证主成分数量
        assert result.orthogonal_factors.shape[1] == 3

        # 验证完全正交
        pc_corr = result.orthogonal_factors.corr()
        off_diagonal = pc_corr.values[~np.eye(3, dtype=bool)]
        assert np.abs(off_diagonal).max() < 1e-10

        # 验证方差解释比例
        assert result.explained_variance is not None
        assert len(result.explained_variance) == 3
        assert result.explained_variance.sum() <= 1.0

    def test_symmetric_orthogonalization(self):
        """测试对称正交化"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = factor1 + np.random.randn(n_samples) * 0.5
        factor3 = np.random.randn(n_samples)

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
                "factor3": factor3,
            }
        )

        orthogonalizer = FactorOrthogonalizer()
        result = orthogonalizer.orthogonalize_symmetric(factor_data)

        # 验证结果形状
        assert result.orthogonal_factors.shape == factor_data.shape

        # 验证正交性
        orthogonal_corr = result.orthogonal_factors.corr()
        off_diagonal = orthogonal_corr.values[~np.eye(3, dtype=bool)]
        assert np.abs(off_diagonal).max() < 0.3


class TestIndependenceEvaluation:
    """测试因子独立性评估"""

    def test_evaluate_independence_high_correlation(self):
        """测试高相关因子的独立性评估"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = factor1 + np.random.randn(n_samples) * 0.2  # 高相关

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
            }
        )

        orthogonalizer = FactorOrthogonalizer()
        metrics = orthogonalizer.evaluate_independence(factor_data)

        # 高相关因子应该有高平均相关性
        assert metrics["mean_correlation"] > 0.7
        assert metrics["max_correlation"] > 0.7
        assert metrics["mean_vif"] > 2.0  # VIF > 2表示存在共线性

    def test_evaluate_independence_low_correlation(self):
        """测试低相关因子的独立性评估"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = np.random.randn(n_samples)  # 独立

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
            }
        )

        orthogonalizer = FactorOrthogonalizer()
        metrics = orthogonalizer.evaluate_independence(factor_data)

        # 独立因子应该有低平均相关性
        assert metrics["mean_correlation"] < 0.3
        assert metrics["max_correlation"] < 0.3
        assert metrics["mean_vif"] < 2.0


class TestCompleteProcess:
    """测试完整流程"""

    def test_process_factors_remove_redundant(self):
        """测试去冗余流程"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = factor1 + np.random.randn(n_samples) * 0.2  # 高相关，IC低
        factor3 = np.random.randn(n_samples)  # 独立，IC高

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
                "factor3": factor3,
            }
        )

        ic_values = {
            "factor1": 0.05,
            "factor2": 0.02,  # IC较低
            "factor3": 0.06,
        }

        orthogonalizer = FactorOrthogonalizer()
        processed_data, info = orthogonalizer.process_factors(
            factor_data,
            ic_values=ic_values,
            remove_redundant=True,
            orthogonalize=False,
            corr_threshold=0.7,
        )

        # 应该剔除factor2
        assert "factor2" in info["removed_factors"]
        assert len(processed_data.columns) == 2

    def test_process_factors_orthogonalize(self):
        """测试正交化流程"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = factor1 + np.random.randn(n_samples) * 0.5
        factor3 = np.random.randn(n_samples)

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
                "factor3": factor3,
            }
        )

        orthogonalizer = FactorOrthogonalizer()
        processed_data, info = orthogonalizer.process_factors(
            factor_data,
            remove_redundant=False,
            orthogonalize=True,
            method=OrthogonalizationMethod.REGRESSION,
        )

        # 验证正交化后相关性降低
        assert info["independence_after"]["mean_correlation"] < info["independence_before"]["mean_correlation"]

    def test_process_factors_complete(self):
        """测试完整流程：去冗余+正交化"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = factor1 + np.random.randn(n_samples) * 0.2  # 冗余
        factor3 = factor1 * 0.5 + np.random.randn(n_samples) * 0.5
        factor4 = np.random.randn(n_samples)

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
                "factor3": factor3,
                "factor4": factor4,
            }
        )

        ic_values = {
            "factor1": 0.05,
            "factor2": 0.02,
            "factor3": 0.04,
            "factor4": 0.06,
        }

        orthogonalizer = FactorOrthogonalizer()
        processed_data, info = orthogonalizer.process_factors(
            factor_data,
            ic_values=ic_values,
            remove_redundant=True,
            orthogonalize=True,
            method=OrthogonalizationMethod.REGRESSION,
            corr_threshold=0.7,
        )

        # 验证因子数量减少
        assert len(processed_data.columns) < len(factor_data.columns)

        # 验证独立性提升
        assert info["independence_after"]["mean_correlation"] < info["independence_before"]["mean_correlation"]


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_dataframe(self):
        """测试空DataFrame"""
        factor_data = pd.DataFrame()

        orthogonalizer = FactorOrthogonalizer()
        result = orthogonalizer.orthogonalize_gram_schmidt(factor_data)

        assert result.orthogonal_factors.empty

    def test_single_factor(self):
        """测试单个因子"""
        factor_data = pd.DataFrame({"factor1": np.random.randn(100)})

        orthogonalizer = FactorOrthogonalizer()
        metrics = orthogonalizer.evaluate_independence(factor_data)

        # 单个因子应该返回默认值
        assert metrics["mean_correlation"] == 0.0
        assert metrics["max_correlation"] == 0.0

    def test_factors_with_nan(self):
        """测试含缺失值的因子"""
        np.random.seed(42)
        n_samples = 100

        factor1 = np.random.randn(n_samples)
        factor2 = np.random.randn(n_samples)
        factor1[::10] = np.nan  # 10%缺失

        factor_data = pd.DataFrame(
            {
                "factor1": factor1,
                "factor2": factor2,
            }
        )

        orthogonalizer = FactorOrthogonalizer()
        result = orthogonalizer.orthogonalize_regression(factor_data)

        # 应该能处理缺失值
        assert not result.orthogonal_factors.empty
