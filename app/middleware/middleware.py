from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.monitoring.metrics import record_request, increment_active_users, decrement_active_users
from app.core.logging import logger
import time

class MetricsMiddleware(BaseHTTPMiddleware):
    """监控中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 增加活跃用户数
        increment_active_users()

        response = await call_next(request)

        # 记录请求指标
        duration = time.time() - start_time
        record_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
            duration=duration
        )

        # 减少活跃用户数
        decrement_active_users()

        return response

class LoggingMiddleware(BaseHTTPMiddleware):
    """日志中间件"""

    async def dispatch(self, request: Request, call_next):
        logger.info(f"Request: {request.method} {request.url}")

        response = await call_next(request)

        logger.info(f"Response: {response.status_code} for {request.method} {request.url}")

        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """简单的限流中间件"""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.user_requests = {}

    async def dispatch(self, request: Request, call_next):
        # 简单的IP限流实现
        client_ip = request.client.host
        current_time = time.time()

        # 清理过期的记录
        if client_ip in self.user_requests:
            self.user_requests[client_ip] = [
                t for t in self.user_requests[client_ip]
                if current_time - t < 60
            ]

        # 检查限流
        if client_ip in self.user_requests and len(self.user_requests[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return Response(status_code=429)

        # 记录请求
        if client_ip not in self.user_requests:
            self.user_requests[client_ip] = []
        self.user_requests[client_ip].append(current_time)

        return await call_next(request)