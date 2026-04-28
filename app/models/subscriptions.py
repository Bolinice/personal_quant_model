from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Index, Integer, String
from sqlalchemy.sql import func

from app.db.base_class import Base


class Subscription(Base):
    """订阅表"""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_sub_user", "user_id"),
        Index("ix_sub_product", "product_id"),
        Index("ix_sub_status", "status"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, index=True, nullable=False)
    product_id: int = Column(Integer, index=True, nullable=True)
    plan_id: int = Column(Integer)
    plan_type: str = Column(String(20))  # month, quarter, year
    start_date: Date = Column(Date)
    end_date: Date = Column(Date)
    status: str = Column(String(20), default="active")  # active, expired, cancelled
    auto_renew: bool = Column(Boolean, default=True)
    payment_method: str = Column(String(50))
    payment_status: str = Column(String(20))  # pending, paid, failed, cancelled
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, product_id={self.product_id})>"


class SubscriptionHistory(Base):
    """订阅历史表"""

    __tablename__ = "subscription_histories"

    id: int = Column(Integer, primary_key=True, index=True)
    subscription_id: int = Column(Integer, index=True, nullable=False)
    action: str = Column(String(20))  # create, renew, cancel, upgrade
    details: JSON = Column(JSON)
    created_at: DateTime = Column(DateTime, server_default=func.now())


class SubscriptionPermission(Base):
    """订阅权限表"""

    __tablename__ = "subscription_permissions"

    id: int = Column(Integer, primary_key=True, index=True)
    subscription_id: int = Column(Integer, index=True, nullable=False)
    permission_type: str = Column(String(50))  # read_report, access_api, full_access
    is_granted: bool = Column(Boolean, default=True)
    created_at: DateTime = Column(DateTime, server_default=func.now())
