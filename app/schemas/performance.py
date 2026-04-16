from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class PerformanceBase(BaseModel):
    performance_type: str  # portfolio, factor, model
    entity_id: int
    metric_name: str
    metric_value: float
    trade_date: datetime

class PerformanceCreate(PerformanceBase):
    pass

class PerformanceUpdate(BaseModel):
    metric_value: Optional[float] = None

class PerformanceInDB(PerformanceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class PerformanceOut(PerformanceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Performance(PerformanceOut):
    pass