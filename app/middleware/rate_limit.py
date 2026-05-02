"""
速率限制中间件

基于滑动窗口算法的速率限制，支持：
- 基于 IP 的限流
- 基于用户的限流
- 自定义限流规则
- Redis 后端（生产环境）
- 内存后端（开发/测试环境）
"""

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RateLimitExceeded(HTTPException):
    """速率限制超出异常"""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


class InMemoryRateLimiter:
    """内存速率限制器（开发/测试环境）"""

    def __init__(self):
        # key -> deque of timestamps
        self._requests: dict[str, deque[float]] = defaultdict(lambda: deque())

    def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """
        检查是否允许请求

        Args:
            key: 限流键（如 IP 地址）
            limit: 时间窗口内最大请求数
            window: 时间窗口（秒）

        Returns:
            (是否允许, 重试等待时间)
        """
        now = time.time()
        requests = self._requests[key]

        # 清理过期请求
        while requests and requests[0] < now - window:
            requests.popleft()

        # 检查是否超限
        if len(requests) >= limit:
            # 计算重试等待时间
            if requests:
                retry_after = int(requests[0] + window - now) + 1
            else:
                # 边界情况：limit=0 时，队列为空
                retry_after = window
            return False, retry_after

        # 记录当前请求
        requests.append(now)
        return True, 0

    def reset(self, key: str) -> None:
        """重置指定键的限流记录"""
        if key in self._requests:
            del self._requests[key]

    def clear(self) -> None:
        """清空所有限流记录"""
        self._requests.clear()


class RedisRateLimiter:
    """Redis 速率限制器（生产环境）"""

    def __init__(self, redis_client):
        """
        初始化 Redis 速率限制器

        Args:
            redis_client: Redis 客户端实例
        """
        self.redis = redis_client

    def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """
        检查是否允许请求（使用 Redis 滑动窗口）

        Args:
            key: 限流键
            limit: 时间窗口内最大请求数
            window: 时间窗口（秒）

        Returns:
            (是否允许, 重试等待时间)
        """
        now = time.time()
        redis_key = f"rate_limit:{key}"

        # 使用 Redis pipeline 提高性能
        pipe = self.redis.pipeline()

        # 清理过期请求
        pipe.zremrangebyscore(redis_key, 0, now - window)

        # 获取当前窗口内的请求数
        pipe.zcard(redis_key)

        # 添加当前请求
        pipe.zadd(redis_key, {str(now): now})

        # 设置过期时间
        pipe.expire(redis_key, window)

        results = pipe.execute()
        count = results[1]

        # 检查是否超限
        if count >= limit:
            # 获取最早的请求时间
            earliest = self.redis.zrange(redis_key, 0, 0, withscores=True)
            if earliest:
                retry_after = int(earliest[0][1] + window - now) + 1
                # 移除刚才添加的请求
                self.redis.zrem(redis_key, str(now))
                return False, retry_after

        return True, 0

    def reset(self, key: str) -> None:
        """重置指定键的限流记录"""
        redis_key = f"rate_limit:{key}"
        self.redis.delete(redis_key)

    def clear(self) -> None:
        """清空所有限流记录"""
        keys = self.redis.keys("rate_limit:*")
        if keys:
            self.redis.delete(*keys)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""

    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: InMemoryRateLimiter | RedisRateLimiter | None = None,
        default_limit: int = 100,
        default_window: int = 60,
        key_func: Callable[[Request], str] | None = None,
        exempt_paths: list[str] | None = None,
    ):
        """
        初始化速率限制中间件

        Args:
            app: ASGI 应用
            limiter: 速率限制器实例（默认使用内存限制器）
            default_limit: 默认限流数量
            default_window: 默认时间窗口（秒）
            key_func: 自定义键生成函数（默认使用客户端 IP）
            exempt_paths: 豁免路径列表
        """
        super().__init__(app)
        self.limiter = limiter or InMemoryRateLimiter()
        self.default_limit = default_limit
        self.default_window = default_window
        self.key_func = key_func or self._default_key_func
        self.exempt_paths = set(exempt_paths or [])

    def _default_key_func(self, request: Request) -> str:
        """默认键生成函数：使用客户端 IP"""
        if request.client:
            return f"ip:{request.client.host}"
        return "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并应用速率限制"""
        # 检查是否豁免
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # 生成限流键
        key = self.key_func(request)

        # 检查速率限制
        allowed, retry_after = self.limiter.is_allowed(
            key, self.default_limit, self.default_window
        )

        if not allowed:
            # 直接返回 429 响应，而不是抛出异常
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        # 执行请求
        response = await call_next(request)

        # 添加速率限制信息到响应头
        response.headers["X-RateLimit-Limit"] = str(self.default_limit)
        response.headers["X-RateLimit-Window"] = str(self.default_window)

        return response
