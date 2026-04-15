from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, index=True)
    product_code = Column(String(100), unique=True, index=True)
    product_name = Column(String(100))
    description = Column(String(500))
    risk_level = Column(String(20))  # low, medium, high
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Product(id={self.id}, product_code='{self.product_code}', product_name='{self.product_name}')>"

class ProductReport(Base):
    __tablename__ = "product_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, index=True)
    report_type = Column(String(20))  # weekly, monthly, backtest
    report_date = Column(DateTime)
    report_path = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<ProductReport(product_id={self.product_id}, report_type='{self.report_type}', report_date='{self.report_date}')>"

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    plan_name = Column(String(100))
    price = Column(Float)
    duration = Column(String(20))  # monthly, quarterly, yearly
    features = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<SubscriptionPlan(id={self.id}, plan_name='{self.plan_name}', price={self.price})>"

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    product_id = Column(Integer, index=True)
    plan_id = Column(Integer, index=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, product_id={self.product_id})>"
