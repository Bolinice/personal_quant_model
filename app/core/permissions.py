"""
权限依赖注入
- require_permission: 检查用户是否拥有指定权限
- require_role: 检查用户是否拥有指定角色
- get_user_permissions: 获取用户当前权限列表
"""

from typing import List, Optional, Dict

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.user import User
from app.models.subscriptions import Subscription
from app.models.permissions import ROLE_PERMISSIONS


class PermissionCode:
    """权限编码常量"""
    FACTOR_VIEW_BASIC = "factor_view_basic"
    FACTOR_VIEW_ALL = "factor_view_all"
    FACTOR_IC_ANALYSIS = "factor_ic_analysis"
    FACTOR_DECAY_MONITOR = "factor_decay_monitor"
    BACKTEST_DAILY_1 = "backtest_daily_1"
    BACKTEST_UNLIMITED = "backtest_unlimited"
    BACKTEST_BATCH = "backtest_batch"
    PORTFOLIO_VIEW = "portfolio_view"
    PORTFOLIO_TRACK = "portfolio_track"
    PORTFOLIO_CHANGE_OBSERVE = "portfolio_change_observe"
    REPORT_VIEW = "report_view"
    REPORT_EXPORT = "report_export"
    DATA_VIEW = "data_view"
    DATA_EXPORT = "data_export"
    API_ACCESS = "api_access"
    SIGNAL_PUSH = "signal_push"
    SIGNAL_VIEW = "signal_push"  # alias


def get_user_role(user: User, db: Session) -> str:
    """获取用户当前有效角色（基于订阅计划）"""
    from datetime import date

    today = date.today()
    # 查找当前有效订阅
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user.id,
        Subscription.status == "active",
        Subscription.start_date <= today,
        Subscription.end_date >= today,
    ).order_by(Subscription.end_date.desc()).first()

    if subscription:
        plan_type = subscription.plan_type
        # 映射订阅类型到角色
        role_map = {
            "trial": "trial",
            "free": "free",
            "basic": "free",
            "standard": "pro",
            "pro": "pro",
            "professional": "pro",
            "advanced": "pro",
            "team": "institution",
            "enterprise": "institution",
            "institution": "institution",
        }
        return role_map.get(plan_type, "free")

    # 无有效订阅，默认 trial
    return "trial"


def get_user_permissions(user: User, db: Session) -> List[str]:
    """获取用户当前权限列表"""
    role = get_user_role(user, db)
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["trial"])


# 权限 → 各订阅等级每日用量限制（None 表示无限制）
PERMISSION_LIMITS: Dict[str, Dict[str, Optional[int]]] = {
    PermissionCode.BACKTEST_DAILY_1: {"free": 1, "basic": 5, "pro": None},
    PermissionCode.FACTOR_VIEW_ALL: {"free": 0, "basic": 0, "pro": None},
    PermissionCode.PORTFOLIO_TRACK: {"free": 0, "basic": 3, "pro": None},
    PermissionCode.SIGNAL_VIEW: {"free": 0, "basic": 0, "pro": None},
    PermissionCode.SIGNAL_PUSH: {"free": 0, "basic": 0, "pro": None},
    PermissionCode.API_ACCESS: {"free": 0, "basic": 0, "pro": None},
}


def _get_current_user():
    """延迟导入 get_current_user 避免循环依赖"""
    from app.api.v1.auth import get_current_user
    return get_current_user


def require_permission(permission_code: str):
    """权限依赖注入工厂函数

    用法:
        @router.post("/generate")
        def generate(current_user=Depends(require_permission("portfolio_track"))):
            ...
    """
    from app.api.v1.auth import get_current_user as _get_auth_user

    async def _check_permission(
        current_user: User = Depends(_get_auth_user),
        db: Session = Depends(get_db),
    ) -> User:
        permissions = get_user_permissions(current_user, db)
        if permission_code not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"当前套餐不支持此功能，请升级订阅方案",
            )
        return current_user

    return _check_permission


def require_role(role_name: str):
    """角色依赖注入工厂函数

    用法:
        @router.post("/admin/config")
        def admin_op(current_user=Depends(require_role("admin"))):
            ...
    """
    from app.api.v1.auth import get_current_user as _get_auth_user

    async def _check_role(
        current_user: User = Depends(_get_auth_user),
        db: Session = Depends(get_db),
    ) -> User:
        user_role = get_user_role(current_user, db)
        # admin 角色始终通过
        if current_user.role == "admin" or current_user.is_superuser:
            return current_user
        if user_role != role_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要 {role_name} 角色权限",
            )
        return current_user

    return _check_role
