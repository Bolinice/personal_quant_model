"""
OpenTelemetry 分布式追踪和可观测性配置

核心功能：
1. 分布式追踪（Distributed Tracing）
2. 日志与追踪关联（Trace Context Injection）
3. 自动化仪表（Auto-instrumentation）
4. 指标收集（Metrics）
"""

import logging
from contextlib import contextmanager
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# ==================== 全局配置 ====================

_tracer_provider: TracerProvider | None = None
_tracer: trace.Tracer | None = None


def setup_telemetry(
    service_name: str = "quant-platform",
    environment: str = "development",
    otlp_endpoint: str | None = None,
    enable_console_export: bool = False,
) -> None:
    """
    初始化 OpenTelemetry 追踪系统

    Args:
        service_name: 服务名称
        environment: 运行环境（development/staging/production）
        otlp_endpoint: OTLP Collector 端点（如 http://localhost:4317）
        enable_console_export: 是否启用控制台导出（调试用）
    """
    global _tracer_provider, _tracer

    # 创建资源标识
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "1.0.0",
            "deployment.environment": environment,
        }
    )

    # 创建 TracerProvider
    _tracer_provider = TracerProvider(resource=resource)

    # 添加导出器
    if otlp_endpoint:
        # OTLP 导出器（生产环境）
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        _tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    if enable_console_export:
        # 控制台导出器（开发环境）
        console_exporter = ConsoleSpanExporter()
        _tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # 设置全局 TracerProvider
    trace.set_tracer_provider(_tracer_provider)

    # 获取 Tracer 实例
    _tracer = trace.get_tracer(__name__)

    logging.info(
        f"OpenTelemetry initialized: service={service_name}, env={environment}, otlp={otlp_endpoint or 'disabled'}"
    )


def instrument_fastapi(app: Any) -> None:
    """
    自动化仪表 FastAPI 应用

    Args:
        app: FastAPI 应用实例
    """
    FastAPIInstrumentor.instrument_app(app)
    logging.info("FastAPI instrumentation enabled")


def get_tracer() -> trace.Tracer:
    """获取全局 Tracer 实例"""
    if _tracer is None:
        raise RuntimeError("Telemetry not initialized. Call setup_telemetry() first.")
    return _tracer


# ==================== Trace Context 注入到日志 ====================


def add_trace_context(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """
    structlog 处理器：自动注入 Trace ID 和 Span ID

    用法：
        structlog.configure(
            processors=[
                add_trace_context,
                ...
            ]
        )
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
        event_dict["trace_flags"] = f"{ctx.trace_flags:02x}"
    return event_dict


# ==================== 手动追踪装饰器 ====================


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None):
    """
    上下文管理器：创建自定义 Span

    用法：
        with trace_span("calculate_factor", {"factor_id": "momentum_20d"}):
            result = calculate_momentum(data)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            span.set_attributes(attributes)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


def traced(name: str | None = None, attributes: dict[str, Any] | None = None):
    """
    函数装饰器：自动创建 Span

    用法：
        @traced("backtest_strategy")
        def run_backtest(strategy_id: str):
            ...

        @traced(attributes={"layer": "data"})
        def fetch_market_data():
            ...
    """
    import functools

    def decorator(func):
        span_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with trace_span(span_name, attributes):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# ==================== 结构化日志增强 ====================


def configure_structlog_with_tracing(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    配置 structlog + OpenTelemetry 集成

    Args:
        log_level: 日志级别
        log_format: 输出格式（json/text）
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_trace_context,  # 注入 Trace ID/Span ID
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 配置标准 logging
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            *shared_processors,
            renderer,
        ],
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


# ==================== 便捷函数 ====================


def get_current_trace_id() -> str | None:
    """获取当前 Trace ID（用于日志关联）"""
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        return format(ctx.trace_id, "032x")
    return None


def get_current_span_id() -> str | None:
    """获取当前 Span ID"""
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        return format(ctx.span_id, "016x")
    return None


# ==================== 示例用法 ====================

if __name__ == "__main__":
    # 初始化
    setup_telemetry(
        service_name="quant-platform",
        environment="development",
        enable_console_export=True,
    )
    configure_structlog_with_tracing(log_format="json")

    logger = structlog.get_logger()

    # 手动 Span
    with trace_span("example_operation", {"user_id": "12345"}):
        logger.info("Processing request", request_id="req-001")

        # 嵌套 Span
        with trace_span("database_query"):
            logger.info("Querying database", table="factors")

    # 装饰器 Span
    @traced("calculate_metrics")
    def calculate():
        logger.info("Calculating metrics")
        return {"sharpe": 1.5}

    calculate()
