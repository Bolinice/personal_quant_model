"""
测试 Combinatorial Purged Cross-Validation (CPCV)

验证：
1. Purging 逻辑正确性（训练集不包含与测试集重叠的样本）
2. Embargo 逻辑正确性（禁运期内的样本被排除）
3. Combinatorial 组合数正确性
4. 与 sklearn.TimeSeriesSplit 的对比
"""

import numpy as np
import pandas as pd
import pytest

from app.core.pure.cpcv import CombinatorialPurgedCV, PurgedKFold, get_embargo_times, get_train_times


class TestGetTrainTimes:
    """测试 get_train_times 函数"""

    def test_basic_purging(self):
        """测试基本的 Purging 逻辑"""
        # 训练样本结束时间
        t1 = pd.Series([10, 20, 30, 40, 50], index=[0, 1, 2, 3, 4])
        # 测试集时间范围 [30, 40]
        test_times = pd.Series([30, 40], index=[2, 3])

        train_times = get_train_times(t1, test_times)

        # 只有结束时间 < 30 的样本应该保留
        assert len(train_times) == 2
        assert list(train_times.index) == [0, 1]
        assert list(train_times.values) == [10, 20]

    def test_no_overlap(self):
        """测试无重叠情况"""
        t1 = pd.Series([10, 20, 30], index=[0, 1, 2])
        test_times = pd.Series([40, 50], index=[3, 4])

        train_times = get_train_times(t1, test_times)

        # 所有训练样本都应该保留
        assert len(train_times) == 3
        assert list(train_times.index) == [0, 1, 2]

    def test_all_overlap(self):
        """测试完全重叠情况"""
        t1 = pd.Series([40, 50, 60], index=[0, 1, 2])
        test_times = pd.Series([30, 35], index=[3, 4])

        train_times = get_train_times(t1, test_times)

        # 所有训练样本都应该被清除
        assert len(train_times) == 0


class TestGetEmbargoTimes:
    """测试 get_embargo_times 函数"""

    def test_basic_embargo(self):
        """测试基本的 Embargo 计算"""
        times = pd.Series([10, 20, 30, 40, 50], index=[0, 1, 2, 3, 4])
        pct_embargo = 0.2  # 20% = 1个样本

        embargo_time = get_embargo_times(times, pct_embargo)

        # 应该返回最后1个样本的时间
        assert embargo_time == 50

    def test_zero_embargo(self):
        """测试零禁运期"""
        times = pd.Series([10, 20, 30], index=[0, 1, 2])
        pct_embargo = 0.0

        embargo_time = get_embargo_times(times, pct_embargo)

        # 应该返回最后一个样本的时间
        assert embargo_time == 30

    def test_large_embargo(self):
        """测试大禁运期"""
        times = pd.Series([10, 20, 30, 40, 50], index=[0, 1, 2, 3, 4])
        pct_embargo = 0.6  # 60% = 3个样本

        embargo_time = get_embargo_times(times, pct_embargo)

        # 应该返回最后3个样本的最大时间
        assert embargo_time == 50


