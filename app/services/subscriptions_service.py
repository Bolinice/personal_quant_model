from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.subscriptions import Subscription, SubscriptionHistory, SubscriptionPermission
from app.schemas.subscriptions import SubscriptionCreate, SubscriptionUpdate, SubscriptionHistoryCreate, SubscriptionPermissionCreate
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def get_subscriptions(user_id: int = None, product_id: int = None, is_active: bool = None, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            query = db.query(Subscription)
            if user_id:
                query = query.filter(Subscription.user_id == user_id)
            if product_id:
                query = query.filter(Subscription.product_id == product_id)
            if is_active is not None:
                query = query.filter(Subscription.is_active == is_active)
            return query.all()
        finally:
            db.close()
    query = db.query(Subscription)
    if user_id:
        query = query.filter(Subscription.user_id == user_id)
    if product_id:
        query = query.filter(Subscription.product_id == product_id)
    if is_active is not None:
        query = query.filter(Subscription.is_active == is_active)
    return query.all()

def create_subscription(subscription: SubscriptionCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_subscription = Subscription(**subscription.dict())
            db.add(db_subscription)
            db.commit()
            db.refresh(db_subscription)
            
            # 创建订阅历史
            history = SubscriptionHistoryCreate(
                subscription_id=db_subscription.id,
                action="create",
                details={"plan_id": subscription.plan_id, "start_time": subscription.start_time}
            )
            create_subscription_history(db_subscription.id, history, db=db)
            
            return db_subscription
        finally:
            db.close()
    db_subscription = Subscription(**subscription.dict())
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    
    # 创建订阅历史
    history = SubscriptionHistoryCreate(
        subscription_id=db_subscription.id,
        action="create",
        details={"plan_id": subscription.plan_id, "start_time": subscription.start_time}
    )
    create_subscription_history(db_subscription.id, history, db=db)
    
    return db_subscription

def update_subscription(subscription_id: int, subscription_update: SubscriptionUpdate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
            if not db_subscription:
                return None
            update_data = subscription_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_subscription, key, value)
            db.commit()
            db.refresh(db_subscription)
            
            # 创建订阅历史
            history = SubscriptionHistoryCreate(
                subscription_id=subscription_id,
                action="update",
                details=update_data
            )
            create_subscription_history(subscription_id, history, db=db)
            
            return db_subscription
        finally:
            db.close()
    db_subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not db_subscription:
        return None
    update_data = subscription_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_subscription, key, value)
    db.commit()
    db.refresh(db_subscription)
    
    # 创建订阅历史
    history = SubscriptionHistoryCreate(
        subscription_id=subscription_id,
        action="update",
        details=update_data
    )
    create_subscription_history(subscription_id, history, db=db)
    
    return db_subscription

def get_subscription_histories(subscription_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(SubscriptionHistory).filter(SubscriptionHistory.subscription_id == subscription_id).all()
        finally:
            db.close()
    return db.query(SubscriptionHistory).filter(SubscriptionHistory.subscription_id == subscription_id).all()

def create_subscription_history(subscription_id: int, history: SubscriptionHistoryCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_history = SubscriptionHistory(**history.dict())
            db.add(db_history)
            db.commit()
            db.refresh(db_history)
            return db_history
        finally:
            db.close()
    db_history = SubscriptionHistory(**history.dict())
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    return db_history

def get_subscription_permissions(subscription_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            return db.query(SubscriptionPermission).filter(SubscriptionPermission.subscription_id == subscription_id).all()
        finally:
            db.close()
    return db.query(SubscriptionPermission).filter(SubscriptionPermission.subscription_id == subscription_id).all()

def create_subscription_permission(permission: SubscriptionPermissionCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
        try:
            db_permission = SubscriptionPermission(**permission.dict())
            db.add(db_permission)
            db.commit()
            db.refresh(db_permission)
            return db_permission
        finally:
            db.close()
    db_permission = SubscriptionPermission(**permission.dict())
    db.add(db_permission)
    db.commit()
    db.refresh(db_permission)
    return db_permission

def check_subscription_permission(subscription_id: int, permission_type: str, db: Session = None):
    """检查订阅权限"""
    if db is None:
        db = SessionLocal()
        try:
            permission = db.query(SubscriptionPermission).filter(
                SubscriptionPermission.subscription_id == subscription_id,
                SubscriptionPermission.permission_type == permission_type
            ).first()
            return permission is not None and permission.is_granted
        finally:
            db.close()
    permission = db.query(SubscriptionPermission).filter(
        SubscriptionPermission.subscription_id == subscription_id,
        SubscriptionPermission.permission_type == permission_type
    ).first()
    return permission is not None and permission.is_granted

def renew_subscription(subscription_id: int, db: Session = None):
    """续订订阅"""
    if db is None:
        db = SessionLocal()
        try:
            subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
            if not subscription or not subscription.auto_renew:
                return False
            
            # 延长订阅时间
            duration = 30  # 简化：延长30天
            subscription.end_time += timedelta(days=duration)
            subscription.payment_status = "pending"
            
            db.commit()
            db.refresh(subscription)
            
            # 创建续订历史
            history = SubscriptionHistoryCreate(
                subscription_id=subscription_id,
                action="renew",
                details={"new_end_time": subscription.end_time}
            )
            create_subscription_history(subscription_id, history, db=db)
            
            return True
        finally:
            db.close()
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription or not subscription.auto_renew:
        return False
    
    # 延长订阅时间
    duration = 30  # 简化：延长30天
    subscription.end_time += timedelta(days=duration)
    subscription.payment_status = "pending"
    
    db.commit()
    db.refresh(subscription)
    
    # 创建续订历史
    history = SubscriptionHistoryCreate(
        subscription_id=subscription_id,
        action="renew",
        details={"new_end_time": subscription.end_time}
    )
    create_subscription_history(subscription_id, history, db=db)
    
    return True
