"""
Combinatorial Purged Cross-Validation (CPCV)

基于 Advances in Financial Machine Learning (Lopez de Prado) 的 CPCV 实现。
解决时间序列回测中的三大问题：
1. 信息泄露 (Information Leakage)
2. 样本重叠 (Sample Overlap)
3. 过拟合 (Overfitting)

核心技术：
- Purging: 清除训练集和测试集之间的重叠样本
- Embargo: 在测试集后添加禁运期，防止标签泄露
- Combinatorial: 组合多个测试集，增加样本外评估的稳健性

参考文献:
- Lopez de Prado, M. (2018). Advances in Financial Machine Learning. Wiley.
- Chapter 7: Cross-Validation in Finance
"""

from itertools import combinations
from typing import Iterator

import numpy as np
import pandas as pd


def get_train_times(
    t1: pd.Series,
    test_times: pd.Series,
) -> pd.Series:
    """
    获取训练集时间索引（排除与测试集重叠的样本）

    Purging 逻辑：
    - 如果训练样本的结束时间 t1[i] >= 测试样本的开始时间 test_times.min()
    - 则该训练样本可能包含测试集信息，需要清除

    Args:
        t1: 训练样本的结束时间 (index=样本ID, value=结束时间)
        test_times: 测试集的时间索引

    Returns:
        清除后的训练集时间索引
    """
    # 测试集的最早时间
    test_start = test_times.min()

    # 保留结束时间早于测试集开始的样本
    train_times = t1[t1 < test_start]

    return train_times


def get_embargo_times(
    times: pd.Series,
    pct_embargo: float,
) -> pd.Series:
    """
    计算禁运期（Embargo Period）

    在测试集后添加一段时间作为缓冲区，防止标签计算时使用了测试集之后的信息。
    例如：如果标签是未来20天收益率，则需要至少20天的禁运期。

    Args:
        times: 时间索引
        pct_embargo: 禁运期百分比（相对于测试集大小）

    Returns:
        禁运期结束时间
    """
    step = int(len(times) * pct_embargo)
    if step == 0:
        # 至少1个样本的禁运期
        mbrg = times.iloc[-1]
    else:
        mbrg = times.iloc[-step:].max()

    return mbrg


class CombinatorialPurgedCV:
    """
    组合清洗交叉验证 (Combinatorial Purged Cross-Validation)

    相比 sklearn.TimeSeriesSplit 的优势：
    1. Purging: 自动清除训练集和测试集之间的重叠样本
    2. Embargo: 在测试集后添加禁运期，防止标签泄露
    3. Combinatorial: 生成多个测试集组合，增加评估稳健性

    Example:
        >>> t1 = pd.Series([10, 20, 30, 40, 50], index=[0, 1, 2, 3, 4])
        >>> cv = CombinatorialPurgedCV(n_splits=3, n_test_splits=2, pct_embargo=0.1)
        >>> for train_idx, test_idx in cv.split(t1):
        ...     print(f"Train: {train_idx}, Test: {test_idx}")
    """

    def __init__(
        self,
        n_splits: int = 5,
        n_test_splits: int = 2,
        pct_embargo: float = 0.01,
    ):
        """
        Args:
            n_splits: 总分割数（类似 KFold 的 n_splits）
            n_test_splits: 每次组合使用的测试集数量（1 = 传统CV，2+ = 组合CV）
            pct_embargo: 禁运期百分比（相对于测试集大小）
        """
        if n_splits < 2:
            raise ValueError(f"n_splits must be >= 2, got {n_splits}")
        if n_test_splits < 1 or n_test_splits > n_splits:
            raise ValueError(f"n_test_splits must be in [1, {n_splits}], got {n_test_splits}")
        if not 0 <= pct_embargo < 1:
            raise ValueError(f"pct_embargo must be in [0, 1), got {pct_embargo}")

        self.n_splits = n_splits
        self.n_test_splits = n_test_splits
        self.pct_embargo = pct_embargo

    def split(
        self,
        X: pd.DataFrame | pd.Series | np.ndarray,
        y: pd.Series | np.ndarray | None = None,
        groups: np.ndarray | None = None,
    ) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """
        生成训练集和测试集索引

        Args:
            X: 特征矩阵或时间序列（必须有时间索引或提供 t1）
            y: 标签（可选）
            groups: 分组（可选，用于按日期分组）

        Yields:
            (train_indices, test_indices) 元组
        """
        # 提取时间索引
        n_samples = len(X)

        # 如果提供了 groups，使用 groups 作为时间标记
        if groups is not None:
            if len(groups) != n_samples:
                raise ValueError(f"groups length {len(groups)} != X length {n_samples}")
            # 将 groups 转换为时间索引
            unique_groups = np.unique(groups)
            group_to_time = {g: i for i, g in enumerate(unique_groups)}
            t1 = pd.Series([group_to_time[g] for g in groups], index=range(n_samples))
        else:
            # 使用位置索引作为时间标记
            if isinstance(X, (pd.DataFrame, pd.Series)) and isinstance(X.index, pd.DatetimeIndex):
                # DatetimeIndex 转换为整数（天数）
                t1 = pd.Series((X.index - X.index.min()).days.values, index=range(n_samples))
            else:
                # 使用位置索引
                t1 = pd.Series(range(n_samples), index=range(n_samples))

        # 分割成 n_splits 个时间段
        split_indices = np.array_split(np.arange(n_samples), self.n_splits)

        # 生成所有可能的测试集组合
        test_splits = list(combinations(range(self.n_splits), self.n_test_splits))

        for test_split_combo in test_splits:
            # 合并测试集
            test_indices = np.concatenate([split_indices[i] for i in test_split_combo])
            test_indices = np.sort(test_indices)

            # 获取测试集的时间范围
            test_times = t1.iloc[test_indices]

            # Purging: 清除与测试集重叠的训练样本
            train_times = get_train_times(t1, test_times)
            train_indices = train_times.index.to_numpy()

            # Embargo: 添加禁运期
            if self.pct_embargo > 0:
                embargo_time = get_embargo_times(test_times, self.pct_embargo)
                # 从训练集中移除禁运期内的样本
                train_indices = train_indices[t1.iloc[train_indices].values < embargo_time]

            # 确保训练集和测试集不为空
            if len(train_indices) == 0 or len(test_indices) == 0:
                continue

            yield train_indices, test_indices

    def get_n_splits(
        self,
        X: pd.DataFrame | pd.Series | np.ndarray | None = None,
        y: pd.Series | np.ndarray | None = None,
        groups: np.ndarray | None = None,
    ) -> int:
        """
        返回交叉验证的折数

        组合数 = C(n_splits, n_test_splits)
        """
        from math import comb
        return comb(self.n_splits, self.n_test_splits)


