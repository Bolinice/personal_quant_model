from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.market import StockDaily

def get_next_trading_date(trade_date: str) -> datetime:
    """获取下一个交易日（简化版本）"""
    # 这是一个简化版本，实际应该查询交易日历表
    date_obj = datetime.strptime(trade_date, "%Y-%m-%d")
    next_day = date_obj + timedelta(days=1)

    # 跳过周末（简化处理）
    while next_day.weekday() >= 5:  # 5=周六, 6=周日
        next_day += timedelta(days=1)

    return next_day

def get_trading_date_after(trade_date: str, days: int) -> datetime:
    """获取指定天数后的交易日（简化版本）"""
    current_date = datetime.strptime(trade_date, "%Y-%m-%d")
    target_date = current_date + timedelta(days=days)

    # 跳过周末（简化处理）
    while target_date.weekday() >= 5:
        target_date += timedelta(days=1)

    return target_date

def get_trading_calendar(exchange: str, start_date: str, end_date: str, db: Session = None):
    """获取交易日历"""
    if db is None:
        db = SessionLocal()
        try:
            from app.models.market import TradingCalendar
            return db.query(TradingCalendar).filter(
                TradingCalendar.exchange == exchange,
                TradingCalendar.cal_date >= start_date,
                TradingCalendar.cal_date <= end_date
            ).all()
        finally:
            db.close()

    from app.models.market import TradingCalendar
    return db.query(TradingCalendar).filter(
        TradingCalendar.exchange == exchange,
        TradingCalendar.cal_date >= start_date,
        TradingCalendar.cal_date <= end_date
    ).all()

def get_stock_price(security_id: str, current_date: datetime, db: Session):
    """获取股票价格"""
    stock_data = db.query(StockDaily).filter(
        StockDaily.ts_code == security_id,
        StockDaily.trade_date == current_date
    ).first()
    return stock_data.close if stock_data else None
