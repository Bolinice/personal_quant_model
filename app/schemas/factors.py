from datetime import datetime, date
from pydantic import BaseModel
from typing import Optional

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

class Factor(FactorOut):
    pass

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

class FactorValue(FactorValueOut):
    pass

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

class FactorAnalysis(FactorAnalysisOut):
    pass

class FactorResultBase(BaseModel):
    factor_id: int
    security_id: int
    trade_date: date
    score: float
    rank: int
    quantile: int
    is_selected: bool = False

class FactorResultCreate(FactorResultBase):
    pass

class FactorResultInDB(FactorResultBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class FactorResultOut(FactorResultBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class FactorResult(FactorResultOut):
    pass