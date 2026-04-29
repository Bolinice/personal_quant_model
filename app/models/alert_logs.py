from sqlalchemy import JSON, Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base_class import Base


class AlertLog(Base):
    """告警日志表"""

    __tablename__ = "alert_logs"
    __table_args__ = (
        Index("ix_alert_rule", "rule_id"),
        Index("ix_alert_status", "status"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    rule_id: int = Column(Integer, index=True)
    alert_type: str = Column(String(50))  # risk, performance, data, system
    severity: str = Column(String(20))  # info, warning, critical
    title: str = Column(String(200), nullable=False)
    message: Text = Column(Text)
    status: str = Column(String(20), default="pending")  # pending, acknowledged, resolved
    acknowledged_by: int = Column(Integer)
    acknowledged_at: DateTime = Column(DateTime)
    resolved_at: DateTime = Column(DateTime)
    meta_json: JSON = Column(JSON)
    created_at: DateTime = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<AlertLog(id={self.id}, alert_type='{self.alert_type}', title='{self.title}')>"


class AlertRule(Base):
    """告警规则表"""

    __tablename__ = "alert_rules"
    __table_args__ = (Index("ix_ar_type", "alert_type"),)

    id: int = Column(Integer, primary_key=True, index=True)
    rule_name: str = Column(String(100), nullable=False)
    alert_type: str = Column(String(50))  # risk, performance, data, system
    severity: str = Column(String(20), default="warning")
    condition: JSON = Column(JSON, nullable=False)  # 触发条件
    notify_config: JSON = Column(JSON)  # 通知配置
    is_active: bool = Column(Boolean, default=True)
    cooldown_minutes: int = Column(Integer, default=60)  # 冷却时间
    last_triggered_at: DateTime = Column(DateTime)
    created_by: int = Column(Integer)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Notification(Base):
    """通知表"""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notif_user", "user_id"),
        Index("ix_notif_status", "status"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, index=True, nullable=False)
    title: str = Column(String(200), nullable=False)
    content: Text = Column(Text)
    notification_type: str = Column(String(30))  # system, alert, rebalance, report
    status: str = Column(String(20), default="unread")  # unread, read
    link: str = Column(String(255))
    created_at: DateTime = Column(DateTime, server_default=func.now())
    read_at: DateTime = Column(DateTime)
