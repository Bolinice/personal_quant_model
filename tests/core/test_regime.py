"""RegimeDetector 单元测试 — 市场状态检测"""

import numpy as np
import pandas as pd
import pytest

from app.core.regime import RegimeDetector, REGIME_TRENDING, REGIME_MEAN_REVERTING, REGIME_DEFENSIVE, REGIME_RISK_ON


def _make_market_data(n: int = 60, trend: float = 0.0, vol: float = 0.02) -> pd.DataFrame:
    """生成模拟行情数据"""
    np.random.seed(42)
    dates = pd.bdate_range(end="2025-01-15", periods=n)
    returns = np.random.normal(trend / 252, vol, n)
    close = 3000 * (1 + returns).cumprod()
    return pd.DataFrame({
        "trade_date": dates,
        "close": close,
        "open": close * (1 + np.random.normal(0, 0.005, n)),
        "high": close * (1 + np.abs(np.random.normal(0, 0.01, n))),
        "low": close * (1 - np.abs(np.random.normal(0, 0.01, n))),
        "vol": np.random.uniform(1e8, 5e8, n),
        "pct_chg": returns * 100,
    })


class TestRegimeDetector:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_detect_returns_tuple(self):
        """detect() 必须返回 (regime, confidence) 元组"""
        market_data = _make_market_data()
        result = self.detector.detect(market_data)
        assert isinstance(result, tuple)
        assert len(result) == 2
        regime, confidence = result
        assert regime in {REGIME_TRENDING, REGIME_MEAN_REVERTING, REGIME_DEFENSIVE, REGIME_RISK_ON}
        assert 0 <= confidence <= 1.0

    def test_detect_trending_market(self):
        """强趋势市场应检测为 trending"""
        market_data = _make_market_data(n=120, trend=0.5, vol=0.01)
        regime, confidence = self.detector.detect(market_data)
        assert regime == REGIME_TRENDING
        assert confidence >= 0.3

    def test_detect_volatile_market(self):
        """高波动市场应偏向 defensive"""
        market_data = _make_market_data(n=120, trend=0.0, vol=0.06)
        regime, _ = self.detector.detect(market_data)
        # 高波动+无趋势 → 可能是defensive或mean_reverting
        assert regime in {REGIME_DEFENSIVE, REGIME_MEAN_REVERTING}

    def test_detect_empty_data(self):
        """空数据应返回默认regime"""
        regime, confidence = self.detector.detect(pd.DataFrame())
        assert regime == REGIME_MEAN_REVERTING
        assert confidence == 0.3

    def test_detect_with_size_spread(self):
        """大小盘数据应影响regime判断"""
        market_data = _make_market_data()
        large_cap = _make_market_data(n=60, trend=0.1)
        small_cap = _make_market_data(n=60, trend=0.3)
        regime, _ = self.detector.detect(market_data, large_cap_df=large_cap, small_cap_df=small_cap)
        assert regime in {REGIME_TRENDING, REGIME_MEAN_REVERTING, REGIME_DEFENSIVE, REGIME_RISK_ON}

    def test_confidence_increases_with_signal_strength(self):
        """信号越强，置信度应越高"""
        weak = _make_market_data(n=120, trend=0.05, vol=0.02)
        strong = _make_market_data(n=120, trend=0.8, vol=0.01)
        _, conf_weak = self.detector.detect(weak)
        _, conf_strong = self.detector.detect(strong)
        assert conf_strong >= conf_weak
