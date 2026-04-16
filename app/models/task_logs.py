from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, JSON
from sqlalchemy.sql import func
from app.db.base import Base

class TaskLog(Base):
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String(50))  # data_import, factor_calculation, backtest, report_generation
    task_name = Column(String(200))
    status = Column(String(20))  # running, completed, failed, cancelled
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)
    progress = Column(Float, nullable=True)  # 0-100
    total_items = Column(Integer, nullable=True)
    completed_items = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    log_data = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<TaskLog(id={self.id}, task_type='{self.task_type}', status='{self.status}')>"