"""监控API路由"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.core.response import success_response
from app.services.monitor_service import MonitorService

router = APIRouter(prefix="/monitor", tags=["监控告警"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/factor-health")
async def get_factor_health(
    trade_date: Optional[date] = None,
    factor_group: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """查询因子健康状态"""
    health = MonitorService.get_factor_health(db, trade_date=trade_date)
    return success_response(data=[{
        "trade_date": str(h.trade_date), "factor_name": h.factor_name,
        "coverage_rate": float(h.coverage_rate) if h.coverage_rate else None,
        "ic_mean": float(h.ic_mean) if h.ic_mean else None,
        "ir": float(h.ir) if h.ir else None,
        "psi": float(h.psi) if h.psi else None,
        "health_status": h.health_status,
    } for h in health])


@router.get("/model-health")
async def get_model_health(
    model_id: Optional[str] = None,
    trade_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """查询模型健康状态"""
    health = MonitorService.get_model_health(db, trade_date=trade_date, model_id=model_id)
    return success_response(data=[{
        "trade_date": str(h.trade_date), "model_id": h.model_id,
        "prediction_drift": float(h.prediction_drift) if h.prediction_drift else None,
        "feature_importance_drift": float(h.feature_importance_drift) if h.feature_importance_drift else None,
        "health_status": h.health_status,
    } for h in health])


@router.get("/portfolio")
async def get_portfolio_monitor(
    model_id: Optional[int] = None,
    trade_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """查询组合监控"""
    result = MonitorService.get_portfolio_monitor(db, trade_date=trade_date)
    return success_response(data=result)


@router.get("/live-tracking")
async def get_live_tracking(
    model_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """查询实盘偏差监控"""
    result = MonitorService.get_live_tracking(db)
    return success_response(data=result)


@router.get("/alerts")
async def get_alerts(
    severity: Optional[str] = None,
    type: Optional[str] = None,
    resolved: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询告警列表"""
    alerts = MonitorService.get_alerts(db, severity=severity, resolved=resolved)
    return success_response(data=alerts)


@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    """标记告警已解决"""
    success = MonitorService.resolve_alert(db, alert_id)
    return success_response(data={"alert_id": alert_id, "resolved": success})


@router.get("/regime")
async def get_regime(
    trade_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """查询市场状态(Regime)"""
    result = MonitorService.get_regime(db, trade_date=trade_date)
    return success_response(data=result)
