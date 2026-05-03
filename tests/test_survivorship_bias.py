"""
测试幸存者偏差修复
验证：回测时应该包含"当时尚未退市"的股票
"""

from datetime import date

import pandas as pd
import pytest

from app.core.universe import UniverseBuilder


class TestSurvivorshipBias:
    """测试幸存者偏差修复"""

    def test_delist_date_filtering(self):
        """测试按退市日期过滤：回测时应包含当时尚未退市的股票"""
        builder = UniverseBuilder()

        # 构造测试数据：某股票在2020-06-01退市
        stock_basic = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ'],
            'list_status': ['D', 'L', 'L'],  # 000001已退市
            'delist_date': [date(2020, 6, 1), None, None],
            'list_date': [date(2010, 1, 1), date(2010, 1, 1), date(2010, 1, 1)]
        })

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ'] * 20,
            'trade_date': [date(2019, 12, i) for i in range(1, 21)] * 3,
            'close': [10.0] * 60,
            'amount': [1e8] * 60
        })

        # 场景1: 回测2019年，000001.SZ当时尚未退市，应该包含
        universe_2019 = builder.build(
            trade_date=date(2019, 12, 31),
            stock_basic_df=stock_basic,
            price_df=price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            exclude_delist=True
        )
        assert '000001.SZ' in universe_2019, "2019年回测应该包含000001.SZ（当时尚未退市）"
        assert '000002.SZ' in universe_2019
        assert '000003.SZ' in universe_2019

        # 场景2: 回测2020-07-01，000001.SZ已退市，应该排除
        universe_2020 = builder.build(
            trade_date=date(2020, 7, 1),
            stock_basic_df=stock_basic,
            price_df=price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            exclude_delist=True
        )
        assert '000001.SZ' not in universe_2020, "2020年7月回测应该排除000001.SZ（已退市）"
        assert '000002.SZ' in universe_2020
        assert '000003.SZ' in universe_2020

        # 场景3: 回测2020-05-31（退市前一天），应该包含
        universe_before_delist = builder.build(
            trade_date=date(2020, 5, 31),
            stock_basic_df=stock_basic,
            price_df=price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            exclude_delist=True
        )
        assert '000001.SZ' in universe_before_delist, "退市前一天应该包含"

    def test_multiple_delisted_stocks(self):
        """测试多只退市股票的时点过滤"""
        builder = UniverseBuilder()

        stock_basic = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ', '000004.SZ'],
            'list_status': ['D', 'D', 'L', 'L'],
            'delist_date': [
                date(2018, 6, 1),   # 2018年退市
                date(2020, 6, 1),   # 2020年退市
                None,
                None
            ],
            'list_date': [date(2010, 1, 1)] * 4
        })

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ', '000004.SZ'] * 20,
            'trade_date': [date(2019, 12, i) for i in range(1, 21)] * 4,
            'close': [10.0] * 80,
            'amount': [1e8] * 80
        })

        # 回测2019年
        universe_2019 = builder.build(
            trade_date=date(2019, 12, 31),
            stock_basic_df=stock_basic,
            price_df=price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            exclude_delist=True
        )

        # 000001.SZ在2018年已退市，应该排除
        assert '000001.SZ' not in universe_2019, "2018年退市的股票应该排除"
        # 000002.SZ在2020年才退市，2019年应该包含
        assert '000002.SZ' in universe_2019, "2020年退市的股票在2019年应该包含"
        assert '000003.SZ' in universe_2019
        assert '000004.SZ' in universe_2019

    def test_no_delist_date_fallback(self):
        """测试无delist_date字段时的降级处理"""
        builder = UniverseBuilder()

        # 无delist_date字段
        stock_basic = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'list_status': ['D', 'L'],  # 只有状态，无日期
            'list_date': [date(2010, 1, 1), date(2010, 1, 1)]
        })

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'] * 20,
            'trade_date': [date(2019, 12, i) for i in range(1, 21)] * 2,
            'close': [10.0] * 40,
            'amount': [1e8] * 40
        })

        # 无delist_date时，会排除所有list_status='D'的股票
        universe = builder.build(
            trade_date=date(2019, 12, 31),
            stock_basic_df=stock_basic,
            price_df=price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            exclude_delist=True
        )

        # 000001.SZ会被排除（次优方案，但至少不会引入更严重的偏差）
        assert '000001.SZ' not in universe
        assert '000002.SZ' in universe

    def test_exclude_delist_false(self):
        """测试exclude_delist=False时不过滤退市股票"""
        builder = UniverseBuilder()

        stock_basic = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'list_status': ['D', 'L'],
            'delist_date': [date(2020, 6, 1), None],
            'list_date': [date(2010, 1, 1), date(2010, 1, 1)]
        })

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'] * 20,
            'trade_date': [date(2021, 1, i) for i in range(1, 21)] * 2,
            'close': [10.0] * 40,
            'amount': [1e8] * 40
        })

        # exclude_delist=False，不过滤退市股票
        universe = builder.build(
            trade_date=date(2021, 1, 31),
            stock_basic_df=stock_basic,
            price_df=price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            exclude_delist=False  # 不过滤
        )

        # 两只股票都应该在
        assert '000001.SZ' in universe
        assert '000002.SZ' in universe

    def test_delist_date_parsing(self):
        """测试退市日期解析的鲁棒性"""
        builder = UniverseBuilder()

        # 测试各种日期格式
        stock_basic = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ', '000004.SZ'],
            'list_status': ['D', 'D', 'D', 'L'],
            'delist_date': [
                date(2020, 6, 1),      # date对象
                '2020-06-01',          # 字符串
                pd.NaT,                # NaT
                None                   # None
            ],
            'list_date': [date(2010, 1, 1)] * 4
        })

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ', '000004.SZ'] * 20,
            'trade_date': [date(2021, 1, i) for i in range(1, 21)] * 4,
            'close': [10.0] * 80,
            'amount': [1e8] * 80
        })

        universe = builder.build(
            trade_date=date(2021, 1, 31),
            stock_basic_df=stock_basic,
            price_df=price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            exclude_delist=True
        )

        # 000001和000002在2020年退市，应该排除
        assert '000001.SZ' not in universe
        assert '000002.SZ' not in universe
        # 000003退市日期为NaT，视为无退市日期，但list_status='D'会被降级处理排除
        # 000004未退市
        assert '000004.SZ' in universe
        # 000003的处理取决于是否有有效的delist_date，NaT会被视为无效日期
        # 由于list_status='D'，会被降级逻辑排除


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
