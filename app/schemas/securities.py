from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class SecurityBase(BaseModel):
    ts_code: str
    symbol: str
    name: str
    board: str
    industry_name: Optional[str] = None
    list_date: Optional[datetime] = None
    status: str = "listed"
    is_st: bool = False

class SecurityCreate(SecurityBase):
    pass

class SecurityUpdate(BaseModel):
    name: Optional[str] = None
    industry_name: Optional[str] = None
    status: Optional[str] = None
    is_st: Optional[bool] = None

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
