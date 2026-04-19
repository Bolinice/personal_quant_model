from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class ModelBase(BaseModel):
    model_code: str
    model_name: str
    description: Optional[str] = None
    model_type: str = "scoring"
    version: str = "1.0"
    status: str = "draft"

class ModelCreate(ModelBase):
    pass

class ModelUpdate(BaseModel):
    model_name: Optional[str] = None
    description: Optional[str] = None
    model_type: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None

class ModelOut(ModelBase):
    id: int
    model_code: Optional[str] = None
    factor_ids: Optional[list] = None
    factor_weights: Optional[dict] = None
    config: Optional[dict] = Field(None, alias="model_config")
    ic_mean: Optional[float] = None
    ic_ir: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

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

    model_config = ConfigDict(from_attributes=True)

class ModelConfigOut(ModelConfigBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

class ModelFactorWeightOut(ModelFactorWeightBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ModelFactorWeight(ModelFactorWeightOut):
    pass

class ModelScoreBase(BaseModel):
    model_id: int
    security_id: str
    score: Optional[float] = None
    rank: Optional[int] = None
    quantile: Optional[float] = None
    is_selected: Optional[bool] = False
    factor_contributions: Optional[dict] = None
    trade_date: date

class ModelScoreCreate(ModelScoreBase):
    pass

class ModelScoreInDB(ModelScoreBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ModelScoreOut(ModelScoreBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ModelScore(ModelScoreOut):
    pass

class ModelPerformanceBase(BaseModel):
    model_id: int
    trade_date: date
    daily_return: Optional[float] = None
    cumulative_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    ic: Optional[float] = None
    rank_ic: Optional[float] = None
    turnover: Optional[float] = None
    num_selected: Optional[int] = None

class ModelPerformanceOut(ModelPerformanceBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
