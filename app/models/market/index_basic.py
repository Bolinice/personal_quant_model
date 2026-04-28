from sqlalchemy import Column, Date, DateTime, Float, Integer, String
from sqlalchemy.sql import func

from app.db.base_class import Base


class IndexBasic(Base):
    """指数基础信息表"""

    __tablename__ = "index_basic"

    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(20), unique=True, nullable=False)
    name = Column(String(50))
    market = Column(String(20))
    publisher = Column(String(50))
    category = Column(String(20))
    base_date = Column(Date)
    base_point = Column(Float)
    list_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
