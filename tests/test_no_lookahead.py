"""
Look-ahead Bias 黄金测试套件
============================
验证系统不会使用未来数据（前瞻偏差），这是量化系统最致命的 bug。

测试策略：
1. 基线测试：运行流水线得到输出
2. 注入未来数据：篡改 T+1/T+2 的数据
3. 重新运行流水线
4. 断言输出不变 — 如果变了，说明存在未来数据泄漏
"""

import warnings
from datetime import date

import pandas as pd
import pytest

from app.core.factor_calculator import pit_filter
from app.core.pit_guard import pit_filter_df, pit_filter_query


class TestPITGuardDataFrame:
    """PIT Guard DataFrame 过滤测试"""

    @pytest.fixture
    def financial_df(self):
        """模拟财务数据，包含未来公告"""
        return pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000001.SZ", "000002.SZ", "000002.SZ"],
                "ann_date": ["20250110", "20250120", "20250110", "20250125"],
                "end_date": ["20240930", "20241231", "20240930", "20241231"],
                "net_profit": [100.0, 120.0, 200.0, 250.0],
                "total_equity": [1000.0, 1050.0, 2000.0, 2100.0],
            }
        )

    def test_filters_future_announcements(self, financial_df):
        """PIT Guard 必须过滤掉 ann_date > trade_date 的记录"""
        trade_date = date(2025, 1, 15)
        result = pit_filter_df(financial_df, trade_date)

        # 20250120 和 20250125 的记录应被过滤
        assert len(result) == 2
        assert all(pd.to_datetime(result["ann_date"]) <= pd.to_datetime(trade_date))

    def test_no_filter_when_all_past(self, financial_df):
        """所有公告都在交易日前时，不应过滤任何记录"""
        trade_date = date(2025, 1, 31)
        result = pit_filter_df(financial_df, trade_date)
        assert len(result) == 4

    def test_empty_dataframe(self):
        """空 DataFrame 应安全返回空"""
        result = pit_filter_df(pd.DataFrame(), date(2025, 1, 15))
        assert result.empty

    def test_missing_ann_date_warns(self):
        """缺少 ann_date 列应发出警告"""
        df = pd.DataFrame({"ts_code": ["000001.SZ"], "net_profit": [100.0]})
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            pit_filter_df(df, date(2025, 1, 15))
            assert len(w) == 1
            assert "look-ahead bias" in str(w[0].message).lower()

    def test_dedup_by_report_period(self):
        """同一股票同一报告期，取最新公告记录"""
        df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000001.SZ", "000001.SZ"],
                "ann_date": ["20250105", "20250110", "20250115"],
                "end_date": ["20241231", "20241231", "20241231"],
                "net_profit": [90.0, 100.0, 110.0],  # 更正公告
            }
        )
        trade_date = date(2025, 1, 12)
        result = pit_filter_df(df, trade_date)

        # 应取 ann_date=20250110 的记录（<= trade_date 中最新的）
        assert len(result) == 1
        assert result.iloc[0]["net_profit"] == 100.0

    def test_preserves_all_columns(self, financial_df):
        """过滤后应保留所有原始列"""
        result = pit_filter_df(financial_df, date(2025, 1, 15))
        assert set(result.columns) == set(financial_df.columns)


class TestPITGuardFactorCalculator:
    """验证 factor_calculator.pit_filter 与 pit_guard.pit_filter_df 行为一致"""

    def test_consistent_with_pit_guard(self):
        """factor_calculator 的 pit_filter 应与 pit_guard 行为一致"""
        df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000001.SZ", "000002.SZ"],
                "ann_date": ["20250110", "20250120", "20250110"],
                "end_date": ["20240930", "20241231", "20240930"],
                "net_profit": [100.0, 120.0, 200.0],
            }
        )
        trade_date = date(2025, 1, 15)

        result_old = pit_filter(df, trade_date)
        result_new = pit_filter_df(df, trade_date)

        assert len(result_old) == len(result_new)
        pd.testing.assert_frame_equal(
            result_old.reset_index(drop=True),
            result_new.reset_index(drop=True),
        )


