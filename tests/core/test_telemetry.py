"""
OpenTelemetry 追踪系统测试

测试覆盖：
1. Telemetry 初始化和配置
2. Trace Context 注入到日志
3. 手动 Span 创建（上下文管理器）
4. 装饰器自动追踪
5. FastAPI 中间件集成
6. 异常处理和状态码
"""

import json
import logging
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core.telemetry import (
    add_trace_context,
    configure_structlog_with_tracing,
    get_current_span_id,
    get_current_trace_id,
    get_tracer,
    setup_telemetry,
    trace_span,
    traced,
)
from app.middleware.tracing import TracingMiddleware


# ==================== Fixtures ====================


@pytest.fixture
def in_memory_exporter():
    """内存 Span 导出器（用于测试）"""
    exporter = InMemorySpanExporter()
    yield exporter
    exporter.clear()


@pytest.fixture
def tracer_provider(in_memory_exporter):
    """测试用 TracerProvider（每个测试独立）"""
    # 强制重置全局 TracerProvider（仅用于测试）
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = None

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(in_memory_exporter))
    trace.set_tracer_provider(provider)

    yield provider

    # 清理：强制重置以便下一个测试
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace._TRACER_PROVIDER = None


@pytest.fixture
def test_tracer(tracer_provider):
    """测试用 Tracer"""
    return trace.get_tracer(__name__)


@pytest.fixture
def reset_telemetry():
    """重置全局状态"""
    import app.core.telemetry as telemetry_module

    telemetry_module._tracer_provider = None
    telemetry_module._tracer = None
    yield
    telemetry_module._tracer_provider = None
    telemetry_module._tracer = None


# ==================== 测试：Telemetry 初始化 ====================


class TestTelemetrySetup:
    """测试 OpenTelemetry 初始化"""

    def test_setup_telemetry_basic(self, reset_telemetry):
        """测试基本初始化"""
        setup_telemetry(service_name="test-service", environment="test", enable_console_export=True)

        tracer = get_tracer()
        assert tracer is not None

        # 验证可以创建 Span
        with tracer.start_as_current_span("test_span") as span:
            assert span.is_recording()

    def test_setup_telemetry_with_otlp(self, reset_telemetry):
        """测试 OTLP 导出器配置"""
        with patch("app.core.telemetry.OTLPSpanExporter") as mock_exporter:
            setup_telemetry(
                service_name="test-service",
                environment="production",
                otlp_endpoint="http://localhost:4317",
            )

            mock_exporter.assert_called_once_with(endpoint="http://localhost:4317", insecure=True)

    def test_get_tracer_before_setup(self, reset_telemetry):
        """测试未初始化时获取 Tracer 抛出异常"""
        with pytest.raises(RuntimeError, match="Telemetry not initialized"):
            get_tracer()


# ==================== 测试：Trace Context 注入 ====================


