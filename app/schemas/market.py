from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date

class StockDailyBase(BaseModel):
    ts_code: str
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pre_close: Optional[float] = None
    change: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    data_source: Optional[str] = None
    amount_is_estimated: Optional[bool] = False

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
    data_source: Optional[str] = None
    amount_is_estimated: Optional[bool] = None

class StockDailyOut(StockDailyBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class IndexDailyBase(BaseModel):
    index_code: str
    trade_date: date
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pre_close: Optional[float] = None
    change: Optional[float] = None
    pct_chg: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    data_source: Optional[str] = None
    amount_is_estimated: Optional[bool] = False

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
    data_source: Optional[str] = None
    amount_is_estimated: Optional[bool] = None

class IndexDailyOut(IndexDailyBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
