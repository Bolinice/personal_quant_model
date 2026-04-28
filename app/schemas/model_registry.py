"""模型注册Schema"""

from datetime import date, datetime

from pydantic import BaseModel


class ModelRegistryBase(BaseModel):
    model_id: str
    model_name: str
    model_type: str | None = None
    feature_set_version: str | None = None
    label_version: str | None = None
    train_start: date | None = None
    train_end: date | None = None
    valid_start: date | None = None
    valid_end: date | None = None
    params_json: str | None = None
    oof_metric_json: str | None = None
    status: str = "candidate"


class ModelRegistryCreate(ModelRegistryBase):
    pass


class ModelRegistryResponse(ModelRegistryBase):
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
