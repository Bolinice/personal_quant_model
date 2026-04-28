# 业务代码优化计划书

> 版本：V2.0 | 日期：2026-04-28 | 状态：规划中

---

## 1. 概述

本文档针对现有量化策略平台的业务代码层进行系统性优化，涵盖因子计算、回测引擎、数据同步、API 接口等核心模块，目标是提升计算性能、代码可维护性与生产稳定性。

---

## 2. 因子计算优化

### 2.1 向量化改造

| 模块 | 现状 | 目标 | 方案 |
|------|------|------|------|
| `alpha_modules.py` | 部分因子逐行计算 | 全量向量化 | `groupby().shift()` 替代逐股票循环 |
| `labels.py` | 标签计算含循环 | 向量化标签 | `groupby().rank()` + 向量化收益计算 |
| `ensemble.py` | IC 加权逐因子 | 矩阵化加权 | `numpy` 矩阵运算替代逐因子循环 |

### 2.2 因子缓存机制

- **计算缓存**：因子值按 `(ts_code, trade_date, factor_name)` 缓存，避免重复计算
- **增量更新**：仅计算新增交易日的因子值，跳过已计算部分
- **缓存失效**：当因子公式变更时，自动清除相关缓存

```python
# 缓存键设计
cache_key = f"factor:{factor_name}:{ts_code}:{trade_date}"
# TTL: 7天（日频数据）
# 失效触发: 因子版本号变更
```

### 2.3 因子预处理流水线

统一预处理流程，确保一致性：

```
原始因子值 → 缺失值处理 → 去极值(MAD) → 标准化(Z-score) → 行业中性化
```

- **缺失值处理**：行业均值填充 / 插值
- **MAD 去极值**：3.5 倍中位数绝对偏差
- **Z-score 标准化**：横截面标准化
- **行业中性化**：申万一级行业虚拟变量回归取残差

---

## 3. 回测引擎优化

### 3.1 向量化回测

| 优化项 | 现状 | 目标 |
|--------|------|------|
| 信号生成 | 逐日循环 | 向量化信号矩阵 |
| 收益计算 | 逐笔计算 | 矩阵乘法 |
| 滑点模拟 | 固定滑点 | 成交量加权滑点 |

### 3.2 A 股交易规则严格执行

- **T+1**：买入当日不可卖出，信号延迟一日执行
- **涨跌停**：涨停不可买入，跌停不可卖出
- **停牌**：停牌日不可交易
- **交易单位**：100 股整数倍，不足部分放弃
- **未来函数检查**：所有财务数据按公告日使用，禁止前视偏差

### 3.3 回测性能指标

| 指标 | 目标 |
|------|------|
| 10 年全 A 回测 | < 60s |
| 单策略年化回测 | < 5s |
| 内存占用 | < 4GB |

---

## 4. 数据同步优化

### 4.1 并行化改造

- **日线数据**：`ProcessPoolExecutor` 4 线程并行同步
- **财务数据**：`ThreadPoolExecutor` 4 线程并行同步
- **增量同步**：基于 `trade_date` 增量拉取，跳过已存在数据

### 4.2 数据质量校验

```python
# 同步后自动校验
checks = [
    "缺失交易日检查",      # 对比交易日历
    "价格异常检查",        # 涨跌幅 > 20% 标记
    "成交量零值检查",      # 成交量为0但价格非零
    "财务数据一致性检查",   # 资产负债表勾稽关系
]
```

### 4.3 数据源容灾

- **主数据源**：Tushare Pro
- **备数据源**：AKShare
- **降级策略**：主源超时 3s 自动切换备源
- **数据对齐**：双源数据交叉验证，偏差 > 1% 告警

---

## 5. API 接口优化

