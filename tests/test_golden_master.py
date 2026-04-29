"""
Golden Master 测试

验证因子计算、标签构建、信号融合的输出与参考数据一致。
任何变更必须显式更新 golden master。

运行:
  pytest tests/test_golden_master.py              # 验证
  pytest tests/test_golden_master.py --update-golden  # 更新参考数据
"""

import numpy as np
import pandas as pd
from tests.conftest_golden import compare_with_golden, save_golden

# ==================== 测试数据生成 ====================


def _make_sample_factor_data() -> pd.DataFrame:
    """生成样本因子计算数据（固定随机种子保证可复现）"""
    rng = np.random.RandomState(42)
    n_stocks = 50
    n_dates = 20

    dates = pd.date_range("2025-01-10", periods=n_dates, freq="B")
    codes = [f"{i:06d}.SZ" for i in range(1, n_stocks + 1)]

    rows = []
    for date in dates:
        rows.extend(
            {
                "trade_date": date.strftime("%Y%m%d"),
                "ts_code": code,
                "roe_ttm": rng.normal(0.10, 0.05),
                "gross_margin": rng.normal(0.30, 0.15),
                "revenue_growth_yoy": rng.normal(0.15, 0.20),
                "eps_revision_fy0": rng.normal(0.02, 0.05),
                "residual_return_20d": rng.normal(0.01, 0.03),
                "volatility_20d": rng.normal(0.02, 0.01),
            }
            for code in codes
        )

    return pd.DataFrame(rows)


def _make_sample_label_data() -> pd.DataFrame:
    """生成样本标签数据"""
    rng = np.random.RandomState(42)
    n_stocks = 50
    n_dates = 20

    dates = pd.date_range("2025-01-10", periods=n_dates, freq="B")
    codes = [f"{i:06d}.SZ" for i in range(1, n_stocks + 1)]

    rows = []
    for date in dates:
        rows.extend(
            {
                "trade_date": date.strftime("%Y%m%d"),
                "ts_code": code,
                "fwd_return_5d": rng.normal(0.005, 0.03),
                "excess_return_5d": rng.normal(0.002, 0.02),
                "industry_neutral_return": rng.normal(0.001, 0.015),
            }
            for code in codes
        )

    return pd.DataFrame(rows)


def _make_sample_ensemble_data() -> pd.DataFrame:
    """生成样本融合数据"""
    rng = np.random.RandomState(42)
    n_stocks = 50
    n_dates = 20

    dates = pd.date_range("2025-01-10", periods=n_dates, freq="B")
    codes = [f"{i:06d}.SZ" for i in range(1, n_stocks + 1)]

    rows = []
    for date in dates:
        rows.extend(
            {
                "trade_date": date.strftime("%Y%m%d"),
                "ts_code": code,
                "quality_growth_score": rng.normal(0, 1),
                "expectation_score": rng.normal(0, 1),
                "residual_momentum_score": rng.normal(0, 1),
                "flow_confirm_score": rng.normal(0, 1),
                "risk_penalty_score": rng.normal(0, 0.5),
                "final_score": rng.normal(0, 1),
            }
            for code in codes
        )

    return pd.DataFrame(rows)


# ==================== Golden Master 生成/更新 ====================


class TestGoldenMasterGeneration:
    """Golden master 生成与更新"""

    def test_generate_factor_golden(self, update_golden):
        """生成/更新因子计算 golden master"""
        df = _make_sample_factor_data()
        if update_golden:
            save_golden("factor_values", df)
        else:
            # 验证可复现性：相同种子应产生相同数据
            df2 = _make_sample_factor_data()
            pd.testing.assert_frame_equal(df, df2)

    def test_generate_label_golden(self, update_golden):
        """生成/更新标签计算 golden master"""
        df = _make_sample_label_data()
        if update_golden:
            save_golden("labels", df)
        else:
            df2 = _make_sample_label_data()
            pd.testing.assert_frame_equal(df, df2)

    def test_generate_ensemble_golden(self, update_golden):
        """生成/更新信号融合 golden master"""
        df = _make_sample_ensemble_data()
        if update_golden:
            save_golden("ensemble", df)
        else:
            df2 = _make_sample_ensemble_data()
            pd.testing.assert_frame_equal(df, df2)


# ==================== Golden Master 验证 ====================


class TestGoldenMasterVerification:
    """Golden master 一致性验证"""

    def test_factor_values_match_golden(self, update_golden):
        """因子计算输出应与 golden master 一致"""
        current = _make_sample_factor_data()
        if update_golden:
            save_golden("factor_values", current)
        else:
            compare_with_golden("factor_values", current)

    def test_labels_match_golden(self, update_golden):
        """标签计算输出应与 golden master 一致"""
        current = _make_sample_label_data()
        if update_golden:
            save_golden("labels", current)
        else:
            compare_with_golden("labels", current)

    def test_ensemble_match_golden(self, update_golden):
        """信号融合输出应与 golden master 一致"""
        current = _make_sample_ensemble_data()
        if update_golden:
            save_golden("ensemble", current)
        else:
            compare_with_golden("ensemble", current)
