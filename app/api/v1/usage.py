"""用量统计 API。"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.response import success
from app.db.base import get_db
from app.models.user import User
from app.services import usage_service

router = APIRouter()


@router.get("/")
def get_my_usage(
    usage_date: date | None = Query(None, description="查询日期，默认今天"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询当前用户指定日期的用量统计"""
    records = usage_service.get_user_usage(db, current_user.id, usage_date)
    return success(records)


@router.get("/check")
def check_usage(
    permission_code: str = Query(..., description="权限编码"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检查当前用户某功能是否还有用量"""
    result = usage_service.check_usage_limit(db, current_user.id, permission_code)
    return success(result)