### 5.1 响应格式统一

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "timestamp": "2026-04-26T10:00:00Z"
}
```

### 5.2 接口性能目标

| 接口类型 | 目标响应时间 |
|----------|-------------|
| 因子查询 | < 200ms |
| 回测启动 | < 500ms |
| 策略列表 | < 100ms |
| 数据同步 | 异步任务 |

### 5.3 分页与过滤

- 所有列表接口支持分页：`page`, `page_size`
- 因子查询支持多维度过滤：`trade_date`, `industry`, `factor_name`
- 回测结果支持时间范围过滤

---

## 6. 数据库优化

### 6.1 索引优化

现有复合索引（已实现）：
- `stock_daily(ts_code, trade_date)`
- `stock_daily(trade_date, ts_code)`
- `factor_values(ts_code, trade_date, factor_name)`
- `factor_values(trade_date, factor_name)`

### 6.2 待新增索引

| 表 | 索引 | 用途 |
|----|------|------|
| `backtest_results` | `(strategy_id, start_date, end_date)` | 回测结果查询 |
| `factor_ic` | `(factor_name, trade_date)` | IC 值查询 |
| `portfolio_positions` | `(portfolio_id, trade_date)` | 组合持仓查询 |

### 6.3 查询优化

- **N+1 消除**：批量 `IN` 查询 + `bulk_save_objects`
- **连接池**：`pool_size=20, max_overflow=40`
- **慢查询监控**：> 1s 的查询自动记录并告警

---

## 7. 监控与告警

### 7.1 因子监控（`factor_monitor.py`）

- **IC 漂移**：滚动 IC 均值低于阈值告警
- **PSI**：因子分布稳定性，PSI > 0.25 告警
- **KS 检验**：因子分布变化，p-value < 0.05 告警

### 7.2 系统监控

- **Celery 任务监控**：任务失败率 > 5% 告警
- **API 响应监控**：P99 > 2s 告警
- **数据同步监控**：同步延迟 > 1 天告警

---

## 8. 实施优先级

| 优先级 | 模块 | 预计工期 |
|--------|------|----------|
| P0 | 因子向量化 + 缓存 | 2 周 |
| P0 | 回测引擎向量化 | 2 周 |
| P1 | 数据同步并行化 | 1 周 |
| P1 | 数据库索引优化 | 1 周 |
| P2 | API 接口优化 | 1 周 |
| P2 | 监控告警体系 | 2 周 |

---

## 8. 开发者技能提升计划

> 基于 2025-2026 行业最佳实践研究，系统性提升项目工程质量

### 8.1 工具链升级

#### 8.1.1 Ruff 替换 black+isort+flake8（P0）

**现状**：black + isort + flake8 三个工具，速度慢、配置分散
**目标**：统一到 Ruff，10-100x 速度提升

```toml
# pyproject.toml 新增配置
[tool.ruff]
target-version = "py311"
line-length = 120
src = ["app"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "SIM", "TCH", "RUF", "PERF", "C4", "DTZ", "PIE", "PT", "RET", "TRY", "FURB", "LOG"]
ignore = ["E501", "TRY003", "B008"]

[tool.ruff.lint.isort]
known-first-party = ["app"]

[tool.ruff.format]
quote-style = "double"
```

**迁移步骤**：
1. `pip install ruff`
2. `ruff check app/ --select E,W,F,I --fix`（基础规则）
3. `ruff format app/`（替换 black）
4. 逐步启用更多规则类别
5. 移除 black、isort、flake8 依赖

#### 8.1.2 pyright 补充 mypy（P0）

**现状**：mypy 1.8 strict 模式
**目标**：添加 pyright 作为补充检查器，捕获更多类型错误

```toml
[tool.pyright]
pythonVersion = "3.11"
typeCheckingMode = "strict"
reportMissingTypeStubs = false
include = ["app"]
exclude = ["alembic", "scripts", ".venv"]
```

**策略**：CI 中运行 mypy，编辑器中用 pyright（Pylance 自带）

#### 8.1.3 迁移依赖管理到 uv（P1）

**现状**：setuptools + pip
**目标**：uv（Astral 团队出品，同 Ruff）

- 10-100x 安装速度
- 替代 pip、pip-tools、poetry、virtualenv
- 自带 `uv.lock` 保证可复现构建
- build-backend 迁移到 hatchling

```bash
uv init && uv sync    # 初始化并安装依赖
uv add structlog      # 添加依赖
uv run pytest         # 在 venv 中运行
```

#### 8.1.4 Pre-commit Hooks 现代化（P1）

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1024']
      - id: check-merge-conflict
      - id: detect-private-key
      - id: check-ast

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic>=2.0, sqlalchemy>=2.0]
        args: ['--ignore-missing-imports']
        exclude: ^(tests/|scripts/|alembic/)
```

**性能**：Ruff ~0.1s vs black+isort+flake8 3-10s，总 pre-commit 时间从 ~15s 降至 ~3s

### 8.2 量化系统专项实践

#### 8.2.1 PIT Guard（点在时数据守卫）（P0）

**问题**：未来函数是量化系统最致命的 bug，当前仅在流水线层面检查，可被绕过
**目标**：在数据访问层强制 `ann_date <= trade_date`，从架构层面杜绝

