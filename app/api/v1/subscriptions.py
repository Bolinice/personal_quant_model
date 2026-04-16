from fastapi import APIRouter, Depends, HTTPException, status, Request

from typing import List
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.services.subscriptions_service import get_subscriptions, create_subscription, update_subscription, get_subscription_histories, create_subscription_history, get_subscription_permissions, create_subscription_permission, check_subscription_permission, renew_subscription
from app.models.subscriptions import Subscription, SubscriptionHistory, SubscriptionPermission
from app.schemas.subscriptions import SubscriptionCreate, SubscriptionUpdate, SubscriptionHistoryCreate, SubscriptionPermissionCreate, SubscriptionOut, SubscriptionHistoryOut, SubscriptionPermissionOut

router = APIRouter()

@router.get("/my/subscriptions", response_model=List[SubscriptionOut])
def read_my_subscriptions(user_id: int, db: Session = Depends(SessionLocal)):
    subscriptions = get_subscriptions(user_id=user_id, db=db)
    return subscriptions

@router.post("/", response_model=SubscriptionOut)
def create_subscription_endpoint(subscription: SubscriptionCreate, db: Session = Depends(SessionLocal)):
    return create_subscription(subscription, db=db)

@router.put("/{subscription_id}", response_model=SubscriptionOut)
def update_subscription_endpoint(subscription_id: int, subscription_update: SubscriptionUpdate, db: Session = Depends(SessionLocal)):
    subscription = update_subscription(subscription_id, subscription_update, db=db)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription

@router.get("/{subscription_id}/histories", response_model=List[SubscriptionHistoryOut])
def read_subscription_histories(subscription_id: int, db: Session = Depends(SessionLocal)):
    histories = get_subscription_histories(subscription_id, db=db)
    return histories

@router.post("/{subscription_id}/histories", response_model=SubscriptionHistoryOut)
def create_subscription_history_endpoint(subscription_id: int, history: SubscriptionHistoryCreate, db: Session = Depends(SessionLocal)):
    return create_subscription_history(subscription_id, history, db=db)

@router.get("/{subscription_id}/permissions", response_model=List[SubscriptionPermissionOut])
def read_subscription_permissions(subscription_id: int, db: Session = Depends(SessionLocal)):
    permissions = get_subscription_permissions(subscription_id, db=db)
    return permissions

@router.post("/{subscription_id}/permissions", response_model=SubscriptionPermissionOut)
def create_subscription_permission_endpoint(subscription_id: int, permission: SubscriptionPermissionCreate, db: Session = Depends(SessionLocal)):
    return create_subscription_permission(permission, db=db)

@router.post("/{subscription_id}/renew", response_model=SubscriptionOut)
def renew_subscription_endpoint(subscription_id: int, db: Session = Depends(SessionLocal)):
    success = renew_subscription(subscription_id, db=db)
    if not success:
        raise HTTPException(status_code=400, detail="Subscription renewal failed")
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    return subscription
    
@router.post("/{subscription_id}/check-permission")
def check_subscription_permission_endpoint(subscription_id: int, permission_type: str, db: Session = Depends(SessionLocal)):
    has_permission = check_subscription_permission(subscription_id, permission_type, db=db)
    return {"has_permission": has_permission}