class TestCombinatorialPurgedCV:
    """测试 CombinatorialPurgedCV"""

    def test_basic_split(self):
        """测试基本分割"""
        # 创建简单的时间序列数据
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        X = pd.DataFrame({"value": range(100)}, index=dates)

        cv = CombinatorialPurgedCV(n_splits=5, n_test_splits=1, pct_embargo=0.0)

        splits = list(cv.split(X))

        # n_test_splits=1 时，由于 Purging，第一个分割会被跳过（没有训练数据在它之前）
        # 所以实际有 4 个有效分割
        assert len(splits) == 4

        # 每个分割应该有训练集和测试集
        for train_idx, test_idx in splits:
            assert len(train_idx) > 0
            assert len(test_idx) > 0
            # 训练集和测试集不应该重叠
            assert len(set(train_idx) & set(test_idx)) == 0

    def test_combinatorial_splits(self):
        """测试组合分割数量"""
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        X = pd.DataFrame({"value": range(100)}, index=dates)

        # n_test_splits=2 时，理论上有 C(5,2) = 10 个组合
        # 但由于 Purging，某些组合会被跳过（训练集为空）
        cv = CombinatorialPurgedCV(n_splits=5, n_test_splits=2, pct_embargo=0.0)
        assert cv.get_n_splits() == 10

        splits = list(cv.split(X))
        # 实际有效分割数会少于理论值
        assert len(splits) >= 6  # 至少有一半的组合是有效的
        assert len(splits) <= 10  # 不会超过理论最大值

    def test_purging_effect(self):
        """测试 Purging 效果"""
        # 创建有明确时间跨度的数据
        t1 = pd.Series([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], index=range(10))

        cv = CombinatorialPurgedCV(n_splits=5, n_test_splits=1, pct_embargo=0.0)

        for train_idx, test_idx in cv.split(t1):
            # 训练集的最大结束时间应该 < 测试集的最小开始时间
            train_max_time = t1.iloc[train_idx].max()
            test_min_time = t1.iloc[test_idx].min()

            assert train_max_time < test_min_time, (
                f"Purging failed: train_max={train_max_time}, test_min={test_min_time}"
            )

    def test_embargo_effect(self):
        """测试 Embargo 效果"""
        t1 = pd.Series(range(100), index=range(100))

        # 无禁运期
        cv_no_embargo = CombinatorialPurgedCV(n_splits=5, n_test_splits=1, pct_embargo=0.0)
        splits_no_embargo = list(cv_no_embargo.split(t1))

        # 有禁运期
        cv_with_embargo = CombinatorialPurgedCV(n_splits=5, n_test_splits=1, pct_embargo=0.1)
        splits_with_embargo = list(cv_with_embargo.split(t1))

        # 有禁运期时，训练集应该更小
        for (train_no, _), (train_with, _) in zip(splits_no_embargo, splits_with_embargo, strict=False):
            assert len(train_with) <= len(train_no), "Embargo should reduce training set size"

    def test_with_numpy_array(self):
        """测试 NumPy 数组输入"""
        X = np.random.randn(100, 5)

        cv = CombinatorialPurgedCV(n_splits=5, n_test_splits=1, pct_embargo=0.0)
        splits = list(cv.split(X))

        # 由于 Purging，第一个分割会被跳过
        assert len(splits) == 4
        for train_idx, test_idx in splits:
            assert len(train_idx) > 0
            assert len(test_idx) > 0

    def test_with_groups(self):
        """测试分组参数"""
        X = np.random.randn(100, 5)
        # 每10个样本一组
        groups = np.repeat(range(10), 10)

        cv = CombinatorialPurgedCV(n_splits=5, n_test_splits=1, pct_embargo=0.0)
        splits = list(cv.split(X, groups=groups))

        # 由于 Purging，第一个分割会被跳过
        assert len(splits) == 4

    def test_invalid_parameters(self):
        """测试无效参数"""
        with pytest.raises(ValueError, match="n_splits must be >= 2"):
            CombinatorialPurgedCV(n_splits=1)

        with pytest.raises(ValueError, match="n_test_splits must be in"):
            CombinatorialPurgedCV(n_splits=5, n_test_splits=6)

        with pytest.raises(ValueError, match="pct_embargo must be in"):
            CombinatorialPurgedCV(n_splits=5, pct_embargo=1.5)


class TestPurgedKFold:
    """测试 PurgedKFold"""

    def test_basic_split(self):
        """测试基本分割"""
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        t1 = pd.Series(dates, index=dates)

        cv = PurgedKFold(n_splits=5, pct_embargo=0.0)
        splits = list(cv.split(t1))

        # 由于 Purging，第一个折会被跳过（没有训练数据在它之前）
        assert len(splits) == 4

        for train_idx, test_idx in splits:
            assert len(train_idx) > 0
            assert len(test_idx) > 0
            # 训练集和测试集不应该重叠
            assert len(set(train_idx) & set(test_idx)) == 0

    def test_purging_in_kfold(self):
        """测试 KFold 中的 Purging"""
        # 创建有时间跨度的数据
        dates = pd.date_range("2020-01-01", periods=50, freq="D")
        t1 = pd.Series(dates, index=dates)

        cv = PurgedKFold(n_splits=5, pct_embargo=0.0)

        for train_idx, test_idx in cv.split(t1):
            # 训练集的最大时间应该 < 测试集的最小时间
            train_times = t1.iloc[train_idx]
            test_times = t1.iloc[test_idx]

            train_max = train_times.max()
            test_min = test_times.min()

            assert train_max < test_min, f"Purging failed: train_max={train_max}, test_min={test_min}"

    def test_embargo_in_kfold(self):
        """测试 KFold 中的 Embargo"""
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        t1 = pd.Series(dates, index=dates)

        # 无禁运期
        cv_no_embargo = PurgedKFold(n_splits=5, pct_embargo=0.0)
        splits_no_embargo = list(cv_no_embargo.split(t1))

        # 有禁运期
        cv_with_embargo = PurgedKFold(n_splits=5, pct_embargo=0.1)
        splits_with_embargo = list(cv_with_embargo.split(t1))

        # 有禁运期时，训练集应该更小
        for (train_no, _), (train_with, _) in zip(splits_no_embargo, splits_with_embargo, strict=False):
            assert len(train_with) <= len(train_no)

    def test_with_dataframe(self):
        """测试 DataFrame 输入"""
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        X = pd.DataFrame({"value": range(100)}, index=dates)

        cv = PurgedKFold(n_splits=5, pct_embargo=0.0)
        splits = list(cv.split(X))

        # 由于 Purging，第一个折会被跳过
        assert len(splits) == 4

    def test_invalid_input(self):
        """测试无效输入"""
        # NumPy 数组应该抛出错误
        X = np.random.randn(100, 5)
        cv = PurgedKFold(n_splits=5)

        with pytest.raises(TypeError, match="X must be pd.DataFrame or pd.Series"):
            list(cv.split(X))

    def test_invalid_parameters(self):
        """测试无效参数"""
        with pytest.raises(ValueError, match="n_splits must be >= 2"):
            PurgedKFold(n_splits=1)

        with pytest.raises(ValueError, match="pct_embargo must be in"):
            PurgedKFold(n_splits=5, pct_embargo=1.5)