class TestTraceContextInjection:
    """测试 Trace ID/Span ID 注入到日志"""

    def test_add_trace_context_with_active_span(self, test_tracer):
        """测试活跃 Span 时注入 Trace Context"""
        with test_tracer.start_as_current_span("test_span") as span:
            event_dict = {"message": "test log"}
            result = add_trace_context(None, None, event_dict)

            ctx = span.get_span_context()
            assert result["trace_id"] == format(ctx.trace_id, "032x")
            assert result["span_id"] == format(ctx.span_id, "016x")
            assert "trace_flags" in result

    def test_add_trace_context_without_span(self):
        """测试无活跃 Span 时不注入"""
        event_dict = {"message": "test log"}
        result = add_trace_context(None, None, event_dict)

        assert "trace_id" not in result
        assert "span_id" not in result

    def test_structlog_integration(self, test_tracer):
        """测试 structlog 集成"""
        # 配置 structlog 输出到内存
        output = StringIO()

        # 保存旧配置
        old_config = structlog.get_config()

        structlog.configure(
            processors=[
                add_trace_context,
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.PrintLoggerFactory(file=output),
            cache_logger_on_first_use=False,
        )

        try:
            logger = structlog.get_logger()

            with test_tracer.start_as_current_span("test_span"):
                logger.info("test message", key="value")

            log_output = output.getvalue()
            log_data = json.loads(log_output)

            assert "trace_id" in log_data
            assert "span_id" in log_data
            assert log_data["event"] == "test message"
            assert log_data["key"] == "value"
        finally:
            # 恢复旧配置
            structlog.configure(**old_config)


# ==================== 测试：手动 Span 创建 ====================


class TestManualSpanCreation:
    """测试手动创建 Span"""

    def test_trace_span_basic(self, test_tracer, in_memory_exporter):
        """测试基本 Span 创建"""
        import app.core.telemetry as telemetry_module

        telemetry_module._tracer = test_tracer

        with trace_span("test_operation"):
            pass

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test_operation"

    def test_trace_span_with_attributes(self, test_tracer, in_memory_exporter):
        """测试带属性的 Span"""
        import app.core.telemetry as telemetry_module

        telemetry_module._tracer = test_tracer

        with trace_span("test_operation", {"user_id": "12345", "request_id": "req-001"}):
            pass

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["user_id"] == "12345"
        assert spans[0].attributes["request_id"] == "req-001"

    def test_trace_span_with_exception(self, test_tracer, in_memory_exporter):
        """测试异常捕获"""
        import app.core.telemetry as telemetry_module

        telemetry_module._tracer = test_tracer

        with pytest.raises(ValueError):
            with trace_span("test_operation"):
                raise ValueError("test error")

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR
        assert "test error" in spans[0].status.description

    def test_nested_spans(self, test_tracer, in_memory_exporter):
        """测试嵌套 Span"""
        import app.core.telemetry as telemetry_module

        telemetry_module._tracer = test_tracer

        with trace_span("parent_operation"):
            with trace_span("child_operation_1"):
                pass
            with trace_span("child_operation_2"):
                pass

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 3

        # 验证父子关系
        child_spans = [s for s in spans if "child" in s.name]
        parent_span = [s for s in spans if s.name == "parent_operation"][0]

        for child in child_spans:
            assert child.parent.span_id == parent_span.context.span_id


# ==================== 测试：装饰器自动追踪 ====================


class TestTracedDecorator:
    """测试 @traced 装饰器"""

    def test_traced_basic(self, test_tracer, in_memory_exporter):
        """测试基本装饰器用法"""
        import app.core.telemetry as telemetry_module

        telemetry_module._tracer = test_tracer

        @traced()
        def test_function():
            return "result"

        result = test_function()
        assert result == "result"

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert "test_function" in spans[0].name

    def test_traced_with_custom_name(self, test_tracer, in_memory_exporter):
        """测试自定义 Span 名称"""
        import app.core.telemetry as telemetry_module

        telemetry_module._tracer = test_tracer

        @traced("custom_operation")
        def test_function():
            return "result"

        test_function()

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "custom_operation"

    def test_traced_with_attributes(self, test_tracer, in_memory_exporter):
        """测试带属性的装饰器"""
        import app.core.telemetry as telemetry_module

        telemetry_module._tracer = test_tracer

        @traced(attributes={"layer": "data", "operation": "fetch"})
        def test_function():
            return "result"

        test_function()

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["layer"] == "data"
        assert spans[0].attributes["operation"] == "fetch"

    def test_traced_with_exception(self, test_tracer, in_memory_exporter):
        """测试装饰器异常处理"""
        import app.core.telemetry as telemetry_module

        telemetry_module._tracer = test_tracer

        @traced()
        def test_function():
            raise RuntimeError("test error")

        with pytest.raises(RuntimeError):
            test_function()

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR


# ==================== 测试：便捷函数 ====================


class TestUtilityFunctions:
    """测试便捷函数"""

    def test_get_current_trace_id(self, test_tracer):
        """测试获取当前 Trace ID"""
        with test_tracer.start_as_current_span("test_span") as span:
            trace_id = get_current_trace_id()
            expected_trace_id = format(span.get_span_context().trace_id, "032x")
            assert trace_id == expected_trace_id

    def test_get_current_trace_id_no_span(self):
        """测试无活跃 Span 时返回 None"""
        trace_id = get_current_trace_id()
        assert trace_id is None

    def test_get_current_span_id(self, test_tracer):
        """测试获取当前 Span ID"""
        with test_tracer.start_as_current_span("test_span") as span:
            span_id = get_current_span_id()
            expected_span_id = format(span.get_span_context().span_id, "016x")
            assert span_id == expected_span_id

    def test_get_current_span_id_no_span(self):
        """测试无活跃 Span 时返回 None"""
        span_id = get_current_span_id()
        assert span_id is None


# ==================== 测试：FastAPI 中间件 ====================


class TestTracingMiddleware:
    """测试 FastAPI 追踪中间件"""

    @pytest.fixture
    def app(self, test_tracer):
        """测试用 FastAPI 应用"""
        app = FastAPI()
        app.add_middleware(TracingMiddleware, tracer=test_tracer)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        @app.get("/error")
        async def error_endpoint():
            raise HTTPException(status_code=500, detail="Internal error")

        @app.get("/client-error")
        async def client_error_endpoint():
            raise HTTPException(status_code=400, detail="Bad request")

        return app

    def test_middleware_basic_request(self, app, in_memory_exporter):
        """测试基本请求追踪"""
        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Trace-Id" in response.headers

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "GET /test"
        assert spans[0].attributes["http.method"] == "GET"
        assert spans[0].attributes["http.status_code"] == 200
        assert spans[0].status.status_code == trace.StatusCode.OK

    def test_middleware_with_query_params(self, app, in_memory_exporter):
        """测试查询参数记录"""
        client = TestClient(app)
        response = client.get("/test?user_id=123&limit=10")

        assert response.status_code == 200

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert "user_id" in spans[0].attributes["http.query_params"]
        assert "limit" in spans[0].attributes["http.query_params"]

    def test_middleware_filters_sensitive_params(self, app, in_memory_exporter):
        """测试敏感参数过滤"""
        client = TestClient(app)
        response = client.get("/test?user_id=123&token=secret&password=pass123")

        assert response.status_code == 200

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        query_params = spans[0].attributes["http.query_params"]
        assert "user_id" in query_params
        assert "token" not in query_params
        assert "password" not in query_params

    def test_middleware_server_error(self, app, in_memory_exporter):
        """测试服务器错误追踪"""
        client = TestClient(app)
        response = client.get("/error")

        assert response.status_code == 500

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["http.status_code"] == 500
        assert spans[0].status.status_code == trace.StatusCode.ERROR

    def test_middleware_client_error(self, app, in_memory_exporter):
        """测试客户端错误追踪"""
        client = TestClient(app)
        response = client.get("/client-error")

        assert response.status_code == 400

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["http.status_code"] == 400
        assert spans[0].status.status_code == trace.StatusCode.ERROR

    def test_middleware_records_duration(self, app, in_memory_exporter):
        """测试请求耗时记录"""
        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert "http.duration_ms" in spans[0].attributes
        assert spans[0].attributes["http.duration_ms"] > 0


# ==================== 测试：集成场景 ====================


class TestIntegrationScenarios:
    """测试集成场景"""

    def test_end_to_end_tracing(self, test_tracer, in_memory_exporter):
        """测试端到端追踪流程"""
        import app.core.telemetry as telemetry_module

        telemetry_module._tracer = test_tracer

        @traced("service_layer")
        def service_function():
            with trace_span("database_query"):
                return "data"

        @traced("controller_layer")
        def controller_function():
            return service_function()

        result = controller_function()
        assert result == "data"

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 3

        # 验证 Span 层级关系
        controller_span = [s for s in spans if s.name == "controller_layer"][0]
        service_span = [s for s in spans if s.name == "service_layer"][0]
        db_span = [s for s in spans if s.name == "database_query"][0]

        assert service_span.parent.span_id == controller_span.context.span_id
        assert db_span.parent.span_id == service_span.context.span_id

    def test_trace_context_propagation(self, test_tracer):
        """测试 Trace Context 在调用链中传播"""
        import app.core.telemetry as telemetry_module

        telemetry_module._tracer = test_tracer

        trace_ids = []

        with trace_span("parent"):
            trace_ids.append(get_current_trace_id())
            with trace_span("child"):
                trace_ids.append(get_current_trace_id())

        # 同一调用链中 Trace ID 应该相同
        assert len(set(trace_ids)) == 1
