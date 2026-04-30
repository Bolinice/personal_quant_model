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


class StockDailyCreate(StockDailyBase):
    pass


class StockDailyInDB(StockDailyBase):
    id: int
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class StockDailyOut(StockDailyBase):
    id: int
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class IndexDailyBase(BaseModel):
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


class IndexDailyCreate(IndexDailyBase):
    pass


class IndexDailyInDB(IndexDailyBase):
    id: int
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class IndexDailyOut(IndexDailyBase):
    id: int
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)