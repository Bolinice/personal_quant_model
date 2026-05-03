"""
测试PIT Guard多版本去重逻辑
验证：业绩预告 → 业绩快报 → 正式报告的优先级处理
"""

from datetime import date

import pandas as pd
import pytest

from app.core.pit_guard import pit_filter_df


class TestPITMultiVersion:
    """测试PIT多版本去重"""

    def test_source_priority_dedup(self):
        """测试按source_priority去重：正式报告 > 快报 > 预告"""
        df = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 3,
            'report_period': [date(2023, 3, 31)] * 3,
            'ann_date': [date(2023, 4, 15), date(2023, 4, 28), date(2023, 4, 30)],
            'source_priority': [1, 2, 3],  # 1=预告, 2=快报, 3=正式
            'net_profit': [100, 105, 110]
        })

        # 场景1: 2023-04-29查询，应该选快报（优先级2）
        result = pit_filter_df(df, date(2023, 4, 29))
        assert len(result) == 1, "应该只保留一条记录"
        assert result.iloc[0]['source_priority'] == 2, "应该选择快报"
        assert result.iloc[0]['net_profit'] == 105, "净利润应该是快报的105"

        # 场景2: 2023-05-01查询，应该选正式报告（优先级3）
        result = pit_filter_df(df, date(2023, 5, 1))
        assert len(result) == 1
        assert result.iloc[0]['source_priority'] == 3, "应该选择正式报告"
        assert result.iloc[0]['net_profit'] == 110, "净利润应该是正式报告的110"

        # 场景3: 2023-04-20查询，应该选预告（优先级1）
        result = pit_filter_df(df, date(2023, 4, 20))
        assert len(result) == 1
        assert result.iloc[0]['source_priority'] == 1, "应该选择预告"
        assert result.iloc[0]['net_profit'] == 100, "净利润应该是预告的100"

    def test_revision_no_dedup(self):
        """测试按revision_no去重：版本号越大越新"""
        df = pd.DataFrame({
            'ts_code': ['000002.SZ'] * 3,
            'report_period': [date(2023, 6, 30)] * 3,
            'ann_date': [date(2023, 8, 30), date(2023, 9, 5), date(2023, 9, 10)],
            'source_priority': [3, 3, 3],  # 都是正式报告
            'revision_no': [0, 1, 2],  # 0=初版, 1=修订1, 2=修订2
            'revenue': [1000, 1050, 1100]
        })

        # 应该选择最新修订版本（revision_no=2）
        result = pit_filter_df(df, date(2023, 9, 15))
        assert len(result) == 1
        assert result.iloc[0]['revision_no'] == 2, "应该选择最新修订版"
        assert result.iloc[0]['revenue'] == 1100, "营收应该是修订2的1100"

    def test_combined_priority_and_revision(self):
        """测试优先级+版本号组合去重"""
        df = pd.DataFrame({
            'ts_code': ['000003.SZ'] * 5,
            'report_period': [date(2023, 9, 30)] * 5,
            'ann_date': [
                date(2023, 10, 15),  # 预告
                date(2023, 10, 28),  # 快报
                date(2023, 10, 30),  # 正式报告初版
                date(2023, 11, 5),   # 正式报告修订1
                date(2023, 11, 10),  # 正式报告修订2
            ],
            'source_priority': [1, 2, 3, 3, 3],
            'revision_no': [0, 0, 0, 1, 2],
            'net_profit': [200, 210, 220, 225, 230]
        })

        # 场景1: 2023-10-20查询，应该选预告
        result = pit_filter_df(df, date(2023, 10, 20))
        assert len(result) == 1
        assert result.iloc[0]['source_priority'] == 1
        assert result.iloc[0]['net_profit'] == 200

        # 场景2: 2023-10-29查询，应该选快报
        result = pit_filter_df(df, date(2023, 10, 29))
        assert len(result) == 1
        assert result.iloc[0]['source_priority'] == 2
        assert result.iloc[0]['net_profit'] == 210

        # 场景3: 2023-11-01查询，应该选正式报告初版
        result = pit_filter_df(df, date(2023, 11, 1))
        assert len(result) == 1
        assert result.iloc[0]['source_priority'] == 3
        assert result.iloc[0]['revision_no'] == 0
        assert result.iloc[0]['net_profit'] == 220

        # 场景4: 2023-11-15查询，应该选正式报告修订2
        result = pit_filter_df(df, date(2023, 11, 15))
        assert len(result) == 1
        assert result.iloc[0]['source_priority'] == 3
        assert result.iloc[0]['revision_no'] == 2
        assert result.iloc[0]['net_profit'] == 230

    def test_multiple_stocks_dedup(self):
        """测试多只股票同时去重"""
        df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000002.SZ', '000002.SZ'],
            'report_period': [date(2023, 3, 31), date(2023, 3, 31),
                              date(2023, 3, 31), date(2023, 3, 31)],
            'ann_date': [date(2023, 4, 15), date(2023, 4, 30),
                         date(2023, 4, 20), date(2023, 4, 28)],
            'source_priority': [1, 3, 1, 2],
            'net_profit': [100, 110, 200, 205]
        })

        result = pit_filter_df(df, date(2023, 5, 1))
        assert len(result) == 2, "应该保留2只股票各1条记录"

        # 000001.SZ应该选正式报告
        stock1 = result[result['ts_code'] == '000001.SZ'].iloc[0]
        assert stock1['source_priority'] == 3
        assert stock1['net_profit'] == 110

        # 000002.SZ应该选快报
        stock2 = result[result['ts_code'] == '000002.SZ'].iloc[0]
        assert stock2['source_priority'] == 2
        assert stock2['net_profit'] == 205

    def test_no_priority_fields_fallback(self):
        """测试无优先级字段时的降级处理：按公告日期去重"""
        df = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 3,
            'report_period': [date(2023, 3, 31)] * 3,
            'ann_date': [date(2023, 4, 15), date(2023, 4, 20), date(2023, 4, 30)],
            'net_profit': [100, 105, 110]
        })

        result = pit_filter_df(df, date(2023, 5, 1))
        assert len(result) == 1
        # 无优先级字段时，应该选最新公告日期
        assert pd.Timestamp(result.iloc[0]['ann_date']) == pd.Timestamp(date(2023, 4, 30))
        assert result.iloc[0]['net_profit'] == 110

    def test_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame()
        result = pit_filter_df(df, date(2023, 5, 1))
        assert result.empty

    def test_future_data_filtered(self):
        """测试未来数据被过滤"""
        df = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 2,
            'report_period': [date(2023, 3, 31)] * 2,
            'ann_date': [date(2023, 4, 15), date(2023, 5, 15)],  # 第二条是未来数据
            'source_priority': [1, 3],
            'net_profit': [100, 110]
        })

        # 2023-05-01查询，第二条未来数据应该被过滤
        result = pit_filter_df(df, date(2023, 5, 1))
        assert len(result) == 1
        assert pd.Timestamp(result.iloc[0]['ann_date']) == pd.Timestamp(date(2023, 4, 15))
        assert result.iloc[0]['net_profit'] == 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
