"""模型注册Schema"""

from datetime import date, datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class ModelRegistryBase(BaseModel):
    model_id: str
    model_name: str
    model_type: Optional[str] = None
    feature_set_version: Optional[str] = None
    label_version: Optional[str] = None
    train_start: Optional[date] = None
    train_end: Optional[date] = None
    valid_start: Optional[date] = None
    valid_end: Optional[date] = None
    params_json: Optional[str] = None
    oof_metric_json: Optional[str] = None
    status: str = "candidate"


class ModelRegistryCreate(ModelRegistryBase):
    pass


class ModelRegistryResponse(ModelRegistryBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
