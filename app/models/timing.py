from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from app.db.base import Base


class TimingModel(Base):
    """择时模型定义表"""
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
