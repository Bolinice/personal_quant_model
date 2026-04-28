"""市场状态检测 单元测试"""

import numpy as np
import pandas as pd
import pytest

from app.core.regime import REGIME_TRENDING, REGIME_MEAN_REVERTING, REGIME_DEFENSIVE, RegimeDetector


def _make_market_data(n: int = 120, trend: float = 0.5, vol: float = 0.01) -> pd.DataFrame:
    """生成模拟市场数据"""
    np.random.seed(42)
    dates = pd.bdate_range("2024-01-01", periods=n)
    returns = np.random.normal(trend / 252, vol, n)
    close = 3000 * (1 + returns).cumprod()
    return pd.DataFrame(
        {
            "trade_date": dates,
            "close": close,
            "open": close * (1 + np.random.normal(0, 0.005, n)),
            "high": close * (1 + abs(np.random.normal(0, 0.01, n))),
            "low": close * (1 - abs(np.random.normal(0, 0.01, n))),
            "vol": np.random.uniform(1e8, 5e8, n),
            "pct_chg": returns * 100,
        }
    )


class TestRegimeDetector:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_detect_returns_tuple(self):
        """detect() 应返回 (regime, confidence) 元组"""
        df = _make_market_data()
        result = self.detector.detect(df)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_detect_regime_is_valid(self):
        """检测到的状态应是有效值"""
        df = _make_market_data()
        regime, confidence = self.detector.detect(df)
        assert regime in {REGIME_TRENDING, REGIME_MEAN_REVERTING, REGIME_DEFENSIVE}

    def test_detect_trending_market(self):
        """强趋势市场应检测为 trending"""
        market_data = _make_market_data(n=120, trend=2.0, vol=0.005)
        regime, confidence = self.detector.detect(market_data)
        assert regime == REGIME_TRENDING
        assert confidence >= 0.3

    def test_detect_volatile_market(self):
        """高波动市场应检测为 mean_reverting 或 defensive"""
        market_data = _make_market_data(n=120, trend=0.0, vol=0.06)
        regime, confidence = self.detector.detect(market_data)
        assert regime in {REGIME_MEAN_REVERTING, REGIME_DEFENSIVE}
        assert confidence >= 0.3

    def test_confidence_bounded(self):
        """置信度应在 [0, 1] 范围内"""
        df = _make_market_data()
        _, confidence = self.detector.detect(df)
        assert 0 <= confidence <= 1.0
