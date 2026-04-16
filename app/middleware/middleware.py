import functools
import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
from prometheus_client import Counter, Histogram, Gauge
import logging

logger = logging.getLogger(__name__)

# Prometheus metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')
active_connections = Gauge('http_active_connections', 'Active HTTP connections')
rate_limit_counts = Counter('rate_limit_exceeded_total', 'Rate limit exceeded', ['endpoint'])

# Rate limiter
class RateLimitMiddleware:
    def __init__(self, app, requests_per_minute: int = 60):
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)

    async def __call__(self, request: Request, call_next):
        client_ip = request.client.host
        current_time = time.time()

        # 清理过期请求
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < 60
        ]

        # 检查是否超过限制
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            rate_limit_counts.labels(endpoint=request.url.path).inc()
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )

        # 记录本次请求
        self.requests[client_ip].append(current_time)

        active_connections.inc()
        try:
            response = await call_next(request)
            return response
        finally:
            active_connections.dec()

# Logging middleware
class LoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        start_time = time.time()

        # 记录请求信息
        logger.info(f"Request: {request.method} {request.url.path}")

        # 处理请求
        response = await call_next(request)

        # 计算处理时间
        process_time = time.time() - start_time

        # 记录响应信息
        logger.info(
            f"Response: {request.method} {request.url.path} "
            f"Status: {response.status_code} "
            f"Time: {process_time:.3f}s"
        )

        # 添加处理时间到响应头
        response.headers["X-Process-Time"] = str(process_time)

        return response

# Metrics middleware
class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        start_time = time.time()

        # 处理请求
        response = await call_next(request)

        # 计算处理时间并记录指标
        process_time = time.time() - start_time
        request_duration.observe(process_time)
        request_count.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        return response
