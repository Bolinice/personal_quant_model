from sqlalchemy import Column, Integer, String, DateTime, Float, Numeric, Boolean, JSON
from sqlalchemy.sql import func
from app.db.base import Base

class StockDaily(Base):
    __tablename__ = "stock_daily"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(20), index=True)
    trade_date = Column(DateTime, index=True)
    open = Column(Numeric(20, 4))
    high = Column(Numeric(20, 4))
    low = Column(Numeric(20, 4))
    close = Column(Numeric(20, 4))
    pre_close = Column(Numeric(20, 4))
    change = Column(Numeric(20, 4))
    pct_chg = Column(Numeric(20, 4))
    vol = Column(Numeric(20, 4))
    amount = Column(Numeric(20, 4))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<StockDaily(ts_code='{self.ts_code}', trade_date='{self.trade_date}', close={self.close})>"

class IndexDaily(Base):
    __tablename__ = "index_daily"

    id = Column(Integer, primary_key=True, index=True)
    index_code = Column(String(20), index=True)
    trade_date = Column(DateTime, index=True)
    open = Column(Numeric(20, 4))
    high = Column(Numeric(20, 4))
    low = Column(Numeric(20, 4))
    close = Column(Numeric(20, 4))
    pre_close = Column(Numeric(20, 4))
    change = Column(Numeric(20, 4))
    pct_chg = Column(Numeric(20, 4))
    vol = Column(Numeric(20, 4))
    amount = Column(Numeric(20, 4))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<IndexDaily(index_code='{self.index_code}', trade_date='{self.trade_date}', close={self.close})>"

class TradingCalendar(Base):
    __tablename__ = "trading_calendar"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(10), index=True)
    cal_date = Column(DateTime, index=True)
    is_open = Column(Boolean, default=True)
    pretrade_date = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<TradingCalendar(cal_date='{self.cal_date}', is_open={self.is_open})>"

class StockFinancial(Base):
    __tablename__ = "stock_financial"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(20), index=True)
    ann_date = Column(DateTime, index=True)
    end_date = Column(DateTime, index=True)
    report_type = Column(String(20))  # 年报、半年报、季报
    update_flag = Column(String(10))
    revenue = Column(Numeric(20, 4))
    yoy_revenue = Column(Numeric(20, 4))
    net_profit = Column(Numeric(20, 4))
    yoy_net_profit = Column(Numeric(20, 4))
    gross_profit = Column(Numeric(20, 4))
    gross_profit_margin = Column(Numeric(20, 4))
    roe = Column(Numeric(20, 4))
    roa = Column(Numeric(20, 4))
    eps = Column(Numeric(20, 4))
    bvps = Column(Numeric(20, 4))
    net_profit_ratio = Column(Numeric(20, 4))
    current_ratio = Column(Numeric(20, 4))
    quick_ratio = Column(Numeric(20, 4))
    cash_ratio = Column(Numeric(20, 4))
    asset_liability_ratio = Column(Numeric(20, 4))
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<StockFinancial(ts_code='{self.ts_code}', ann_date='{self.ann_date}', revenue={self.revenue})>"

class StockIndustry(Base):
    __tablename__ = "stock_industry"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(20), index=True)
    trade_date = Column(DateTime, index=True)
    industry_code = Column(String(20))
    industry_name = Column(String(100))
    level = Column(Integer)  # 1: 一级行业, 2: 二级行业, 3: 三级行业
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<StockIndustry(ts_code='{self.ts_code}', industry_name='{self.industry_name}'>"

class StockBasic(Base):
    __tablename__ = "stock_basic"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(20), index=True)
    symbol = Column(String(20))
    name = Column(String(100))
    area = Column(String(20))
    industry = Column(String(100))
    fullname = Column(String(100))
    enname = Column(String(100))
    market = Column(String(20))
    exchange = Column(String(20))
    curr_type = Column(String(20))
    list_status = Column(String(10))
    list_date = Column(DateTime)
    delist_date = Column(DateTime)
    is_hs = Column(Boolean)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<StockBasic(ts_code='{self.ts_code}', name='{self.name}'>"