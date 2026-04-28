from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskLogBase(BaseModel):
    task_type: str  # data_import, factor_calculation, backtest, report_generation
    task_name: str
    status: str  # running, completed, failed, cancelled
    start_time: datetime
    end_time: datetime | None = None
    duration: float | None = None
    progress: float | None = None  # 0-100
    total_items: int | None = None
    completed_items: int | None = None
    error_message: str | None = None
    log_data: dict | None = None


class TaskLogCreate(TaskLogBase):
    pass


class TaskLogUpdate(BaseModel):
    status: str | None = None
    end_time: datetime | None = None
    duration: float | None = None
    progress: float | None = None
    completed_items: int | None = None
    error_message: str | None = None
    log_data: dict | None = None


class TaskLogInDB(TaskLogBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskLogOut(TaskLogBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskLog(TaskLogOut):
    pass
