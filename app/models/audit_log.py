"""
审计日志模型

使用哈希链技术确保日志的完整性和不可篡改性。
每条日志记录包含前一条记录的哈希值，形成不可断裂的链条。
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class AuditLog(Base):
    """审计日志模型"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    # 用户信息
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv6 最长 45 字符

    # 操作信息
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 请求信息
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)  # GET, POST, PUT, DELETE
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status_code: Mapped[int | None] = mapped_column(nullable=True)

    # 额外数据（JSON 格式）
    extra_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 哈希链字段
    previous_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # SHA-256 哈希值（64 字符）
    current_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )  # 当前记录的哈希值

    __table_args__ = (
        # 复合索引：按用户和时间查询
        Index("ix_audit_logs_user_time", "user_id", "created_at"),
        # 复合索引：按操作和时间查询
        Index("ix_audit_logs_action_time", "action", "created_at"),
        # 复合索引：按资源类型和时间查询
        Index("ix_audit_logs_resource_time", "resource_type", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action={self.action}, "
            f"user={self.username}, created_at={self.created_at})>"
        )
