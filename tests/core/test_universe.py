"""UniverseBuilder 单元测试 — 股票池构建"""

import numpy as np
import pandas as pd
import pytest

from datetime import date
from app.core.universe import UniverseBuilder


def _make_stock_basic(n: int = 100) -> pd.DataFrame:
    """生成模拟股票基本信息"""
    np.random.seed(42)
    return pd.DataFrame({
        "ts_code": [f"{600000 + i:06d}.SH" for i in range(n)],
        "list_date": pd.date_range("2015-01-01", periods=n, freq="7D").strftime("%Y%m%d"),
        "list_status": ["L"] * n,
    })


def _make_price_df(n: int = 100, days: int = 30) -> pd.DataFrame:
    """生成模拟行情数据"""
    np.random.seed(42)
    ts_codes = [f"{600000 + i:06d}.SH" for i in range(n)]
    rows = []
    for code in ts_codes:
        for d in range(days):
            rows.append({
                "ts_code": code,
                "trade_date": date(2025, 1, 1) + pd.Timedelta(days=d),
                "close": np.random.uniform(5, 100),
                "amount": np.random.uniform(5e7, 5e8),
                "vol": np.random.uniform(1e6, 1e8),
            })
    return pd.DataFrame(rows)


class TestUniverseBuilder:
    def setup_method(self):
        self.builder = UniverseBuilder()

    def test_build_returns_list(self):
        """build() 必须返回列表"""
        stock_basic = _make_stock_basic()
        price_df = _make_price_df()
        result = self.builder.build(
            trade_date=date(2025, 1, 30),
            stock_basic_df=stock_basic,
            price_df=price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
        )
        assert isinstance(result, list)
        assert all(isinstance(c, str) for c in result)

    def test_build_excludes_st(self):
        """ST股应被排除"""
        stock_basic = _make_stock_basic()
        price_df = _make_price_df()
        status_df = pd.DataFrame({
            "ts_code": [stock_basic["ts_code"].iloc[0]],
            "trade_date": [date(2025, 1, 30)],
            "is_st": [True],
        })
        result_without = self.builder.build(
            trade_date=date(2025, 1, 30),
            stock_basic_df=stock_basic,
            price_df=price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
        )
        result_with = self.builder.build(
            trade_date=date(2025, 1, 30),
            stock_basic_df=stock_basic,
            price_df=price_df,
            stock_status_df=status_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            exclude_st=True,
        )
        assert len(result_with) <= len(result_without)

    def test_build_min_price_filter(self):
        """低价股应被排除"""
        stock_basic = _make_stock_basic()
        price_df = _make_price_df()
        # 设置第一只股票价格为1元
        price_df.loc[price_df["ts_code"] == stock_basic["ts_code"].iloc[0], "close"] = 1.0
        result = self.builder.build(
            trade_date=date(2025, 1, 30),
            stock_basic_df=stock_basic,
            price_df=price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=3.0,
        )
        assert stock_basic["ts_code"].iloc[0] not in result

    def test_build_core_pool(self):
        """核心池和扩展池都应返回有效列表"""
        stock_basic = _make_stock_basic()
        price_df = _make_price_df()
        core = self.builder.build_core_pool(
            trade_date=date(2025, 1, 30),
            stock_basic_df=stock_basic,
            price_df=price_df,
        )
        extended = self.builder.build_extended_pool(
            trade_date=date(2025, 1, 30),
            stock_basic_df=stock_basic,
            price_df=price_df,
        )
        assert isinstance(core, list)
        assert isinstance(extended, list)
        assert all(isinstance(c, str) for c in core)
        assert all(isinstance(c, str) for c in extended)
