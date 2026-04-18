from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, JSON, Text, Index
from sqlalchemy.sql import func
from app.db.base import Base


class TaskLog(Base):
    """任务运行表"""
    __tablename__ = "task_logs"
    __table_args__ = (
        Index("ix_tl_type", "task_type"),
        Index("ix_tl_status", "status"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    task_type: str = Column(String(50), nullable=False)  # data_sync, factor_calc, model_score, backtest, report
    task_name: str = Column(String(200), nullable=False)
    run_id: str = Column(String(50), unique=True, index=True)  # 运行ID
    status: str = Column(String(20), default="pending")  # pending, running, success, failed
    params_json: JSON = Column(JSON)  # 参数
    progress: float = Column(Float, default=0.0)  # 进度 0-100
    total_items: int = Column(Integer)
    completed_items: int = Column(Integer)
    started_at: DateTime = Column(DateTime)
    ended_at: DateTime = Column(DateTime)
    duration: float = Column(Float)  # 耗时(秒)
    error_message: Text = Column(Text)
    result_json: JSON = Column(JSON)  # 结果
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<TaskLog(id={self.id}, task_type='{self.task_type}', status='{self.status}')>"


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_al_user", "user_id"),
        Index("ix_al_action", "action"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, index=True)
    action: str = Column(String(50), nullable=False)  # create, update, delete, login, logout
    resource_type: str = Column(String(50))  # model, factor, backtest, portfolio
    resource_id: int = Column(Integer)
    detail_json: JSON = Column(JSON)
    ip_address: str = Column(String(50))
    created_at: DateTime = Column(DateTime, server_default=func.now())