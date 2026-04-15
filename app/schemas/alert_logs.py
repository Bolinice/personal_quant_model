from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class AlertLogBase(BaseModel):
    alert_type: str
    severity: str
    title: str
    message: str
    source: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None
    related_data: Optional[dict] = None

class AlertLogCreate(AlertLogBase):
    pass

class AlertLogUpdate(BaseModel):
    severity: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None
    status: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None
    related_data: Optional[dict] = None

class AlertLogOut(AlertLogBase):
    id: int

    class Config:
        orm_mode = True