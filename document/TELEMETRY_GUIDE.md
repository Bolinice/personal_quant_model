# OpenTelemetry 分布式追踪指南

## 概述

本项目集成了 OpenTelemetry 分布式追踪系统，提供：
- **自动追踪**：FastAPI 请求自动创建 Span
- **手动追踪**：装饰器和上下文管理器支持
- **Trace ID 注入**：自动注入到 structlog 日志
- **灵活导出**：支持 OTLP、控制台等多种导出器

## 快速开始

### 1. 初始化 Telemetry

在 `app/main.py` 中初始化：

```python
from app.core.telemetry import setup_telemetry
from app.middleware.tracing import TracingMiddleware

# 初始化 OpenTelemetry
setup_telemetry(
    service_name="quant-model-api",
    environment="production",
    otlp_endpoint="http://localhost:4318",  # 可选，用于导出到 Jaeger/Tempo
    enable_console=False  # 生产环境关闭控制台输出
)

# 添加追踪中间件
app.add_middleware(TracingMiddleware)
```

### 2. 自动追踪 HTTP 请求

添加 `TracingMiddleware` 后，所有 HTTP 请求会自动创建 Span，记录：
- HTTP 方法、路径、状态码
- 查询参数
- 请求耗时
- Trace ID（注入到响应头 `X-Trace-Id`）

```bash
# 请求示例
curl -v http://localhost:8000/api/v1/factors

# 响应头包含
X-Trace-Id: 1234567890abcdef1234567890abcdef
```

### 3. 手动追踪函数

#### 使用装饰器

```python
from app.core.telemetry import traced

@traced(name="calculate_factor", attributes={"factor_type": "momentum"})
def calculate_momentum_factor(data):
    # 函数执行会自动创建 Span
    return data.pct_change(20)

# 自动使用函数名作为 Span 名称
@traced()
def process_data(df):
    return df.dropna()
```

#### 使用上下文管理器

```python
from app.core.telemetry import trace_span

def complex_calculation():
    with trace_span("data_loading", attributes={"source": "database"}):
        data = load_data()
    
    with trace_span("feature_engineering"):
        features = engineer_features(data)
    
    with trace_span("model_training", attributes={"model": "xgboost"}):
        model = train_model(features)
    
    return model
```

### 4. Trace ID 注入到日志

Trace ID 会自动注入到 structlog 日志上下文：

```python
import structlog

logger = structlog.get_logger()

@traced()
def process_order(order_id):
    logger.info("processing_order", order_id=order_id)
    # 日志输出：
    # {"event": "processing_order", "order_id": 123, "trace_id": "...", "span_id": "..."}
```

### 5. 获取当前 Trace ID

```python
from app.core.telemetry import get_current_trace_id, get_current_span_id

trace_id = get_current_trace_id()  # 返回 32 字符十六进制字符串
span_id = get_current_span_id()    # 返回 16 字符十六进制字符串
```

## 配置选项

### 环境变量

```bash
# OTLP 导出端点（可选）
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

# 服务名称
OTEL_SERVICE_NAME=quant-model-api

# 环境标识
DEPLOYMENT_ENVIRONMENT=production
```

### 初始化参数

```python
setup_telemetry(
    service_name="quant-model-api",      # 服务名称
    environment="production",             # 环境标识（dev/staging/production）
    otlp_endpoint="http://localhost:4318",  # OTLP 导出端点（可选）
    enable_console=False                  # 是否启用控制台导出（开发环境用）
)
```

## 与 Jaeger 集成

### 1. 启动 Jaeger（Docker）

```bash
docker run -d --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

### 2. 配置应用

```python
setup_telemetry(
    service_name="quant-model-api",
    environment="production",
    otlp_endpoint="http://localhost:4318"  # Jaeger OTLP 端点
)
```

### 3. 查看追踪

访问 http://localhost:16686 打开 Jaeger UI，搜索 `quant-model-api` 服务的追踪记录。

## 与 Grafana Tempo 集成

### 1. 配置 Tempo

```yaml
# tempo.yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        http:
          endpoint: 0.0.0.0:4318

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/traces
```

### 2. 启动 Tempo

```bash
docker run -d --name tempo \
  -p 3200:3200 \
  -p 4318:4318 \
  -v $(pwd)/tempo.yaml:/etc/tempo.yaml \
  grafana/tempo:latest \
  -config.file=/etc/tempo.yaml
