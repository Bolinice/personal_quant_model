from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Optional
from app.core.config import settings
from app.core.logging import logger

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def with_db(func):
    """数据库会话装饰器 - 如果调用者未提供db则自动创建"""
    def wrapper(*args, **kwargs):
        if 'db' in kwargs and kwargs['db'] is not None:
            return func(*args, **kwargs)
        db = SessionLocal()
        try:
            kwargs['db'] = db
            return func(*args, **kwargs)
        finally:
            db.close()
    return wrapper


from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass