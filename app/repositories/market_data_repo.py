"""
市场数据Repository
==================
负责所有市场数据的查询：日线、财务、资金流、北向资金等

设计原则:
- 所有方法返回DataFrame
- 支持批量查询
- 自动处理PIT约束
- 统一异常处理
"""

from datetime import date
from typing import List, Optional

import pandas as pd
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from app.models.market.stock_daily import StockDaily
from app.models.market.stock_financial import StockFinancial
from app.models.market.stock_money_flow import StockMoneyFlow
from app.models.market.stock_northbound import StockNorthbound
from app.models.market.stock_basic import StockBasic
from app.models.market.index_daily import IndexDaily
from app.core.exceptions import DatabaseException, DataNotAvailableException
from app.core.retry import retry_on_db_connection_error


class MarketDataRepository:
    """市场数据Repository"""

    def __init__(self, session: Session):
        self.session = session

    # ==================== 股票基础信息 ====================

    @retry_on_db_connection_error(max_attempts=3)
    def get_stock_basic(
        self,
        ts_codes: Optional[List[str]] = None,
        list_status: str = "L",
    ) -> pd.DataFrame:
        """
        获取股票基础信息

        Args:
            ts_codes: 股票代码列表（None表示全部）
            list_status: 上市状态（L:上市 D:退市 P:暂停）

        Returns:
            股票基础信息DataFrame

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            query = select(StockBasic).where(StockBasic.list_status == list_status)

            if ts_codes:
                query = query.where(StockBasic.ts_code.in_(ts_codes))

            df = pd.read_sql(query, self.session.bind)

            if df.empty and ts_codes:
                raise DataNotAvailableException(
                    message=f"未找到股票基础信息",
                    context={"ts_codes": ts_codes, "list_status": list_status}
                )

            return df

        except DataNotAvailableException:
            raise
        except Exception as e:
            raise DatabaseException(
                message="查询股票基础信息失败",
                context={"ts_codes": ts_codes, "list_status": list_status, "error": str(e)},
                retryable=False,
            ) from e

    # ==================== 日线数据 ====================

    @retry_on_db_connection_error(max_attempts=3)
    def get_stock_daily(
        self,
        trade_date: date,
        ts_codes: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取指定日期的日线数据

        Args:
            trade_date: 交易日期
            ts_codes: 股票代码列表（None表示全部）

        Returns:
            日线数据DataFrame

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            query = select(StockDaily).where(StockDaily.trade_date == trade_date)

            if ts_codes:
                query = query.where(StockDaily.ts_code.in_(ts_codes))

            df = pd.read_sql(query, self.session.bind)

            if df.empty:
                raise DataNotAvailableException(
                    message=f"未找到 {trade_date} 的日线数据",
                    context={"trade_date": str(trade_date), "ts_codes": ts_codes}
                )

            return df

        except DataNotAvailableException:
            raise
        except Exception as e:
            raise DatabaseException(
                message=f"查询日线数据失败: {trade_date}",
                context={"trade_date": str(trade_date), "ts_codes": ts_codes, "error": str(e)},
                retryable=False,
            ) from e

    @retry_on_db_connection_error(max_attempts=3)
    def get_stock_daily_range(
        self,
        start_date: date,
        end_date: date,
        ts_codes: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取日期范围内的日线数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            ts_codes: 股票代码列表（None表示全部）

        Returns:
            日线数据DataFrame

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            query = select(StockDaily).where(
                and_(
                    StockDaily.trade_date >= start_date,
                    StockDaily.trade_date <= end_date,
                )
            )

            if ts_codes:
                query = query.where(StockDaily.ts_code.in_(ts_codes))

            df = pd.read_sql(query, self.session.bind)

            if df.empty:
                raise DataNotAvailableException(
                    message=f"未找到 {start_date} 至 {end_date} 的日线数据",
                    context={
                        "start_date": str(start_date),
                        "end_date": str(end_date),
                        "ts_codes": ts_codes,
                    }
                )

            return df

        except DataNotAvailableException:
            raise
        except Exception as e:
            raise DatabaseException(
                message=f"查询日线数据失败: {start_date} - {end_date}",
                context={
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "ts_codes": ts_codes,
                    "error": str(e),
                },
                retryable=False,
            ) from e

    # ==================== 财务数据（PIT约束） ====================

    @retry_on_db_connection_error(max_attempts=3)
    def get_financial_data_pit(
        self,
        trade_date: date,
        ts_codes: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取财务数据（严格遵守PIT约束）

        PIT约束: 仅返回 ann_date <= trade_date 的财务数据
        对于同一股票同一报告期，返回最新的公告记录

        Args:
            trade_date: 交易日期
            ts_codes: 股票代码列表（None表示全部）

        Returns:
            财务数据DataFrame

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            # 子查询：获取每只股票最新的财务数据
            # 条件：ann_date <= trade_date
            subquery = (
                select(
                    StockFinancial.ts_code,
                    StockFinancial.end_date,
                    StockFinancial.ann_date,
                )
                .where(StockFinancial.ann_date <= trade_date)
                .order_by(
                    StockFinancial.ts_code,
                    StockFinancial.end_date.desc(),
                    StockFinancial.ann_date.desc(),
                )
                .distinct(StockFinancial.ts_code)
            )

            if ts_codes:
                subquery = subquery.where(StockFinancial.ts_code.in_(ts_codes))

            # 主查询：根据子查询结果获取完整财务数据
            query = select(StockFinancial).where(
                and_(
                    StockFinancial.ts_code.in_(select(subquery.c.ts_code)),
                    StockFinancial.end_date.in_(select(subquery.c.end_date)),
                    StockFinancial.ann_date.in_(select(subquery.c.ann_date)),
                )
            )

            df = pd.read_sql(query, self.session.bind)

            # 财务数据可能为空（新股、退市股），不抛出异常
            return df

        except Exception as e:
            raise DatabaseException(
                message=f"查询财务数据失败: {trade_date}",
                context={"trade_date": str(trade_date), "ts_codes": ts_codes, "error": str(e)},
                retryable=False,
            ) from e

    # ==================== 资金流数据 ====================

    @retry_on_db_connection_error(max_attempts=3)
    def get_money_flow(
        self,
        trade_date: date,
        ts_codes: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取资金流数据

        Args:
            trade_date: 交易日期
            ts_codes: 股票代码列表（None表示全部）

        Returns:
            资金流数据DataFrame

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            query = select(StockMoneyFlow).where(StockMoneyFlow.trade_date == trade_date)

            if ts_codes:
                query = query.where(StockMoneyFlow.ts_code.in_(ts_codes))

            df = pd.read_sql(query, self.session.bind)

            # 资金流数据可能为空，不抛出异常
            return df

        except Exception as e:
            raise DatabaseException(
                message=f"查询资金流数据失败: {trade_date}",
                context={"trade_date": str(trade_date), "ts_codes": ts_codes, "error": str(e)},
                retryable=False,
            ) from e

    # ==================== 北向资金数据 ====================

    @retry_on_db_connection_error(max_attempts=3)
    def get_northbound_flow(
        self,
        trade_date: date,
        ts_codes: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取北向资金数据

        Args:
            trade_date: 交易日期
            ts_codes: 股票代码列表（None表示全部）

        Returns:
            北向资金数据DataFrame

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            query = select(StockNorthbound).where(StockNorthbound.trade_date == trade_date)

            if ts_codes:
                query = query.where(StockNorthbound.ts_code.in_(ts_codes))

            df = pd.read_sql(query, self.session.bind)

            # 北向资金数据可能为空，不抛出异常
            return df

        except Exception as e:
            raise DatabaseException(
                message=f"查询北向资金数据失败: {trade_date}",
                context={"trade_date": str(trade_date), "ts_codes": ts_codes, "error": str(e)},
                retryable=False,
            ) from e

    # ==================== 指数数据 ====================

    @retry_on_db_connection_error(max_attempts=3)
    def get_index_daily(
        self,
        trade_date: date,
        ts_codes: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取指数日线数据

        Args:
            trade_date: 交易日期
            ts_codes: 指数代码列表（None表示全部）

        Returns:
            指数日线数据DataFrame

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            query = select(IndexDaily).where(IndexDaily.trade_date == trade_date)

            if ts_codes:
                query = query.where(IndexDaily.ts_code.in_(ts_codes))

            df = pd.read_sql(query, self.session.bind)

            if df.empty:
                raise DataNotAvailableException(
                    message=f"未找到 {trade_date} 的指数数据",
                    context={"trade_date": str(trade_date), "ts_codes": ts_codes}
                )

            return df

        except DataNotAvailableException:
            raise
        except Exception as e:
            raise DatabaseException(
                message=f"查询指数数据失败: {trade_date}",
                context={"trade_date": str(trade_date), "ts_codes": ts_codes, "error": str(e)},
                retryable=False,
            ) from e

    # ==================== 批量插入 ====================

    def bulk_insert_stock_daily(self, data: pd.DataFrame) -> int:
        """
        批量插入日线数据

        Args:
            data: 日线数据DataFrame

        Returns:
            插入的记录数

        Raises:
            DatabaseException: 数据库插入失败
        """
        try:
            if data.empty:
                return 0

            # 使用pandas to_sql批量插入
            data.to_sql(
                "stock_daily",
                self.session.bind,
                if_exists="append",
                index=False,
                method="multi",
            )

            return len(data)

        except Exception as e:
            raise DatabaseException(
                message="批量插入日线数据失败",
                context={"rows": len(data), "error": str(e)},
                retryable=False,
            ) from e
