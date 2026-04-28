from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class StockIndustry(Base):
    """股票行业分类表"""

    __tablename__ = "stock_industry"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(20), index=True)
    industry_name = Column(String(50))
    industry_code = Column(String(20))
    level = Column(String(10))  # L1, L2, L3
    standard = Column(String(20))  # sw(申万), zjh(证监会), cs(中信)
    created_at = Column(DateTime, server_default=func.now())


class IndustryClassification(Base):
    """行业分类表"""

    __tablename__ = "industry_classification"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(20), index=True)
    industry_name = Column(String(50))
    industry_code = Column(String(20))
    level = Column(String(10))  # L1, L2, L3
    standard = Column(String(20))  # sw(申万), zjh(证监会), cs(中信)
    created_at = Column(DateTime, server_default=func.now())
