from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date

class FilterConfig(BaseModel):
    exclude_st: bool = True
    exclude_suspended: bool = True
    exclude_new_stock_days: int = 120
    min_avg_amount: float = 50000000
    min_market_cap: Optional[float] = None
    max_market_cap: Optional[float] = None
    industry_whitelist: Optional[list[str]] = None
    industry_blacklist: Optional[list[str]] = None
    board_whitelist: Optional[list[str]] = None
    board_blacklist: Optional[list[str]] = None

class StockPoolBase(BaseModel):
    pool_code: str
    pool_name: str
    base_index_code: str
    filter_config: Dict[str, Any] = Field(default_factory=lambda: {
        "exclude_st": True,
        "exclude_suspended": True,
        "exclude_new_stock_days": 120,
        "min_avg_amount": 50000000
    })
    description: Optional[str] = None

class StockPoolCreate(StockPoolBase):
    pass

class StockPoolUpdate(BaseModel):
    pool_name: Optional[str] = None
    base_index_code: Optional[str] = None
    filter_config: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class StockPoolInDB(StockPoolBase):
    id: int
    is_active: bool
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class StockPoolOut(StockPoolBase):
    id: int
    is_active: bool
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class StockPoolSnapshotBase(BaseModel):
    pool_id: int
    trade_date: date
    securities: list[str]
    eligible_count: int

class StockPoolSnapshotCreate(StockPoolSnapshotBase):
    pass

class StockPoolSnapshotInDB(StockPoolSnapshotBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class StockPoolSnapshotOut(StockPoolSnapshotBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True
