from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SubscriptionBase(BaseModel):
    user_id: int
    product_id: int
    plan_id: int
    start_time: datetime
    end_time: datetime
    is_active: bool = True
    auto_renew: bool = True
    payment_method: str = "credit_card"
    payment_status: str = "pending"


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(BaseModel):
    is_active: bool | None = None
    auto_renew: bool | None = None
    payment_method: str | None = None
    payment_status: str | None = None


class SubscriptionInDB(SubscriptionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionOut(SubscriptionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Subscription(SubscriptionOut):
    pass


class SubscriptionHistoryBase(BaseModel):
    subscription_id: int
    action: str  # create, renew, cancel, upgrade
    details: dict[str, Any] | None = None


class SubscriptionHistoryCreate(SubscriptionHistoryBase):
    pass


class SubscriptionHistoryInDB(SubscriptionHistoryBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionHistoryOut(SubscriptionHistoryBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionHistory(SubscriptionHistoryOut):
    pass


class SubscriptionPermissionBase(BaseModel):
    subscription_id: int
    permission_type: str  # read_report, access_api, full_access
    is_granted: bool = True


class SubscriptionPermissionCreate(SubscriptionPermissionBase):
    pass


class SubscriptionPermissionInDB(SubscriptionPermissionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPermissionOut(SubscriptionPermissionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPermission(SubscriptionPermissionOut):
    pass