class TestCPCVComparison:
    """对比 CPCV 与 sklearn.TimeSeriesSplit"""

    def test_vs_timeseries_split(self):
        """对比 CPCV 和 TimeSeriesSplit 的差异"""
        from sklearn.model_selection import TimeSeriesSplit

        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        X = pd.DataFrame({"value": range(100)}, index=dates)

        # sklearn TimeSeriesSplit
        tscv = TimeSeriesSplit(n_splits=5)
        ts_splits = list(tscv.split(X))

        # CPCV (n_test_splits=1, 无禁运期)
        cpcv = CombinatorialPurgedCV(n_splits=5, n_test_splits=1, pct_embargo=0.0)
        cp_splits = list(cpcv.split(X))

        # CPCV 由于 Purging 会跳过第一个分割
        assert len(ts_splits) == 5
        assert len(cp_splits) == 4

        # CPCV 的训练集应该 <= TimeSeriesSplit（因为 Purging）
        # 比较除第一个之外的分割
        for ts_split, cp_split in zip(ts_splits[1:], cp_splits, strict=False):
            ts_train, _ = ts_split
            cp_train, _ = cp_split
            assert len(cp_train) <= len(ts_train), "CPCV should have smaller or equal training set"

    def test_information_leakage_prevention(self):
        """验证 CPCV 防止信息泄露"""
        # 创建有重叠标签的数据
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        # 假设每个样本的标签依赖未来20天的数据
        t1 = pd.Series(dates + pd.Timedelta(days=20), index=dates)

        cv = CombinatorialPurgedCV(n_splits=5, n_test_splits=1, pct_embargo=0.2)

        for train_idx, test_idx in cv.split(t1):
            # 训练集的最大结束时间应该 < 测试集的最小开始时间
            train_max_time = t1.iloc[train_idx].max()
            test_min_time = t1.iloc[test_idx].min()

            assert train_max_time < test_min_time, "Information leakage detected!"


class TestCPCVIntegration:
    """集成测试：CPCV 在实际场景中的应用"""

    def test_with_factor_data(self):
        """测试 CPCV 在因子数据上的应用"""
        # 模拟因子数据 - 按日期级别进行交叉验证
        dates = pd.date_range("2020-01-01", periods=252, freq="D")  # 1年交易日

        # 创建日期级别的数据（每个日期一个样本）
        X = pd.DataFrame({
            "factor1": np.random.randn(252),
            "factor2": np.random.randn(252),
        }, index=dates)

        y = pd.Series(np.random.randn(252) * 0.02, index=dates)

        cv = CombinatorialPurgedCV(n_splits=5, n_test_splits=1, pct_embargo=0.05)

        # 验证可以正常分割
        splits = list(cv.split(X, y))
        # 由于 Purging，第一个分割会被跳过
        assert len(splits) >= 3  # 至少有3个有效分割

        # 验证每个分割的训练集和测试集大小合理
        for train_idx, test_idx in splits:
            assert len(train_idx) > 0
            assert len(test_idx) > 0
            # 训练集应该大于等于测试集
            assert len(train_idx) >= len(test_idx)

    def test_walk_forward_compatibility(self):
        """测试 CPCV 与 Walk-Forward 的兼容性"""
        dates = pd.date_range("2020-01-01", periods=500, freq="D")
        X = pd.DataFrame({"value": range(500)}, index=dates)

        # 使用 CPCV 进行 Walk-Forward 式分割
        cv = CombinatorialPurgedCV(n_splits=10, n_test_splits=1, pct_embargo=0.05)

        splits = list(cv.split(X))

        # 验证时间顺序
        for i, (train_idx, test_idx) in enumerate(splits):
            # 训练集应该在测试集之前
            assert train_idx.max() < test_idx.min(), f"Split {i}: training set overlaps with test set"

            # 测试集应该是连续的时间段
            test_dates = X.index[test_idx]
            assert (test_dates == pd.date_range(test_dates[0], periods=len(test_dates), freq="D")).all()
