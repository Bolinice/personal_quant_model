"""
行业分类Repository
==================
负责行业分类数据的查询，支持历史时点查询

设计原则:
- 支持PIT（Point-in-Time）查询
- 返回DataFrame格式
- 统一异常处理
"""

from datetime import date
from typing import List, Optional

import pandas as pd
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from app.models.market.stock_industry import StockIndustry
from app.core.exceptions import DatabaseException, DataNotAvailableException
from app.core.retry import retry_on_db_connection_error


class IndustryRepository:
    """行业分类Repository"""

    def __init__(self, session: Session):
        self.session = session

    @retry_on_db_connection_error(max_attempts=3)
    def get_industry_at_date(
        self,
        trade_date: date,
        ts_codes: Optional[List[str]] = None,
        standard: str = "sw",
        level: str = "L1",
    ) -> pd.DataFrame:
        """
        获取指定日期的行业分类（历史时点查询）

        Args:
            trade_date: 交易日期
            ts_codes: 股票代码列表（None表示全部）
            standard: 行业分类标准（sw:申万, zjh:证监会, cs:中信）
            level: 行业级别（L1, L2, L3）

        Returns:
            DataFrame with columns: ts_code, industry_name, industry_code, level, standard

        Examples:
            >>> repo = IndustryRepository(session)
            >>> # 查询2020年1月1日的申万一级行业
            >>> df = repo.get_industry_at_date(
            ...     trade_date=date(2020, 1, 1),
            ...     standard="sw",
            ...     level="L1"
            ... )
        """
        try:
            # 构建查询条件
            conditions = [
                StockIndustry.standard == standard,
                StockIndustry.level == level,
                # 历史时点查询：effective_date <= trade_date
                or_(
                    StockIndustry.effective_date.is_(None),
                    StockIndustry.effective_date <= trade_date
                ),
                # 且 expire_date > trade_date 或为 NULL（当前有效）
                or_(
                    StockIndustry.expire_date.is_(None),
                    StockIndustry.expire_date > trade_date
                )
            ]

            # 如果指定了股票代码，添加过滤条件
            if ts_codes:
                conditions.append(StockIndustry.ts_code.in_(ts_codes))

            # 执行查询
            stmt = select(
                StockIndustry.ts_code,
                StockIndustry.industry_name,
                StockIndustry.industry_code,
                StockIndustry.level,
                StockIndustry.standard,
            ).where(and_(*conditions))

            result = self.session.execute(stmt)
            rows = result.fetchall()

            if not rows:
                return pd.DataFrame(columns=[
                    'ts_code', 'industry_name', 'industry_code', 'level', 'standard'
                ])

            # 转换为DataFrame
            df = pd.DataFrame(rows, columns=[
                'ts_code', 'industry_name', 'industry_code', 'level', 'standard'
            ])

            return df

        except Exception as e:
            raise DatabaseException(f"查询行业分类失败: {str(e)}")

    @retry_on_db_connection_error(max_attempts=3)
    def get_current_industry(
        self,
        ts_codes: Optional[List[str]] = None,
        standard: str = "sw",
        level: str = "L1",
    ) -> pd.DataFrame:
        """
        获取当前有效的行业分类

        Args:
            ts_codes: 股票代码列表（None表示全部）
            standard: 行业分类标准（sw:申万, zjh:证监会, cs:中信）
            level: 行业级别（L1, L2, L3）

        Returns:
            DataFrame with columns: ts_code, industry_name, industry_code, level, standard
        """
        try:
            # 构建查询条件
            conditions = [
                StockIndustry.standard == standard,
                StockIndustry.level == level,
                StockIndustry.expire_date.is_(None),  # 当前有效
            ]

            if ts_codes:
                conditions.append(StockIndustry.ts_code.in_(ts_codes))

            stmt = select(
                StockIndustry.ts_code,
                StockIndustry.industry_name,
                StockIndustry.industry_code,
                StockIndustry.level,
                StockIndustry.standard,
            ).where(and_(*conditions))

            result = self.session.execute(stmt)
            rows = result.fetchall()

            if not rows:
                return pd.DataFrame(columns=[
                    'ts_code', 'industry_name', 'industry_code', 'level', 'standard'
                ])

            df = pd.DataFrame(rows, columns=[
                'ts_code', 'industry_name', 'industry_code', 'level', 'standard'
            ])

            return df

        except Exception as e:
            raise DatabaseException(f"查询当前行业分类失败: {str(e)}")

    @retry_on_db_connection_error(max_attempts=3)
    def get_industry_changes(
        self,
        start_date: date,
        end_date: date,
        ts_codes: Optional[List[str]] = None,
        standard: str = "sw",
        level: str = "L1",
    ) -> pd.DataFrame:
        """
        获取指定时间范围内的行业变更记录

        Args:
            start_date: 开始日期
            end_date: 结束日期
            ts_codes: 股票代码列表（None表示全部）
            standard: 行业分类标准
            level: 行业级别

        Returns:
            DataFrame with columns: ts_code, industry_name, industry_code,
                                   effective_date, expire_date, level, standard
        """
        try:
            conditions = [
                StockIndustry.standard == standard,
                StockIndustry.level == level,
                # 在时间范围内生效或失效的记录
                or_(
                    and_(
                        StockIndustry.effective_date >= start_date,
                        StockIndustry.effective_date <= end_date
                    ),
                    and_(
                        StockIndustry.expire_date >= start_date,
                        StockIndustry.expire_date <= end_date
                    )
                )
            ]

            if ts_codes:
                conditions.append(StockIndustry.ts_code.in_(ts_codes))

            stmt = select(
                StockIndustry.ts_code,
                StockIndustry.industry_name,
                StockIndustry.industry_code,
                StockIndustry.effective_date,
                StockIndustry.expire_date,
                StockIndustry.level,
                StockIndustry.standard,
            ).where(and_(*conditions)).order_by(
                StockIndustry.ts_code,
                StockIndustry.effective_date
            )

            result = self.session.execute(stmt)
            rows = result.fetchall()

            if not rows:
                return pd.DataFrame(columns=[
                    'ts_code', 'industry_name', 'industry_code',
                    'effective_date', 'expire_date', 'level', 'standard'
                ])

            df = pd.DataFrame(rows, columns=[
                'ts_code', 'industry_name', 'industry_code',
                'effective_date', 'expire_date', 'level', 'standard'
            ])

            return df

        except Exception as e:
            raise DatabaseException(f"查询行业变更记录失败: {str(e)}")
