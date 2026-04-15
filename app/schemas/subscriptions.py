from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date

class SubscriptionBase(BaseModel):
    user_id: int
    product_id: int
    plan_id: int
    start_time: date
    end_time: date
    is_active: bool = True
    auto_renew: bool = True
    payment_method: str = "credit_card"
    payment_status: str = "pending"

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionUpdate(BaseModel):
    is_active: Optional[bool] = None
    auto_renew: Optional[bool] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None

class SubscriptionInDB(SubscriptionBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class SubscriptionOut(SubscriptionBase):
    id: int
    created_at: date
    updated_at: date

    class Config:
        from_attributes = True

class SubscriptionHistoryBase(BaseModel):
    subscription_id: int
    action: str
    details: Optional[Dict[str, Any]] = None

class SubscriptionHistoryCreate(SubscriptionHistoryBase):
    pass

class SubscriptionHistoryInDB(SubscriptionHistoryBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class SubscriptionHistoryOut(SubscriptionHistoryBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class SubscriptionPermissionBase(BaseModel):
    subscription_id: int
    permission_type: str
    is_granted: bool = True

class SubscriptionPermissionCreate(SubscriptionPermissionBase):
    pass

class SubscriptionPermissionInDB(SubscriptionPermissionBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True

class SubscriptionPermissionOut(SubscriptionPermissionBase):
    id: int
    created_at: date

    class Config:
        from_attributes = True
