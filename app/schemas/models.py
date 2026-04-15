from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date

class TimingConfig(BaseModel):
    benchmark_code: str
    ma_window: int = 120
    below_ma_exposure: float = 0.5

class ConstraintConfig(BaseModel):
    single_stock_max_weight: float = 0.1
    industry_max_deviation: float = 0.05
    max_turnover: float = 0.3

class ModelBase(BaseModel):
    model_code: str
    model_name: str
    pool_id: int
    rebalance_frequency: str = "monthly"
    hold_count: int = 20
    weighting_method: str = "equal_weight"
    timing_enabled: bool = True
    timing_config: Optional[Dict[str, Any]] = None
    constraint_config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None

class ModelCreate(ModelBase):
    pass

class ModelUpdate(BaseModel):
    model_name: Optional[str] = None
    pool_id: Optional[int] = None
    rebalance_frequency: Optional[str] = None
    hold_count: Optional[int] = None
    weighting_method: Optional[str] = None
    timing_enabled: Optional[bool] = None
    timing_config: Optional[Dict[str, Any]] = None
    constraint_config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ModelInDB(ModelBase):
    id: int
    is_active: bool
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class ModelOut(ModelBase):
    id: int
    is_active: bool
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class ModelFactorWeightBase(BaseModel):
    model_id: int
    factor_id: int
    weight: float

class ModelFactorWeightCreate(ModelFactorWeightBase):
    pass

class ModelFactorWeightInDB(ModelFactorWeightBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class ModelFactorWeightOut(ModelFactorWeightBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class ModelScoreBase(BaseModel):
    model_id: int
    trade_date: date
    security_id: int
    total_score: float

class ModelScoreCreate(ModelScoreBase):
    pass

class ModelScoreInDB(ModelScoreBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class ModelScoreOut(ModelScoreBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True
