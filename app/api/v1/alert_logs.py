from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.alert_logs_service import (
    get_alert_logs, create_alert_log, get_alert_log_by_id, update_alert_log, delete_alert_log,
    monitor_risk_exposure, monitor_performance, trigger_alerts
)
from app.models.alert_logs import AlertLog
from app.schemas.alert_logs import AlertLogCreate, AlertLogUpdate, AlertLogOut

router = APIRouter()

@router.get("/", response_model=List[AlertLogOut])
def read_alert_logs(skip: int = 0, limit: int = 100, alert_type: str = None, severity: str = None, status: str = None, db: Session = Depends(get_db)):
    logs = get_alert_logs(skip=skip, limit=limit, alert_type=alert_type, severity=severity, status=status, db=db)
    return logs

@router.get("/{log_id}", response_model=AlertLogOut)
def read_alert_log(log_id: int, db: Session = Depends(get_db)):
    log = get_alert_log_by_id(log_id, db=db)
    if log is None:
        raise HTTPException(status_code=404, detail="Alert log not found")
    return log

@router.post("/", response_model=AlertLogOut)
def create_alert_log_endpoint(log: AlertLogCreate, db: Session = Depends(get_db)):
    return create_alert_log(log, db=db)

@router.put("/{log_id}", response_model=AlertLogOut)
def update_alert_log_endpoint(log_id: int, log_update: AlertLogUpdate, db: Session = Depends(get_db)):
    log = update_alert_log(log_id, log_update, db=db)
    if log is None:
        raise HTTPException(status_code=404, detail="Alert log not found")
    return log

@router.delete("/{log_id}")
def delete_alert_log_endpoint(log_id: int, db: Session = Depends(get_db)):
    success = delete_alert_log(log_id, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Alert log not found")
    return {"message": "Alert log deleted successfully"}

@router.post("/risk-monitor/{portfolio_id}")
def trigger_risk_alerts(portfolio_id: int, date: str, db: Session = Depends(get_db)):
    alerts = monitor_risk_exposure(portfolio_id, date, db=db)
    if not alerts:
        return {"message": "No risk alerts triggered"}
    return {"alerts_triggered": len(alerts), "alerts": alerts}

@router.post("/performance-monitor/{portfolio_id}")
def trigger_performance_alerts(portfolio_id: int, date: str, db: Session = Depends(get_db)):
    alerts = monitor_performance(portfolio_id, date, db=db)
    if not alerts:
        return {"message": "No performance alerts triggered"}
    return {"alerts_triggered": len(alerts), "alerts": alerts}

@router.post("/trigger-all/{portfolio_id}")
def trigger_all_alerts(portfolio_id: int, date: str, db: Session = Depends(get_db)):
    alerts = trigger_alerts(portfolio_id, date, db=db)
    if not alerts:
        return {"message": "No alerts triggered"}
    return {"alerts_triggered": len(alerts), "alerts": alerts}
