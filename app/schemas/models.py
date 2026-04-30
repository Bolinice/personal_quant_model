from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelBase(BaseModel):
    name: str
    description: str | None = None
    version: str | None = None
    factor_ids: list[int] | None = None
    is_active: bool = True


class ModelCreate(ModelBase):
    pass


class ModelUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    version: str | None = None
    factor_ids: list[int] | None = None
    is_active: bool | None = None


class ModelInDB(ModelBase):
    id: int
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelOut(ModelBase):
    id: int
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Model(ModelOut):
    pass


class ModelScoreBase(BaseModel):
    model_id: int
    security_id: str
    trade_date: str | None = None
    score: float | None = None
    rank: int | None = None
    quantile: int | None = None
    is_selected: bool = False
    factor_contributions: dict | None = None


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


class ModelFactorWeightBase(BaseModel):
    model_id: int
    factor_id: int
    weight: float = 1.0


class ModelFactorWeightCreate(ModelFactorWeightBase):
    pass


class ModelFactorWeightOut(ModelFactorWeightBase):
    id: int

    model_config = ConfigDict(from_attributes=True)