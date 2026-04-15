from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(50))  # risk, performance, system, data
    severity = Column(String(20))  # critical, high, medium, low
    title = Column(String(200))
    message = Column(Text)
    source = Column(String(100))
    status = Column(String(20))  # open, resolved, acknowledged
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)
    resolution = Column(Text, nullable=True)
    related_data = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<AlertLog(id={self.id}, alert_type='{self.alert_type}', severity='{self.severity}')>"