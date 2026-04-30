"""
因子正交化与去冗余模块
核心功能：
1. 因子相关性分析（Pearson/Spearman/IC相关性）
2. 冗余因子识别与剔除
3. 因子正交化（Gram-Schmidt/PCA/回归残差法）
4. 因子独立性评估

设计原则：
- 高相关因子（>0.7）保留IC更高的一个
- 正交化保留因子的预测能力，去除冗余信息
- 支持分组正交化（按因子类别）
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.decomposition import PCA

from app.core.logging import logger

if TYPE_CHECKING:
    from datetime import date


class OrthogonalizationMethod(StrEnum):
    """正交化方法"""

    GRAM_SCHMIDT = "gram_schmidt"  # Gram-Schmidt正交化
    REGRESSION = "regression"  # 回归残差法
    PCA = "pca"  # 主成分分析
    SYMMETRIC = "symmetric"  # 对称正交化


@dataclass
class FactorCorrelation:
    """因子相关性结果"""

    factor1: str
    factor2: str
    pearson_corr: float
    spearman_corr: float
    ic_corr: float  # IC序列相关性
    is_redundant: bool  # 是否冗余


@dataclass
class OrthogonalizationResult:
    """正交化结果"""

    original_factors: pd.DataFrame
    orthogonal_factors: pd.DataFrame
    transformation_matrix: np.ndarray | None
    explained_variance: np.ndarray | None
    method: str


class FactorOrthogonalizer:
    """
    因子正交化器

    核心理念：
    1. 因子间高相关会导致信息冗余，降低组合效率
    2. 正交化可以去除冗余，保留独立信息
    3. 需要在去冗余和保留原始因子可解释性之间平衡
    """

    # 相关性阈值
    HIGH_CORR_THRESHOLD = 0.7  # 高相关阈值，超过则认为冗余
    MODERATE_CORR_THRESHOLD = 0.5  # 中等相关阈值
    IC_CORR_THRESHOLD = 0.6  # IC相关性阈值

    def __init__(self):
        pass

    # ==================== 1. 因子相关性分析 ====================

    def compute_factor_correlation(
        self,
        factor_data: pd.DataFrame,
        ic_data: pd.DataFrame | None = None,
        method: str = "pearson",
    ) -> pd.DataFrame:
        """
        计算因子相关性矩阵

        Args:
            factor_data: 因子数据，columns为因子名，index为(ts_code, trade_date)
            ic_data: IC数据，columns为因子名，index为trade_date
            method: 相关性方法 ('pearson', 'spearman')

        Returns:
            相关性矩阵 DataFrame
        """
        if factor_data.empty:
            return pd.DataFrame()

        # 计算因子值相关性
        if method == "pearson":
            corr_matrix = factor_data.corr(method="pearson")
        elif method == "spearman":
            corr_matrix = factor_data.corr(method="spearman")
        else:
            raise ValueError(f"Unknown correlation method: {method}")

        # 如果提供了IC数据，也计算IC相关性
        if ic_data is not None and not ic_data.empty:
            ic_corr = ic_data.corr(method="pearson")
            logger.info(f"Computed IC correlation matrix: {ic_corr.shape}")

        return corr_matrix

    def identify_redundant_factors(
        self,
        factor_data: pd.DataFrame,
        ic_values: dict[str, float] | None = None,
        corr_threshold: float = 0.7,
    ) -> list[FactorCorrelation]:
        """
        识别冗余因子对

        Args:
            factor_data: 因子数据
            ic_values: 各因子的IC均值，用于决定保留哪个因子
            corr_threshold: 相关性阈值

        Returns:
            冗余因子对列表
        """
        corr_matrix = self.compute_factor_correlation(factor_data, method="pearson")
        spearman_corr = self.compute_factor_correlation(factor_data, method="spearman")

        redundant_pairs = []
        factors = corr_matrix.columns.tolist()

        for i, factor1 in enumerate(factors):
            for j, factor2 in enumerate(factors):
                if i >= j:  # 只看上三角
                    continue

                pearson = corr_matrix.loc[factor1, factor2]
                spearman = spearman_corr.loc[factor1, factor2]

                # 判断是否冗余：Pearson或Spearman相关性超过阈值
                is_redundant = abs(pearson) > corr_threshold or abs(spearman) > corr_threshold

                if is_redundant:
                    redundant_pairs.append(
                        FactorCorrelation(
                            factor1=factor1,
                            factor2=factor2,
                            pearson_corr=pearson,
                            spearman_corr=spearman,
                            ic_corr=0.0,  # 暂不计算IC相关性
                            is_redundant=True,
                        )
                    )

        logger.info(f"Found {len(redundant_pairs)} redundant factor pairs (threshold={corr_threshold})")
        return redundant_pairs

    def select_factors_by_ic(
        self,
        redundant_pairs: list[FactorCorrelation],
        ic_values: dict[str, float],
    ) -> set[str]:
        """
        根据IC选择要保留的因子，剔除冗余因子

        策略：对于每对冗余因子，保留IC更高的一个

        Args:
            redundant_pairs: 冗余因子对
            ic_values: 各因子的IC均值

        Returns:
            要剔除的因子集合
        """
        factors_to_remove = set()

        for pair in redundant_pairs:
            ic1 = abs(ic_values.get(pair.factor1, 0.0))
            ic2 = abs(ic_values.get(pair.factor2, 0.0))

            # 保留IC更高的因子，剔除IC更低的
            if ic1 < ic2:
                factors_to_remove.add(pair.factor1)
            else:
                factors_to_remove.add(pair.factor2)

        logger.info(f"Selected {len(factors_to_remove)} factors to remove based on IC")
        return factors_to_remove

    # ==================== 2. 因子正交化 ====================

    def orthogonalize_gram_schmidt(self, factor_data: pd.DataFrame) -> OrthogonalizationResult:
        """
        Gram-Schmidt正交化

        将因子向量组正交化，保持第一个因子不变，后续因子依次正交化

        Args:
            factor_data: 因子数据，columns为因子名

        Returns:
            正交化结果
        """
        if factor_data.empty:
            return OrthogonalizationResult(
                original_factors=factor_data,
                orthogonal_factors=factor_data,
                transformation_matrix=None,
                explained_variance=None,
                method="gram_schmidt",
            )

        # 标准化因子
        factor_std = (factor_data - factor_data.mean()) / factor_data.std()
        factor_std = factor_std.fillna(0)

        # Gram-Schmidt正交化
        orthogonal = pd.DataFrame(index=factor_std.index, columns=factor_std.columns)
        factors = factor_std.columns.tolist()

        # 第一个因子保持不变
        orthogonal[factors[0]] = factor_std[factors[0]]

        # 依次正交化后续因子
        for i in range(1, len(factors)):
            factor = factor_std[factors[i]].values
            # 减去在前面所有正交向量上的投影
            for j in range(i):
                prev_factor = orthogonal[factors[j]].values
                projection = np.dot(factor, prev_factor) / (np.dot(prev_factor, prev_factor) + 1e-10)
                factor = factor - projection * prev_factor

            orthogonal[factors[i]] = factor

        # 重新标准化
        orthogonal = (orthogonal - orthogonal.mean()) / orthogonal.std()
        orthogonal = orthogonal.fillna(0)

        logger.info(f"Gram-Schmidt orthogonalization completed for {len(factors)} factors")

        return OrthogonalizationResult(
            original_factors=factor_data,
            orthogonal_factors=orthogonal,
            transformation_matrix=None,
            explained_variance=None,
            method="gram_schmidt",
        )

    def orthogonalize_regression(
        self,
        factor_data: pd.DataFrame,
        base_factors: list[str] | None = None,
    ) -> OrthogonalizationResult:
        """
        回归残差法正交化

        将因子对基准因子组回归，取残差作为正交化后的因子
        适用于：将新因子对已有因子组正交化，保留增量信息

        Args:
            factor_data: 因子数据
            base_factors: 基准因子列表，如果为None则使用第一个因子作为基准

        Returns:
            正交化结果
        """
        if factor_data.empty:
            return OrthogonalizationResult(
                original_factors=factor_data,
                orthogonal_factors=factor_data,
                transformation_matrix=None,
                explained_variance=None,
                method="regression",
            )

        factors = factor_data.columns.tolist()
        if base_factors is None:
            base_factors = [factors[0]]

        orthogonal = factor_data.copy()

        # 对非基准因子进行正交化
        for factor in factors:
            if factor in base_factors:
                continue

            # 对基准因子组回归
            X = factor_data[base_factors].values
            y = factor_data[factor].values

            # 处理缺失值
            valid_mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
            if valid_mask.sum() < 10:
                logger.warning(f"Factor {factor} has too few valid samples for regression")
                continue

            X_valid = X[valid_mask]
            y_valid = y[valid_mask]

            # 线性回归
            try:
                from sklearn.linear_model import LinearRegression

                model = LinearRegression()
                model.fit(X_valid, y_valid)

                # 预测并计算残差
                y_pred = model.predict(X)
                residuals = y - y_pred

                # 标准化残差
                residuals = (residuals - np.nanmean(residuals)) / (np.nanstd(residuals) + 1e-10)
                orthogonal[factor] = residuals

            except Exception as e:
                logger.error(f"Regression orthogonalization failed for {factor}: {e}")
                continue

        logger.info(f"Regression orthogonalization completed for {len(factors)} factors")

        return OrthogonalizationResult(
            original_factors=factor_data,
            orthogonal_factors=orthogonal,
            transformation_matrix=None,
            explained_variance=None,
            method="regression",
        )

    def orthogonalize_pca(
        self,
        factor_data: pd.DataFrame,
        n_components: int | None = None,
        variance_threshold: float = 0.95,
    ) -> OrthogonalizationResult:
        """
        PCA正交化

        使用主成分分析将因子转换为正交的主成分
        优点：完全正交，降维
        缺点：失去原始因子的可解释性

        Args:
            factor_data: 因子数据
            n_components: 主成分数量，None则根据方差阈值自动确定
            variance_threshold: 累计方差解释比例阈值

        Returns:
            正交化结果
        """
        if factor_data.empty:
            return OrthogonalizationResult(
                original_factors=factor_data,
                orthogonal_factors=factor_data,
                transformation_matrix=None,
                explained_variance=None,
                method="pca",
            )

        # 标准化
        factor_std = (factor_data - factor_data.mean()) / factor_data.std()
        factor_std = factor_std.fillna(0)

        # PCA
        if n_components is None:
            pca = PCA(n_components=variance_threshold, svd_solver="full")
        else:
            pca = PCA(n_components=n_components)

        try:
            principal_components = pca.fit_transform(factor_std.values)

            # 创建主成分DataFrame
            pc_names = [f"PC{i+1}" for i in range(principal_components.shape[1])]
            orthogonal = pd.DataFrame(
                principal_components,
                index=factor_data.index,
                columns=pc_names,
            )

            logger.info(
                f"PCA orthogonalization: {len(factor_data.columns)} factors -> "
                f"{len(pc_names)} components (variance explained: {pca.explained_variance_ratio_.sum():.2%})"
            )

            return OrthogonalizationResult(
                original_factors=factor_data,
                orthogonal_factors=orthogonal,
                transformation_matrix=pca.components_,
                explained_variance=pca.explained_variance_ratio_,
                method="pca",
            )

        except Exception as e:
            logger.error(f"PCA orthogonalization failed: {e}")
            return OrthogonalizationResult(
                original_factors=factor_data,
                orthogonal_factors=factor_data,
                transformation_matrix=None,
                explained_variance=None,
                method="pca",
            )

    def orthogonalize_symmetric(self, factor_data: pd.DataFrame) -> OrthogonalizationResult:
        """
        对称正交化

        使用对称正交化方法，所有因子地位平等
        方法：X_orth = X @ (X.T @ X)^(-1/2)

        Args:
            factor_data: 因子数据

        Returns:
            正交化结果
        """
        if factor_data.empty:
            return OrthogonalizationResult(
                original_factors=factor_data,
                orthogonal_factors=factor_data,
                transformation_matrix=None,
                explained_variance=None,
                method="symmetric",
            )

        # 标准化
        factor_std = (factor_data - factor_data.mean()) / factor_data.std()
        factor_std = factor_std.fillna(0)

        try:
            # 计算相关矩阵
            corr_matrix = factor_std.T @ factor_std / len(factor_std)

            # 特征值分解
            eigenvalues, eigenvectors = np.linalg.eigh(corr_matrix)

            # 避免数值问题
            eigenvalues = np.maximum(eigenvalues, 1e-10)

            # 计算 (X.T @ X)^(-1/2)
            inv_sqrt = eigenvectors @ np.diag(1.0 / np.sqrt(eigenvalues)) @ eigenvectors.T

            # 对称正交化
            orthogonal_values = factor_std.values @ inv_sqrt
            orthogonal = pd.DataFrame(
                orthogonal_values,
                index=factor_data.index,
                columns=factor_data.columns,
            )

            logger.info(f"Symmetric orthogonalization completed for {len(factor_data.columns)} factors")

            return OrthogonalizationResult(
                original_factors=factor_data,
                orthogonal_factors=orthogonal,
                transformation_matrix=inv_sqrt,
                explained_variance=None,
                method="symmetric",
            )

        except Exception as e:
            logger.error(f"Symmetric orthogonalization failed: {e}")
            return OrthogonalizationResult(
                original_factors=factor_data,
                orthogonal_factors=factor_data,
                transformation_matrix=None,
                explained_variance=None,
                method="symmetric",
            )

    # ==================== 3. 因子独立性评估 ====================

    def evaluate_independence(self, factor_data: pd.DataFrame) -> dict[str, float]:
        """
        评估因子独立性

        指标：
        1. 平均相关性：因子间平均绝对相关系数
        2. 最大相关性：因子间最大绝对相关系数
        3. VIF（方差膨胀因子）：衡量多重共线性

        Args:
            factor_data: 因子数据

        Returns:
            独立性指标字典
        """
        if factor_data.empty or len(factor_data.columns) < 2:
            return {
                "mean_correlation": 0.0,
                "max_correlation": 0.0,
                "mean_vif": 1.0,
            }

        # 计算相关矩阵
        corr_matrix = factor_data.corr(method="pearson").abs()

        # 平均相关性（排除对角线）
        mask = ~np.eye(len(corr_matrix), dtype=bool)
        mean_corr = corr_matrix.values[mask].mean()

        # 最大相关性（排除对角线）
        max_corr = corr_matrix.values[mask].max()

        # 计算VIF
        vif_values = []
        factors = factor_data.columns.tolist()

        for i, factor in enumerate(factors):
            # 用其他因子预测当前因子
            X = factor_data.drop(columns=[factor]).values
            y = factor_data[factor].values

            # 处理缺失值
            valid_mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
            if valid_mask.sum() < 10:
                continue

            X_valid = X[valid_mask]
            y_valid = y[valid_mask]

            try:
                from sklearn.linear_model import LinearRegression

                model = LinearRegression()
                model.fit(X_valid, y_valid)
                r_squared = model.score(X_valid, y_valid)

                # VIF = 1 / (1 - R^2)
                vif = 1.0 / (1.0 - r_squared + 1e-10)
                vif_values.append(vif)

            except Exception:
                continue

        mean_vif = np.mean(vif_values) if vif_values else 1.0

        metrics = {
            "mean_correlation": float(mean_corr),
            "max_correlation": float(max_corr),
            "mean_vif": float(mean_vif),
        }

        logger.info(
            f"Independence metrics: mean_corr={mean_corr:.3f}, "
            f"max_corr={max_corr:.3f}, mean_vif={mean_vif:.2f}"
        )

        return metrics

    # ==================== 4. 完整流程 ====================

    def process_factors(
        self,
        factor_data: pd.DataFrame,
        ic_values: dict[str, float] | None = None,
        remove_redundant: bool = True,
        orthogonalize: bool = True,
        method: OrthogonalizationMethod = OrthogonalizationMethod.REGRESSION,
        corr_threshold: float = 0.7,
    ) -> tuple[pd.DataFrame, dict[str, any]]:
        """
        完整的因子去冗余与正交化流程

        Args:
            factor_data: 因子数据
            ic_values: 各因子IC均值
            remove_redundant: 是否剔除冗余因子
            orthogonalize: 是否正交化
            method: 正交化方法
            corr_threshold: 冗余判断阈值

        Returns:
            (处理后的因子数据, 处理信息字典)
        """
        info = {
            "original_factors": factor_data.columns.tolist(),
            "removed_factors": [],
            "orthogonalization_method": None,
            "independence_before": {},
            "independence_after": {},
        }

        # 评估原始因子独立性
        info["independence_before"] = self.evaluate_independence(factor_data)

        processed_data = factor_data.copy()

        # 1. 剔除冗余因子
        if remove_redundant and ic_values is not None:
            redundant_pairs = self.identify_redundant_factors(
                factor_data,
                ic_values=ic_values,
                corr_threshold=corr_threshold,
            )

            if redundant_pairs:
                factors_to_remove = self.select_factors_by_ic(redundant_pairs, ic_values)
                processed_data = processed_data.drop(columns=list(factors_to_remove))
                info["removed_factors"] = list(factors_to_remove)

                logger.info(f"Removed {len(factors_to_remove)} redundant factors")

        # 2. 正交化
        if orthogonalize and len(processed_data.columns) > 1:
            if method == OrthogonalizationMethod.GRAM_SCHMIDT:
                result = self.orthogonalize_gram_schmidt(processed_data)
            elif method == OrthogonalizationMethod.REGRESSION:
                result = self.orthogonalize_regression(processed_data)
            elif method == OrthogonalizationMethod.PCA:
                result = self.orthogonalize_pca(processed_data)
            elif method == OrthogonalizationMethod.SYMMETRIC:
                result = self.orthogonalize_symmetric(processed_data)
            else:
                raise ValueError(f"Unknown orthogonalization method: {method}")

            processed_data = result.orthogonal_factors
            info["orthogonalization_method"] = method

        # 评估处理后的因子独立性
        info["independence_after"] = self.evaluate_independence(processed_data)

        logger.info(
            f"Factor processing completed: {len(factor_data.columns)} -> {len(processed_data.columns)} factors"
        )

        return processed_data, info
