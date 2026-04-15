from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class Model(Base):
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    model_code = Column(String(100), unique=True, index=True)
    model_name = Column(String(100))
    pool_id = Column(Integer)
    rebalance_frequency = Column(String(20))  # daily, weekly, monthly
    hold_count = Column(Integer)
    weighting_method = Column(String(50))  # equal_weight, ic_weight, custom_weight
    timing_enabled = Column(Boolean, default=True)
    timing_config = Column(JSON)
    constraint_config = Column(JSON)
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Model(id={self.id}, model_code='{self.model_code}', model_name='{self.model_name}')>"

class ModelFactorWeight(Base):
    __tablename__ = "model_factor_weights"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, index=True)
    factor_id = Column(Integer, index=True)
    weight = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<ModelFactorWeight(model_id={self.model_id}, factor_id={self.factor_id}, weight={self.weight})>"

class ModelScore(Base):
    __tablename__ = "model_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, index=True)
    trade_date = Column(DateTime, index=True)
    security_id = Column(Integer, index=True)
    total_score = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<ModelScore(model_id={self.model_id}, trade_date='{self.trade_date}', security_id={self.security_id}, total_score={self.total_score})>"
