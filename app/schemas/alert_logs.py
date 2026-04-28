from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertLogBase(BaseModel):
    alert_type: str  # risk, performance, system, data
    severity: str  # critical, high, medium, low
    title: str
    message: str
    source: str
    status: str  # open, resolved, acknowledged
    resolved_at: datetime | None = None
    resolution: str | None = None
    related_data: dict | None = None


class AlertLogCreate(AlertLogBase):
    pass


class AlertLogUpdate(BaseModel):
    title: str | None = None
    message: str | None = None
    status: str | None = None
    resolution: str | None = None
    resolved_at: datetime | None = None


class AlertLogInDB(AlertLogBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertLogOut(AlertLogBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertLog(AlertLogOut):
    pass
