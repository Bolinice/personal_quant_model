"""订阅管理 API。"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.response import success
from app.db.base import get_db
from app.models.products import Product, SubscriptionPlan
from app.models.subscriptions import Subscription, SubscriptionPermission
from app.schemas.subscriptions import (
    SubscriptionCreate,
    SubscriptionHistoryCreate,
    SubscriptionPermissionCreate,
    SubscriptionUpdate,
)
from app.services.subscriptions_service import (
    check_subscription_permission,
    create_subscription,
    create_subscription_history,
    create_subscription_permission,
    get_subscription_histories,
    get_subscription_permissions,
    get_subscriptions,
    renew_subscription,
    update_subscription,
)

router = APIRouter()

# 付费模型对应的 product_code 映射
PAID_PRODUCT_MAP = {
    "ZZ1000": "ZZ1000_REPORT",
    "ALL_A": "ALL_A_REPORT",
}


class CheckAccessRequest(BaseModel):
    user_id: int
    resource_code: str  # e.g. 'ZZ1000' or 'ALL_A'


class SubscribeRequest(BaseModel):
    user_id: int
    plan_id: int


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    """列出订阅方案"""
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active).all()
    return success(
        [
            {
                "id": p.id,
                "plan_name": p.plan_name,
                "plan_type": p.plan_type,
                "price": p.price,
                "duration_days": p.duration_days,
                "features": p.features,
            }
            for p in plans
        ]
    )


@router.post("/check-access")
def check_access(req: CheckAccessRequest, db: Session = Depends(get_db)):
    """检查用户是否有权限访问付费资源"""
    product_code = PAID_PRODUCT_MAP.get(req.resource_code)
    if not product_code:
        return success({"has_access": True, "resource_code": req.resource_code})

    product = db.query(Product).filter(Product.product_code == product_code).first()
    if not product:
        return success({"has_access": False, "resource_code": req.resource_code})

    today = datetime.now(tz=UTC).date()
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == req.user_id,
            Subscription.product_id == product.id,
            Subscription.status == "active",
            Subscription.payment_status == "paid",
            Subscription.end_date >= today,
        )
        .first()
    )

    return success({"has_access": subscription is not None, "resource_code": req.resource_code})


@router.post("/subscribe")
def subscribe(req: SubscribeRequest, db: Session = Depends(get_db)):
    """创建订阅并模拟支付成功"""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == req.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")

    products = db.query(Product).filter(Product.is_active).all()
    if not products:
        raise HTTPException(status_code=404, detail="没有可订阅的产品")

    today = datetime.now(tz=UTC).date()
    end_date = today + timedelta(days=plan.duration_days or 30)

    created = []
    for product in products:
        existing = (
            db.query(Subscription)
            .filter(
                Subscription.user_id == req.user_id,
                Subscription.product_id == product.id,
                Subscription.status == "active",
                Subscription.end_date >= today,
            )
            .first()
        )
        if existing:
            created.append(
                {"product_id": product.id, "product_name": product.product_name, "status": "already_subscribed"}
            )
            continue

        sub = Subscription(
            user_id=req.user_id,
            product_id=product.id,
            plan_id=plan.id,
            plan_type=plan.plan_type,
            start_date=today,
            end_date=end_date,
            status="active",
            auto_renew=True,
            payment_method="mock",
            payment_status="paid",
        )
        db.add(sub)
        db.flush()

        perm = SubscriptionPermission(
            subscription_id=sub.id,
            permission_type="read_report",
            is_granted=True,
        )
        db.add(perm)
        created.append({"product_id": product.id, "product_name": product.product_name, "status": "subscribed"})

    db.commit()
    return success({"plan_name": plan.plan_name, "price": plan.price, "end_date": str(end_date), "products": created})


@router.get("/my/subscriptions")
def read_my_subscriptions(user_id: int, db: Session = Depends(get_db)):
    """获取我的订阅"""
    subscriptions = get_subscriptions(user_id=user_id, db=db)
    return success(subscriptions)


@router.post("/")
def create_subscription_endpoint(subscription: SubscriptionCreate, db: Session = Depends(get_db)):
    """创建订阅"""
    result = create_subscription(subscription, db=db)
    return success(result)


@router.put("/{subscription_id}")
def update_subscription_endpoint(
    subscription_id: int, subscription_update: SubscriptionUpdate, db: Session = Depends(get_db)
):
    """更新订阅"""
    subscription = update_subscription(subscription_id, subscription_update, db=db)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return success(subscription)


@router.get("/{subscription_id}/histories")
def read_subscription_histories(subscription_id: int, db: Session = Depends(get_db)):
    """获取订阅历史"""
    histories = get_subscription_histories(subscription_id, db=db)
    return success(histories)


@router.post("/{subscription_id}/history")
def create_subscription_history_endpoint(
    subscription_id: int, history: SubscriptionHistoryCreate, db: Session = Depends(get_db)
):
    """创建订阅历史"""
    result = create_subscription_history(subscription_id, history, db=db)
    return success(result)


@router.get("/{subscription_id}/permissions")
def read_subscription_permissions(subscription_id: int, db: Session = Depends(get_db)):
    """获取订阅权限"""
    permissions = get_subscription_permissions(subscription_id, db=db)
    return success(permissions)


@router.post("/{subscription_id}/permissions")
def create_subscription_permission_endpoint(
    subscription_id: int, permission: SubscriptionPermissionCreate, db: Session = Depends(get_db)
):
    """创建订阅权限"""
    result = create_subscription_permission(permission, db=db)
    return success(result)


@router.post("/{subscription_id}/renew")
def renew_subscription_endpoint(subscription_id: int, db: Session = Depends(get_db)):
    """续订"""
    renewed = renew_subscription(subscription_id, db=db)
    if not renewed:
        raise HTTPException(status_code=400, detail="Subscription renewal failed")
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    return success(subscription)


@router.post("/{subscription_id}/check-permission")
def check_subscription_permission_endpoint(subscription_id: int, permission_type: str, db: Session = Depends(get_db)):
    """检查订阅权限"""
    has_permission = check_subscription_permission(subscription_id, permission_type, db=db)
    return success({"has_permission": has_permission})
