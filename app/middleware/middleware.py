"""
中间件模块
- LoggingMiddleware: 请求日志记录
- MetricsMiddleware: Prometheus 指标收集
- RateLimitMiddleware: 内存滑动窗口限流（开发/降级用）
- RedisRateLimitMiddleware: Redis 滑动窗口限流（生产推荐）
- ComplianceMiddleware: 合规免责声明自动注入
- SlowQueryMiddleware: 慢查询监控
"""

import time
import json
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.compliance import add_disclaimer, DISCLAIMER_SIMPLE
from app.monitoring.metrics import REQUEST_DURATION, REQUEST_COUNT, ACTIVE_USERS

logger = logging.getLogger(__name__)


# ============================================================
# 日志中间件
# ============================================================

class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        logger.info(f"Request: {request.method} {request.url.path}")
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            f"Response: {request.method} {request.url.path} "
            f"Status: {response.status_code} "
            f"Time: {process_time:.3f}s"
        )
        response.headers["X-Process-Time"] = str(process_time)
        return response


# ============================================================
# Prometheus 指标中间件
# ============================================================

class MetricsMiddleware(BaseHTTPMiddleware):
    """Prometheus 指标收集中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        REQUEST_DURATION.observe(process_time)
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        ).inc()
        return response


# ============================================================
# 合规免责声明中间件
# ============================================================

# 需要注入免责声明的路由前缀 → 页面类型映射
COMPLIANCE_ROUTE_MAP = {
    "/api/v1/backtests": "backtest",
    "/api/v1/portfolios": "portfolio",
    "/api/v1/timing": "signal",
    "/api/v1/factors": "factor",
    "/api/v1/performance": "backtest",
    "/api/v1/simulated-portfolios": "portfolio",
}


class ComplianceMiddleware(BaseHTTPMiddleware):
    """合规免责声明自动注入中间件

    在含收益/回测/组合数据的API响应中自动注入 disclaimer 字段。
    根据路由前缀自动判断 page_type。
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 判断当前路由是否需要注入免责声明
        page_type = None
        path = request.url.path
        for prefix, ptype in COMPLIANCE_ROUTE_MAP.items():
            if path.startswith(prefix):
                page_type = ptype
                break

        if page_type is None:
            return response

        # 仅处理 JSON 响应
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # 读取响应体，注入免责声明
        try:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            data = json.loads(body)
            if isinstance(data, dict):
                data = add_disclaimer(data, page_type)

            new_body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            return Response(
                content=new_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type="application/json; charset=utf-8",
            )
        except Exception as e:
            logger.warning(f"ComplianceMiddleware 注入失败: {e}")
            return response


# ============================================================
# 慢查询监控中间件
# ============================================================

SLOW_QUERY_THRESHOLD = 1.0  # 秒


class SlowQueryMiddleware(BaseHTTPMiddleware):
    """慢查询监控中间件

    超过阈值的请求自动记录告警日志。
    """

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start

        if elapsed > SLOW_QUERY_THRESHOLD:
            logger.warning(
                "Slow query detected",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "elapsed_ms": round(elapsed * 1000, 1),
                    "status_code": response.status_code,
                },
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """内存滑动窗口限流中间件（开发/降级用）"""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._requests: Dict[str, List[float]] = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = 60  # 1分钟窗口

        # 清理过期记录
        if client_ip in self._requests:
            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if now - t < window
            ]
        else:
            self._requests[client_ip] = []

        # 检查限流
        if len(self._requests[client_ip]) >= self.requests_per_minute:
            return Response(
                content='{"code":429,"message":"请求过于频繁，请稍后再试"}',
                status_code=429,
                media_type="application/json",
            )

        self._requests[client_ip].append(now)
        response = await call_next(request)
        return response


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    """Redis 滑动窗口限流中间件（生产推荐）

    使用 Redis sorted set 实现滑动窗口限流：
    - key: ratelimit:{client_ip}
    - member: timestamp
    - score: timestamp
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        redis_url: Optional[str] = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._redis = None
        self._redis_url = redis_url
        self._fallback = RateLimitMiddleware(app, requests_per_minute)

    def _get_redis(self):
        """懒加载 Redis 连接"""
        if self._redis is not None:
            return self._redis

        try:
            import redis

            url = self._redis_url or "redis://localhost:6379/0"
            self._redis = redis.from_url(url, decode_responses=True)
            self._redis.ping()
            logger.info("Redis 限流中间件已连接")
            return self._redis
        except Exception as e:
            logger.warning(f"Redis 连接失败，降级为内存限流: {e}")
            self._redis = None
            return None

    async def dispatch(self, request: Request, call_next):
        redis_client = self._get_redis()

        # Redis 不可用时降级为内存限流
        if redis_client is None:
            return await self._fallback.dispatch(request, call_next)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = 60  # 1分钟窗口
        key = f"ratelimit:{client_ip}"

        try:
            pipe = redis_client.pipeline()
            # 移除窗口外的记录
            pipe.zremrangebyscore(key, 0, now - window)
            # 添加当前请求
            pipe.zadd(key, {str(now): now})
            # 获取窗口内请求数
            pipe.zcard(key)
            # 设置过期时间（防止冷键堆积）
            pipe.expire(key, window)
            results = pipe.execute()

            request_count = results[2]
            if request_count > self.requests_per_minute:
                return Response(
                    content='{"code":429,"message":"请求过于频繁，请稍后再试"}',
                    status_code=429,
                    media_type="application/json",
                )
        except Exception as e:
            logger.warning(f"Redis 限流异常，放行请求: {e}")

        response = await call_next(request)
        return response
