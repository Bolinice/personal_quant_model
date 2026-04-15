from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

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

class TradingCalendarBase(BaseModel):
    exchange: str
    cal_date: date
    is_open: bool = True
    pretrade_date: Optional[date] = None

class TradingCalendarCreate(TradingCalendarBase):
    pass

class TradingCalendarUpdate(BaseModel):
    exchange: Optional[str] = None
    is_open: Optional[bool] = None
    pretrade_date: Optional[date] = None

class TradingCalendarInDB(TradingCalendarBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class TradingCalendarOut(TradingCalendarBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class StockFinancialBase(BaseModel):
    ts_code: str
    ann_date: date
    end_date: date
    report_type: str
    update_flag: str
    revenue: Optional[float] = None
    yoy_revenue: Optional[float] = None
    net_profit: Optional[float] = None
    yoy_net_profit: Optional[float] = None
    gross_profit: Optional[float] = None
    gross_profit_margin: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    eps: Optional[float] = None
    bvps: Optional[float] = None
    net_profit_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    cash_ratio: Optional[float] = None
    asset_liability_ratio: Optional[float] = None

class StockFinancialCreate(StockFinancialBase):
    pass

class StockFinancialOut(StockFinancialBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class StockIndustryBase(BaseModel):
    ts_code: str
    trade_date: date
    industry_code: str
    industry_name: str
    level: int

class StockIndustryCreate(StockIndustryBase):
    pass

class StockIndustryOut(StockIndustryBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class StockBasicBase(BaseModel):
    ts_code: str
    symbol: str
    name: str
    area: str
    industry: str
    fullname: str
    enname: str
    market: str
    exchange: str
    curr_type: str
    list_status: str
    list_date: Optional[date] = None
    delist_date: Optional[date] = None
    is_hs: bool

class StockBasicCreate(StockBasicBase):
    pass

class StockBasicOut(StockBasicBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True
