from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.market import StockDaily, IndexDaily, TradingCalendar, StockFinancial, StockIndustry, StockBasic
from app.schemas.market import StockDailyCreate, IndexDailyCreate, TradingCalendarCreate, StockFinancialCreate, StockIndustryCreate, StockBasicCreate

def get_stock_daily(ts_code: str, start_date: str, end_date: str, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(StockDaily).filter(
                StockDaily.ts_code == ts_code,
                StockDaily.trade_date >= start_date,
                StockDaily.trade_date <= end_date
            ).all()
        finally:
            db.close()
    return db.query(StockDaily).filter(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date >= start_date,
        StockDaily.trade_date <= end_date
    ).all()

def get_index_daily(index_code: str, start_date: str, end_date: str, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(IndexDaily).filter(
                IndexDaily.index_code == index_code,
                IndexDaily.trade_date >= start_date,
                IndexDaily.trade_date <= end_date
            ).all()
        finally:
            db.close()
    return db.query(IndexDaily).filter(
        IndexDaily.index_code == index_code,
        IndexDaily.trade_date >= start_date,
        IndexDaily.trade_date <= end_date
    ).all()

def get_trading_calendar(exchange: str, start_date: str, end_date: str, is_open: bool = None, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            query = db.query(TradingCalendar).filter(
                TradingCalendar.exchange == exchange,
                TradingCalendar.cal_date >= start_date,
                TradingCalendar.cal_date <= end_date
            )
            if is_open is not None:
                query = query.filter(TradingCalendar.is_open == is_open)
            return query.all()
        finally:
            db.close()
    query = db.query(TradingCalendar).filter(
        TradingCalendar.exchange == exchange,
        TradingCalendar.cal_date >= start_date,
        TradingCalendar.cal_date <= end_date
    )
    if is_open is not None:
        query = query.filter(TradingCalendar.is_open == is_open)
    return query.all()

def create_stock_daily(stock_data: StockDailyCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_stock = StockDaily(**stock_data.dict())
            db.add(db_stock)
            db.commit()
            db.refresh(db_stock)
            return db_stock
        finally:
            db.close()
    db_stock = StockDaily(**stock_data.dict())
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock

def create_index_daily(index_data: IndexDailyCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_index = IndexDaily(**index_data.dict())
            db.add(db_index)
            db.commit()
            db.refresh(db_index)
            return db_index
        finally:
            db.close()
    db_index = IndexDaily(**index_data.dict())
    db.add(db_index)
    db.commit()
    db.refresh(db_index)
    return db_index

def create_trading_calendar(calendar_data: TradingCalendarCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_calendar = TradingCalendar(**calendar_data.dict())
            db.add(db_calendar)
            db.commit()
            db.refresh(db_calendar)
            return db_calendar
        finally:
            db.close()
    db_calendar = TradingCalendar(**calendar_data.dict())
    db.add(db_calendar)
    db.commit()
    db.refresh(db_calendar)
    return db_calendar

def get_stock_financial(ts_code: str, start_date: str, end_date: str, report_type: str = None, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            query = db.query(StockFinancial).filter(
                StockFinancial.ts_code == ts_code,
                StockFinancial.ann_date >= start_date,
                StockFinancial.ann_date <= end_date
            )
            if report_type:
                query = query.filter(StockFinancial.report_type == report_type)
            return query.all()
        finally:
            db.close()
    query = db.query(StockFinancial).filter(
        StockFinancial.ts_code == ts_code,
        StockFinancial.ann_date >= start_date,
        StockFinancial.ann_date <= end_date
    )
    if report_type:
        query = query.filter(StockFinancial.report_type == report_type)
    return query.all()

def get_stock_industry(ts_code: str, trade_date: str, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(StockIndustry).filter(
                StockIndustry.ts_code == ts_code,
                StockIndustry.trade_date == trade_date
            ).all()
        finally:
            db.close()
    return db.query(StockIndustry).filter(
        StockIndustry.ts_code == ts_code,
        StockIndustry.trade_date == trade_date
    ).all()

def get_stock_basic(ts_code: str, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(StockBasic).filter(StockBasic.ts_code == ts_code).first()
        finally:
            db.close()
    return db.query(StockBasic).filter(StockBasic.ts_code == ts_code).first()

def create_stock_financial(financial_data: StockFinancialCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_financial = StockFinancial(**financial_data.dict())
            db.add(db_financial)
            db.commit()
            db.refresh(db_financial)
            return db_financial
        finally:
            db.close()
    db_financial = StockFinancial(**financial_data.dict())
    db.add(db_financial)
    db.commit()
    db.refresh(db_financial)
    return db_financial

def create_stock_industry(industry_data: StockIndustryCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_industry = StockIndustry(**industry_data.dict())
            db.add(db_industry)
            db.commit()
            db.refresh(db_industry)
            return db_industry
        finally:
            db.close()
    db_industry = StockIndustry(**industry_data.dict())
    db.add(db_industry)
    db.commit()
    db.refresh(db_industry)
    return db_industry

def create_stock_basic(basic_data: StockBasicCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_basic = StockBasic(**basic_data.dict())
            db.add(db_basic)
            db.commit()
            db.refresh(db_basic)
            return db_basic
        finally:
            db.close()
    db_basic = StockBasic(**basic_data.dict())
    db.add(db_basic)
    db.commit()
    db.refresh(db_basic)
    return db_basic
