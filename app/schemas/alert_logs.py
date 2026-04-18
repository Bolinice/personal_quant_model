from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

class AlertLogBase(BaseModel):
    alert_type: str  # risk, performance, system, data
    severity: str  # critical, high, medium, low
    title: str
    message: str
    source: str
    status: str  # open, resolved, acknowledged
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None
    related_data: Optional[dict] = None

class AlertLogCreate(AlertLogBase):
    pass

class AlertLogUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    status: Optional[str] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None

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