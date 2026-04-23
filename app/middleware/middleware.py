import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.monitoring.metrics import REQUEST_DURATION, REQUEST_COUNT, ACTIVE_USERS
from app.core.logging import logger

# Rate limiter
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        self._last_cleanup = time.time()

    def _cleanup_expired(self, current_time: float):
        """清理过期的请求记录，防止内存泄漏"""
        if current_time - self._last_cleanup > 60:
            expired_ips = [
                ip for ip, reqs in self.requests.items()
                if not reqs or current_time - reqs[-1] > 60
            ]
            for ip in expired_ips:
                del self.requests[ip]
            self._last_cleanup = current_time

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        self._cleanup_expired(current_time)

        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < 60
        ]

        if len(self.requests[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )

        self.requests[client_ip].append(current_time)

        ACTIVE_USERS.inc()
        try:
            response = await call_next(request)
            return response
        finally:
            ACTIVE_USERS.dec()

# Logging middleware
class LoggingMiddleware(BaseHTTPMiddleware):
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

# Metrics middleware
class MetricsMiddleware(BaseHTTPMiddleware):
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