class PurgedKFold:
    """
    清洗 K 折交叉验证 (Purged K-Fold)

    相比 sklearn.KFold 的改进：
    1. 考虑样本的时间跨度（t0 到 t1）
    2. 自动清除训练集中与测试集时间重叠的样本
    3. 支持禁运期（Embargo）

    适用场景：
    - 样本有明确的开始时间和结束时间
    - 需要防止信息泄露（如标签计算依赖未来数据）

    Example:
        >>> t1 = pd.Series([10, 20, 30, 40, 50], index=[0, 10, 20, 30, 40])
        >>> cv = PurgedKFold(n_splits=3, pct_embargo=0.1)
        >>> for train_idx, test_idx in cv.split(t1):
        ...     print(f"Train: {train_idx}, Test: {test_idx}")
    """

    def __init__(
        self,
        n_splits: int = 5,
        pct_embargo: float = 0.01,
    ):
        """
        Args:
            n_splits: 折数
            pct_embargo: 禁运期百分比
        """
        if n_splits < 2:
            raise ValueError(f"n_splits must be >= 2, got {n_splits}")
        if not 0 <= pct_embargo < 1:
            raise ValueError(f"pct_embargo must be in [0, 1), got {pct_embargo}")

        self.n_splits = n_splits
        self.pct_embargo = pct_embargo

    def split(
        self,
        X: pd.DataFrame | pd.Series,
        y: pd.Series | None = None,
        groups: np.ndarray | None = None,
    ) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """
        生成训练集和测试集索引

        Args:
            X: 特征矩阵（必须有 DatetimeIndex）或样本结束时间 Series
            y: 标签（可选）
            groups: 分组（可选）

        Yields:
            (train_indices, test_indices) 元组
        """
        # 提取样本结束时间 t1
        if isinstance(X, pd.Series):
            # 如果是 Series，使用其值作为时间，索引作为位置
            if isinstance(X.index, pd.DatetimeIndex):
                # 索引是时间，转换为整数
                t1 = pd.Series((X.index - X.index.min()).days.values, index=range(len(X)))
            else:
                # 使用 Series 的值作为时间
                t1 = pd.Series(X.values, index=range(len(X)))
        elif isinstance(X, pd.DataFrame):
            if not isinstance(X.index, pd.DatetimeIndex):
                raise ValueError("X must have DatetimeIndex or provide t1 as Series")
            # 假设每个样本的结束时间就是其索引时间
            t1 = pd.Series((X.index - X.index.min()).days.values, index=range(len(X)))
        else:
            raise TypeError("X must be pd.DataFrame or pd.Series")

        # 分割索引
        n_samples = len(t1)
        indices = np.arange(n_samples)
        split_indices = np.array_split(indices, self.n_splits)

        for i in range(self.n_splits):
            # 测试集
            test_indices = split_indices[i]
            test_times = t1.iloc[test_indices]

            # 训练集（排除测试集）
            train_indices = np.concatenate([split_indices[j] for j in range(self.n_splits) if j != i])

            # Purging: 清除与测试集重叠的训练样本
            train_times_series = t1.iloc[train_indices]
            # 重新索引为位置索引
            train_times_series.index = train_indices
            purged_train_times = get_train_times(train_times_series, test_times)
            train_indices = purged_train_times.index.to_numpy()

            # Embargo: 添加禁运期
            if self.pct_embargo > 0:
                embargo_time = get_embargo_times(test_times, self.pct_embargo)
                # 从训练集中移除禁运期内的样本
                train_indices = train_indices[t1.iloc[train_indices].values < embargo_time]

            # 确保训练集不为空
            if len(train_indices) == 0:
                continue

            yield train_indices, test_indices

    def get_n_splits(
        self,
        X: pd.DataFrame | pd.Series | None = None,
        y: pd.Series | None = None,
        groups: np.ndarray | None = None,
    ) -> int:
        """返回折数"""
        return self.n_splits
