"""证券管理 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.response import success
from app.db.base import get_db
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
def create_security_endpoint(security: SecurityCreate, db: Session = Depends(get_db)):
    """创建证券"""
    result = create_security(security, db=db)
    return success(result)


@router.put("/{security_id}")
def update_security_endpoint(security_id: int, security_update: SecurityUpdate, db: Session = Depends(get_db)):
    """更新证券"""
    security = update_security(security_id, security_update, db=db)
    if security is None:
        raise HTTPException(status_code=404, detail="Security not found")
    return success(security)


@router.delete("/{security_id}")
def delete_security_endpoint(security_id: int, db: Session = Depends(get_db)):
    """删除证券"""
    deleted = delete_security(security_id, db=db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Security not found")
    return success(message="Security deleted successfully")
