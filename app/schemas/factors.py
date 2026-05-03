from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator


class FactorBase(BaseModel):
    factor_code: str
    factor_name: str
    category: str
    sub_category: str | None = None
    direction: int = 1
    calc_expression: str | None = None
    formula_desc: str | None = None
    parameter_config: dict | None = None
    description: str | None = None
    is_active: bool = True

    @field_validator("direction", mode="before")
    @classmethod
    def normalize_direction(cls, v: int | str) -> int:
        if isinstance(v, str):
            return 1 if v == "desc" else -1
        return v


class FactorCreate(FactorBase):
    pass


class FactorUpdate(BaseModel):
    factor_name: str | None = None
    category: str | None = None
    sub_category: str | None = None
    direction: int | None = None
    calc_expression: str | None = None
    formula_desc: str | None = None
    parameter_config: dict | None = None
    description: str | None = None
    is_active: bool | None = None


class FactorInDB(FactorBase):
    id: int
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FactorOut(FactorBase):
    id: int
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Factor(FactorOut):
    pass


class FactorValueBase(BaseModel):
    factor_id: int
    trade_date: date
    security_id: str
    value: float | None = None
    raw_value: float | None = None
    processed_value: float | None = None
    neutralized_value: float | None = None
    zscore_value: float | None = None
    coverage_flag: bool | None = None
    run_id: str | None = None


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
    start_date: date | None = None
    end_date: date | None = None
    benchmark_code: str | None = None
    ic: float | None = None
    rank_ic: float | None = None
    ic_ir: float | None = None
    rank_ic_ir: float | None = None
    mean: float | None = None
    std: float | None = None
    quantile_25: float | None = None
    quantile_50: float | None = None
    quantile_75: float | None = None
    coverage: float | None = None
    long_short_return: float | None = None
    correlation: float | None = None
    result_json: dict | None = None
    report_path: str | None = None


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
    security_id: str
    trade_date: date
    score: float | None = None
    rank: int | None = None
    quantile: int | None = None
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


# 新增：因子计算请求和响应模型
class FactorCalculationRequest(BaseModel):
    """因子计算请求"""
    ts_codes: list[str]
    trade_date: str | date
    factor_groups: list[str] | None = None
    lookback_days: int = 252


class FactorCalculationResponse(BaseModel):
    """因子计算响应"""
    success: bool
    message: str
    data: list[dict]
    total_stocks: int
    total_factors: int


class FactorGroupResponse(BaseModel):
    """因子组响应"""
    group_key: str
    group_name: str
    factors: list[str]
    factor_count: int


class FactorListResponse(BaseModel):
    """因子列表响应"""
    total_factors: int
    total_groups: int
    factors: list[dict]