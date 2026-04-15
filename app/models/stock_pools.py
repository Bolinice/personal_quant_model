from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class StockPool(Base):
    __tablename__ = "stock_pools"
    
    id = Column(Integer, primary_key=True, index=True)
    pool_code = Column(String(50), unique=True, index=True)
    pool_name = Column(String(100))
    base_index_code = Column(String(20))
    filter_config = Column(JSON)
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<StockPool(id={self.id}, pool_code='{self.pool_code}', pool_name='{self.pool_name}')>"

class StockPoolSnapshot(Base):
    __tablename__ = "stock_pool_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    pool_id = Column(Integer, index=True)
    trade_date = Column(DateTime, index=True)
    securities = Column(JSON)
    eligible_count = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<StockPoolSnapshot(pool_id={self.pool_id}, trade_date='{self.trade_date}', eligible_count={self.eligible_count})>"
