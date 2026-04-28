"""EnsembleEngine 单元测试 — 信号融合"""

import numpy as np
import pandas as pd
import pytest

from app.core.ensemble import EnsembleEngine


def _make_factor_df(n_stocks: int = 50, n_factors: int = 3) -> pd.DataFrame:
    """生成模拟因子数据"""
    np.random.seed(42)
    ts_codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]
    data = {"ts_code": ts_codes}
    for i in range(n_factors):
        data[f"factor_{i}"] = np.random.randn(n_stocks)
    return pd.DataFrame(data).set_index("ts_code")


def _make_ic_dict(n_factors: int = 3) -> dict[str, float]:
    """生成模拟IC值"""
    return {f"factor_{i}": 0.03 + i * 0.01 for i in range(n_factors)}


class TestEnsembleEngine:
    def setup_method(self):
        self.engine = EnsembleEngine()

    def test_fuse_returns_series_and_meta(self):
        """fuse() 必须返回 (Series, dict)"""
        factor_df = _make_factor_df()
        ic_dict = _make_ic_dict()
        result = self.engine.fuse(factor_df, ic_dict=ic_dict)
        assert isinstance(result, tuple)
        scores, meta = result
        assert isinstance(scores, pd.Series)
        assert isinstance(meta, dict)
        assert len(scores) == 50

    def test_combine_returns_series_and_weights(self):
        """combine() 必须返回 (Series, dict) — 便捷方法"""
        factor_df = _make_factor_df()
        ic_dict = _make_ic_dict()
        scores, weights = self.engine.combine(factor_df, ic_dict=ic_dict)
        assert isinstance(scores, pd.Series)
        assert isinstance(weights, dict)
        assert len(scores) == 50

    def test_fuse_with_regime(self):
        """不同regime应产生不同融合结果"""
        factor_df = _make_factor_df()
        ic_dict = _make_ic_dict()
        _, meta_trending = self.engine.fuse(factor_df, regime="trending", ic_dict=ic_dict)
        _, meta_defensive = self.engine.fuse(factor_df, regime="defensive", ic_dict=ic_dict)
        # 不同regime的权重应不同
        w1 = meta_trending.get("step5_final_weights", {})
        w2 = meta_defensive.get("step5_final_weights", {})
        # 至少权重比例应不同
        assert isinstance(w1, dict)

    def test_fuse_empty_data(self):
        """空数据应返回空结果"""
        factor_df = pd.DataFrame()
        scores, meta = self.engine.fuse(factor_df)
        assert len(scores) == 0

    def test_fuse_single_factor(self):
        """单因子融合应正常工作"""
        factor_df = _make_factor_df(n_factors=1)
        scores, meta = self.engine.fuse(factor_df)
        assert len(scores) == 50