class TestNoLookaheadBias:
    """
    核心前瞻偏差检测测试
    ====================
    原理：注入未来数据后，流水线输出必须不变
    """

    def test_financial_data_no_future_leakage(self):
        """
        财务数据前瞻偏差检测：
        修改 T+1 的财务数据，T 日的因子计算结果不应改变
        """
        trade_date = date(2025, 1, 15)

        # 基线数据
        baseline_financial = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
                "ann_date": ["20250110", "20250110", "20250110"],
                "end_date": ["20240930", "20240930", "20240930"],
                "net_profit": [100.0, 200.0, 300.0],
                "total_equity": [1000.0, 2000.0, 3000.0],
                "total_assets": [5000.0, 10000.0, 15000.0],
            }
        )

        # 注入未来数据（ann_date 在 trade_date 之后）
        future_injected = pd.concat(
            [
                baseline_financial,
                pd.DataFrame(
                    {
                        "ts_code": ["000001.SZ", "000002.SZ"],
                        "ann_date": ["20250116", "20250120"],  # 未来公告
                        "end_date": ["20241231", "20241231"],
                        "net_profit": [999.0, 888.0],  # 篡改数据
                        "total_equity": [9999.0, 8888.0],
                        "total_assets": [99999.0, 88888.0],
                    }
                ),
            ],
            ignore_index=True,
        )

        # PIT 过滤后，两组数据应产生相同结果
        result_baseline = pit_filter_df(baseline_financial, trade_date)
        result_injected = pit_filter_df(future_injected, trade_date)

        pd.testing.assert_frame_equal(
            result_baseline.sort_values("ts_code").reset_index(drop=True),
            result_injected.sort_values("ts_code").reset_index(drop=True),
        )

    def test_pit_filter_idempotent(self):
        """PIT 过滤是幂等的：多次过滤结果不变"""
        df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000001.SZ"],
                "ann_date": ["20250110", "20250120"],
                "end_date": ["20240930", "20241231"],
                "net_profit": [100.0, 120.0],
            }
        )
        trade_date = date(2025, 1, 15)

        result1 = pit_filter_df(df, trade_date)
        result2 = pit_filter_df(result1, trade_date)

        pd.testing.assert_frame_equal(
            result1.reset_index(drop=True),
            result2.reset_index(drop=True),
        )

    def test_earlier_trade_date_subset(self):
        """更早的 trade_date 应产生更少或相等的记录数"""
        df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ"] * 5,
                "ann_date": [f"2025010{i}" for i in range(1, 6)],
                "end_date": ["20240930"] * 5,
                "net_profit": [100.0, 110.0, 120.0, 130.0, 140.0],
            }
        )

        result_early = pit_filter_df(df, date(2025, 1, 3))
        result_late = pit_filter_df(df, date(2025, 1, 5))

        assert len(result_early) <= len(result_late)


class TestPITGuardSQLAlchemy:
    """PIT Guard SQLAlchemy Query 过滤测试"""

    def test_pit_filter_query_string_column(self):
        """ann_date 为 String 类型时，应使用字符串比较"""
        from unittest.mock import MagicMock

        from app.models.market.stock_financial import StockFinancial

        query = MagicMock()
        session = MagicMock()
        result = pit_filter_query(query, StockFinancial, "20250115", session)

        # 验证 query.filter 被调用（添加了 ann_date <= "20250115" 条件）
        query.filter.assert_called_once()
        assert result is not None

    def test_pit_filter_query_missing_ann_date(self):
        """模型缺少 ann_date 列时应跳过 PIT 过滤并发出警告"""
        from unittest.mock import MagicMock

        model_class = MagicMock(spec=[])
        model_class.__name__ = "SomeModel"

        query = MagicMock()
        session = MagicMock()
        result = pit_filter_query(query, model_class, "20250115", session)

        # 缺少 ann_date 时应返回原始 query
        assert result is query
