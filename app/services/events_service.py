"""事件中心服务"""

from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.event_center import EventCenter
from app.models.risk_flag_daily import RiskFlagDaily
from app.schemas.events import EventCreate, RiskFlagResponse


class EventService:
    """事件中心服务"""

    @staticmethod
    def get_events(
        db: Session,
        stock_id: Optional[int] = None,
        event_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[EventCenter]:
        """查询事件列表"""
        query = db.query(EventCenter)
        if stock_id is not None:
            query = query.filter(EventCenter.stock_id == stock_id)
        if event_type is not None:
            query = query.filter(EventCenter.event_type == event_type)
        if start_date is not None:
            query = query.filter(EventCenter.event_date >= start_date)
        if end_date is not None:
            query = query.filter(EventCenter.event_date <= end_date)
        if severity is not None:
            query = query.filter(EventCenter.severity == severity)
        return query.order_by(EventCenter.event_date.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def get_event_by_id(db: Session, event_id: int) -> Optional[EventCenter]:
        """获取事件详情"""
        return db.query(EventCenter).filter(EventCenter.id == event_id).first()

    @staticmethod
    def create_event(db: Session, event_data: EventCreate) -> EventCenter:
        """创建事件"""
        event = EventCenter(**event_data.model_dump())
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def get_risk_flags(
        db: Session,
        trade_date: date,
        stock_id: Optional[int] = None,
    ) -> List[RiskFlagDaily]:
        """查询风险标签"""
        query = db.query(RiskFlagDaily).filter(RiskFlagDaily.trade_date == trade_date)
        if stock_id is not None:
            query = query.filter(RiskFlagDaily.stock_id == stock_id)
        return query.all()

    @staticmethod
    def get_blacklist(db: Session, trade_date: date) -> List[RiskFlagDaily]:
        """获取黑名单股票"""
        return db.query(RiskFlagDaily).filter(
            and_(
                RiskFlagDaily.trade_date == trade_date,
                RiskFlagDaily.blacklist_flag == True,
            )
        ).all()
