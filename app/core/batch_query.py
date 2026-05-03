"""
批量查询工具

提供批量查询和预加载功能，消除N+1查询问题
"""

from typing import Dict, List, Optional, Any, TypeVar, Generic
from sqlalchemy.orm import Session
from sqlalchemy import and_
import pandas as pd

from app.models.market.stock_daily import StockDaily
from app.models.factor import Factor, FactorValue
from app.models.model import Model, ModelFactorWeight
from app.models.portfolio import Portfolio, PortfolioPosition

T = TypeVar('T')


class BatchQueryHelper:
    """批量查询助手"""

    def __init__(self, db: Session):
        self.db = db

    def get_factor_values_batch(
        self,
        factor_ids: List[int],
        trade_date: Any,
        security_ids: Optional[List[str]] = None
    ) -> Dict[int, Dict[str, float]]:
        """
        批量获取因子值

        Args:
            factor_ids: 因子ID列表
            trade_date: 交易日期
            security_ids: 股票代码列表（可选）

        Returns:
            {factor_id: {security_id: value}}
        """
        query = self.db.query(FactorValue).filter(
            and_(
                FactorValue.factor_id.in_(factor_ids),
                FactorValue.trade_date == trade_date
            )
        )

        if security_ids:
            query = query.filter(FactorValue.security_id.in_(security_ids))

        values = query.all()

        # 构建嵌套字典
        result: Dict[int, Dict[str, float]] = {}
        for v in values:
            if v.factor_id not in result:
                result[v.factor_id] = {}
            result[v.factor_id][v.security_id] = v.value

        return result

    def get_factors_by_ids(self, factor_ids: List[int]) -> Dict[int, Factor]:
        """
        批量获取因子定义

        Args:
            factor_ids: 因子ID列表

        Returns:
            {factor_id: Factor}
        """
        factors = self.db.query(Factor).filter(Factor.id.in_(factor_ids)).all()
        return {f.id: f for f in factors}

    def get_model_factor_weights_batch(
        self,
        model_ids: List[int]
    ) -> Dict[int, List[ModelFactorWeight]]:
        """
        批量获取模型因子权重

        Args:
            model_ids: 模型ID列表

        Returns:
            {model_id: [ModelFactorWeight]}
        """
        weights = (
            self.db.query(ModelFactorWeight)
            .filter(
                and_(
                    ModelFactorWeight.model_id.in_(model_ids),
                    ModelFactorWeight.is_active
                )
            )
            .all()
        )

        result: Dict[int, List[ModelFactorWeight]] = {}
        for w in weights:
            if w.model_id not in result:
                result[w.model_id] = []
            result[w.model_id].append(w)

        return result

    def get_stock_daily_batch(
        self,
        ts_codes: List[str],
        trade_date: Any
    ) -> Dict[str, StockDaily]:
        """
        批量获取股票日线数据

        Args:
            ts_codes: 股票代码列表
            trade_date: 交易日期

        Returns:
            {ts_code: StockDaily}
        """
        daily_data = (
            self.db.query(StockDaily)
            .filter(
                and_(
                    StockDaily.ts_code.in_(ts_codes),
                    StockDaily.trade_date == trade_date
                )
            )
            .all()
        )

        return {d.ts_code: d for d in daily_data}

    def get_stock_daily_range_batch(
        self,
        ts_codes: List[str],
        start_date: Any,
        end_date: Any
    ) -> Dict[str, List[StockDaily]]:
        """
        批量获取股票日线数据（日期范围）

        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            {ts_code: [StockDaily]}
        """
        daily_data = (
            self.db.query(StockDaily)
            .filter(
                and_(
                    StockDaily.ts_code.in_(ts_codes),
                    StockDaily.trade_date >= start_date,
                    StockDaily.trade_date <= end_date
                )
            )
            .order_by(StockDaily.ts_code, StockDaily.trade_date)
            .all()
        )

        result: Dict[str, List[StockDaily]] = {}
        for d in daily_data:
            if d.ts_code not in result:
                result[d.ts_code] = []
            result[d.ts_code].append(d)

        return result

    def get_portfolios_by_model_ids(
        self,
        model_ids: List[int]
    ) -> Dict[int, Portfolio]:
        """
        批量获取模型组合

        Args:
            model_ids: 模型ID列表

        Returns:
            {model_id: Portfolio}
        """
        portfolios = (
            self.db.query(Portfolio)
            .filter(Portfolio.model_id.in_(model_ids))
            .all()
        )

        return {p.model_id: p for p in portfolios}

    def get_portfolio_positions_batch(
        self,
        portfolio_ids: List[int]
    ) -> Dict[int, List[PortfolioPosition]]:
        """
        批量获取组合持仓

        Args:
            portfolio_ids: 组合ID列表

        Returns:
            {portfolio_id: [PortfolioPosition]}
        """
        positions = (
            self.db.query(PortfolioPosition)
            .filter(PortfolioPosition.portfolio_id.in_(portfolio_ids))
            .all()
        )

        result: Dict[int, List[PortfolioPosition]] = {}
        for p in positions:
            if p.portfolio_id not in result:
                result[p.portfolio_id] = []
            result[p.portfolio_id].append(p)

        return result


def batch_insert_objects(db: Session, objects: List[Any], batch_size: int = 1000):
    """
    批量插入对象

    Args:
        db: 数据库会话
        objects: 对象列表
        batch_size: 批次大小
    """
    for i in range(0, len(objects), batch_size):
        batch = objects[i:i + batch_size]
        db.bulk_save_objects(batch)
        db.flush()


def batch_insert_mappings(
    db: Session,
    model_class: type,
    mappings: List[Dict[str, Any]],
    batch_size: int = 1000
):
    """
    批量插入映射（更高效）

    Args:
        db: 数据库会话
        model_class: 模型类
        mappings: 字典列表
        batch_size: 批次大小
    """
    for i in range(0, len(mappings), batch_size):
        batch = mappings[i:i + batch_size]
        db.bulk_insert_mappings(model_class, batch)
        db.flush()


def batch_update_mappings(
    db: Session,
    model_class: type,
    mappings: List[Dict[str, Any]],
    batch_size: int = 1000
):
    """
    批量更新映射

    Args:
        db: 数据库会话
        model_class: 模型类
        mappings: 字典列表（必须包含主键）
        batch_size: 批次大小
    """
    for i in range(0, len(mappings), batch_size):
        batch = mappings[i:i + batch_size]
        db.bulk_update_mappings(model_class, batch)
        db.flush()
