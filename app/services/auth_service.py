"""
认证服务
实现JWT认证、refresh token机制、密码强度校验
符合ADD 11节安全规范
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from jose import JWTError, jwt

from app.core.config import settings
from app.core.logging import logger
from app.core.token_blacklist import get_token_blacklist
from app.models.user import APIKey, User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class AuthService:
    """认证服务"""

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
        """创建访问令牌"""
        to_encode = data.copy()
        expire = datetime.now(tz=UTC) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        # 在payload中嵌入type字段，防止access token被当作refresh token滥用
        to_encode.update({"exp": expire, "type": "access"})
        # HS256对称签名 — 密钥由settings.SECRET_KEY统一管理，适用于单体应用；分布式场景需考虑RS256非对称签名
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """创建刷新令牌"""
        to_encode = data.copy()
        expire = datetime.now(tz=UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        # refresh token与access token使用相同密钥和算法，仅通过type和exp区分用途
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> dict | None:
        """
        验证令牌
        通过type字段区分access/refresh，防止用refresh token调用业务接口

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
    def refresh_access_token(refresh_token: str) -> tuple[str, str] | None:
        """
        使用refresh token刷新access token
        同时签发新的refresh token（轮转策略），旧token加入黑名单

        Returns:
            (new_access_token, new_refresh_token) 或 None
        """
        # 检查黑名单（使用Redis）
        blacklist = get_token_blacklist()
        if blacklist.is_blacklisted(refresh_token):
            logger.warning("Attempted to use blacklisted refresh token")
            return None

        payload = AuthService.verify_token(refresh_token, "refresh")
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        # 将旧refresh token加入黑名单（使用Redis，自动过期）
        blacklist.add(refresh_token)

        new_data = {"sub": user_id, "role": payload.get("role", "user")}
        new_access = AuthService.create_access_token(new_data)
        new_refresh = AuthService.create_refresh_token(new_data)
        return new_access, new_refresh

    @staticmethod
    def hash_password(password: str) -> str:
        # bcrypt自适应哈希 — 内置salt，gensalt()默认cost factor=12，兼顾安全与性能
        import bcrypt

        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        import bcrypt

        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """
        密码强度校验
        - 至少8位
        - 包含大小写字母
        - 包含数字
        """
        if len(password) < 8:
            return False, "密码至少8位"
        if not re.search(r"[A-Z]", password):
            return False, "密码需包含大写字母"
        if not re.search(r"[a-z]", password):
            return False, "密码需包含小写字母"
        if not re.search(r"\d", password):
            return False, "密码需包含数字"
        return True, ""

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> User | None:
        """用户认证"""
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not user.is_active:
            return None  # 不区分"用户不存在"和"用户已禁用"，防止枚举攻击
        if not AuthService.verify_password(password, user.hashed_password):
            return None

        # 更新登录信息
        user.last_login_at = datetime.now(tz=UTC)
        user.login_count = (user.login_count or 0) + 1
        db.commit()

        return user

    @staticmethod
    def create_api_key(db: Session, user_id: int, name: str | None = None) -> dict:
        """创建API Key"""
        # 前缀qpm_标识本平台API Key，便于日志识别和来源追溯
        api_key = f"qpm_{secrets.token_hex(16)}"
        secret = secrets.token_hex(32)
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()  # 只存哈希，防止数据库泄露导致secret暴露

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
            "api_secret": secret,  # 只在创建时返回一次，后续无法再获取原文
            "name": name,
        }

    @staticmethod
    def verify_api_key(db: Session, api_key: str) -> APIKey | None:
        """验证API Key"""
        key_record = (
            db.query(APIKey)
            .filter(
                APIKey.api_key == api_key,
                APIKey.status == "active",
            )
            .first()
        )

        if key_record:
            key_record.last_used_at = datetime.now(tz=UTC)
            db.commit()

        return key_record

    @staticmethod
    def generate_reset_token(db: Session, email: str) -> str | None:
        """生成密码重置令牌"""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None

        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.now(tz=UTC) + timedelta(hours=1)  # 重置令牌1小时有效，缩短窗口降低泄露风险
        db.commit()

        logger.info(f"Password reset token generated for {email}")
        # 生产环境应发送邮件，暂时仅记录日志
        return token

    @staticmethod
    def reset_password_with_token(db: Session, token: str, new_password: str) -> tuple[bool, str]:
        """使用重置令牌重置密码

        Returns:
            (success, error_message) - 成功时 error_message 为空字符串
        """
        user = db.query(User).filter(User.reset_token == token).first()
        if not user:
            return False, "重置令牌无效"

        if user.reset_token_expires and user.reset_token_expires < datetime.now(tz=UTC):
            # 令牌已过期，清除 — 防止过期token被反复尝试
            user.reset_token = None
            user.reset_token_expires = None
            db.commit()
            return False, "重置令牌已过期"

        valid, msg = AuthService.validate_password_strength(new_password)
        if not valid:
            return False, msg

        user.hashed_password = AuthService.hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        db.commit()
        return True, ""

    # ==================== 兼容旧接口 ====================

    @staticmethod
    def create_user(
        db: Session,
        username: str,
        email: str,
        password: str,
        role: str = "user",
        real_name: str | None = None,
        phone: str | None = None,
    ) -> User:
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
    def update_user(db: Session, user_id: int, **kwargs) -> User | None:
        """更新用户"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        if "password" in kwargs:
            kwargs["hashed_password"] = AuthService.hash_password(
                kwargs.pop("password")
            )  # 明文password不入库，转为哈希存储
        for key, value in kwargs.items():
            setattr(user, key, value)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_current_user(token: str, db: Session) -> User | None:
        """从token获取当前用户"""
        payload = AuthService.verify_token(token, "access")
        if not payload:
            return None
        username = payload.get("sub")
        if not username:
            return None
        return db.query(User).filter(User.username == username).first()


# Module-level aliases for backward compatibility — 旧代码直接调用函数，新代码应使用AuthService类方法
create_user = AuthService.create_user
update_user = AuthService.update_user
get_current_user = AuthService.get_current_user
verify_password = AuthService.verify_password
get_password_hash = AuthService.hash_password
create_access_token = AuthService.create_access_token
authenticate_user = AuthService.authenticate_user
