# A股多因子增强策略平台

## 项目概述
基于 Python + FastAPI 的 A 股中低频量化策略平台，核心能力：多因子选股、指数择时、组合构建、回测验证、模拟组合、商业化交付。

## 技术栈
- 后端：Python 3.11+ / FastAPI / SQLAlchemy 2.x / Celery + Redis
- 前端：React + TypeScript + Vite + Ant Design
- 数据源：Tushare / AKShare
- 数据库：PostgreSQL / Redis

## 关键目录
- `app/api/v1/` — API 路由
- `app/core/` — 核心量化模块（因子引擎、评分、择时、回测等）
- `app/models/` — SQLAlchemy 模型（含 `market/` 子目录）
- `app/schemas/` — Pydantic 模型
- `app/services/` — 业务逻辑
- `app/tasks/` — Celery 异步任务
- `app/data_sources/` — 数据源适配器
- `scripts/` — 工具脚本
- `document/` — 项目文档

## 文档
- [PRD](document/PRD.md) — 产品需求文档 V2.1
- [TDD](document/TDD.md) — 技术架构与数据库设计 V2.1
- [ADD](document/ADD.md) — 算法设计说明书 V1.0
- [WORKFLOW](document/WORKFLOW.md) — 工作流文档（日终流水线、数据流、自然语言解读）
- [API](document/API.md) — API 接口文档
- [DEPLOYMENT](document/DEPLOYMENT.md) — 部署指南
- [user_guide](document/user_guide.md) — 客户端使用指南

## 开发规范
- 所有财务数据必须按公告发布日期使用，禁止未来函数
- 因子预处理流程：缺失值处理 → 去极值(MAD) → 标准化(Z-score) → 中性化
- 回测必须遵守 A 股交易规则：T+1、涨跌停、停牌、100 股交易单位
- 统一响应格式：`{"code": 0, "message": "success", "data": {}}`

## 常用命令
```bash
uvicorn app.main:app --reload                    # 启动 API
celery -A app.core.celery_config worker -l info   # 启动 Worker
python scripts/init_db.py --seed                  # 初始化数据库
python scripts/sync_data.py                       # 同步数据
pytest                                            # 运行测试
```
