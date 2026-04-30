from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.base_class import Base


class Security(Base):
    """证券表 — 应用层视图，核心数据源自 stock_basic"""
    __tablename__ = "securities"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(20), unique=True, index=True)
    symbol = Column(String(10), index=True)
    name = Column(String(100))
    board = Column(String(20))  # main,创业板,科创板
    industry_name = Column(String(100))
    list_date = Column(Date)  # 统一为Date类型，与stock_basic.list_date一致
    status = Column(String(20))  # listed, delisted
    is_st = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Security(id={self.id}, ts_code='{self.ts_code}', name='{self.name}')>"
