"""
回测数据Repository
==================
负责回测结果的查询和存储

设计原则:
- 所有方法返回DataFrame或基础数据类型
- 支持批量操作
- 统一异常处理
"""

from datetime import date
from typing import List, Optional, Dict, Any

import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.models.backtests import Backtest
from app.core.exceptions import DatabaseException, DataNotAvailableException
from app.core.retry import retry_on_db_connection_error, retry_on_db_deadlock


class BacktestRepository:
    """回测数据Repository"""

    def __init__(self, session: Session):
        self.session = session

    # ==================== 查询回测 ====================

    @retry_on_db_connection_error(max_attempts=3)
    def get_backtest_by_id(self, backtest_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取回测记录

        Args:
            backtest_id: 回测ID

        Returns:
            回测记录字典，不存在返回None

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            backtest = self.session.query(Backtest).filter(Backtest.id == backtest_id).first()

            if not backtest:
                return None

            return {
                "id": backtest.id,
                "model_id": backtest.model_id,
                "start_date": backtest.start_date,
                "end_date": backtest.end_date,
                "initial_capital": backtest.initial_capital,
                "status": backtest.status,
                "results": backtest.results,
                "created_at": backtest.created_at,
                "updated_at": backtest.updated_at,
            }

        except Exception as e:
            raise DatabaseException(
                message=f"查询回测记录失败: {backtest_id}",
                context={"backtest_id": backtest_id, "error": str(e)},
                retryable=False,
            ) from e

    @retry_on_db_connection_error(max_attempts=3)
    def get_backtests(
        self,
        model_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        查询回测列表

        Args:
            model_id: 模型ID（None表示全部）
            status: 状态（None表示全部）
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            回测记录列表

        Raises:
            DatabaseException: 数据库查询失败
        """
        try:
            query = self.session.query(Backtest)

            if model_id is not None:
                query = query.filter(Backtest.model_id == model_id)

            if status:
                query = query.filter(Backtest.status == status)

            query = query.order_by(Backtest.created_at.desc()).offset(skip).limit(limit)

            backtests = query.all()

            return [
                {
                    "id": bt.id,
                    "model_id": bt.model_id,
                    "start_date": bt.start_date,
                    "end_date": bt.end_date,
                    "initial_capital": bt.initial_capital,
                    "status": bt.status,
                    "results": bt.results,
                    "created_at": bt.created_at,
                    "updated_at": bt.updated_at,
                }
                for bt in backtests
            ]

        except Exception as e:
            raise DatabaseException(
                message="查询回测列表失败",
                context={
                    "model_id": model_id,
                    "status": status,
                    "skip": skip,
                    "limit": limit,
                    "error": str(e),
                },
                retryable=False,
            ) from e

    # ==================== 创建回测 ====================

    @retry_on_db_deadlock(max_attempts=3)
    def create_backtest(self, data: Dict[str, Any]) -> int:
        """
        创建回测记录

        Args:
            data: 回测数据字典

        Returns:
            回测ID

        Raises:
            DatabaseException: 数据库创建失败
        """
        try:
            backtest = Backtest(**data)
            self.session.add(backtest)
            self.session.commit()
            self.session.refresh(backtest)

            return backtest.id

        except Exception as e:
            self.session.rollback()
            raise DatabaseException(
                message="创建回测记录失败",
                context={"data": data, "error": str(e)},
                retryable=True,
            ) from e

    # ==================== 更新回测 ====================

    @retry_on_db_deadlock(max_attempts=3)
    def update_backtest(self, backtest_id: int, data: Dict[str, Any]) -> bool:
        """
        更新回测记录

        Args:
            backtest_id: 回测ID
            data: 更新数据字典

        Returns:
            是否更新成功

        Raises:
            DatabaseException: 数据库更新失败
        """
        try:
            backtest = self.session.query(Backtest).filter(Backtest.id == backtest_id).first()

            if not backtest:
                return False

            for key, value in data.items():
                if hasattr(backtest, key):
                    setattr(backtest, key, value)

            self.session.commit()
            return True

        except Exception as e:
            self.session.rollback()
            raise DatabaseException(
                message=f"更新回测记录失败: {backtest_id}",
                context={"backtest_id": backtest_id, "data": data, "error": str(e)},
                retryable=True,
            ) from e

    # ==================== 删除回测 ====================

    @retry_on_db_deadlock(max_attempts=3)
    def delete_backtest(self, backtest_id: int) -> bool:
        """
        删除回测记录

        Args:
            backtest_id: 回测ID

        Returns:
            是否删除成功

        Raises:
            DatabaseException: 数据库删除失败
        """
        try:
            backtest = self.session.query(Backtest).filter(Backtest.id == backtest_id).first()

            if not backtest:
                return False

            self.session.delete(backtest)
            self.session.commit()
            return True

        except Exception as e:
            self.session.rollback()
            raise DatabaseException(
                message=f"删除回测记录失败: {backtest_id}",
                context={"backtest_id": backtest_id, "error": str(e)},
                retryable=True,
            ) from e
