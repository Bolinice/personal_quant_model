"""
因子数据Repository
==================
负责因子数据的查询和存储

设计原则:
- 所有方法返回DataFrame
- 支持批量操作
- 统一异常处理
"""

from datetime import date
from typing import List, Optional

import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.factors import Factor
from app.core.exceptions import DatabaseException, DataNotAvailableException
from app.core.retry import retry_on_db_connection_error, retry_on_db_deadlock


class FactorRepository:
    """因子数据Repository"""

    def __init__(self, session: Session):
        self.session = session

    # ==================== 查询因子 ====================

    @retry_on_db_connection_error(max_attempts=3)
    def get_factors(
        self,
        trade_date: date,
        ts_codes: Optional[List[str]] = None,
        factor_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取指定日期的因子数据

        Args:
            trade_date: 交易日期
            ts_codes: 股票代码列表（None表示全部）
            factor_names: 因子名称列表（None表示全部）

        Returns:
            因子数据DataFrame

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            query = select(Factor).where(Factor.trade_date == trade_date)

            if ts_codes:
                query = query.where(Factor.ts_code.in_(ts_codes))

            if factor_names:
                # 假设Factor模型有factor_name字段
                query = query.where(Factor.factor_name.in_(factor_names))

            df = pd.read_sql(query, self.session.bind)

            if df.empty:
                raise DataNotAvailableException(
                    message=f"未找到 {trade_date} 的因子数据",
                    context={
                        "trade_date": str(trade_date),
                        "ts_codes": ts_codes,
                        "factor_names": factor_names,
                    }
                )

            return df

        except DataNotAvailableException:
            raise
        except Exception as e:
            raise DatabaseException(
                message=f"查询因子数据失败: {trade_date}",
                context={
                    "trade_date": str(trade_date),
                    "ts_codes": ts_codes,
                    "factor_names": factor_names,
                    "error": str(e),
                },
                retryable=False,
            ) from e

    @retry_on_db_connection_error(max_attempts=3)
    def get_factors_range(
        self,
        start_date: date,
        end_date: date,
        ts_codes: Optional[List[str]] = None,
        factor_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取日期范围内的因子数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            ts_codes: 股票代码列表（None表示全部）
            factor_names: 因子名称列表（None表示全部）

        Returns:
            因子数据DataFrame

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            query = select(Factor).where(
                and_(
                    Factor.trade_date >= start_date,
                    Factor.trade_date <= end_date,
                )
            )

            if ts_codes:
                query = query.where(Factor.ts_code.in_(ts_codes))

            if factor_names:
                query = query.where(Factor.factor_name.in_(factor_names))

            df = pd.read_sql(query, self.session.bind)

            if df.empty:
                raise DataNotAvailableException(
                    message=f"未找到 {start_date} 至 {end_date} 的因子数据",
                    context={
                        "start_date": str(start_date),
                        "end_date": str(end_date),
                        "ts_codes": ts_codes,
                        "factor_names": factor_names,
                    }
                )

            return df

        except DataNotAvailableException:
            raise
        except Exception as e:
            raise DatabaseException(
                message=f"查询因子数据失败: {start_date} - {end_date}",
                context={
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "ts_codes": ts_codes,
                    "factor_names": factor_names,
                    "error": str(e),
                },
                retryable=False,
            ) from e

    # ==================== 保存因子 ====================

    @retry_on_db_deadlock(max_attempts=3)
    def save_factors(self, data: pd.DataFrame) -> int:
        """
        批量保存因子数据

        Args:
            data: 因子数据DataFrame

        Returns:
            保存的记录数

        Raises:
            DatabaseException: 数据库保存失败
        """
        try:
            if data.empty:
                return 0

            # 使用pandas to_sql批量插入
            data.to_sql(
                "factors",
                self.session.bind,
                if_exists="append",
                index=False,
                method="multi",
            )

            return len(data)

        except Exception as e:
            raise DatabaseException(
                message="批量保存因子数据失败",
                context={"rows": len(data), "error": str(e)},
                retryable=True,  # 死锁可重试
            ) from e

    @retry_on_db_deadlock(max_attempts=3)
    def delete_factors(
        self,
        trade_date: date,
        ts_codes: Optional[List[str]] = None,
        factor_names: Optional[List[str]] = None,
    ) -> int:
        """
        删除因子数据

        Args:
            trade_date: 交易日期
            ts_codes: 股票代码列表（None表示全部）
            factor_names: 因子名称列表（None表示全部）

        Returns:
            删除的记录数

        Raises:
            DatabaseException: 数据库删除失败
        """
        try:
            query = self.session.query(Factor).filter(Factor.trade_date == trade_date)

            if ts_codes:
                query = query.filter(Factor.ts_code.in_(ts_codes))

            if factor_names:
                query = query.filter(Factor.factor_name.in_(factor_names))

            count = query.delete(synchronize_session=False)
            self.session.commit()

            return count

        except Exception as e:
            self.session.rollback()
            raise DatabaseException(
                message=f"删除因子数据失败: {trade_date}",
                context={
                    "trade_date": str(trade_date),
                    "ts_codes": ts_codes,
                    "factor_names": factor_names,
                    "error": str(e),
                },
                retryable=True,
            ) from e
