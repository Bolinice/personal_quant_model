"""
股票池构建模块
实现GPT设计4.1节: 股票池是第一道风险控制
筛选条件: 上市天数/非ST/非停牌/流动性/价格阈值/成交额
支持核心池(中大市值+高流动性)和扩展池(覆盖更多)
"""
from typing import Dict, List, Optional, Set, Tuple
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.core.logging import logger


class UniverseBuilder:
    """股票池构建器 - GPT设计4.1节"""

    # 默认参数 (GPT设计建议值)
    DEFAULT_CORE_PARAMS = {
        'min_list_days': 250,        # 核心池: 上市满250个交易日(约1年)
        'min_daily_amount': 1e8,     # 日均成交额>1亿
        'min_price': 3.0,            # 价格>3元
        'liquidity_pct': 0.80,       # 流动性前80%
        'exclude_st': True,
        'exclude_suspended': True,
        'exclude_delist': True,
        'min_market_cap': 5e9,       # 最低市值50亿
    }

    DEFAULT_EXTENDED_PARAMS = {
        'min_list_days': 120,        # 扩展池: 上市满120个交易日
        'min_daily_amount': 5e7,     # 日均成交额>5000万
        'min_price': 2.0,            # 价格>2元
        'liquidity_pct': 0.70,       # 流动性前70%
        'exclude_st': True,
        'exclude_suspended': True,
        'exclude_delist': True,
        'min_market_cap': 0,         # 无市值下限
    }

    def __init__(self):
        pass

    def build(self, trade_date: date,
              stock_basic_df: pd.DataFrame,
              price_df: pd.DataFrame,
              stock_status_df: pd.DataFrame = None,
              daily_basic_df: pd.DataFrame = None,
              min_list_days: int = 120,
              min_daily_amount: float = 5e7,
              min_price: float = 2.0,
              liquidity_pct: float = 0.70,
              exclude_st: bool = True,
              exclude_suspended: bool = True,
              exclude_delist: bool = True,
              min_market_cap: float = 0) -> List[str]:
        """
        构建股票池

        Args:
            trade_date: 交易日期
            stock_basic_df: 股票基本信息, 需含 ts_code/list_date/list_status/delist_date
            price_df: 近期行情, 需含 ts_code/trade_date/close/amount/volume
            stock_status_df: 股票状态, 需含 ts_code/trade_date/is_st/is_suspended/is_delist
            daily_basic_df: 每日指标, 需含 ts_code/trade_date/total_mv (可选,用于市值过滤)
            min_list_days: 最小上市天数
            min_daily_amount: 最小日均成交额(元)
            min_price: 最低价格
            liquidity_pct: 流动性百分位阈值 (0-1, 保留前N%)
            exclude_st: 是否排除ST股
            exclude_suspended: 是否排除停牌股
            exclude_delist: 是否排除退市整理股
            min_market_cap: 最低总市值(元), 0=不限制

        Returns:
            符合条件的股票代码列表
        """
        candidates = set(stock_basic_df['ts_code'].dropna().unique())
        excluded_reasons: Dict[str, int] = {}

        # 1. 排除退市/非上市
        if exclude_delist and 'list_status' in stock_basic_df.columns:
            delisted = stock_basic_df[stock_basic_df['list_status'] == 'D']['ts_code']
            excluded_reasons['delisted'] = len(delisted)
            candidates -= set(delisted)

        if 'list_status' in stock_basic_df.columns:
            non_listed = stock_basic_df[~stock_basic_df['list_status'].isin(['L', 'P'])]['ts_code']
            excluded_reasons['non_listed'] = len(non_listed)
            candidates -= set(non_listed)

        # 2. 上市天数过滤
        if min_list_days > 0 and 'list_date' in stock_basic_df.columns:
            list_dates = pd.to_datetime(stock_basic_df.set_index('ts_code')['list_date'], errors='coerce')
            min_list_date = pd.Timestamp(trade_date) - pd.Timedelta(days=min_list_days)
            too_new = list_dates[list_dates > min_list_date].index
            excluded_reasons['too_new'] = len(too_new)
            candidates -= set(too_new)

        # 3. ST状态过滤
        if exclude_st and stock_status_df is not None and not stock_status_df.empty:
            status_on_date = self._filter_by_date(stock_status_df, trade_date)
            if 'is_st' in status_on_date.columns:
                st_stocks = status_on_date[status_on_date['is_st'] == True]['ts_code']  # noqa: E712
                excluded_reasons['st'] = len(st_stocks)
                candidates -= set(st_stocks)

        # 4. 停牌过滤
        if exclude_suspended and stock_status_df is not None and not stock_status_df.empty:
            status_on_date = self._filter_by_date(stock_status_df, trade_date)
            if 'is_suspended' in status_on_date.columns:
                suspended = status_on_date[status_on_date['is_suspended'] == True]['ts_code']  # noqa: E712
                excluded_reasons['suspended'] = len(suspended)
                candidates -= set(suspended)

        # 5. 退市整理过滤
        if exclude_delist and stock_status_df is not None and not stock_status_df.empty:
            status_on_date = self._filter_by_date(stock_status_df, trade_date)
            if 'is_delist' in status_on_date.columns:
                delist_stocks = status_on_date[status_on_date['is_delist'] == True]['ts_code']  # noqa: E712
                excluded_reasons['delist_organizing'] = len(delist_stocks)
                candidates -= set(delist_stocks)

        # 6. 流动性和价格过滤 (基于近期行情)
        if not price_df.empty:
            recent = self._get_recent_data(price_df, trade_date, window=20)
            if not recent.empty:
                # 日均成交额
                if 'amount' in recent.columns:
                    avg_amount = recent.groupby('ts_code')['amount'].mean()
                    low_liquidity = avg_amount[avg_amount < min_daily_amount].index
                    excluded_reasons['low_amount'] = len(low_liquidity)
                    candidates -= set(low_liquidity)

                    # 流动性百分位过滤
                    if liquidity_pct < 1.0 and len(avg_amount) > 0:
                        threshold = avg_amount.quantile(1 - liquidity_pct)
                        below_pct = avg_amount[avg_amount < threshold].index
                        excluded_reasons['below_liquidity_pct'] = len(below_pct)
                        candidates -= set(below_pct)

                # 最低价格
                if 'close' in recent.columns:
                    latest_prices = recent.groupby('ts_code')['close'].last()
                    low_price = latest_prices[latest_prices < min_price].index
                    excluded_reasons['low_price'] = len(low_price)
                    candidates -= set(low_price)

        # 7. 市值过滤
        if min_market_cap > 0 and daily_basic_df is not None and not daily_basic_df.empty:
            daily_on_date = self._filter_by_date(daily_basic_df, trade_date)
            if 'total_mv' in daily_on_date.columns:
                small_cap = daily_on_date[daily_on_date['total_mv'] < min_market_cap]['ts_code']
                excluded_reasons['small_cap'] = len(small_cap)
                candidates -= set(small_cap)

        # 只保留在candidates中的有效代码
        result = sorted([c for c in candidates if isinstance(c, str) and len(c) > 0])

        logger.info(
            "Universe built",
            extra={
                "trade_date": str(trade_date),
                "universe_size": len(result),
                "excluded": excluded_reasons,
            },
        )

        return result

    def build_core_pool(self, trade_date: date,
                        stock_basic_df: pd.DataFrame,
                        price_df: pd.DataFrame,
                        stock_status_df: pd.DataFrame = None,
                        daily_basic_df: pd.DataFrame = None) -> List[str]:
        """构建核心池: 中大市值+高流动性, 更稳定, 适合第一版"""
        return self.build(trade_date, stock_basic_df, price_df,
                          stock_status_df, daily_basic_df,
                          **self.DEFAULT_CORE_PARAMS)

    def build_extended_pool(self, trade_date: date,
                            stock_basic_df: pd.DataFrame,
                            price_df: pd.DataFrame,
                            stock_status_df: pd.DataFrame = None,
                            daily_basic_df: pd.DataFrame = None) -> List[str]:
        """构建扩展池: 覆盖更多股票, alpha更多但噪音更大"""
        return self.build(trade_date, stock_basic_df, price_df,
                          stock_status_df, daily_basic_df,
                          **self.DEFAULT_EXTENDED_PARAMS)

    # ==================== 辅助方法 ====================

    @staticmethod
    def _filter_by_date(df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
        """按交易日期过滤DataFrame"""
        if 'trade_date' not in df.columns:
            return df
        df_dates = pd.to_datetime(df['trade_date'], errors='coerce')
        mask = df_dates == pd.Timestamp(trade_date)
        if mask.any():
            return df[mask]
        # 没有精确匹配, 取最近的
        mask = df_dates <= pd.Timestamp(trade_date)
        if mask.any():
            latest = df_dates[mask].max()
            return df[df_dates == latest]
        return pd.DataFrame()

    @staticmethod
    def _get_recent_data(df: pd.DataFrame, trade_date: date,
                         window: int = 20) -> pd.DataFrame:
        """获取最近N个交易日的数据"""
        if 'trade_date' not in df.columns:
            return df

        df_dates = pd.to_datetime(df['trade_date'], errors='coerce')
        cutoff = pd.Timestamp(trade_date) - pd.Timedelta(days=window * 2)  # 多取一些确保有足够交易日
        mask = (df_dates >= cutoff) & (df_dates <= pd.Timestamp(trade_date))
        recent = df[mask].copy()

        if recent.empty:
            return recent

        # 每只股票只保留最近window条
        if 'ts_code' in recent.columns:
            recent = recent.sort_values(['ts_code', 'trade_date'])
            recent = recent.groupby('ts_code').tail(window)

        return recent