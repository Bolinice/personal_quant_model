from sqlalchemy import Column, Date, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.base_class import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(16), unique=True, index=True)
    symbol = Column(String(16))
    name = Column(String(50))
    area = Column(String(20))
    industry = Column(String(50))  # 行业
    industry_sw = Column(String(50))  # 申万行业分类
    industry_zjh = Column(String(50))  # 证监会行业分类
    fullname = Column(String(100))
    enname = Column(String(100))
    market = Column(String(10))
    exchange = Column(String(10))
    curr_type = Column(String(10))
    list_status = Column(String(10))
    list_date = Column(Date)
    delist_date = Column(Date)
    is_hs = Column(String(5))  # 是否沪深港通标的
    status = Column(String(10), default="L")  # L上市 D退市 P暂停
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<StockBasic(ts_code='{self.ts_code}', name='{self.name}', list_date='{self.list_date}')>"
