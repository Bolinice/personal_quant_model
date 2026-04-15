from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    product_id = Column(Integer, index=True)
    plan_id = Column(Integer, index=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    is_active = Column(Boolean, default=True)
    auto_renew = Column(Boolean, default=True)
    payment_method = Column(String(50))
    payment_status = Column(String(20))  # pending, paid, failed, cancelled
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, product_id={self.product_id})>"

class SubscriptionHistory(Base):
    __tablename__ = "subscription_histories"
    
    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, index=True)
    action = Column(String(20))  # create, renew, cancel, upgrade
    details = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<SubscriptionHistory(subscription_id={self.subscription_id}, action='{self.action}')>"

class SubscriptionPermission(Base):
    __tablename__ = "subscription_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, index=True)
    permission_type = Column(String(50))  # read_report, access_api, full_access
    is_granted = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<SubscriptionPermission(subscription_id={self.subscription_id}, permission_type='{self.permission_type}')>"
