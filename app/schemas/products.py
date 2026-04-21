from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class ProductBase(BaseModel):
    product_code: str
    product_name: str
    description: Optional[str] = None
    risk_level: str = "medium"
    is_active: bool = True

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    description: Optional[str] = None
    risk_level: Optional[str] = None
    is_active: Optional[bool] = None

class ProductInDB(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProductOut(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Product(ProductOut):
    pass

class ProductReportBase(BaseModel):
    product_id: int
    report_type: str
    report_date: datetime
    content: str

class ProductReportCreate(ProductReportBase):
    pass

class ProductReportInDB(ProductReportBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProductReportOut(ProductReportBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProductReport(ProductReportOut):
    pass

class SubscriptionPlanBase(BaseModel):
    plan_name: str
    plan_type: Optional[str] = None
    plan_tier: int = 0
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    price_unit: Optional[str] = None
    custom_price: Optional[str] = None
    stock_pools: Optional[List[str]] = None
    frequencies: Optional[List[str]] = None
    features: Optional[List[str]] = None
    description: Optional[str] = None
    highlight: bool = False
    buttons: Optional[List[str]] = None
    is_active: bool = True

class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass

class SubscriptionPlanOut(SubscriptionPlanBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class SubscriptionPlan(SubscriptionPlanOut):
    pass


class PricingMatrixOut(BaseModel):
    billing_cycle: str
    pools: List[str]
    frequencies: List[str]
    prices: List[List[int]]
    note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UpgradePackageOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    price_standard: Optional[str] = None
    price_advanced: Optional[str] = None
    price_unit: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PricingOverviewOut(BaseModel):
    """定价总览 - 一次返回所有定价数据"""
    plans: List[SubscriptionPlanOut]
    pricing_matrix: List[PricingMatrixOut]
    upgrade_packages: List[UpgradePackageOut]