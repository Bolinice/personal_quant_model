from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelBase(BaseModel):
    model_code: str
    model_name: str
    description: str | None = None
    model_type: str = "scoring"
    version: str = "1.0"
    status: str = "draft"


class ModelCreate(ModelBase):
    pass


class ModelUpdate(BaseModel):
    model_name: str | None = None
    description: str | None = None
    model_type: str | None = None
    version: str | None = None
    status: str | None = None


class ModelOut(ModelBase):
    id: int
    model_code: str | None = None
    factor_ids: list | None = None
    factor_weights: dict | None = None
    config: dict | None = Field(None, alias="model_config")
    ic_mean: float | None = None
    ic_ir: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ModelConfigBase(BaseModel):
    model_id: int
    config_name: str
    config_value: str
    description: str | None = None


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
    score: float | None = None
    rank: int | None = None
    quantile: float | None = None
    is_selected: bool | None = False
    factor_contributions: dict | None = None
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
    daily_return: float | None = None
    cumulative_return: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    ic: float | None = None
    rank_ic: float | None = None
    turnover: float | None = None
    num_selected: int | None = None


class ModelPerformanceOut(ModelPerformanceBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
