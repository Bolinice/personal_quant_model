from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator


class FactorBase(BaseModel):
    factor_code: str
    factor_name: str
    category: str
    direction: str = "desc"
    calc_expression: str
    description: str | None = None
    is_active: bool = True

    @field_validator("direction", mode="before")
    @classmethod
    def normalize_direction(cls, v: int | str) -> str:
        if isinstance(v, int):
            return "desc" if v == 1 else "asc"
        return v


class FactorCreate(FactorBase):
    pass


class FactorUpdate(BaseModel):
    factor_name: str | None = None
    category: str | None = None
    direction: str | None = None
    calc_expression: str | None = None
    description: str | None = None
    is_active: bool | None = None


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
    analysis_type: str | None = "ic_analysis"
    ic: float | None = None
    rank_ic: float | None = None
    mean: float | None = None
    std: float | None = None
    quantile_25: float | None = None
    quantile_50: float | None = None
    quantile_75: float | None = None
    coverage: float | None = None
    ic_decay: list[float] | None = None
    group_returns: list[float] | None = None
    long_short_return: float | None = None
    correlation: float | None = None
    compare_factor_id: int | None = None


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
