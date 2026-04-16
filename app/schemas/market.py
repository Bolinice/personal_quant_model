from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date

class StockDailyBase(BaseModel):
    ts_code: str
    trade_date: date
    open: float = Field(ge=0)
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    close: float = Field(ge=0)
    pre_close: float = Field(ge=0)
    change: float = Field(default=0)
    pct_chg: float = Field(default=0)
    vol: float = Field(ge=0)
    amount: float = Field(ge=0)

class StockDailyCreate(StockDailyBase):
    pass

class StockDailyUpdate(BaseModel):
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pre_close: Optional[float] = None
    change: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None

class StockDailyInDB(StockDailyBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class StockDailyOut(StockDailyBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class StockDaily(StockDailyOut):
    pass

class IndexDailyBase(BaseModel):
    index_code: str
    trade_date: date
    open: float = Field(ge=0)
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    close: float = Field(ge=0)
    pre_close: float = Field(ge=0)
    change: float = Field(default=0)
    pct_chg: float = Field(default=0)
    vol: float = Field(ge=0)
    amount: float = Field(ge=0)

class IndexDailyCreate(IndexDailyBase):
    pass

class IndexDailyUpdate(BaseModel):
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pre_close: Optional[float] = None
    change: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None

class IndexDailyInDB(IndexDailyBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class IndexDailyOut(IndexDailyBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class IndexDaily(IndexDailyOut):
    pass