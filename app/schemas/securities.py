"""证券管理 Pydantic 模型。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class SecurityBase(BaseModel):
    ts_code: str
    symbol: str
    name: str
    board: str | None = None
    industry_name: str | None = None
    list_date: date | None = None
    status: str = "listed"
    is_st: bool = False


class SecurityCreate(SecurityBase):
    pass


class SecurityUpdate(BaseModel):
    name: str | None = None
    industry_name: str | None = None
    status: str | None = None
    is_st: bool | None = None


class SecurityInDB(SecurityBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityOut(SecurityBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Security(SecurityOut):
    pass