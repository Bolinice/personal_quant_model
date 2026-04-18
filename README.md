# A股多因子增强策略平台

基于 Python 的 A 股中低频量化投资策略平台，支持因子研究、模型构建、回测验证、模拟组合和商业化交付。

## 核心特性

- **多因子选股模型** — 质量因子、估值因子、动量因子、成长因子、风险因子、流动性因子
- **A股特殊规则** — T+1 交易、涨跌停限制、停牌处理、100 股交易单位
- **指数择时** — 均线择时、市场宽度择时、波动率择时、回撤触发、多信号融合
- **回测系统** — 完整 A 股回测引擎，含交易成本、滑点、成交失败模拟
- **模拟组合** — 实时跟踪策略表现，对比回测与模拟偏差
- **风控告警** — 风险暴露、回撤、换手率、因子失效监控
- **商业化交付** — 策略订阅、组合建议、调仓信号、API 服务

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.x / Alembic / Pydantic |
| 任务队列 | Celery + Redis |
| 数据分析 | Pandas / NumPy / SciPy |
| 数据源 | Tushare / AKShare |
| 前端 | React + TypeScript + Vite + Ant Design |
| 数据库 | PostgreSQL / Redis / SQLite(开发) |
| 部署 | Docker Compose / Nginx |

## 快速开始

### 1. 环境准备

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
```

### 2. 配置

```bash
cp app/.env.example app/.env
# 编辑 app/.env，配置数据库、Redis、数据源 Token 等
```

### 3. 初始化数据库

```bash
python scripts/init_db.py --seed
```

### 4. 启动服务

```bash
# API 服务
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 或使用启动脚本
python scripts/start.py

# Celery Worker
celery -A app.core.celery_config worker --loglevel=info
```

访问 http://localhost:8000/docs 查看 Swagger API 文档。

### 5. 同步数据

```bash
# 使用 AKShare（免费，无需注册）
python scripts/sync_data.py

# 或指定日期范围
python scripts/sync_data.py --start-date 2023-01-01 --end-date 2023-12-31
```

## 项目结构

```
app/
├── api/v1/               # API 路由（auth, users, factors, models, portfolios, backtests...）
├── core/                 # 核心模块
│   ├── factor_engine.py          # 因子计算引擎
│   ├── factor_preprocess.py      # 因子预处理（去极值、标准化、中性化）
│   ├── factor_analyzer.py        # 因子分析（IC、分层回测）
│   ├── model_scorer.py           # 多因子评分
│   ├── timing_engine.py          # 择时信号
│   ├── portfolio_builder.py      # 组合构建
│   ├── backtest_engine.py        # A 股回测引擎
│   ├── risk_model.py             # 风险模型
│   └── performance_analyzer.py   # 绩效分析
├── data_sources/         # 数据源适配器（Tushare / AKShare）
├── models/               # SQLAlchemy 数据模型
│   └── market/           # 市场数据子模型（stock_basic, stock_daily, index_daily...）
├── schemas/              # Pydantic 请求/响应模型
├── services/             # 业务逻辑层
├── tasks/                # Celery 异步任务
├── monitoring/           # 监控指标
├── middleware/            # 中间件
├── db/                   # 数据库连接与会话
└── main.py               # 应用入口

frontend/                 # React 前端
scripts/                 # 工具脚本（init_db, sync_data, run_example...）
tests/                   # 测试
document/                # 项目文档
```

## 开发指南

### 添加新模块

1. `app/models/` — 创建数据模型
2. `app/schemas/` — 创建 Pydantic 模型
3. `app/services/` — 实现业务逻辑
4. `app/api/v1/` — 添加 API 路由
5. `app/main.py` — 注册路由

### 数据库迁移

```bash
alembic revision --autogenerate -m "描述"
alembic upgrade head
```

### 运行测试

```bash
pytest
```

## 文档索引

| 文档 | 说明 |
|---|---|
| [产品需求文档](document/PRD.md) | PRD V2.1 — 产品定义、功能需求、验收标准 |
| [技术架构文档](document/TDD.md) | TDD V2.1 — 架构设计、数据库表结构、任务流 |
| [算法设计说明书](document/ADD.md) | ADD V1.0 — 因子体系、评分模型、择时算法、回测规则 |
| [API 接口文档](document/API.md) | RESTful API 定义、请求/响应格式、错误码 |
| [部署指南](document/DEPLOYMENT.md) | 开发/生产环境部署、Docker、监控 |
| [客户端使用指南](document/user_guide.md) | 面向订阅客户的使用说明 |

## 许可证

MIT License
