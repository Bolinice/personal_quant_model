from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, JSON, Text, Index
from sqlalchemy.sql import func
from app.db.base import Base


class Product(Base):
    """策略产品表"""
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_prod_model", "model_id"),
        Index("ix_prod_status", "status"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    model_id: int = Column(Integer, index=True)
    product_code: str = Column(String(100), unique=True, index=True, nullable=False)
    product_name: str = Column(String(100), nullable=False)
    product_type: str = Column(String(20))  # signal, report, api
    display_name: str = Column(String(100))
    description: Text = Column(Text)
    risk_disclosure: Text = Column(Text)  # 风险揭示
    risk_level: str = Column(String(20))  # low, medium, high
    status: str = Column(String(20), default="draft")  # draft, online, offline
    is_active: bool = Column(Boolean, default=True)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Product(id={self.id}, product_code='{self.product_code}', product_name='{self.product_name}')>"


class ProductReport(Base):
    """产品报告表"""
    __tablename__ = "product_reports"
    __table_args__ = (
        Index("ix_pr_product", "product_id"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    product_id: int = Column(Integer, index=True, nullable=False)
    report_type: str = Column(String(20))  # weekly, monthly, rebalance
    report_date: Date = Column(Date)
    title: str = Column(String(200))
    file_path: str = Column(String(255))
    meta_json: JSON = Column(JSON)
    created_at: DateTime = Column(DateTime, server_default=func.now())


class SubscriptionPlan(Base):
    """订阅套餐表"""
    __tablename__ = "subscription_plans"

    id: int = Column(Integer, primary_key=True, index=True)
    plan_name: str = Column(String(100), nullable=False)
    plan_type: str = Column(String(20))  # month, quarter, year
    price: float = Column(Float)
    duration_days: int = Column(Integer)
    features: JSON = Column(JSON)
    is_active: bool = Column(Boolean, default=True)
    created_at: DateTime = Column(DateTime, server_default=func.now())