"""用户管理 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.response import success
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/")
def create_user_endpoint(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建用户（需认证）"""
    result = AuthService.create_user(
        db,
        username=user.username,
        email=user.email,
        password=user.password,
        role=user.role,
        real_name=user.real_name,
        phone=user.phone,
    )
    return success(result)


@router.get("/")
def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户列表（需认证）"""
    users = db.query(User).offset(skip).limit(limit).all()
    return success(users)


@router.get("/{user_id}")
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户详情（需认证）"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return success(user)


@router.put("/{user_id}")
def update_user_endpoint(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新用户（需认证）"""
    user = AuthService.update_user(db, user_id, **user_update.model_dump(exclude_unset=True))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return success(user)
