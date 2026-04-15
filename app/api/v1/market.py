from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.services.market_service import get_stock_daily, get_index_daily, get_trading_calendar, create_stock_daily, create_index_daily, create_trading_calendar, get_stock_financial, get_stock_industry, get_stock_basic, create_stock_financial, create_stock_industry, create_stock_basic
from app.models.market import StockDaily, IndexDaily, TradingCalendar, StockFinancial, StockIndustry, StockBasic
from app.schemas.market import StockDailyCreate, IndexDailyCreate, TradingCalendarCreate, StockDailyOut, IndexDailyOut, TradingCalendarOut, StockFinancialCreate, StockFinancialOut, StockIndustryCreate, StockIndustryOut, StockBasicCreate, StockBasicOut

router = APIRouter()

@router.get("/stock-daily", response_model=list[StockDailyOut])
def read_stock_daily(ts_code: str, start_date: str, end_date: str, db: Session = Depends(SessionLocal)):
    stock_data = get_stock_daily(ts_code, start_date, end_date, db=db)
    if not stock_data:
        raise HTTPException(status_code=404, detail="Stock data not found")
    return stock_data

@router.get("/index-daily", response_model=list[IndexDailyOut])
def read_index_daily(index_code: str, start_date: str, end_date: str, db: Session = Depends(SessionLocal)):
    index_data = get_index_daily(index_code, start_date, end_date, db=db)
    if not index_data:
        raise HTTPException(status_code=404, detail="Index data not found")
    return index_data

@router.get("/trading-calendar", response_model=list[TradingCalendarOut])
def read_trading_calendar(exchange: str, start_date: str, end_date: str, is_open: bool = None, db: Session = Depends(SessionLocal)):
    calendar_data = get_trading_calendar(exchange, start_date, end_date, is_open, db=db)
    if not calendar_data:
        raise HTTPException(status_code=404, detail="Trading calendar not found")
    return calendar_data

@router.get("/stock-financial", response_model=list[StockFinancialOut])
def read_stock_financial(ts_code: str, start_date: str, end_date: str, report_type: str = None, db: Session = Depends(SessionLocal)):
    financial_data = get_stock_financial(ts_code, start_date, end_date, report_type, db=db)
    if not financial_data:
        raise HTTPException(status_code=404, detail="Financial data not found")
    return financial_data

@router.get("/stock-industry", response_model=list[StockIndustryOut])
def read_stock_industry(ts_code: str, trade_date: str, db: Session = Depends(SessionLocal)):
    industry_data = get_stock_industry(ts_code, trade_date, db=db)
    if not industry_data:
        raise HTTPException(status_code=404, detail="Industry data not found")
    return industry_data

@router.get("/stock-basic", response_model=StockBasicOut)
def read_stock_basic(ts_code: str, db: Session = Depends(SessionLocal)):
    basic_data = get_stock_basic(ts_code, db=db)
    if not basic_data:
        raise HTTPException(status_code=404, detail="Stock basic data not found")
    return basic_data

@router.post("/stock-daily", response_model=StockDailyOut)
def create_stock_daily_endpoint(stock_data: StockDailyCreate, db: Session = Depends(SessionLocal)):
    return create_stock_daily(stock_data, db=db)

@router.post("/index-daily", response_model=IndexDailyOut)
def create_index_daily_endpoint(index_data: IndexDailyCreate, db: Session = Depends(SessionLocal)):
    return create_index_daily(index_data, db=db)

@router.post("/trading-calendar", response_model=TradingCalendarOut)
def create_trading_calendar_endpoint(calendar_data: TradingCalendarCreate, db: Session = Depends(SessionLocal)):
    return create_trading_calendar(calendar_data, db=db)

@router.post("/stock-financial", response_model=StockFinancialOut)
def create_stock_financial_endpoint(financial_data: StockFinancialCreate, db: Session = Depends(SessionLocal)):
    return create_stock_financial(financial_data, db=db)

@router.post("/stock-industry", response_model=StockIndustryOut)
def create_stock_industry_endpoint(industry_data: StockIndustryCreate, db: Session = Depends(SessionLocal)):
    return create_stock_industry(industry_data, db=db)

@router.post("/stock-basic", response_model=StockBasicOut)
def create_stock_basic_endpoint(basic_data: StockBasicCreate, db: Session = Depends(SessionLocal)):
    return create_stock_basic(basic_data, db=db)