```python
# app/core/pit_guard.py
def pit_guard(trade_date: date):
    """装饰器：强制点在时数据访问，过滤所有 ann_date > trade_date 的行"""
    def decorator(query_func):
        def wrapper(*args, **kwargs):
            result = query_func(*args, **kwargs)
            if isinstance(result, pd.DataFrame) and 'ann_date' in result.columns:
                before = len(result)
                result = result[result['ann_date'] <= trade_date]
                leaked = before - len(result)
                if leaked > 0:
                    logger.warning(f"PIT guard filtered {leaked} future rows")
            return result
        return wrapper
    return decorator
```

**实施**：
- 创建 `app/core/pit_guard.py`
- 所有财务数据查询必须通过 PIT guard
- 添加 `tests/test_no_lookahead.py`：注入未来数据 → 断言系统捕获

#### 8.2.2 Look-ahead Bias 黄金测试套件（P0）

```python
# tests/test_no_lookahead.py
def test_no_future_data_leakage():
    """注入未来数据后，流水线输出必须不变"""
    result_t = run_pipeline(trade_date="2025-01-10")
    alter_data_for("2025-01-15")  # 篡改未来数据
    result_t_again = run_pipeline(trade_date="2025-01-10")
    assert result_t.equals(result_t_again), "检测到未来数据泄漏！"
```

#### 8.2.3 Property-based Testing（Hypothesis）（P1）

**核心价值**：自动生成边界用例，覆盖手动测试遗漏的角落

```python
from hypothesis import given, strategies as st

@given(values=st.lists(st.floats(min_value=-1e6, max_value=1e6), min_size=50),
       threshold=st.floats(min_value=1.0, max_value=5.0))
def test_mad_winsorization_preserves_order(values, threshold):
    """MAD 去极值必须保持排序不变"""
    result = mad_winsorize(np.array(values), threshold)
    assert rankdata(result).tolist() == rankdata(values).tolist()

def test_zscore_mean_zero_std_one():
    """Z-score 标准化后均值≈0，标准差≈1"""
    ...

def test_neutralization_group_mean_zero():
    """行业中性化后组内均值≈0"""
    ...
```

**待验证不变量**：
- MAD 去极值保持排序
- Z-score 标准化后均值≈0、标准差≈1
- 中性化后组内均值≈0
- 组合权重之和 = 1.0 且满足持仓限制
- 回测净值曲线在所有收益非负时单调不减

#### 8.2.4 Golden Master Testing（P1）

**目标**：冻结已知正确的流水线输出，任何变更必须显式确认

- 在 `tests/fixtures/` 中存储固定数据集（parquet 格式）
- 存储参考输出，后续运行比对
- 因子计算逻辑变更时，必须更新 golden master 并记录原因

#### 8.2.5 回测完整性检查（P1）

```python
# tests/test_backtest_integrity.py
def test_sharpe_sanity_ceiling():
    """Sharpe > 5 几乎必然是 bug 或过拟合"""
    assert result.sharpe < 5.0

def test_turnover_within_bounds():
    """单次调仓换手率不应超过合理范围"""
    assert result.turnover_ratio < 1.5

def test_t_plus_1_constraint():
    """T 日买入的股票 T 日不可卖出"""
    ...

def test_no_trades_on_non_trading_days():
    """非交易日不应有交易"""
    ...
```

#### 8.2.6 CPCV 替代简单交叉验证（P2）

**问题**：标准 k-fold CV 在时序数据上会通过序列相关性泄漏信息
**方案**：实现组合清洗交叉验证（Combinatorial Purged Cross-Validation）
- 来源：Lopez de Prado《Advances in Financial Machine Learning》
- 在训练/测试边界设置 embargo 窗口
- 追踪实验总数，应用 Deflated Sharpe Ratio 校正多重检验

#### 8.2.7 熔断器（Circuit Breaker）（P2）

**问题**：Tushare/AKShare 外部数据源不稳定，连续失败会拖垮流水线
**方案**：

```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=300)
def fetch_tushare_data(api, ts_code, start_date, end_date):
    """连续失败5次自动断开，5分钟后恢复"""
    return api.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
```

### 8.3 架构与工程质量

#### 8.3.1 CI Pipeline（P0）

**现状**：项目缺少 `.github/workflows/`，这是最大基础设施缺口
**目标**：建立四阶段 CI 流水线

```
Stage 1: 快速检查 (< 2 min)
  - ruff check（代码规范）
  - ruff format --check（格式检查）
  - mypy --strict（类型检查）

Stage 2: 单元测试 (< 5 min)
  - pytest tests/ -x -n auto --timeout=30
  - pytest --cov=app/core --cov-fail-under=70

Stage 3: 集成测试 (< 15 min)
  - Docker Compose: app + PostgreSQL + Redis
  - pytest tests/test_e2e.py -v
  - 数据库迁移测试（alembic upgrade head）

Stage 4: 每日定时（非逐 PR）
  - 完整回测验证
  - 统计不变量测试
  - 性能回归基准
  - 安全扫描（pip-audit, bandit）
```

