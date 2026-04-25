"""监控Schema"""

from datetime import date, datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class FactorHealthResponse(BaseModel):
    trade_date: date
    factor_name: str
    coverage_rate: Optional[float] = None
    missing_rate: Optional[float] = None
    ic_rolling: Optional[float] = None
    ic_mean: Optional[float] = None
    ir: Optional[float] = None
    psi: Optional[float] = None
    health_status: str = "healthy"

    class Config:
        from_attributes = True


class ModelHealthResponse(BaseModel):
    trade_date: date
    model_id: str
    prediction_drift: Optional[float] = None
    feature_importance_drift: Optional[float] = None
    oos_score: Optional[float] = None
    health_status: str = "healthy"

    class Config:
        from_attributes = True


class PortfolioMonitorResponse(BaseModel):
    trade_date: Optional[date] = None
    model_id: Optional[int] = None
    industry_exposure: Optional[Dict[str, float]] = None
    style_exposure: Optional[Dict[str, float]] = None
    turnover_rate: Optional[float] = None
    crowding_score: Optional[float] = None


class LiveTrackingResponse(BaseModel):
    model_id: Optional[int] = None
    execution_deviation: Optional[float] = None
    cost_deviation: Optional[float] = None
    drawdown: Optional[float] = None
    fill_rate: Optional[float] = None


class MonitorAlertResponse(BaseModel):
    alert_id: int
    alert_time: Optional[datetime] = None
    alert_type: Optional[str] = None
    severity: Optional[str] = None
    object_type: Optional[str] = None
    object_name: Optional[str] = None
    message: Optional[str] = None
    resolved_flag: bool = False

    class Config:
        from_attributes = True


class RegimeResponse(BaseModel):
    trade_date: Optional[str] = None
    regime: str = "trending"
    confidence: Optional[float] = None
    regime_detail: Optional[Dict[str, Any]] = None
    module_weight_adjustment: Optional[Dict[str, float]] = None
