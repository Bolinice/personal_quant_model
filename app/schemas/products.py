from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import date

class ProductBase(BaseModel):
    model_id: int
    product_code: str
    product_name: str
    description: str
    risk_level: str = "medium"

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    description: Optional[str] = None
    risk_level: Optional[str] = None
    is_active: Optional[bool] = None

class ProductInDB(ProductBase):
    id: int
    is_active: bool
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class ProductOut(ProductBase):
    id: int
    is_active: bool
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class ProductReportBase(BaseModel):
    product_id: int
    report_type: str
    report_date: date
    report_path: str

class ProductReportCreate(ProductReportBase):
    pass

class ProductReportInDB(ProductReportBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class ProductReportOut(ProductReportBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class SubscriptionPlanBase(BaseModel):
    plan_name: str
    price: float
    duration: str
    features: Optional[Dict[str, Any]] = None

class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass

class SubscriptionPlanUpdate(BaseModel):
    plan_name: Optional[str] = None
    price: Optional[float] = None
    duration: Optional[str] = None
    features: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class SubscriptionPlanInDB(SubscriptionPlanBase):
    id: int
    is_active: bool
    created_at: date

    class Config:
        from_attributes = True

class SubscriptionPlanOut(SubscriptionPlanBase):
    id: int
    is_active: bool
    created_at: date

    class Config:
        from_attributes = True

class SubscriptionBase(BaseModel):
    user_id: int
    product_id: int
    plan_id: int
    start_time: date
    end_time: date

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionUpdate(BaseModel):
    is_active: Optional[bool] = None

class SubscriptionInDB(SubscriptionBase):
    id: int
    is_active: bool
    created_at: date

    class Config:
        from_attributes = True

class SubscriptionOut(SubscriptionBase):
    id: int
    is_active: bool
    created_at: date

    class Config:
        from_attributes = True
