from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class StockDailyBase(BaseModel):
    ts_code: str
    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    pre_close: float | None = None
    change: float | None = None
    pct_chg: float | None = None
    vol: float | None = None
    amount: float | None = None
    data_source: str | None = None
    amount_is_estimated: bool | None = False


class StockDailyCreate(StockDailyBase):
    pass


class StockDailyUpdate(BaseModel):
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    pre_close: float | None = None
    change: float | None = None
    pct_chg: float | None = None
    vol: float | None = None
    amount: float | None = None
    data_source: str | None = None
    amount_is_estimated: bool | None = None


class StockDailyOut(StockDailyBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class IndexDailyBase(BaseModel):
    index_code: str
    trade_date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    pre_close: float | None = None
    change: float | None = None
    pct_chg: float | None = None
    vol: float | None = None
    amount: float | None = None
    data_source: str | None = None
    amount_is_estimated: bool | None = False


class IndexDailyCreate(IndexDailyBase):
    pass


class IndexDailyUpdate(BaseModel):
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    pre_close: float | None = None
    change: float | None = None
    pct_chg: float | None = None
    vol: float | None = None
    amount: float | None = None
    data_source: str | None = None
    amount_is_estimated: bool | None = None


class IndexDailyOut(IndexDailyBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
