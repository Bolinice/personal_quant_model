"""监控Schema"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class FactorHealthResponse(BaseModel):
    trade_date: date
    factor_name: str
    coverage_rate: float | None = None
    missing_rate: float | None = None
    ic_rolling: float | None = None
    ic_mean: float | None = None
    icir: float | None = None
    psi: float | None = None
    health_status: str = "healthy"

    class Config:
        from_attributes = True


class ModelHealthResponse(BaseModel):
    trade_date: date
    model_id: str
    prediction_drift: float | None = None
    feature_importance_drift: float | None = None
    oos_score: float | None = None
    health_status: str = "healthy"

    class Config:
        from_attributes = True


class PortfolioMonitorResponse(BaseModel):
    trade_date: date | None = None
    model_id: int | None = None
    industry_exposure: dict[str, float] | None = None
    style_exposure: dict[str, float] | None = None
    turnover_rate: float | None = None
    crowding_score: float | None = None


class LiveTrackingResponse(BaseModel):
    model_id: int | None = None
    execution_deviation: float | None = None
    cost_deviation: float | None = None
    drawdown: float | None = None
    fill_rate: float | None = None


class MonitorAlertResponse(BaseModel):
    alert_id: int
    alert_time: datetime | None = None
    alert_type: str | None = None
    severity: str | None = None
    object_type: str | None = None
    object_name: str | None = None
    message: str | None = None
    resolved_flag: bool = False

    class Config:
        from_attributes = True


class RegimeResponse(BaseModel):
    trade_date: str | None = None
    regime: str = "trending"
    confidence: float | None = None
    regime_detail: dict[str, Any] | None = None
    module_weight_adjustment: dict[str, float] | None = None
