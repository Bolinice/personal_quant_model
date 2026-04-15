from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class Security(Base):
    __tablename__ = "securities"
    
    id = Column(Integer, primary_key=True, index=True)
    ts_code = Column(String(20), unique=True, index=True)
    symbol = Column(String(10), index=True)
    name = Column(String(100))
    board = Column(String(20))  # main,创业板,科创板
    industry_name = Column(String(100))
    list_date = Column(DateTime)
    status = Column(String(20))  # listed, delisted
    is_st = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Security(id={self.id}, ts_code='{self.ts_code}', name='{self.name}')>"
