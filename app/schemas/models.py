from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class ModelBase(BaseModel):
    name: str
    description: Optional[str] = None
    model_type: str  # factor, timing, portfolio
    version: str = "1.0"
    is_active: bool = True

class ModelCreate(ModelBase):
    pass

class ModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model_type: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None

class ModelInDB(ModelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ModelOut(ModelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Model(ModelOut):
    pass

class ModelConfigBase(BaseModel):
    model_id: int
    config_name: str
    config_value: str
    description: Optional[str] = None

class ModelConfigCreate(ModelConfigBase):
    pass

class ModelConfigInDB(ModelConfigBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ModelConfigOut(ModelConfigBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ModelConfig(ModelConfigOut):
    pass