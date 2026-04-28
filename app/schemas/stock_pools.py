from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class FilterConfig(BaseModel):
    exclude_st: bool = True
    exclude_suspended: bool = True
    exclude_new_stock_days: int = 120
    min_avg_amount: float = 50000000
    min_market_cap: float | None = None
    max_market_cap: float | None = None
    industry_whitelist: list[str] | None = None
    industry_blacklist: list[str] | None = None
    board_whitelist: list[str] | None = None
    board_blacklist: list[str] | None = None


class StockPoolBase(BaseModel):
    pool_code: str
    pool_name: str
    base_index_code: str | None = None
    filter_config: dict[str, Any] | None = None
    description: str | None = None


class StockPoolCreate(StockPoolBase):
    pass


class StockPoolUpdate(BaseModel):
    pool_name: str | None = None
    base_index_code: str | None = None
    filter_config: dict[str, Any] | None = None
    description: str | None = None
    is_active: bool | None = None


class StockPoolInDB(StockPoolBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockPoolOut(StockPoolBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockPool(StockPoolOut):
    pass


class StockPoolSnapshotBase(BaseModel):
    pool_id: int
    trade_date: date
    securities: list[str]
    eligible_count: int


class StockPoolSnapshotCreate(StockPoolSnapshotBase):
    pass


class StockPoolSnapshotInDB(StockPoolSnapshotBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StockPoolSnapshotOut(StockPoolSnapshotBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
