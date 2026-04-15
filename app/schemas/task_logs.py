from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class TaskLogBase(BaseModel):
    task_type: str
    task_name: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    progress: Optional[float] = None
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

class TaskLogOut(TaskLogBase):
    id: int

    class Config:
        orm_mode = True