#### 8.3.2 核心层纯化（P1）

**现状**：`app/core/` 中纯计算与 DB/IO 混合（如 `data_sync.py` 直接使用 `SessionLocal`，`backtest_engine.py` 导入 `Session`）
**目标**：分离纯计算与基础设施

```
app/core/pure/          ← 纯函数，无 I/O 副效应，无 DB 访问
  factor_math.py        ← 因子计算（接受 DataFrame，返回 DataFrame）
  risk_calc.py          ← 风险计算
  portfolio_opt.py      ← 组合优化
app/core/               ← 现有模块，调用 pure/ 层
app/services/           ← DB 交互层
app/api/                ← 路由层
```

**依赖方向**：`app/core/pure/` → `app/core/` → `app/services/` → `app/api/`，禁止反向导入

#### 8.3.3 结构化错误体系（P1）

**现状**：通用 `success()` / `error()` 响应辅助函数
**目标**：领域化错误层级

```python
class QuantPlatformError(Exception):
    """平台基础错误"""

class DataError(QuantPlatformError):
    """数据源/质量问题"""

class LookaheadBiasError(DataError):
    """检测到未来数据"""

class FactorDegradationError(QuantPlatformError):
    """因子 IC 衰减超阈值"""

class TradingRuleViolationError(QuantPlatformError):
    """回测违反 A 股交易规则"""
```

每个错误类映射到特定告警通道和严重级别。

#### 8.3.4 structlog 替换自定义 JsonFormatter（P2）

**优势**：
- 内置上下文变量（请求 ID 自动绑定）
- 原生 JSON 输出 + 处理器管道
- OpenTelemetry 集成
- 兼容标准 logging，无需一次性重写

```python
import structlog
logger = structlog.get_logger()
logger.info("factor_calculated", factor_id="momentum_20", ic=0.05, n_stocks=500)

# 上下文绑定（自动附加到请求内所有日志）
structlog.contextvars.bind_contextvars(request_id="abc-123", user_id=42)
```

#### 8.3.5 OpenTelemetry 分布式追踪（P2）

**目标**：日终流水线各模块可追踪耗时和错误传播

```python
from opentelemetry import trace
tracer = trace.get_tracer("quant_platform")

async def run_daily_pipeline(trade_date):
    with tracer.start_as_current_span("daily_pipeline") as span:
        span.set_attribute("trade_date", str(trade_date))
        with tracer.start_as_current_span("universe_construction"):
            universe = construct_universe(trade_date)
        with tracer.start_as_current_span("factor_calculation"):
            factors = calculate_factors(universe, trade_date)
```

集成 Prometheus：`prometheus_fastapi_instrumentator` 自动暴露 `/metrics`

#### 8.3.6 安全头中间件（P2）

```python
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

#### 8.3.7 审计日志（哈希链）（P3）

金融数据访问记录，防篡改：

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(BigInteger, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=False)
    ip_address = Column(String(45))
    timestamp = Column(DateTime, server_default=func.now())
    previous_hash = Column(String(64))   # 哈希链防篡改
    payload_hash = Column(String(64))    # 访问数据的哈希
```

#### 8.3.8 asyncpg + AsyncSession（P3）

**现状**：FastAPI 路由使用同步 SQLAlchemy（psycopg2-binary），阻塞事件循环
**目标**：迁移到 asyncpg + SQLAlchemy async

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine("postgresql+asyncpg://...", pool_size=20, max_overflow=40)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

CPU 密集型回测用 `asyncio.to_thread()` 避免阻塞事件循环。

### 8.4 量化系统常见陷阱防范

| 陷阱 | 说明 | 防范措施 |
|------|------|----------|
| 幸存者偏差 | 用今天的股票列表回测历史 | UniverseBuilder 必须加载历史时点的实际上市股票 |
| 复权处理不当 | 除权除息扭曲价格因子 | 因子计算用前复权价，交易模拟用原始价 |
| 过拟合 | 测试数百因子组合选最优 | Deflated Sharpe Ratio + 追踪实验总数 + CPCV |
| NaN/Inf 混用 | 不同 pandas 操作处理不同导致静默数据损坏 | 全局 `sanitize_dataframe()` 管道步骤，替换所有 Inf/-Inf 为 NaN |
| 交易日历错误 | `pandas.bdate_range` 用美国假日 | 必须用 A 股专用交易日历（Tushare/交易所日历） |
| 隐式全局状态 | 模块级单例、全局缓存、可变默认参数 | 依赖注入，显式传递所有依赖 |
| 批量与事件驱动不一致 | 向量化快速路径与事件驱动路径结果不同 | 测试断言两条路径输出完全一致 |
| 静默数据过期 | 数据源返回缓存/过期数据 | 同步后验证 `max(trade_date) >= expected_latest_date` |
| 缺少熔断 | 因子异常（NaN 传播导致单股 100% 权重） | 组合构建前检查：单股最大权重、行业集中度、最大换手率 |

