from sqlalchemy import Column, Integer, String, DateTime, Date
from sqlalchemy.sql import func
from app.db.base import Base

class StockIndustry(Base):
    __tablename__ = "stock_industry"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(16), index=True)
    trade_date = Column(Date, index=True)
    industry_code = Column(String(20))
    industry_name = Column(String(50))
    level = Column(Integer)

    def __repr__(self):
        return f"<StockIndustry(ts_code='{self.ts_code}', industry_name='{self.industry_name}', trade_date='{self.trade_date}')>"