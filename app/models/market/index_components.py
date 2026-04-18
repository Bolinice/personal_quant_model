from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Index
from sqlalchemy.sql import func
from app.db.base import Base


class IndexComponent(Base):
    """指数成分股历史表"""
    __tablename__ = "index_components"

    id = Column(Integer, primary_key=True, index=True)
    index_code = Column(String(20), nullable=False)
    trade_date = Column(Date, nullable=False)
    ts_code = Column(String(20), nullable=False)
    weight = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
