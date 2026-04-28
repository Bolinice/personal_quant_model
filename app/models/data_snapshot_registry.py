"""数据快照注册表"""

from sqlalchemy import Column, Date, DateTime, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class DataSnapshotRegistry(Base):
    """数据快照注册表 - 每日数据版本管理"""

    __tablename__ = "data_snapshot_registry"

    snapshot_id = Column(String(100), primary_key=True, comment="快照ID")
    snapshot_date = Column(Date, nullable=False, index=True, comment="快照日期")
    description = Column(Text, comment="描述")
    source_version_json = Column(Text, comment="数据源版本JSON")
    code_version = Column(String(50), comment="代码版本(Git commit)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = ({"comment": "数据快照注册表"},)
