"""
重试机制
========
提供统一的重试装饰器和策略

依赖: tenacity库（需添加到pyproject.toml）
"""

import logging
from functools import wraps
from typing import Callable, TypeVar

from sqlalchemy.exc import OperationalError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    after_log,
)

from app.core.exceptions import (
    DataSourceException,
    DatabaseDeadlockException,
    DatabaseConnectionException,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ==================== 网络请求重试 ====================


def retry_on_network_error(
    max_attempts: int = 3,
    min_wait: int = 2,
    max_wait: int = 10,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    网络请求重试装饰器

    适用场景：
    - Tushare/AKShare数据获取
    - HTTP API调用
    - 外部服务调用

    Args:
        max_attempts: 最大重试次数
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）

    Example:
        @retry_on_network_error(max_attempts=3)
        def fetch_tushare_data(ts_code: str):
            return ts_api.daily(ts_code=ts_code)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type((DataSourceException, ConnectionError, TimeoutError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        )(func)

    return decorator


# ==================== 数据库死锁重试 ====================


def retry_on_db_deadlock(
    max_attempts: int = 3,
    min_wait: float = 0.5,
    max_wait: int = 5,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    数据库死锁重试装饰器

    适用场景：
    - 数据库写操作
    - 事务操作

    Args:
        max_attempts: 最大重试次数
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）

    Example:
        @retry_on_db_deadlock(max_attempts=3)
        def update_factors(session: Session, factors: pd.DataFrame):
            session.bulk_insert_mappings(Factor, factors.to_dict('records'))
            session.commit()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=0.5, min=min_wait, max=max_wait),
            retry=retry_if_exception_type((DatabaseDeadlockException, OperationalError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        )(func)

    return decorator


# ==================== 数据库连接重试 ====================


def retry_on_db_connection_error(
    max_attempts: int = 5,
    min_wait: int = 1,
    max_wait: int = 10,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    数据库连接重试装饰器

    适用场景：
    - 数据库连接建立
    - 连接池获取连接

    Args:
        max_attempts: 最大重试次数
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）

    Example:
        @retry_on_db_connection_error(max_attempts=5)
        def get_db_connection():
            return engine.connect()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type((DatabaseConnectionException, OperationalError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        )(func)

    return decorator


# ==================== 通用重试装饰器 ====================


def retry_on_exception(
    exception_types: tuple[type[Exception], ...],
    max_attempts: int = 3,
    min_wait: int = 1,
    max_wait: int = 10,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    通用异常重试装饰器

    Args:
        exception_types: 需要重试的异常类型元组
        max_attempts: 最大重试次数
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）

    Example:
        @retry_on_exception((ValueError, KeyError), max_attempts=3)
        def risky_operation():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(exception_types),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        )(func)

    return decorator


# ==================== 手动重试辅助函数 ====================


def retry_with_backoff(
    func: Callable[..., T],
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    backoff_factor: float = 2.0,
    exception_types: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """
    手动重试函数（不使用装饰器）

    适用场景：
    - 需要在运行时动态决定是否重试
    - 需要在重试间执行额外逻辑

    Args:
        func: 要执行的函数
        max_attempts: 最大重试次数
        initial_wait: 初始等待时间（秒）
        backoff_factor: 退避因子
        exception_types: 需要重试的异常类型

    Returns:
        函数执行结果

    Raises:
        最后一次尝试的异常

    Example:
        result = retry_with_backoff(
            lambda: fetch_data(ts_code),
            max_attempts=3,
            exception_types=(DataSourceException,)
        )
    """
    import time

    last_exception = None
    wait_time = initial_wait

    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except exception_types as e:
            last_exception = e
            if attempt < max_attempts:
                logger.warning(
                    f"尝试 {attempt}/{max_attempts} 失败: {e}. "
                    f"等待 {wait_time:.1f}秒后重试..."
                )
                time.sleep(wait_time)
                wait_time *= backoff_factor
            else:
                logger.error(f"所有 {max_attempts} 次尝试均失败")

    # 抛出最后一次异常
    if last_exception:
        raise last_exception
    raise RuntimeError("重试失败但未捕获异常")


# ==================== Celery任务重试配置 ====================


# Celery任务重试配置（在任务定义时使用）
CELERY_RETRY_CONFIG = {
    "autoretry_for": (DataSourceException, DatabaseDeadlockException, DatabaseConnectionException),
    "retry_kwargs": {"max_retries": 3, "countdown": 60},  # 60秒后重试
    "retry_backoff": True,  # 启用指数退避
    "retry_backoff_max": 600,  # 最大退避时间10分钟
    "retry_jitter": True,  # 添加随机抖动，避免重试风暴
}

# 使用示例：
# @celery_app.task(bind=True, **CELERY_RETRY_CONFIG)
# def sync_stock_daily_task(self, ts_code: str, start_date: str):
#     ...
