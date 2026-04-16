from typing import Generator, Callable, TypeVar, ParamSpec
from functools import wraps
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.core.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """数据库会话依赖函数"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 类型变量用于装饰器
P = ParamSpec('P')
T = TypeVar('T')

def with_db(func: Callable[P, T]) -> Callable[P, T]:
    """
    装饰器：自动处理数据库会话。
    如果 db 参数为 None，自动创建并管理会话生命周期。

    用法:
        @with_db
        def get_user(user_id: int, db: Session = None):
            return db.query(User).filter(User.id == user_id).first()
    """
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        db = kwargs.get('db')
        if db is None:
            db = SessionLocal()
            try:
                kwargs['db'] = db
                return func(*args, **kwargs)
            finally:
                db.close()
        return func(*args, **kwargs)
    return wrapper
