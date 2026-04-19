"""
A股交易工具 (机构级: 交易日历表查询)
"""
import logging
from datetime import date, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TradingCalendar:
    """
    A股交易日历 (机构级: 基于交易日历表查询)
    替代简单跳周末，正确处理节假日、调休等
    """

    def __init__(self, db_session=None):
        """
        Args:
            db_session: SQLAlchemy session, 用于查询TradingCalendar表
                       如果为None, 回退到简单工作日计算
        """
        self.db = db_session
        self._calendar_cache = None

    def _load_calendar(self) -> List[date]:
        """加载交易日历(带缓存)"""
        if self._calendar_cache is not None:
            return self._calendar_cache

        if self.db is None:
            return None

        try:
            from app.models.market import TradingCalendar as TradingCalendarModel
            records = self.db.query(TradingCalendarModel).filter(
                TradingCalendarModel.is_open == True  # noqa: E712
            ).order_by(TradingCalendarModel.cal_date).all()
            self._calendar_cache = sorted([r.cal_date for r in records])
            return self._calendar_cache
        except Exception as e:
            logger.warning(f"Failed to load trading calendar from DB: {e}")
            return None

    def is_trading_day(self, dt: date) -> bool:
        """判断是否为交易日"""
        calendar = self._load_calendar()
        if calendar is not None:
            return dt in calendar
        # 回退: 工作日
        return dt.weekday() < 5

    def get_next_trading_date(self, dt: date, n: int = 1) -> date:
        """
        获取第n个后续交易日

        Args:
            dt: 基准日期
            n: 第n个交易日 (1=下一个)

        Returns:
            第n个后续交易日
        """
        calendar = self._load_calendar()
        if calendar is not None:
            future_dates = [d for d in calendar if d > dt]
            if len(future_dates) >= n:
                return future_dates[n - 1]
            # 超出日历范围, 回退到工作日
            logger.warning(f"Trading calendar insufficient for {dt}+{n}, falling back to business days")

        # 回退: 跳过周末
        result = dt
        for _ in range(n):
            result += timedelta(days=1)
            while result.weekday() >= 5:
                result += timedelta(days=1)
        return result

    def get_prev_trading_date(self, dt: date, n: int = 1) -> date:
        """
        获取第n个前序交易日

        Args:
            dt: 基准日期
            n: 第n个交易日 (1=上一个)

        Returns:
            第n个前序交易日
        """
        calendar = self._load_calendar()
        if calendar is not None:
            past_dates = [d for d in calendar if d < dt]
            if len(past_dates) >= n:
                return past_dates[-n]
            logger.warning(f"Trading calendar insufficient for {dt}-{n}, falling back to business days")

        result = dt
        for _ in range(n):
            result -= timedelta(days=1)
            while result.weekday() >= 5:
                result -= timedelta(days=1)
        return result

    def get_trading_dates_between(self, start_date: date, end_date: date) -> List[date]:
        """
        获取两个日期之间的所有交易日

        Args:
            start_date: 开始日期 (含)
            end_date: 结束日期 (含)

        Returns:
            交易日列表
        """
        calendar = self._load_calendar()
        if calendar is not None:
            return [d for d in calendar if start_date <= d <= end_date]

        # 回退: 工作日
        result = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                result.append(current)
            current += timedelta(days=1)
        return result

    def get_n_trading_days_before(self, dt: date, n: int) -> date:
        """
        获取dt之前第n个交易日

        Args:
            dt: 基准日期
            n: 交易日数

        Returns:
            对应日期
        """
        return self.get_prev_trading_date(dt, n)

    def count_trading_days(self, start_date: date, end_date: date) -> int:
        """
        计算两个日期之间的交易日数

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            交易日数
        """
        return len(self.get_trading_dates_between(start_date, end_date))


# ==================== 交易辅助函数 ====================

def get_next_trading_date(dt: date, n: int = 1, db_session=None) -> date:
    """
    获取第n个后续交易日 (便捷函数)
    优先查询TradingCalendar表, 回退到工作日计算
    """
    cal = TradingCalendar(db_session)
    return cal.get_next_trading_date(dt, n)


def get_prev_trading_date(dt: date, n: int = 1, db_session=None) -> date:
    """获取第n个前序交易日"""
    cal = TradingCalendar(db_session)
    return cal.get_prev_trading_date(dt, n)


def get_trading_dates_between(start_date: date, end_date: date, db_session=None) -> List[date]:
    """获取两个日期之间的所有交易日"""
    cal = TradingCalendar(db_session)
    return cal.get_trading_dates_between(start_date, end_date)


def get_n_trading_days_before(dt: date, n: int, db_session=None) -> date:
    """获取dt之前第n个交易日"""
    cal = TradingCalendar(db_session)
    return cal.get_n_trading_days_before(dt, n)


def count_trading_days(start_date: date, end_date: date, db_session=None) -> int:
    """计算两个日期之间的交易日数"""
    cal = TradingCalendar(db_session)
    return cal.count_trading_days(start_date, end_date)


def get_trading_calendar(exchange: str = 'SSE',
                          start_date: str = None,
                          end_date: str = None,
                          is_open: bool = None,
                          db_session=None):
    """
    查询交易日历记录 (兼容backtests_service接口)
    返回TradingCalendar模型对象列表

    Args:
        exchange: 交易所代码
        start_date: 开始日期 (str或date)
        end_date: 结束日期 (str或date)
        is_open: 是否交易日
        db_session: 数据库会话
    """
    if db_session is None:
        return []

    try:
        from app.models.market import TradingCalendar as TradingCalendarModel

        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)

        query = db_session.query(TradingCalendarModel).filter(
            TradingCalendarModel.exchange == exchange,
            TradingCalendarModel.cal_date >= start_date,
            TradingCalendarModel.cal_date <= end_date,
        )
        if is_open is not None:
            query = query.filter(TradingCalendarModel.is_open == is_open)
        return query.order_by(TradingCalendarModel.cal_date).all()
    except Exception as e:
        logger.warning(f"Failed to query trading calendar: {e}")
        return []