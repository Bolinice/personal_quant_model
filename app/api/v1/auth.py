"""
认证API
支持JWT登录、refresh token、API Key认证
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.core.response import success
from app.db.base import get_db
from app.models.user import User
from app.services.auth_service import AuthService

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class APIKeyCreateRequest(BaseModel):
    name: str | None = None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        # 确保是 access token，而非 refresh token
        if payload.get("type") != "access":
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """用户登录 (JSON格式，支持邮箱登录)"""
    # 支持邮箱或用户名登录
    user = db.query(User).filter((User.email == request.email) | (User.username == request.email)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not AuthService.verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # 更新登录信息
    user.last_login_at = datetime.now(tz=timezone.utc)
    user.login_count = (user.login_count or 0) + 1
    db.commit()

    token_data = {"sub": user.username, "role": user.role}
    access_token = AuthService.create_access_token(token_data)
    refresh_token = AuthService.create_refresh_token(token_data)

    return success(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """刷新访问令牌"""
    result = AuthService.refresh_access_token(request.refresh_token)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌",
        )

    new_access, new_refresh = result
    return success(
        {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
        }
    )


@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return success(
        {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
            "created_at": str(current_user.created_at) if current_user.created_at else None,
        }
    )


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """修改密码"""
    if not AuthService.verify_password(request.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码错误")

    valid, msg = AuthService.validate_password_strength(request.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    current_user.hashed_password = AuthService.hash_password(request.new_password)
    db.commit()
    return success(message="密码修改成功")


@router.post("/api-keys")
def create_api_key(
    request: APIKeyCreateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """创建API Key"""
    result = AuthService.create_api_key(db, current_user.id, request.name)
    return success(result, message="API Key创建成功，请妥善保管secret")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str


@router.post("/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查邮箱是否已注册
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="该邮箱已注册")

    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="该用户名已存在")

    # 验证密码强度
    valid, msg = AuthService.validate_password_strength(request.password)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    # 创建用户
    user = AuthService.create_user(db, request.username, request.email, request.password)
    if not user:
        raise HTTPException(status_code=500, detail="注册失败")

    # 自动创建试用订阅（7天试用期）
    from app.models.subscriptions import Subscription

    sub = Subscription(
        user_id=user.id,
        plan_type="trial",
        status="active",
        start_date=datetime.now(tz=timezone.utc).date(),
        end_date=(datetime.now(tz=timezone.utc) + timedelta(days=7)).date(),  # 7天试用
    )
    db.add(sub)
    db.commit()

    # 返回 token
    token_data = {"sub": user.username, "role": user.role}
    access_token = AuthService.create_access_token(token_data)
    refresh_token = AuthService.create_refresh_token(token_data)

    return success(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
            },
        },
        message="注册成功",
    )


@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """请求密码重置"""
    token = AuthService.generate_reset_token(db, request.email)
    # 无论邮箱是否存在都返回成功，防止邮箱枚举
    if token:
        logger.info(f"Reset token for {request.email}: {token}")
    return success(message="如果该邮箱已注册，重置链接已发送")


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """重置密码"""
    ok, msg = AuthService.reset_password_with_token(db, request.token, request.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg or "重置令牌无效或已过期")
    return success(message="密码重置成功")
