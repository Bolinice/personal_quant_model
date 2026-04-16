from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class TaskLogBase(BaseModel):
    task_type: str  # data_import, factor_calculation, backtest, report_generation
    task_name: str
    status: str  # running, completed, failed, cancelled
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    progress: Optional[float] = None  # 0-100
    total_items: Optional[int] = None
    completed_items: Optional[int] = None
    error_message: Optional[str] = None
    log_data: Optional[dict] = None

class TaskLogCreate(TaskLogBase):
    pass

class TaskLogUpdate(BaseModel):
    status: Optional[str] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    progress: Optional[float] = None
    completed_items: Optional[int] = None
    error_message: Optional[str] = None
    log_data: Optional[dict] = None

class TaskLogInDB(TaskLogBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TaskLogOut(TaskLogBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TaskLog(TaskLogOut):
    pass