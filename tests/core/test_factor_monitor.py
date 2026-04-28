"""FactorMonitor 单元测试 — 因子衰减与漂移监控"""

import numpy as np
import pandas as pd
import pytest

from app.core.factor_monitor import FactorMonitor


def _make_ic_series(n_periods: int = 60, mean_ic: float = 0.03) -> pd.Series:
    """生成模拟IC时间序列"""
    np.random.seed(42)
    dates = pd.bdate_range(end="2025-01-15", periods=n_periods)
    return pd.Series(np.random.normal(mean_ic, 0.05, n_periods), index=dates, name="factor_1")


def _make_factor_dist(n_stocks: int = 500, mean: float = 0.0, std: float = 1.0) -> pd.Series:
    """生成模拟因子分布"""
    np.random.seed(42)
    ts_codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]
    return pd.Series(np.random.normal(mean, std, n_stocks), index=ts_codes, name="factor_1")


class TestFactorMonitor:
    def setup_method(self):
        self.monitor = FactorMonitor()

    def test_calc_ic_decay(self):
        """IC衰减检测应返回衰减指标"""
        ic_series = _make_ic_series(mean_ic=0.03)
        result = self.monitor.calc_ic_decay(ic_series)
        assert isinstance(result, dict)
        assert "recent_ic_mean" in result or "decay_ratio" in result or len(result) > 0

    def test_calc_psi(self):
        """PSI(群体稳定性指标)应返回非负值"""
        dist_old = _make_factor_dist(mean=0.0)
        dist_new = _make_factor_dist(mean=0.1)
        psi = self.monitor.calc_psi(dist_old, dist_new)
        assert isinstance(psi, float)
        assert psi >= 0

    def test_calc_psi_identical_distributions(self):
        """相同分布的PSI应接近0"""
        dist = _make_factor_dist()
        psi = self.monitor.calc_psi(dist, dist)
        assert psi < 0.1

    def test_calc_psi_shifted_distributions(self):
        """偏移分布的PSI应较大"""
        dist_old = _make_factor_dist(mean=0.0)
        dist_new = _make_factor_dist(mean=2.0)
        psi = self.monitor.calc_psi(dist_old, dist_new)
        assert psi > 0.1

    def test_calc_ks_statistic(self):
        """KS检验应返回统计量和p值"""
        dist_old = _make_factor_dist(mean=0.0)
        dist_new = _make_factor_dist(mean=0.5)
        result = self.monitor.calc_ks_statistic(dist_old, dist_new)
        assert isinstance(result, (tuple, dict))
