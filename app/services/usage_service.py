"""
用量统计服务
- 检查用户是否超出每日用量限制
- 记录用量
- 查询用量
"""

from datetime import date
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.usage import UsageRecord
from app.models.subscriptions import Subscription

# 用量限制定义（避免从 permissions 循环导入）
PERMISSION_LIMITS = {
    "backtest_daily_1": {"free": 1, "basic": 5, "pro": None},
    "factor_view_all": {"free": 0, "basic": 0, "pro": None},
    "portfolio_track": {"free": 0, "basic": 3, "pro": None},
    "signal_push": {"free": 0, "basic": 0, "pro": None},
    "timing_view": {"free": 0, "basic": 3, "pro": None},
    "api_access": {"free": 0, "basic": 0, "pro": None},
}


def check_usage_limit(db: Session, user_id: int, permission_code: str) -> Dict:
    """检查用户是否超出用量限制

    Returns:
        {"allowed": bool, "current": int, "limit": int|None}
    """
    # 查询用户订阅等级
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    tier = sub.plan_code if sub else "free"

    # 获取该权限的限制
    limit_info = PERMISSION_LIMITS.get(permission_code, {})
    limit = limit_info.get(tier)

    # 无限制
    if limit is None:
        return {"allowed": True, "current": 0, "limit": None}

    # 查询当日用量
    today = date.today()
    record = db.query(UsageRecord).filter(
        and_(
            UsageRecord.user_id == user_id,
            UsageRecord.permission_code == permission_code,
            UsageRecord.usage_date == today,
        )
    ).first()

    current = record.count if record else 0
    allowed = current < limit

    return {"allowed": allowed, "current": current, "limit": limit}


def record_usage(db: Session, user_id: int, permission_code: str) -> UsageRecord:
    """记录一次用量（原子递增）"""
    today = date.today()
    record = db.query(UsageRecord).filter(
        and_(
            UsageRecord.user_id == user_id,
            UsageRecord.permission_code == permission_code,
            UsageRecord.usage_date == today,
        )
    ).first()

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


def get_user_usage(db: Session, user_id: int, usage_date: Optional[date] = None) -> List[Dict]:
    """查询用户指定日期的用量"""
    if usage_date is None:
        usage_date = date.today()

    records = db.query(UsageRecord).filter(
        and_(
            UsageRecord.user_id == user_id,
            UsageRecord.usage_date == usage_date,
        )
    ).all()

    return [
        {
            "permission_code": r.permission_code,
            "count": r.count,
            "limit": PERMISSION_LIMITS.get(r.permission_code, {}).get(
                _get_user_tier(db, user_id), None
            ),
        }
        for r in records
    ]


def _get_user_tier(db: Session, user_id: int) -> str:
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    return sub.plan_code if sub else "free"
