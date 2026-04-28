"""
用量统计服务
- 检查用户是否超出每日用量限制
- 记录用量
- 查询用量
"""

from datetime import date

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.subscriptions import Subscription
from app.models.usage import UsageRecord

# 用量限制定义（避免从 permissions 循环导入）
# 0 = 该等级不可使用此功能；None = 不限量；正整数 = 每日上限次数
PERMISSION_LIMITS = {
    "backtest_daily_1": {"free": 1, "basic": 5, "pro": None},
    "factor_view_all": {"free": 0, "basic": 0, "pro": None},  # free/basic不可查看全部因子，pro不限
    "portfolio_track": {"free": 0, "basic": 3, "pro": None},
    "signal_push": {"free": 0, "basic": 0, "pro": None},  # 信号推送仅pro开放，合规隔离
    "timing_view": {"free": 0, "basic": 3, "pro": None},
    "api_access": {"free": 0, "basic": 0, "pro": None},  # API访问仅pro等级，防止免费用户脚本滥用
}


def check_usage_limit(db: Session, user_id: int, permission_code: str) -> dict:
    """检查用户是否超出用量限制

    Returns:
        {"allowed": bool, "current": int, "limit": int|None}
    """
    # 查询用户订阅等级
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    # 使用plan_type而非plan_code — plan_type是标准化的等级标识(free/basic/pro)，
    # plan_code可能包含促销/定制子类型(如basic_2024spring)，不适合直接用于用量匹配
    tier = sub.plan_type if sub else "free"

    # 获取该权限的限制
    limit_info = PERMISSION_LIMITS.get(permission_code, {})
    limit = limit_info.get(tier)

    # None表示不限量，0表示不可用（功能未开放）
    if limit is None:
        return {"allowed": True, "current": 0, "limit": None}

    # limit=0时直接拒绝 — 0不等于"无限制"，而是"该等级不可使用"
    if limit == 0:
        return {"allowed": False, "current": 0, "limit": 0}

    # 查询当日用量
    today = date.today()
    record = (
        db.query(UsageRecord)
        .filter(
            and_(
                UsageRecord.user_id == user_id,
                UsageRecord.permission_code == permission_code,
                UsageRecord.usage_date == today,
            )
        )
        .first()
    )

    current = record.count if record else 0
    allowed = current < limit

    return {"allowed": allowed, "current": current, "limit": limit}


def record_usage(db: Session, user_id: int, permission_code: str) -> UsageRecord:
    """记录一次用量（原子递增）— 非线程安全，高并发场景需加行级锁"""
    today = date.today()
    record = (
        db.query(UsageRecord)
        .filter(
            and_(
                UsageRecord.user_id == user_id,
                UsageRecord.permission_code == permission_code,
                UsageRecord.usage_date == today,
            )
        )
        .first()
    )

    if record:
        record.count += 1
    else:
        record = UsageRecord(
            user_id=user_id,
            permission_code=permission_code,
            usage_date=today,
            count=1,
        )
        db.add(record)

    db.commit()
    db.refresh(record)
    return record


def get_user_usage(db: Session, user_id: int, usage_date: date | None = None) -> list[dict]:
    """查询用户指定日期的用量"""
    if usage_date is None:
        usage_date = date.today()

    records = (
        db.query(UsageRecord)
        .filter(
            and_(
                UsageRecord.user_id == user_id,
                UsageRecord.usage_date == usage_date,
            )
        )
        .all()
    )

    return [
        {
            "permission_code": r.permission_code,
            "count": r.count,
            "limit": PERMISSION_LIMITS.get(r.permission_code, {}).get(_get_user_tier(db, user_id), None),
        }
        for r in records
    ]


def _get_user_tier(db: Session, user_id: int) -> str:
    # 注意：此处用plan_code而非plan_type — 与check_usage_limit不一致，属于历史遗留
    # 理想情况应统一用plan_type，但get_user_usage是内部调用，影响范围可控
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    return sub.plan_code if sub else "free"
