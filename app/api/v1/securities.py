"""证券管理 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.response import success
from app.db.base import get_db
from app.models.user import User
from app.schemas.securities import SecurityCreate, SecurityUpdate
from app.services.securities_service import (
    create_security,
    delete_security,
    get_securities,
    get_security_by_ts_code,
    update_security,
)

router = APIRouter()


@router.get("/")
def read_securities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取证券列表"""
    securities = get_securities(skip=skip, limit=limit, db=db)
    return success(securities)


@router.get("/{ts_code}")
def read_security(ts_code: str, db: Session = Depends(get_db)):
    """获取证券详情"""
    security = get_security_by_ts_code(ts_code, db=db)
    if security is None:
        raise HTTPException(status_code=404, detail="Security not found")
    return success(security)


@router.post("/")
def create_security_endpoint(
    security: SecurityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建证券（需认证）"""
    result = create_security(security, db=db)
    return success(result)


@router.put("/{ts_code}")
def update_security_endpoint(
    ts_code: str,
    security_update: SecurityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新证券（需认证）"""
    result = update_security(ts_code, security_update, db=db)
    return success(result)


@router.delete("/{ts_code}")
def delete_security_endpoint(
    ts_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除证券（需认证）"""
    result = delete_security(ts_code, db=db)
    return success(result)
