"""用户管理 API。"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.auth_service import AuthService
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.core.response import success, error

router = APIRouter()


@router.post("/")
def create_user_endpoint(user: UserCreate, db: Session = Depends(get_db)):
    """创建用户"""
    result = AuthService.create_user(
        db, username=user.username, email=user.email,
        password=user.password, role=user.role,
        real_name=user.real_name, phone=user.phone,
    )
    return success(result)


@router.get("/")
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取用户列表"""
    users = db.query(User).offset(skip).limit(limit).all()
    return success(users)


@router.get("/{user_id}")
def read_user(user_id: int, db: Session = Depends(get_db)):
    """获取用户详情"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return success(user)


@router.put("/{user_id}")
def update_user_endpoint(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    """更新用户"""
    user = AuthService.update_user(db, user_id, **user_update.model_dump(exclude_unset=True))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return success(user)