```

### 3. 配置应用

```python
setup_telemetry(
    service_name="quant-model-api",
    environment="production",
    otlp_endpoint="http://localhost:4318"  # Tempo OTLP 端点
)
```

## 最佳实践

### 1. Span 命名规范

- 使用动词+名词：`calculate_factor`, `load_data`, `train_model`
- 避免过于通用：`process` → `process_order`
- 保持一致性：同类操作使用相同前缀

### 2. 属性注入

```python
@traced(attributes={
    "factor_type": "momentum",
    "window": 20,
    "universe": "hs300"
})
def calculate_factor(data, window=20):
    # 关键参数注入到 Span 属性
    pass
```

### 3. 异常处理

异常会自动记录到 Span：

```python
@traced()
def risky_operation():
    try:
        result = may_fail()
    except ValueError as e:
        # 异常自动记录到 Span（status=ERROR）
        logger.error("operation_failed", error=str(e))
        raise
```

### 4. 嵌套 Span

```python
@traced(name="backtest_pipeline")
def run_backtest():
    with trace_span("load_data"):
        data = load_data()
    
    with trace_span("calculate_signals"):
        signals = calculate_signals(data)
    
    with trace_span("simulate_trading"):
        results = simulate_trading(signals)
    
    return results
```

### 5. 性能考虑

- **避免过度追踪**：不要为每个小函数都添加 `@traced`
- **批量操作**：循环内避免创建 Span，在循环外创建一个 Span
- **采样率**：生产环境可配置采样率（默认 100%）

```python
# ❌ 不推荐：循环内创建 Span
for item in items:
    with trace_span("process_item"):
        process(item)

# ✅ 推荐：循环外创建 Span
with trace_span("process_batch", attributes={"count": len(items)}):
    for item in items:
        process(item)
```

## 故障排查

### 1. Span 未导出

检查 OTLP 端点是否可达：

```bash
curl -v http://localhost:4318/v1/traces
```

### 2. Trace ID 未注入到日志

确保在 `setup_telemetry()` 之后调用 `add_trace_context()`：

```python
from app.core.telemetry import setup_telemetry, add_trace_context

setup_telemetry(...)
add_trace_context()  # 注入 Trace ID 到 structlog
```

### 3. 测试环境 TracerProvider 冲突

使用 `reset_tracer_provider` fixture：

```python
@pytest.fixture
def reset_tracer_provider():
    from opentelemetry.trace import _TRACER_PROVIDER_SET_ONCE, _TRACER_PROVIDER
    _TRACER_PROVIDER_SET_ONCE._done = False
    _TRACER_PROVIDER = None
    yield
    _TRACER_PROVIDER_SET_ONCE._done = False
    _TRACER_PROVIDER = None
```

## 示例：完整追踪流程

```python
from fastapi import FastAPI
from app.core.telemetry import setup_telemetry, traced, trace_span
from app.middleware.tracing import TracingMiddleware
import structlog

logger = structlog.get_logger()

# 初始化
app = FastAPI()
setup_telemetry(
    service_name="quant-model-api",
    environment="production",
    otlp_endpoint="http://localhost:4318"
)
app.add_middleware(TracingMiddleware)

# API 端点
@app.get("/api/v1/backtest")
async def run_backtest(strategy: str):
    # HTTP 请求自动创建根 Span
    logger.info("backtest_started", strategy=strategy)
    
    result = execute_backtest(strategy)
    
    logger.info("backtest_completed", strategy=strategy, sharpe=result["sharpe"])
    return result

# 业务逻辑
@traced(name="execute_backtest", attributes={"strategy": "momentum"})
def execute_backtest(strategy: str):
    with trace_span("load_data", attributes={"source": "database"}):
        data = load_data()
    
    with trace_span("calculate_signals"):
        signals = calculate_signals(data, strategy)
    
    with trace_span("simulate_trading"):
        results = simulate_trading(signals)
    
    return results

# 日志输出示例：
# {
#   "event": "backtest_started",
#   "strategy": "momentum",
#   "trace_id": "1234567890abcdef1234567890abcdef",
#   "span_id": "abcdef1234567890"
# }
```

## 参考资料

- [OpenTelemetry Python 文档](https://opentelemetry.io/docs/instrumentation/python/)
- [Jaeger 文档](https://www.jaegertracing.io/docs/)
- [Grafana Tempo 文档](https://grafana.com/docs/tempo/latest/)
- [structlog 文档](https://www.structlog.org/)