### 8.5 测试策略升级

#### 8.5.1 测试工具链扩展

| 工具 | 用途 | 优先级 |
|------|------|--------|
| Hypothesis | 属性测试，自动生成边界用例 | P1 |
| pytest-xdist | 并行测试执行 `pytest -n auto` | P1 |
| pytest-timeout | 防止测试挂起（30s 超时） | P1 |
| pytest-randomly | 随机化测试顺序，捕获顺序依赖 | P2 |
| factory-boy | SQLAlchemy 模型工厂 | P2 |
| mutmut | 变异测试，验证测试套件质量 | P3 |

#### 8.5.2 测试分层策略

```
第一层：单元测试（纯计算，无 I/O）
  - app/core/pure/ 下所有函数
  - Property-based testing (Hypothesis)
  - 覆盖率目标：80%

第二层：集成测试（流水线各阶段，真实数据）
  - Golden master testing
  - Look-ahead bias 检测
  - 回测完整性检查
  - 覆盖率目标：60%

第三层：端到端验证（已知结果的完整回测）
  - 固定日期范围 + 固定数据
  - 输出必须与参考结果 bit-identical
  - 变异测试验证测试质量
```

#### 8.5.3 覆盖率要求

| 模块 | 最低覆盖率 | 说明 |
|------|-----------|------|
| `app/core/` | 80% | 核心量化逻辑 |
| `app/api/` | 60% | API 路由 |
| `app/services/` | 70% | 业务逻辑 |
| `app/core/pure/` | 90% | 纯计算函数，必须充分测试 |

---

## 9. 综合实施优先级

| 优先级 | 改进项 | 模块 | 预计工期 | 收益 |
|--------|--------|------|----------|------|
| **P0** | Ruff 替换 black+isort+flake8 | 工具链 | 0.5 天 | 10x 速度，统一工具 |
| **P0** | pyright 补充 mypy | 工具链 | 0.5 天 | 更多类型错误捕获 |
| **P0** | PIT Guard（点在时数据守卫） | 量化专项 | 2 天 | 架构层面杜绝未来函数 |
| **P0** | Look-ahead Bias 黄金测试 | 量化专项 | 1 天 | 自动化检测未来数据泄漏 |
| **P0** | CI Pipeline（GitHub Actions） | 工程 | 2 天 | 最大基础设施缺口 |
| **P1** | 迁移依赖管理到 uv | 工具链 | 1 天 | 10-100x 安装速度 |
| **P1** | Pre-commit Hooks | 工具链 | 0.5 天 | 提交前自动拦截 |
| **P1** | Property-based Testing | 量化专项 | 2 天 | 覆盖边界用例 |
| **P1** | Golden Master Testing | 量化专项 | 1 天 | 回归检测 |
| **P1** | 回测完整性检查 | 量化专项 | 1 天 | Sharpe/换手率/T+1 验证 |
| **P1** | 核心层纯化 | 架构 | 3 天 | 可测试性+可审计性 |
| **P1** | 结构化错误体系 | 架构 | 1 天 | 精准告警 |
| **P2** | CPCV 替代简单 CV | 量化专项 | 3 天 | 防止信息泄漏 |
| **P2** | 熔断器 | 量化专项 | 1 天 | 外部数据源容灾 |
| **P2** | structlog | 架构 | 2 天 | 可观测性 |
| **P2** | OpenTelemetry 追踪 | 架构 | 2 天 | 流水线追踪 |
| **P2** | 安全头中间件 | 架构 | 0.5 天 | 安全基线 |
| **P3** | 审计日志（哈希链） | 架构 | 2 天 | 合规审计 |
| **P3** | asyncpg + AsyncSession | 架构 | 3 天 | 非阻塞 DB |
| **P3** | 变异测试（mutmut） | 测试 | 1 天 | 验证测试质量 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| V2.0 | 2026-04-28 | 新增第8-9节：开发者技能提升计划（工具链升级、量化专项实践、架构工程质量、常见陷阱防范、测试策略升级），重构实施优先级 |
| V1.0 | 2026-04-26 | 初始版本 |
