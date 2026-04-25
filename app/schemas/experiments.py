"""实验注册Schema"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ExperimentRegistryBase(BaseModel):
    experiment_id: str
    experiment_name: str
    snapshot_id: Optional[str] = None
    config_version: Optional[str] = None
    code_version: Optional[str] = None
    result_summary: Optional[str] = None
    status: str = "pending"


class ExperimentRegistryCreate(ExperimentRegistryBase):
    pass


class ExperimentRegistryResponse(ExperimentRegistryBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
