"""
OpenTelemetry 追踪中间件

功能：
1. 自动为每个请求创建 Root Span
2. 记录请求/响应元数据
3. 捕获异常并标记 Span 状态
4. 与 structlog 日志关联
"""

import time

import structlog
from fastapi import Request, Response
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """
    OpenTelemetry 追踪中间件

    为每个 HTTP 请求创建 Root Span，记录请求元数据和性能指标
    """

    def __init__(self, app, tracer: trace.Tracer | None = None):
        super().__init__(app)
        self.tracer = tracer or trace.get_tracer(__name__)

    async def dispatch(self, request: Request, call_next):
        # 创建 Span 名称：HTTP Method + Path
        span_name = f"{request.method} {request.url.path}"

        with self.tracer.start_as_current_span(span_name) as span:
            # 记录请求元数据
            span.set_attributes(
                {
                    "http.method": request.method,
                    "http.url": str(request.url),
                    "http.scheme": request.url.scheme,
                    "http.host": request.url.hostname or "unknown",
                    "http.target": request.url.path,
                    "http.user_agent": request.headers.get("user-agent", "unknown"),
                    "http.client_ip": request.client.host if request.client else "unknown",
                }
            )

            # 记录查询参数（敏感参数需过滤）
            if request.query_params:
                # 过滤敏感参数
                safe_params = {k: v for k, v in request.query_params.items() if k not in {"token", "password", "api_key"}}
                if safe_params:
                    span.set_attribute("http.query_params", str(safe_params))

            start_time = time.time()

            try:
                # 执行请求
                response: Response = await call_next(request)

                # 记录响应元数据
                duration = time.time() - start_time
                span.set_attributes(
                    {
                        "http.status_code": response.status_code,
                        "http.response_content_length": response.headers.get("content-length", 0),
                        "http.duration_ms": round(duration * 1000, 2),
                    }
                )

                # 设置 Span 状态
                if 200 <= response.status_code < 400:
                    span.set_status(Status(StatusCode.OK))
                elif 400 <= response.status_code < 500:
                    span.set_status(Status(StatusCode.ERROR, f"Client error: {response.status_code}"))
                else:
                    span.set_status(Status(StatusCode.ERROR, f"Server error: {response.status_code}"))

                # 添加 Trace ID 到响应头（便于前端关联）
                trace_id = format(span.get_span_context().trace_id, "032x")
                response.headers["X-Trace-Id"] = trace_id

                # 结构化日志（自动包含 trace_id）
                logger.info(
                    "http_request_completed",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round(duration * 1000, 2),
                )

                return response

            except Exception as e:
                # 记录异常
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))

                logger.error(
                    "http_request_failed",
                    method=request.method,
                    path=request.url.path,
                    error=str(e),
                    exc_info=True,
                )

                raise
