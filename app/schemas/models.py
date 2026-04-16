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

class ModelFactorWeightBase(BaseModel):
    model_id: int
    factor_id: int
    weight: float

class ModelFactorWeightCreate(ModelFactorWeightBase):
    pass

class ModelFactorWeightInDB(ModelFactorWeightBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ModelFactorWeightOut(ModelFactorWeightBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ModelFactorWeight(ModelFactorWeightOut):
    pass

class ModelScoreBase(BaseModel):
    model_id: int
    security_id: int
    total_score: float
    trade_date: datetime

class ModelScoreCreate(ModelScoreBase):
    pass

class ModelScoreInDB(ModelScoreBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ModelScoreOut(ModelScoreBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class ModelScore(ModelScoreOut):
    pass
