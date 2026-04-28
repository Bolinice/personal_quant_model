"""AlphaModules 单元测试 — 因子计算"""

import numpy as np
import pandas as pd
import pytest

from app.core.alpha_modules import AlphaModules


def _make_price_df(n_stocks: int = 30, n_days: int = 120) -> pd.DataFrame:
    """生成模拟行情数据"""
    np.random.seed(42)
    ts_codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]
    rows = []
    for code in ts_codes:
        base_price = np.random.uniform(10, 100)
        for d in range(n_days):
            ret = np.random.normal(0.0005, 0.02)
            base_price *= (1 + ret)
            rows.append({
                "ts_code": code,
                "trade_date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=d),
                "open": base_price * (1 + np.random.normal(0, 0.005)),
                "high": base_price * (1 + abs(np.random.normal(0, 0.01))),
                "low": base_price * (1 - abs(np.random.normal(0, 0.01))),
                "close": base_price,
                "vol": np.random.uniform(1e6, 1e8),
                "amount": np.random.uniform(5e7, 5e8),
                "pct_chg": ret * 100,
            })
    return pd.DataFrame(rows)


def _make_financial_df(n_stocks: int = 30) -> pd.DataFrame:
    """生成模拟财务数据"""
    np.random.seed(42)
    ts_codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]
    return pd.DataFrame({
        "ts_code": ts_codes,
        "ann_date": "20240331",
        "end_date": "20240331",
        "roe": np.random.uniform(0.05, 0.25, n_stocks),
        "netprofit_margin": np.random.uniform(0.05, 0.3, n_stocks),
        "rev_yoy": np.random.uniform(-0.2, 0.5, n_stocks),
        "profit_yoy": np.random.uniform(-0.3, 0.6, n_stocks),
        "turnover_rate": np.random.uniform(0.01, 0.1, n_stocks),
        "ep_cf": np.random.uniform(0.02, 0.15, n_stocks),
    })


class TestAlphaModules:
    def setup_method(self):
        self.alpha = AlphaModules()

    def test_price_factors_returns_dataframe(self):
        """价格因子计算应返回DataFrame"""
        price_df = _make_price_df()
        result = self.alpha.calc_price_factors(price_df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_fundamental_factors_returns_dataframe(self):
        """基本面因子计算应返回DataFrame"""
        price_df = _make_price_df()
        fin_df = _make_financial_df()
        result = self.alpha.calc_fundamental_factors(price_df, fin_df)
        assert isinstance(result, pd.DataFrame)

    def test_price_factors_no_nan_in_momentum(self):
        """动量因子在足够数据下不应有NaN"""
        price_df = _make_price_df(n_days=120)
        result = self.alpha.calc_price_factors(price_df)
        if "momentum_20d" in result.columns:
            # 至少最近的数据不应有NaN
            recent = result.groupby("ts_code").tail(1)
            assert recent["momentum_20d"].notna().all()

    def test_all_factors_combined(self):
        """全因子组合应正常工作"""
        price_df = _make_price_df()
        fin_df = _make_financial_df()
        result = self.alpha.calc_all_factors(price_df, fin_df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
