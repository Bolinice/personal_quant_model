from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class Report(Base):
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String(50))  # strategy_report, performance_report, backtest_report
    report_date = Column(DateTime)
    report_data = Column(JSON)
    report_path = Column(String(255))
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<Report(id={self.id}, report_type='{self.report_type}', report_date='{self.report_date}')>"

class ReportTemplate(Base):
    __tablename__ = "report_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String(100))
    template_content = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ReportTemplate(id={self.id}, template_name='{self.template_name}')>"

class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String(50))
    frequency = Column(String(20))  # daily, weekly, monthly
    recipients = Column(JSON)
    is_active = Column(Boolean, default=True)
    next_run_time = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<ReportSchedule(id={self.id}, report_type='{self.report_type}', frequency='{self.frequency}')>"
