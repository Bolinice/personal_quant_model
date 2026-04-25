"""实验注册表"""

from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.base import Base


class ExperimentRegistry(Base):
    """实验注册表 - AB实验与灰度发布"""
    __tablename__ = "experiment_registry"

    experiment_id = Column(String(100), primary_key=True, comment="实验ID")
    experiment_name = Column(String(200), nullable=False, comment="实验名称")
    snapshot_id = Column(String(50), comment="快照ID")
    config_version = Column(String(50), comment="配置版本")
    code_version = Column(String(50), comment="代码版本(Git commit)")
    result_summary = Column(Text, comment="结果摘要")
    status = Column(String(20), default="pending", comment="状态: pending/running/completed/failed")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        {"comment": "实验注册表"},
    )