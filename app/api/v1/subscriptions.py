from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.db.base import get_db
from app.services.subscriptions_service import get_subscriptions, create_subscription, update_subscription, get_subscription_histories, create_subscription_history, get_subscription_permissions, create_subscription_permission, check_subscription_permission, renew_subscription
from app.models.subscriptions import Subscription, SubscriptionHistory, SubscriptionPermission
from app.models.products import Product, SubscriptionPlan
from app.schemas.subscriptions import SubscriptionCreate, SubscriptionUpdate, SubscriptionHistoryCreate, SubscriptionPermissionCreate, SubscriptionOut, SubscriptionHistoryOut, SubscriptionPermissionOut

router = APIRouter()

# 付费模型对应的 product_code 映射
PAID_PRODUCT_MAP = {
    'ZZ1000': 'ZZ1000_REPORT',
    'ALL_A': 'ALL_A_REPORT',
}


class CheckAccessRequest(BaseModel):
    user_id: int
    resource_code: str  # e.g. 'ZZ1000' or 'ALL_A'


class SubscribeRequest(BaseModel):
    user_id: int
    plan_id: int


@router.get("/plans", response_model=List[dict])
def list_plans(db: Session = Depends(get_db)):
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).all()
    return [{"id": p.id, "plan_name": p.plan_name, "plan_type": p.plan_type, "price": p.price, "duration_days": p.duration_days, "features": p.features} for p in plans]


@router.post("/check-access")
def check_access(req: CheckAccessRequest, db: Session = Depends(get_db)):
    """检查用户是否有权限访问付费资源"""
    product_code = PAID_PRODUCT_MAP.get(req.resource_code)
    if not product_code:
        # 不在付费映射中的资源，默认免费
        return {"has_access": True, "resource_code": req.resource_code}

    # 查找对应产品
    product = db.query(Product).filter(Product.product_code == product_code).first()
    if not product:
        return {"has_access": False, "resource_code": req.resource_code}

    # 检查用户是否有该产品的有效订阅
    today = date.today()
    subscription = db.query(Subscription).filter(
        Subscription.user_id == req.user_id,
        Subscription.product_id == product.id,
        Subscription.status == 'active',
        Subscription.payment_status == 'paid',
        Subscription.end_date >= today,
    ).first()

    return {"has_access": subscription is not None, "resource_code": req.resource_code}


@router.post("/subscribe")
def subscribe(req: SubscribeRequest, db: Session = Depends(get_db)):
    """创建订阅并模拟支付成功"""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == req.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")

    # 获取套餐关联的产品
    products = db.query(Product).filter(Product.is_active == True).all()
    if not products:
        raise HTTPException(status_code=404, detail="没有可订阅的产品")

    today = date.today()
    end_date = today + timedelta(days=plan.duration_days or 30)

    created = []
    for product in products:
        # 检查是否已有有效订阅
        existing = db.query(Subscription).filter(
            Subscription.user_id == req.user_id,
            Subscription.product_id == product.id,
            Subscription.status == 'active',
            Subscription.end_date >= today,
        ).first()
        if existing:
            created.append({"product_id": product.id, "product_name": product.product_name, "status": "already_subscribed"})
            continue

        sub = Subscription(
            user_id=req.user_id,
            product_id=product.id,
            plan_id=plan.id,
            plan_type=plan.plan_type,
            start_date=today,
            end_date=end_date,
            status='active',
            auto_renew=True,
            payment_method='mock',
            payment_status='paid',
        )
        db.add(sub)
        db.flush()

        # 创建权限
        perm = SubscriptionPermission(
            subscription_id=sub.id,
            permission_type='read_report',
            is_granted=True,
        )
        db.add(perm)
        created.append({"product_id": product.id, "product_name": product.product_name, "status": "subscribed"})

    db.commit()
    return {"success": True, "plan_name": plan.plan_name, "price": plan.price, "end_date": str(end_date), "products": created}


@router.get("/my/subscriptions", response_model=List[SubscriptionOut])
def read_my_subscriptions(user_id: int, db: Session = Depends(get_db)):
    subscriptions = get_subscriptions(user_id=user_id, db=db)
    return subscriptions


@router.post("/", response_model=SubscriptionOut)
def create_subscription_endpoint(subscription: SubscriptionCreate, db: Session = Depends(get_db)):
    return create_subscription(subscription, db=db)


@router.put("/{subscription_id}", response_model=SubscriptionOut)
def update_subscription_endpoint(subscription_id: int, subscription_update: SubscriptionUpdate, db: Session = Depends(get_db)):
    subscription = update_subscription(subscription_id, subscription_update, db=db)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


@router.get("/{subscription_id}/histories", response_model=List[SubscriptionHistoryOut])
def read_subscription_histories(subscription_id: int, db: Session = Depends(get_db)):
    histories = get_subscription_histories(subscription_id, db=db)
    return histories


@router.post("/{subscription_id}/history", response_model=SubscriptionHistoryOut)
def create_subscription_history_endpoint(subscription_id: int, history: SubscriptionHistoryCreate, db: Session = Depends(get_db)):
    return create_subscription_history(subscription_id, history, db=db)


@router.get("/{subscription_id}/permissions", response_model=List[SubscriptionPermissionOut])
def read_subscription_permissions(subscription_id: int, db: Session = Depends(get_db)):
    permissions = get_subscription_permissions(subscription_id, db=db)
    return permissions


@router.post("/{subscription_id}/permissions", response_model=SubscriptionPermissionOut)
def create_subscription_permission_endpoint(subscription_id: int, permission: SubscriptionPermissionCreate, db: Session = Depends(get_db)):
    return create_subscription_permission(permission, db=db)


@router.post("/{subscription_id}/renew", response_model=SubscriptionOut)
def renew_subscription_endpoint(subscription_id: int, db: Session = Depends(get_db)):
    success = renew_subscription(subscription_id, db=db)
    if not success:
        raise HTTPException(status_code=400, detail="Subscription renewal failed")
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    return subscription


@router.post("/{subscription_id}/check-permission")
def check_subscription_permission_endpoint(subscription_id: int, permission_type: str, db: Session = Depends(get_db)):
    has_permission = check_subscription_permission(subscription_id, permission_type, db=db)
    return {"has_permission": has_permission}