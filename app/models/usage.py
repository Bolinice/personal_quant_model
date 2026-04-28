"""
用量记录模型
- UsageRecord: 用户功能用量追踪
"""

from sqlalchemy import Column, Date, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base


class UsageRecord(Base):
    """用量记录表"""

    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("user_id", "permission_code", "usage_date", name="uq_usage_user_perm_date"),
        Index("ix_usage_user_date", "user_id", "usage_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    permission_code = Column(String(64), nullable=False, index=True, comment="权限编码，如 backtest_daily_1")
    usage_date = Column(Date, nullable=False, comment="使用日期")
    count = Column(Integer, default=0, comment="当日使用次数")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<UsageRecord(user_id={self.user_id}, perm={self.permission_code}, date={self.usage_date}, count={self.count})>"
