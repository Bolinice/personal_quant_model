from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, Field, ConfigDict
from typing import Optional, Dict, Any, List

class FilterConfig(BaseModel):
    exclude_st: bool = True
    exclude_suspended: bool = True
    exclude_new_stock_days: int = 120
    min_avg_amount: float = 50000000
    min_market_cap: Optional[float] = None
    max_market_cap: Optional[float] = None
    industry_whitelist: Optional[List[str]] = None
    industry_blacklist: Optional[List[str]] = None
    board_whitelist: Optional[List[str]] = None
    board_blacklist: Optional[List[str]] = None

class StockPoolBase(BaseModel):
    pool_code: str
    pool_name: str
    base_index_code: Optional[str] = None
    filter_config: Optional[Dict[str, Any]] = None
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
    securities: List[str]
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