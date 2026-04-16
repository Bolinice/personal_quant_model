from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class TradingCalendar(Base):
    __tablename__ = "trading_calendar"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(10))
    cal_date = Column(Date, index=True)
    is_open = Column(Boolean, default=True)
    pretrade_date = Column(Date)

    def __repr__(self):
        return f"<TradingCalendar(exchange='{self.exchange}', cal_date='{self.cal_date}', is_open={self.is_open})>"