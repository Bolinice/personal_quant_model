"""支付服务层 - 核心业务逻辑"""
import hashlib
import time
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.payments import PaymentConfig, PaymentOrder
from app.models.products import SubscriptionPlan
from app.models.subscriptions import Subscription, SubscriptionPermission
from app.schemas.payments import PaymentOrderCreate


def generate_order_no() -> str:
    """生成订单号：时间戳 + 随机数"""
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    random_str = hashlib.md5(str(time.time()).encode()).hexdigest()[:6].upper()
    return f"PAY{timestamp}{random_str}"


def create_payment_order(order_data: PaymentOrderCreate, db: Session) -> PaymentOrder:
    """创建支付订单"""
    # 获取套餐信息
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == order_data.plan_id).first()
    if not plan:
        raise ValueError("套餐不存在")

    # 计算金额（根据支付类型选择月付或年付）
    if order_data.payment_type in ["yearly", "year"]:
        amount = plan.price_yearly or plan.price or 0
        subject = f"{plan.plan_name} - 年付"
    else:
        amount = plan.price_monthly or plan.price or 0
        subject = f"{plan.plan_name} - 月付"

    # 创建订单
    order = PaymentOrder(
        order_no=generate_order_no(),
        user_id=order_data.user_id,
        plan_id=order_data.plan_id,
        subject=subject,
        body=plan.description or "",
        amount=amount,
        currency="CNY",
        payment_method=order_data.payment_method,
        payment_type=order_data.payment_type,
        status="pending",
        client_ip=order_data.client_ip,
        expired_at=datetime.now(UTC) + timedelta(hours=2),  # 2小时过期
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    return order


def get_payment_order(order_no: str, db: Session) -> Optional[PaymentOrder]:
    """获取支付订单"""
    return db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).first()


def get_user_payment_orders(user_id: int, db: Session, limit: int = 50) -> list[PaymentOrder]:
    """获取用户的支付订单列表"""
    return (
        db.query(PaymentOrder)
        .filter(PaymentOrder.user_id == user_id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(limit)
        .all()
    )


def update_order_status(
    order_no: str, status: str, trade_no: Optional[str] = None, notify_data: Optional[dict] = None, db: Session = None
) -> Optional[PaymentOrder]:
    """更新订单状态"""
    order = get_payment_order(order_no, db)
    if not order:
        return None

    order.status = status
    if trade_no:
        order.trade_no = trade_no
    if notify_data:
        order.notify_data = notify_data
        order.notify_time = datetime.now(UTC)

    if status == "paid":
        order.paid_at = datetime.now(UTC)
        # 支付成功后创建订阅
        _create_subscription_after_payment(order, db)

    db.commit()
    db.refresh(order)
    return order


def _create_subscription_after_payment(order: PaymentOrder, db: Session):
    """支付成功后创建订阅"""
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == order.plan_id).first()
    if not plan:
        return

    # 计算订阅时长
    if order.payment_type in ["yearly", "year"]:
        duration_days = 365
    else:
        duration_days = 30

    today = datetime.now(UTC).date()
    end_date = today + timedelta(days=duration_days)

    # 检查是否已有订阅
    existing = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == order.user_id,
            Subscription.plan_id == order.plan_id,
            Subscription.status == "active",
            Subscription.end_date >= today,
        )
        .first()
    )

    if existing:
        # 续费：延长结束日期
        existing.end_date = max(existing.end_date, today) + timedelta(days=duration_days)
        db.commit()
        order.subscription_id = existing.id
    else:
        # 新订阅
        subscription = Subscription(
            user_id=order.user_id,
            plan_id=order.plan_id,
            plan_type=plan.plan_type,
            start_date=today,
            end_date=end_date,
            status="active",
            auto_renew=True,
            payment_method=order.payment_method,
            payment_status="paid",
        )
        db.add(subscription)
        db.flush()

        # 创建权限
        permission = SubscriptionPermission(
            subscription_id=subscription.id,
            permission_type="full_access",
            is_granted=True,
        )
        db.add(permission)
        db.flush()

        order.subscription_id = subscription.id

    db.commit()


def cancel_order(order_no: str, db: Session) -> Optional[PaymentOrder]:
    """取消订单"""
    return update_order_status(order_no, "cancelled", db=db)


def get_payment_config(payment_method: str, db: Session) -> Optional[PaymentConfig]:
    """获取支付配置"""
    return db.query(PaymentConfig).filter(PaymentConfig.payment_method == payment_method).first()


def create_or_update_payment_config(payment_method: str, config_data: dict, db: Session) -> PaymentConfig:
    """创建或更新支付配置"""
    config = get_payment_config(payment_method, db)

    if config:
        # 更新
        for key, value in config_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    else:
        # 创建
        config = PaymentConfig(payment_method=payment_method, **config_data)
        db.add(config)

    db.commit()
    db.refresh(config)
    return config
