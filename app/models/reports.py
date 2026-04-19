from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, JSON, Text, Index
from sqlalchemy.sql import func
from app.db.base import Base


class Report(Base):
    """报告表"""
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_rpt_type", "report_type"),
        Index("ix_rpt_date", "report_date"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    title: str = Column(String(200), nullable=False)
    report_type: str = Column(String(20), nullable=False)  # daily, weekly, monthly, rebalance, factor, backtest
    report_date: Date = Column(Date, index=True)
    model_id: int = Column(Integer, index=True)
    backtest_id: int = Column(Integer, index=True)
    content: Text = Column(Text)  # 报告内容(HTML/Markdown)
    summary: Text = Column(Text)  # 摘要
    file_path: str = Column(String(255))  # 文件路径
    file_format: str = Column(String(10))  # pdf, html, md
    status: str = Column(String(20), default="draft")  # draft, generated, published
    meta_json: JSON = Column(JSON)  # 元数据
    created_by: int = Column(Integer)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Report(id={self.id}, title='{self.title}', type='{self.report_type}')>"


class ReportTemplate(Base):
    """报告模板表"""
    __tablename__ = "report_templates"

    id: int = Column(Integer, primary_key=True, index=True)
    template_name: str = Column(String(100), nullable=False)
    report_type: str = Column(String(20), nullable=False)
    template_content: Text = Column(Text)  # Jinja2模板
    variables: JSON = Column(JSON)  # 变量定义
    is_default: bool = Column(Boolean, default=False)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ReportSchedule(Base):
    """报告调度表"""
    __tablename__ = "report_schedules"

    id: int = Column(Integer, primary_key=True, index=True)
    schedule_name: str = Column(String(100), nullable=False)
    report_template_id: int = Column(Integer, nullable=False)
    cron_expression: str = Column(String(100), nullable=False)
    is_active: bool = Column(Boolean, default=True)
    next_run_time: DateTime = Column(DateTime)
    meta_json: JSON = Column(JSON)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())