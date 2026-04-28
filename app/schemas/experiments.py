"""实验注册Schema"""

from datetime import datetime

from pydantic import BaseModel


class ExperimentRegistryBase(BaseModel):
    experiment_id: str
    experiment_name: str
    snapshot_id: str | None = None
    config_version: str | None = None
    code_version: str | None = None
    result_summary: str | None = None
    status: str = "pending"


class ExperimentRegistryCreate(ExperimentRegistryBase):
    pass


class ExperimentRegistryResponse(ExperimentRegistryBase):
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
