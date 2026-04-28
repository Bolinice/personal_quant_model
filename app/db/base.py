from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base_class import Base  # noqa: F401 — re-exported for backward compatibility

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    pool_recycle=1800,
    pool_timeout=30,
    connect_args={"connect_timeout": 10},
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
        if "db" in kwargs and kwargs["db"] is not None:
            return func(*args, **kwargs)
        db = SessionLocal()
        try:
            kwargs["db"] = db
            return func(*args, **kwargs)
        finally:
            db.close()

    return wrapper
