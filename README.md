# A股多因子增强策略平台

一个基于Python的A股多因子量化投资策略平台，支持因子研究、模型构建、回测、模拟组合和商业化交付。

## 功能特性

- **多因子选股模型**：支持多种因子计算、分析和组合构建
- **A股特殊规则处理**：T+1交易、涨跌停限制、停牌处理等
- **回测系统**：完整的A股回测引擎，支持历史绩效分析
- **模拟组合**：实时跟踪策略表现
- **绩效分析**：多维度绩效指标计算和可视化
- **风控告警**：实时风险监控和告警系统
- **报告管理**：自动生成和调度策略报告
- **商业化交付**：支持策略订阅和API服务

## 技术栈

- **后端框架**：FastAPI
- **数据库**：SQLAlchemy + PostgreSQL
- **任务队列**：Celery + Redis
- **数据分析**：Pandas, NumPy, SciPy
- **可视化**：Matplotlib, Seaborn
- **认证**：FastAPI-Users
- **配置管理**：Python-decouple

## 安装指南

### 环境要求

- Python 3.8+
- PostgreSQL 12+
- Redis 5.0+
- MinIO (可选，用于文件存储)

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/your-username/quant-platform.git
cd quant-platform
```

2. **创建虚拟环境**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. **安装依赖**
```bash
pip install -r app/requirements.txt
```

4. **配置环境变量**
复制 `.env.example` 到 `.env` 并修改配置：
```bash
cp app/.env.example app/.env
# 编辑 app/.env 文件，设置数据库、Redis等连接信息
```

5. **数据库迁移**
```bash
alembic upgrade head
```

6. **启动服务**
```bash
cd app
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API使用示例

### 获取市场数据
```bash
curl "http://localhost:8000/api/v1/market/stock-daily?ts_code=000001.SZ&start_date=2023-01-01&end_date=2023-12-31"
```

### 创建因子
```bash
curl -X POST "http://localhost:8000/api/v1/factors/" \
-H "Content-Type: application/json" \
-d '{
  "factor_code": "ROE",
  "factor_name": "净资产收益率",
  "category": "quality",
  "expression": "net_profit / total_assets",
  "is_active": true
}'
```

### 运行回测
```bash
curl -X POST "http://localhost:8000/api/v1/backtests/" \
-H "Content-Type: application/json" \
-d '{
  "model_id": 1,
  "start_date": "2020-01-01",
  "end_date": "2023-12-31",
  "benchmark": "000300.SH",
  "initial_capital": 1000000,
  "transaction_cost": 0.001
}'
```

### 获取绩效分析
```bash
curl "http://localhost:8000/api/v1/performance/backtests/1/analysis"
```

## 项目结构

```
app/
├── api/                  # API路由
│   └── v1/               # API v1版本
│       ├── auth.py       # 认证相关
│       ├── users.py      # 用户管理
│       ├── securities.py # 证券管理
│       ├── market.py     # 市场数据
│       ├── stock_pools.py # 股票池管理
│       ├── factors.py    # 因子管理
│       ├── models.py     # 模型管理
│       ├── timing.py     # 择时模块
│       ├── portfolios.py # 组合管理
│       ├── backtests.py  # 回测系统
│       ├── simulated_portfolios.py # 模拟组合
│       ├── products.py   # 产品管理
│       ├── subscriptions.py # 订阅管理
│       ├── reports.py    # 报告管理
│       ├── task_logs.py  # 任务日志
│       ├── alert_logs.py # 告警日志
│       └── performance.py # 绩效分析
├── core/                 # 核心配置
│   └── config.py        # 配置文件
├── db/                   # 数据库相关
│   └── base.py          # 数据库基类
├── models/               # 数据模型
│   ├── user.py          # 用户模型
│   ├── securities.py    # 证券模型
│   ├── market.py        # 市场数据模型
│   ├── stock_pools.py   # 股票池模型
│   ├── factors.py       # 因子模型
│   ├── models.py        # 模型定义
│   ├── timing.py        # 择时模型
│   ├── portfolios.py    # 组合模型
│   ├── backtests.py     # 回测模型
│   ├── simulated_portfolios.py # 模拟组合模型
│   ├── products.py      # 产品模型
│   ├── subscriptions.py # 订阅模型
│   ├── reports.py       # 报告模型
│   ├── task_logs.py     # 任务日志模型
│   └── alert_logs.py    # 告警日志模型
├── schemas/              # Pydantic模型
│   ├── user.py          # 用户数据模型
│   ├── securities.py    # 证券数据模型
│   ├── market.py        # 市场数据模型
│   ├── stock_pools.py   # 股票池数据模型
│   ├── factors.py       # 因子数据模型
│   ├── models.py        # 模型数据模型
│   ├── timing.py        # 择时数据模型
│   ├── portfolios.py    # 组合数据模型
│   ├── backtests.py     # 回测数据模型
│   ├── simulated_portfolios.py # 模拟组合数据模型
│   ├── products.py      # 产品数据模型
│   ├── subscriptions.py # 订阅数据模型
│   ├── reports.py       # 报告数据模型
│   ├── task_logs.py     # 任务日志数据模型
│   └── alert_logs.py    # 告警日志数据模型
├── services/             # 业务逻辑
│   ├── auth_service.py  # 认证服务
│   ├── securities_service.py # 证券服务
│   ├── market_service.py # 市场数据服务
│   ├── stock_pool_service.py # 股票池服务
│   ├── factors_service.py # 因子服务
│   ├── models_service.py # 模型服务
│   ├── timing_service.py # 择时服务
│   ├── portfolios_service.py # 组合服务
│   ├── backtests_service.py # 回测服务
│   ├── simulated_portfolios_service.py # 模拟组合服务
│   ├── products_service.py # 产品服务
│   ├── subscriptions_service.py # 订阅服务
│   ├── reports_service.py # 报告服务
│   ├── task_logs_service.py # 任务日志服务
│   └── alert_logs_service.py # 告警日志服务
└── main.py              # 应用入口
```

## 开发指南

### 添加新模块

1. 在 `models/` 目录下创建新的数据模型
2. 在 `schemas/` 目录下创建对应的Pydantic模型
3. 在 `services/` 目录下实现业务逻辑
4. 在 `api/v1/` 目录下添加API路由
5. 在 `main.py` 中注册路由

### 数据库迁移

使用Alembic进行数据库迁移：
```bash
alembic revision --autogenerate -m "描述"
alembic upgrade head
```

### 运行测试

```bash
pytest
```

## 部署指南

### Docker部署

1. 构建Docker镜像：
```bash
docker build -t quant-platform .
```

2. 运行容器：
```bash
docker run -p 8000:8000 quant-platform
```

### 生产环境配置

- 配置Nginx反向代理
- 配置SSL证书
- 配置数据库连接池
- 配置Celery worker集群
- 配置监控和日志系统

## 贡献指南

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 联系方式

- 邮箱：your-email@example.com
- GitHub：https://github.com/your-username/quant-platform

## 相关文档

- [产品需求文档](document/PRD.md)
- [API文档](document/api_document.md)
- [用户指南](document/user_guide.md)
- [测试文档](document/TDD.md)
