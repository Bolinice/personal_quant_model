"""告警日志 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.response import success
from app.db.base import get_db
from app.schemas.alert_logs import AlertLogCreate, AlertLogUpdate
from app.services.alert_logs_service import (
    create_alert_log,
    delete_alert_log,
    get_alert_log_by_id,
    get_alert_logs,
    monitor_performance,
    monitor_risk_exposure,
    trigger_alerts,
    update_alert_log,
)

router = APIRouter()


@router.get("/")
def read_alert_logs(
    skip: int = 0,
    limit: int = 100,
    alert_type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """获取告警日志列表"""
    logs = get_alert_logs(skip=skip, limit=limit, alert_type=alert_type, severity=severity, status=status, db=db)
    return success(logs)


@router.get("/{log_id}")
def read_alert_log(log_id: int, db: Session = Depends(get_db)):
    """获取告警日志详情"""
    log = get_alert_log_by_id(log_id, db=db)
    if log is None:
        raise HTTPException(status_code=404, detail="Alert log not found")
    return success(log)


@router.post("/")
def create_alert_log_endpoint(log: AlertLogCreate, db: Session = Depends(get_db)):
    """创建告警日志"""
    result = create_alert_log(log, db=db)
    return success(result)


@router.put("/{log_id}")
def update_alert_log_endpoint(log_id: int, log_update: AlertLogUpdate, db: Session = Depends(get_db)):
    """更新告警日志"""
    log = update_alert_log(log_id, log_update, db=db)
    if log is None:
        raise HTTPException(status_code=404, detail="Alert log not found")
    return success(log)


@router.delete("/{log_id}")
def delete_alert_log_endpoint(log_id: int, db: Session = Depends(get_db)):
    """删除告警日志"""
    deleted = delete_alert_log(log_id, db=db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert log not found")
    return success(message="Alert log deleted successfully")


@router.post("/risk-monitor/{portfolio_id}")
def trigger_risk_alerts(portfolio_id: int, date: str, db: Session = Depends(get_db)):
    """触发风控告警"""
    alerts = monitor_risk_exposure(portfolio_id, date, db=db)
    if not alerts:
        return success(message="No risk alerts triggered")
    return success({"alerts_triggered": len(alerts), "alerts": alerts})


@router.post("/performance-monitor/{portfolio_id}")
def trigger_performance_alerts(portfolio_id: int, date: str, db: Session = Depends(get_db)):
    """触发绩效告警"""
    alerts = monitor_performance(portfolio_id, date, db=db)
    if not alerts:
        return success(message="No performance alerts triggered")
    return success({"alerts_triggered": len(alerts), "alerts": alerts})


@router.post("/trigger-all/{portfolio_id}")
def trigger_all_alerts(portfolio_id: int, date: str, db: Session = Depends(get_db)):
    """触发所有告警"""
    alerts = trigger_alerts(portfolio_id, date, db=db)
    if not alerts:
        return success(message="No alerts triggered")
    return success({"alerts_triggered": len(alerts), "alerts": alerts})
