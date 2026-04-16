from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    username: str = Column(String(50), unique=True, index=True)
    email: str = Column(String(100), unique=True, index=True)
    real_name: Optional[str] = Column(String(100))
    phone: Optional[str] = Column(String(20))
    hashed_password: str = Column(String(255))
    role: str = Column(String(50), default="user")
    is_active: bool = Column(Boolean, default=True)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
