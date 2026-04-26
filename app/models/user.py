from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    username: str = Column(String(50), unique=True, index=True, nullable=False)
    email: str = Column(String(100), unique=True, index=True, nullable=False)
    real_name: Optional[str] = Column(String(100))
    phone: Optional[str] = Column(String(20))
    hashed_password: str = Column(String(255), nullable=False)
    role: str = Column(String(50), default="user")  # admin, researcher, pm, risk_manager, client, org_admin
    user_type: str = Column(String(20), default="user")  # admin, researcher, client
    org_id: Optional[int] = Column(Integer)  # 所属机构
    is_active: bool = Column(Boolean, default=True)
    is_superuser: bool = Column(Boolean, default=False)
    avatar_url: Optional[str] = Column(String(255))
    reset_token: Optional[str] = Column(String(255), nullable=True, comment='密码重置令牌')
    reset_token_expires: Optional[DateTime] = Column(DateTime, nullable=True, comment='重置令牌过期时间')
    last_login_at: Optional[DateTime] = Column(DateTime)
    login_count: int = Column(Integer, default=0)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class Role(Base):
    __tablename__ = "roles"

    id: int = Column(Integer, primary_key=True, index=True)
    role_name: str = Column(String(50), unique=True, nullable=False)
    role_code: str = Column(String(50), unique=True, nullable=False)
    description: Optional[str] = Column(String(200))
    created_at: DateTime = Column(DateTime, server_default=func.now())


class UserRole(Base):
    __tablename__ = "user_roles"

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, index=True, nullable=False)
    role_id: int = Column(Integer, index=True, nullable=False)
    created_at: DateTime = Column(DateTime, server_default=func.now())


class APIKey(Base):
    __tablename__ = "api_keys"

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, index=True, nullable=False)
    api_key: str = Column(String(100), unique=True, index=True, nullable=False)
    secret_hash: str = Column(String(255), nullable=False)
    name: Optional[str] = Column(String(100))
    status: str = Column(String(20), default="active")  # active, revoked
    expired_at: Optional[DateTime] = Column(DateTime)
    last_used_at: Optional[DateTime] = Column(DateTime)
    created_at: DateTime = Column(DateTime, server_default=func.now())
