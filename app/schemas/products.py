from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductBase(BaseModel):
    product_code: str
    product_name: str
    description: str | None = None
    risk_level: str = "medium"
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    product_name: str | None = None
    description: str | None = None
    risk_level: str | None = None
    is_active: bool | None = None


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
    plan_type: str | None = None
    plan_tier: int = 0
    price_monthly: float | None = None
    price_yearly: float | None = None
    price_unit: str | None = None
    custom_price: str | None = None
    stock_pools: list[str] | None = None
    frequencies: list[str] | None = None
    features: list[str] | None = None
    description: str | None = None
    highlight: bool = False
    buttons: list[str] | None = None
    is_active: bool = True


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanOut(SubscriptionPlanBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPlan(SubscriptionPlanOut):
    pass


class PricingMatrixOut(BaseModel):
    billing_cycle: str
    pools: list[str]
    frequencies: list[str]
    prices: list[list[int]]
    note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UpgradePackageOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    price_monthly: float | None = None
    price_yearly: float | None = None
    price_standard: str | None = None
    price_advanced: str | None = None
    price_unit: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PricingOverviewOut(BaseModel):
    """定价总览 - 一次返回所有定价数据"""

    plans: list[SubscriptionPlanOut]
    pricing_matrix: list[PricingMatrixOut]
    upgrade_packages: list[UpgradePackageOut]
