from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class TimingSignal(Base):
    __tablename__ = "timing_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, index=True)
    trade_date = Column(DateTime, index=True)
    signal_type = Column(String(20))  # long, short, neutral
    exposure = Column(Float)  # 仓位比例 0-1
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<TimingSignal(model_id={self.model_id}, trade_date='{self.trade_date}', signal_type='{self.signal_type}', exposure={self.exposure})>"

class TimingConfig(Base):
    __tablename__ = "timing_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, unique=True, index=True)
    config_type = Column(String(50))  # ma_timing, breadth_timing, volatility_timing
    config_params = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<TimingConfig(model_id={self.model_id}, config_type='{self.config_type}')>"

class TimingModel(Base):
    __tablename__ = "timing_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    description = Column(String(500))
    signal_type = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<TimingModel(id={self.id}, name='{self.name}', signal_type='{self.signal_type}')>"
