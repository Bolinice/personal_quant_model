"""
审计日志装饰器

提供便捷的装饰器用于自动记录关键操作
"""

import functools
from typing import Any, Callable

from fastapi import Request

from app.core.audit import AuditService


def audit_log(
    action: str,
    resource_type: str | None = None,
    description: str | None = None,
    extract_resource_id: Callable[[Any], str] | None = None,
):
    """
    审计日志装饰器

    自动记录函数调用的审计日志

    Args:
        action: 操作类型（如 "user.login", "strategy.create"）
        resource_type: 资源类型（如 "strategy", "portfolio"）
        description: 操作描述
        extract_resource_id: 从函数返回值中提取资源 ID 的函数

    Example:
        @audit_log(
            action="strategy.create",
            resource_type="strategy",
            description="创建新策略",
            extract_resource_id=lambda result: str(result.id)
        )
        async def create_strategy(request: Request, db: Session, data: StrategyCreate):
            # ... 创建策略逻辑
            return strategy
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 执行原函数
            result = await func(*args, **kwargs)

            # 提取请求对象和数据库会话
            request: Request | None = None
            db = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif hasattr(arg, "query"):  # 检查是否是 SQLAlchemy Session
                    db = arg

            # 从 kwargs 中查找
            if request is None:
                request = kwargs.get("request")
            if db is None:
                db = kwargs.get("db")

            # 如果找到数据库会话，记录审计日志
            if db is not None:
                audit_service = AuditService(db)

                # 提取用户信息
                user_id = None
                username = None
                if request and hasattr(request.state, "user"):
                    user = request.state.user
                    user_id = getattr(user, "id", None)
                    username = getattr(user, "username", None)

                # 提取 IP 地址
                ip_address = None
                if request and request.client:
                    ip_address = request.client.host

                # 提取资源 ID
                resource_id = None
                if extract_resource_id and result:
                    try:
                        resource_id = extract_resource_id(result)
                    except Exception:
                        pass  # 忽略提取失败

                # 提取请求信息
                method = None
                path = None
                if request:
                    method = request.method
                    path = str(request.url.path)

                # 记录审计日志
                audit_service.log(
                    action=action,
                    user_id=user_id,
                    username=username,
                    ip_address=ip_address,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    description=description,
                    method=method,
                    path=path,
                )

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 执行原函数
            result = func(*args, **kwargs)

            # 提取请求对象和数据库会话
            request: Request | None = None
            db = None

            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif hasattr(arg, "query"):  # 检查是否是 SQLAlchemy Session
                    db = arg

            # 从 kwargs 中查找
            if request is None:
                request = kwargs.get("request")
            if db is None:
                db = kwargs.get("db")

            # 如果找到数据库会话，记录审计日志
            if db is not None:
                audit_service = AuditService(db)

                # 提取用户信息
                user_id = None
                username = None
                if request and hasattr(request.state, "user"):
                    user = request.state.user
                    user_id = getattr(user, "id", None)
                    username = getattr(user, "username", None)

                # 提取 IP 地址
                ip_address = None
                if request and request.client:
                    ip_address = request.client.host

                # 提取资源 ID
                resource_id = None
                if extract_resource_id and result:
                    try:
                        resource_id = extract_resource_id(result)
                    except Exception:
                        pass  # 忽略提取失败

                # 提取请求信息
                method = None
                path = None
                if request:
                    method = request.method
                    path = str(request.url.path)

                # 记录审计日志
                audit_service.log(
                    action=action,
                    user_id=user_id,
                    username=username,
                    ip_address=ip_address,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    description=description,
                    method=method,
                    path=path,
                )

            return result

        # 根据函数类型返回对应的包装器
        if functools.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
