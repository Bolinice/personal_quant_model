from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from app.core.pit_guard import pit_filter_query
from app.db.base import with_db
from app.models.market import IndexDaily, StockBasic, StockDaily, StockFinancial, StockIndustry, TradingCalendar

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.schemas.market import IndexDailyCreate, StockDailyCreate


def _parse_date(date_str: str) -> date:
    """Parse date string in various formats to date"""
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=UTC).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


@with_db
def get_stock_daily(ts_code: str, start_date: str, end_date: str, db: Session = None):
    return (
        db.query(StockDaily)
        .filter(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= _parse_date(start_date),
            StockDaily.trade_date <= _parse_date(end_date),
        )
        .all()
    )


@with_db
def get_index_daily(index_code: str, start_date: str, end_date: str, db: Session = None):
    return (
        db.query(IndexDaily)
        .filter(
            IndexDaily.index_code == index_code,
            IndexDaily.trade_date >= _parse_date(start_date),
            IndexDaily.trade_date <= _parse_date(end_date),
        )
        .all()
    )


@with_db
def get_trading_calendar(
    exchange: str, start_date: str, end_date: str, is_open: bool | None = None, db: Session | None = None
):
    query = db.query(TradingCalendar).filter(
        TradingCalendar.exchange == exchange,
        TradingCalendar.cal_date >= _parse_date(start_date),
        TradingCalendar.cal_date <= _parse_date(end_date),
    )
    if is_open is not None:
        query = query.filter(TradingCalendar.is_open == is_open)
    return query.all()


@with_db
def create_stock_daily(stock_data: StockDailyCreate, db: Session = None):
    db_stock = StockDaily(**stock_data.model_dump())
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock


@with_db
def create_index_daily(index_data: IndexDailyCreate, db: Session = None):
    db_index = IndexDaily(**index_data.model_dump())
    db.add(db_index)
    db.commit()
    db.refresh(db_index)
    return db_index


@with_db
def create_trading_calendar(calendar_data, db: Session = None):
    db_calendar = TradingCalendar(**calendar_data.model_dump())
    db.add(db_calendar)
    db.commit()
    db.refresh(db_calendar)
    return db_calendar


@with_db
def get_stock_financial(ts_code: str, end_date: str, report_type: str | None = None, db: Session | None = None):
    """获取财务数据，PIT Guard 自动过滤 ann_date <= end_date"""
    query = db.query(StockFinancial).filter(
        StockFinancial.ts_code == ts_code,
    )
    # PIT Guard: 仅使用截至 end_date 已公告的财务数据，杜绝未来函数
    query = pit_filter_query(query, StockFinancial, _parse_date(end_date), db)
    return query.all()


@with_db
def get_stock_industry(ts_code: str, trade_date: str, db: Session = None):
    return (
        db.query(StockIndustry)
        .filter(StockIndustry.ts_code == ts_code, StockIndustry.trade_date == _parse_date(trade_date))
        .all()
    )


@with_db
def get_stock_basic(ts_code: str, db: Session = None):
    return db.query(StockBasic).filter(StockBasic.ts_code == ts_code).first()


@with_db
def create_stock_financial(financial_data, db: Session = None):
    db_financial = StockFinancial(**financial_data.model_dump())
    db.add(db_financial)
    db.commit()
    db.refresh(db_financial)
    return db_financial


@with_db
def create_stock_industry(industry_data, db: Session = None):
    db_industry = StockIndustry(**industry_data.model_dump())
    db.add(db_industry)
    db.commit()
    db.refresh(db_industry)
    return db_industry


@with_db
def create_stock_basic(basic_data, db: Session = None):
    db_basic = StockBasic(**basic_data.model_dump())
    db.add(db_basic)
    db.commit()
    db.refresh(db_basic)
    return db_basic
