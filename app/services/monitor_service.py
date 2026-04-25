"""监控服务"""

from datetime import date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.monitor_factor_health import MonitorFactorHealth
from app.models.monitor_model_health import MonitorModelHealth
from app.schemas.monitor import (
    FactorHealthResponse,
    ModelHealthResponse,
    RegimeResponse,
)


class MonitorService:
    """监控服务 - 因子健康/模型健康/组合监控/实盘跟踪"""

    @staticmethod
    def get_factor_health(
        db: Session,
        trade_date: Optional[date] = None,
        factor_name: Optional[str] = None,
        health_status: Optional[str] = None,
        limit: int = 100,
    ) -> List[MonitorFactorHealth]:
        """查询因子健康状态"""
        query = db.query(MonitorFactorHealth)
        if trade_date:
            query = query.filter(MonitorFactorHealth.trade_date == trade_date)
        if factor_name:
            query = query.filter(MonitorFactorHealth.factor_name == factor_name)
        if health_status:
            query = query.filter(MonitorFactorHealth.health_status == health_status)
        return query.order_by(MonitorFactorHealth.trade_date.desc()).limit(limit).all()

    @staticmethod
    def get_model_health(
        db: Session,
        trade_date: Optional[date] = None,
        model_id: Optional[str] = None,
        health_status: Optional[str] = None,
        limit: int = 100,
    ) -> List[MonitorModelHealth]:
        """查询模型健康状态"""
        query = db.query(MonitorModelHealth)
        if trade_date:
            query = query.filter(MonitorModelHealth.trade_date == trade_date)
        if model_id:
            query = query.filter(MonitorModelHealth.model_id == model_id)
        if health_status:
            query = query.filter(MonitorModelHealth.health_status == health_status)
        return query.order_by(MonitorModelHealth.trade_date.desc()).limit(limit).all()

    @staticmethod
    def get_regime(db: Session, trade_date: Optional[date] = None) -> Dict[str, Any]:
        """获取市场状态"""
        from app.core.regime import RegimeDetector
        detector = RegimeDetector()
        regime_result = detector.detect_regime()
        return regime_result

    @staticmethod
    def get_portfolio_monitor(
        db: Session,
        trade_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """组合监控"""
        return {
            "trade_date": str(trade_date or date.today()),
            "industry_exposure": {},
            "style_exposure": {},
            "turnover_rate": 0.0,
            "crowding_score": 0.0,
        }

    @staticmethod
    def get_live_tracking(db: Session) -> Dict[str, Any]:
        """实盘跟踪"""
        return {
            "execution_deviation": 0.0,
            "cost_deviation": 0.0,
            "drawdown": 0.0,
            "fill_rate": 0.0,
        }

    @staticmethod
    def get_alerts(
        db: Session,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取告警列表"""
        # TODO: 实现告警存储后对接
        return []

    @staticmethod
    def resolve_alert(db: Session, alert_id: int) -> bool:
        """解决告警"""
        # TODO: 实现告警存储后对接
        return True
