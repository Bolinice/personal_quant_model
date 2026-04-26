"""
认证服务
实现JWT认证、refresh token机制、密码强度校验
符合ADD 11节安全规范
"""
from typing import Optional, Dict, Tuple
import secrets
from datetime import datetime, timedelta
import hashlib
import re
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.user import User, APIKey


class AuthService:
    """认证服务"""

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
        """创建访问令牌"""
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """创建刷新令牌"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict]:
        """
        验证令牌

        Args:
            token: JWT令牌
            token_type: 令牌类型 (access/refresh)
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            if payload.get("type") != token_type:
                return None
            return payload
        except JWTError:
            return None

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[Tuple[str, str]]:
        """
        使用refresh token刷新access token

        Returns:
            (new_access_token, new_refresh_token) 或 None
        """
        payload = AuthService.verify_token(refresh_token, "refresh")
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        new_data = {"sub": user_id, "role": payload.get("role", "user")}
        new_access = AuthService.create_access_token(new_data)
        new_refresh = AuthService.create_refresh_token(new_data)
        return new_access, new_refresh

    @staticmethod
    def hash_password(password: str) -> str:
        """密码哈希"""
        import bcrypt
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        import bcrypt
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, str]:
        """
        密码强度校验
        - 至少8位
        - 包含大小写字母
        - 包含数字
        """
        if len(password) < 8:
            return False, "密码至少8位"
        if not re.search(r'[A-Z]', password):
            return False, "密码需包含大写字母"
        if not re.search(r'[a-z]', password):
            return False, "密码需包含小写字母"
        if not re.search(r'\d', password):
            return False, "密码需包含数字"
        return True, ""

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """用户认证"""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not user.is_active:
            return None
        if not AuthService.verify_password(password, user.hashed_password):
            return None

        # 更新登录信息
        user.last_login_at = datetime.now()
        user.login_count = (user.login_count or 0) + 1
        db.commit()

        return user

    @staticmethod
    def create_api_key(db: Session, user_id: int, name: str = None) -> Dict:
        """创建API Key"""
        api_key = f"qpm_{secrets.token_hex(16)}"
        secret = secrets.token_hex(32)
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()

        key_record = APIKey(
            user_id=user_id,
            api_key=api_key,
            secret_hash=secret_hash,
            name=name,
        )
        db.add(key_record)
        db.commit()
        db.refresh(key_record)

        return {
            "api_key": api_key,
            "api_secret": secret,  # 只在创建时返回一次
            "name": name,
        }

    @staticmethod
    def verify_api_key(db: Session, api_key: str) -> Optional[APIKey]:
        """验证API Key"""
        key_record = db.query(APIKey).filter(
            APIKey.api_key == api_key,
            APIKey.status == "active",
        ).first()

        if key_record:
            key_record.last_used_at = datetime.now()
            db.commit()

        return key_record

    @staticmethod
    def generate_reset_token(db: Session, email: str) -> Optional[str]:
        """生成密码重置令牌"""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None

        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.now() + timedelta(hours=1)
        db.commit()

        logger.info(f"Password reset token generated for {email}")
        # 生产环境应发送邮件，暂时仅记录日志
        return token

    @staticmethod
    def reset_password_with_token(db: Session, token: str, new_password: str) -> bool:
        """使用重置令牌重置密码"""
        user = db.query(User).filter(User.reset_token == token).first()
        if not user:
            return False

        if user.reset_token_expires and user.reset_token_expires < datetime.now():
            # 令牌已过期，清除
            user.reset_token = None
            user.reset_token_expires = None
            db.commit()
            return False

        valid, msg = AuthService.validate_password_strength(new_password)
        if not valid:
            return False

        user.hashed_password = AuthService.hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        db.commit()
        return True

    # ==================== 兼容旧接口 ====================

    @staticmethod
    def create_user(db: Session, username: str, email: str, password: str,
                    role: str = "user", real_name: str = None, phone: str = None) -> User:
        """创建用户"""
        hashed_password = AuthService.hash_password(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role=role,
            real_name=real_name,
            phone=phone,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_user(db: Session, user_id: int, **kwargs) -> Optional[User]:
        """更新用户"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        if "password" in kwargs:
            kwargs["hashed_password"] = AuthService.hash_password(kwargs.pop("password"))
        for key, value in kwargs.items():
            setattr(user, key, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_current_user(token: str, db: Session) -> Optional[User]:
        """从token获取当前用户"""
        payload = AuthService.verify_token(token, "access")
        if not payload:
            return None
        username = payload.get("sub")
        if not username:
            return None
        return db.query(User).filter(User.username == username).first()


# Module-level aliases for backward compatibility
create_user = AuthService.create_user
update_user = AuthService.update_user
get_current_user = AuthService.get_current_user
verify_password = AuthService.verify_password
get_password_hash = AuthService.hash_password
create_access_token = AuthService.create_access_token
authenticate_user = AuthService.authenticate_user