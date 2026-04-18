from datetime import datetime, date
from pydantic import BaseModel, ConfigDict
from typing import Optional, List

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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FactorOut(FactorBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FactorValueOut(FactorValueBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FactorValue(FactorValueOut):
    pass

class FactorAnalysisBase(BaseModel):
    factor_id: int
    analysis_date: date
    analysis_type: Optional[str] = "ic_analysis"
    ic: Optional[float] = None
    rank_ic: Optional[float] = None
    mean: Optional[float] = None
    std: Optional[float] = None
    quantile_25: Optional[float] = None
    quantile_50: Optional[float] = None
    quantile_75: Optional[float] = None
    coverage: Optional[float] = None
    ic_decay: Optional[List[float]] = None
    group_returns: Optional[List[float]] = None
    long_short_return: Optional[float] = None
    correlation: Optional[float] = None
    compare_factor_id: Optional[int] = None

class FactorAnalysisCreate(FactorAnalysisBase):
    pass

class FactorAnalysisInDB(FactorAnalysisBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FactorAnalysisOut(FactorAnalysisBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

class FactorResultOut(FactorResultBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FactorResult(FactorResultOut):
    pass