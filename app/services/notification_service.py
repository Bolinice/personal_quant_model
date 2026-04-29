"""
通知服务
实现告警通知、组合调仓通知、报告生成通知
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.models.alert_logs import AlertLog, Notification

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class NotificationService:
    """通知服务"""

    def __init__(self, db: Session):
        self.db = db

    def create_notification(
        self, user_id: int, title: str, content: str, notification_type: str = "system", link: str | None = None
    ) -> Notification:
        """创建通知"""
        notification = Notification(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            link=link,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_unread_notifications(self, user_id: int, limit: int = 20) -> list[Notification]:
        """获取未读通知"""
        return (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.status == "unread",
            )
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )

    def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """标记为已读"""
        notification = (
            self.db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .first()
        )

        if not notification:
            return False

        notification.status = "read"
        notification.read_at = datetime.now(tz=UTC)
        self.db.commit()
        return True

    def mark_all_as_read(self, user_id: int) -> int:
        """全部标记为已读"""
        notifications = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.status == "unread",
            )
            .all()
        )

        count = 0
        for n in notifications:
            n.status = "read"
            n.read_at = datetime.now()
            count += 1

        self.db.commit()
        return count

    def send_alert_notification(self, alert: AlertLog, user_ids: list[int] | None = None) -> int:
        """发送告警通知"""
        if not user_ids:
            # 默认发送给所有管理员
            from app.models.user import User

            admins = (
                self.db.query(User)
                .filter(
                    User.role.in_(["admin", "risk_manager"]),
                    User.is_active,
                )
                .all()
            )
            user_ids = [u.id for u in admins]

        count = 0
        for user_id in user_ids:
            self.create_notification(
                user_id=user_id,
                title=f"[{alert.severity.upper()}] {alert.title}",
                content=alert.message or "",
                notification_type="alert",
            )
            count += 1

        return count

    def send_rebalance_notification(self, model_id: int, trade_date: str, user_ids: list[int]) -> int:
        """发送调仓通知"""
        count = 0
        for user_id in user_ids:
            self.create_notification(
                user_id=user_id,
                title=f"调仓信号 - {trade_date}",
                content=f"模型 {model_id} 在 {trade_date} 生成了新的调仓信号",
                notification_type="rebalance",
            )
            count += 1
        return count

    def send_report_notification(self, report_id: int, title: str, user_ids: list[int]) -> int:
        """发送报告通知"""
        count = 0
        for user_id in user_ids:
            self.create_notification(
                user_id=user_id,
                title=f"新报告: {title}",
                content="报告已生成",
                notification_type="report",
                link=f"/reports/{report_id}",
            )
            count += 1
        return count
