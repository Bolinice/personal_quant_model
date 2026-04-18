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
    price: float
    duration: str  # monthly, quarterly, yearly
    features: List[str]

class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass

class SubscriptionPlanInDB(SubscriptionPlanBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SubscriptionPlanOut(SubscriptionPlanBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SubscriptionPlan(SubscriptionPlanOut):
    pass