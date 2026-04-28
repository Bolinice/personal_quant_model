from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Float, Index, Integer, String, Text
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
    __table_args__ = (Index("ix_pr_product", "product_id"),)

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
    plan_type: str = Column(String(20))  # basic, advanced, professional, team, enterprise
    plan_tier: int = Column(Integer, default=0)  # 排序: 1=基础, 2=进阶, 3=专业, 4=团队, 5=机构

    # 价格
    price_monthly: float = Column(Float)  # 月付价格
    price_yearly: float = Column(Float)  # 年付价格
    price_unit: str = Column(String(20))  # 价格单位文案，如 "元/年起"
    custom_price: str = Column(String(100))  # 自定义价格文案

    # 权限范围
    stock_pools = Column(JSON)  # ["沪深300", "中证500"] 等
    frequencies = Column(JSON)  # ["Monthly", "Biweekly"] 等
    features = Column(JSON)  # 功能列表

    # 展示
    description: str = Column(Text)
    highlight: bool = Column(Boolean, default=False)  # 是否推荐
    buttons = Column(JSON)  # ["立即体验", "查看样例"]
    is_active: bool = Column(Boolean, default=True)

    # 兼容旧字段
    duration_days: int = Column(Integer)
    price: float = Column(Float)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PricingMatrix(Base):
    """单模型价格矩阵"""

    __tablename__ = "pricing_matrix"

    id: int = Column(Integer, primary_key=True, index=True)
    billing_cycle: str = Column(String(10))  # yearly / monthly
    pools = Column(JSON)  # ["沪深300", "中证500", "中证1000", "全A"]
    frequencies = Column(JSON)  # ["Monthly", "Biweekly", "Weekly", "Daily"]
    prices = Column(JSON)  # 4x4 二维数组
    note: str = Column(Text)
    is_active: bool = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UpgradePackage(Base):
    """升级包"""

    __tablename__ = "upgrade_packages"

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String(100), nullable=False)
    description: str = Column(Text)
    price_monthly: float = Column(Float)
    price_yearly: float = Column(Float)
    price_standard: str = Column(String(50))  # "500元/月"
    price_advanced: str = Column(String(50))  # "2000元/月起"
    price_unit: str = Column(String(50))  # "元/席位/年起"
    sort_order: int = Column(Integer, default=0)
    is_active: bool = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
