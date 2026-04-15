from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

class FactorBase(BaseModel):
    factor_code: str
    factor_name: str
    category: str
    direction: str = "desc"
    calc_expression: str
    description: Optional[str] = None
    is_active: bool = True

class FactorCreate(FactorBase):
    pass

class FactorUpdate(BaseModel):
    factor_name: Optional[str] = None
    category: Optional[str] = None
    direction: Optional[str] = None
    calc_expression: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class FactorInDB(FactorBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class FactorOut(FactorBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class FactorValueBase(BaseModel):
    factor_id: int
    trade_date: date
    security_id: int
    value: float
    is_valid: bool = True

class FactorValueCreate(FactorValueBase):
    pass

class FactorValueInDB(FactorValueBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class FactorValueOut(FactorValueBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class FactorAnalysisBase(BaseModel):
    factor_id: int
    analysis_date: date
    ic: float
    rank_ic: float
    mean: float
    std: float
    quantile_25: float
    quantile_50: float
    quantile_75: float
    coverage: float

class FactorAnalysisCreate(FactorAnalysisBase):
    pass

class FactorAnalysisInDB(FactorAnalysisBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class FactorAnalysisOut(FactorAnalysisBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True
