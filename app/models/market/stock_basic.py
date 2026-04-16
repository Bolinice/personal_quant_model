from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class StockBasic(Base):
    __tablename__ = "stock_basic"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(16), unique=True, index=True)
    symbol = Column(String(16))
    name = Column(String(50))
    area = Column(String(20))
    industry = Column(String(50))
    fullname = Column(String(100))
    enname = Column(String(100))
    market = Column(String(10))
    exchange = Column(String(10))
    curr_type = Column(String(10))
    list_status = Column(String(10))
    list_date = Column(Date)
    delist_date = Column(Date)
    is_hs = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<StockBasic(ts_code='{self.ts_code}', name='{self.name}', list_date='{self.list_date}')>"