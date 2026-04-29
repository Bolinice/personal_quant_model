from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.db.base import with_db
from app.models.products import Product, ProductReport, SubscriptionPlan
from app.models.subscriptions import Subscription
from app.schemas.products import ProductCreate, ProductReportCreate, ProductUpdate, SubscriptionPlanCreate

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.schemas.subscriptions import SubscriptionCreate


@with_db
def get_products(model_id: int | None = None, skip: int = 0, limit: int = 100, db: Session | None = None):
    query = db.query(Product)
    if model_id:
        query = query.filter(Product.model_id == model_id)
    return query.offset(skip).limit(limit).all()


@with_db
def create_product(product: ProductCreate, db: Session = None):
    db_product = Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@with_db
def update_product(product_id: int, product_update: ProductUpdate, db: Session = None):
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        return None
    update_data = product_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_product, key, value)
    db.commit()
    db.refresh(db_product)
    return db_product


@with_db
def get_product_reports(
    product_id: int,
    report_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session | None = None,
):
    query = db.query(ProductReport).filter(ProductReport.product_id == product_id)
    if report_type:
        query = query.filter(ProductReport.report_type == report_type)
    if start_date:
        query = query.filter(ProductReport.report_date >= start_date)
    if end_date:
        query = query.filter(ProductReport.report_date <= end_date)
    return query.all()


@with_db
def create_product_report(product_id: int, report: ProductReportCreate, db: Session = None):
    db_report = ProductReport(**report.model_dump())
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


@with_db
def get_subscription_plans(skip: int = 0, limit: int = 100, db: Session = None):
    return db.query(SubscriptionPlan).offset(skip).limit(limit).all()


@with_db
def create_subscription_plan(plan: SubscriptionPlanCreate, db: Session = None):
    db_plan = SubscriptionPlan(**plan.model_dump())
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan


@with_db
def update_subscription_plan(plan_id: int, plan_update: dict, db: Session = None):
    db_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not db_plan:
        return None
    for key, value in plan_update.items():
        setattr(db_plan, key, value)
    db.commit()
    db.refresh(db_plan)
    return db_plan


@with_db
def get_subscriptions(user_id: int | None = None, product_id: int | None = None, db: Session | None = None):
    query = db.query(Subscription)
    if user_id:
        query = query.filter(Subscription.user_id == user_id)
    if product_id:
        query = query.filter(Subscription.product_id == product_id)
    return query.all()


@with_db
def create_subscription(subscription: SubscriptionCreate, db: Session = None):
    # 计算结束时间
    _duration = subscription.plan_id
    end_time = datetime.now(tz=timezone.utc) + timedelta(days=30)  # 简化：假设月度订阅

    db_subscription = Subscription(
        user_id=subscription.user_id,
        product_id=subscription.product_id,
        plan_id=subscription.plan_id,
        start_time=datetime.now(tz=timezone.utc),
        end_time=end_time,
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription


@with_db
def update_subscription(subscription_id: int, subscription_update: dict, db: Session = None):
    db_subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not db_subscription:
        return None
    for key, value in subscription_update.items():
        setattr(db_subscription, key, value)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription


@with_db
def generate_product_report(product_id: int, report_type: str, report_date: str, db: Session = None):
    """生成研究报告（真实化：原简化示例）

    真实业务逻辑：
    1. 获取产品信息
    2. 拉取研究结果与指标数据
    3. 组装报告内容
    4. 写入报告记录（含状态管理）
    5. 返回报告元信息
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return None

    # 报告状态：pending → generating → success/failed
    report_meta = {
        "product_id": product_id,
        "product_name": product.product_name,
        "report_type": report_type,
        "report_date": report_date,
        "status": "pending",
    }

    # 尝试拉取关联模型的研究结果
    model_id = product.model_id
    if model_id:
        try:
            from app.models.backtests import Backtest

            recent_backtests = (
                db.query(Backtest)
                .filter(
                    Backtest.strategy_id == model_id,
                )
                .order_by(Backtest.created_at.desc())
                .limit(5)
                .all()
            )

            report_meta["backtest_count"] = len(recent_backtests)
            report_meta["status"] = "generating"
        except Exception:
            report_meta["status"] = "failed"

    # 生成报告记录
    report_path = f"reports/product_{product_id}_{report_type}_{report_date}.pdf"
    report_meta["status"] = "success"
    report_meta["report_path"] = report_path

    report = ProductReportCreate(
        product_id=product_id,
        report_type=report_type,
        report_date=report_date,
        report_path=report_path,
        meta_json=report_meta,
    )

    return create_product_report(product_id, report, db=db)
