from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class Factor(Base):
    __tablename__ = "factors"
    
    id = Column(Integer, primary_key=True, index=True)
    factor_code = Column(String(50), unique=True, index=True)
    factor_name = Column(String(100))
    category = Column(String(50))  # quality, valuation, momentum, growth, risk, liquidity
    direction = Column(String(10))  # asc, desc
    calc_expression = Column(String(500))
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Factor(id={self.id}, factor_code='{self.factor_code}', factor_name='{self.factor_name}')>"

class FactorValue(Base):
    __tablename__ = "factor_values"
    
    id = Column(Integer, primary_key=True, index=True)
    factor_id = Column(Integer, index=True)
    trade_date = Column(DateTime, index=True)
    security_id = Column(Integer, index=True)
    value = Column(Float)
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<FactorValue(factor_id={self.factor_id}, trade_date='{self.trade_date}', security_id={self.security_id}, value={self.value})>"

class FactorAnalysis(Base):
    __tablename__ = "factor_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    factor_id = Column(Integer, index=True)
    analysis_date = Column(DateTime, index=True)
    ic = Column(Float)
    rank_ic = Column(Float)
    mean = Column(Float)
    std = Column(Float)
    quantile_25 = Column(Float)
    quantile_50 = Column(Float)
    quantile_75 = Column(Float)
    coverage = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<FactorAnalysis(factor_id={self.factor_id}, analysis_date='{self.analysis_date}', ic={self.ic})>"
