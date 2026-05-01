# A股多因子增强策略平台 - 部署指南

**文档版本**：V1.4
**最后更新**：2026-04-24
**关联文档**：PRD V2.4、技术架构与数据库设计 V2.3

---

## 1. 环境要求

| 组件 | 版本要求 |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 15+ |
| Redis | 5.0+ |
| Node.js | 18+（前端构建） |
| Docker | 20+（可选） |

### 1.1 macOS 特定依赖

**LightGBM 依赖（macOS）**

LightGBM 需要 OpenMP 支持，在 macOS 上需要安装 `libomp`：

```bash
# 使用 Homebrew 安装
brew install libomp

# 验证安装
brew list libomp
```

如果遇到 `libomp.dylib` 缺失错误，执行：

```bash
# 重新链接 libomp
brew reinstall libomp

# 设置环境变量（可选，添加到 ~/.zshrc 或 ~/.bash_profile）
export LDFLAGS="-L/opt/homebrew/opt/libomp/lib"
export CPPFLAGS="-I/opt/homebrew/opt/libomp/include"
```

---

## 2. 开发环境部署

### 2.1 本地开发（推荐）

```bash
# 1. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -r app/requirements.txt

# 3. 配置环境变量
cp app/.env.example app/.env
# 编辑 app/.env，配置数据库、Redis、数据源等
```

**启动依赖服务：**

```bash
# PostgreSQL
docker run -d --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:15

# Redis
redis-server
# 或 Docker 方式
docker run -d --name redis -p 6379:6379 redis:7
```

**启动应用：**

```bash
# API 服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Celery Worker
celery -A app.core.celery_config worker --loglevel=info

# 初始化数据库
python scripts/init_db.py --seed
```

### 2.2 Docker Compose 部署

```bash
# 安装 Docker（macOS）
brew install docker

# 配置环境变量
cp app/.env.example app/.env

# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

**Docker Compose 服务说明：**

| 服务 | 说明 | 端口 |
|---|---|---|
| backend | FastAPI 应用 | 8000 |
| worker | Celery 异步任务 | - |
| postgres | PostgreSQL 数据库 | 5432 |
| redis | Redis 缓存/消息队列 | 6379 |
| nginx | 反向代理 | 80 |

---

## 3. 环境变量说明

关键环境变量（在 `app/.env` 中配置）：

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/quant_platform

# Redis
REDIS_URL=redis://localhost:6379/0

# 数据源
TUSHARE_TOKEN=your_token          # Tushare Token（注册 https://tushare.pro 获取）
PRIMARY_DATA_SOURCE=akshare       # 主数据源: tushare 或 akshare

# JWT
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=120

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

---

## 4. 生产环境部署

### 4.1 服务器准备

```bash
sudo apt update && sudo apt upgrade -y

# 安装 Docker
curl -sSL https://get.docker.com/ | sh
sudo usermod -aG docker $USER
```

### 4.2 部署应用

```bash
sudo mkdir -p /opt/quant-platform
sudo chown -R $USER:$USER /opt/quant-platform
cd /opt/quant-platform

git clone <repository-url> .
cp app/.env.example app/.env
# 编辑 app/.env 配置生产环境参数

docker-compose build
docker-compose up -d
```

### 4.3 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4.4 SSL 证书

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

### 4.5 开机自启

```ini
[Unit]
Description=Quant Platform API
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/quant-platform
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

---

## 5. 监控与维护

### 5.1 日志

```bash
docker-compose logs -f app       # API 日志
docker-compose logs -f worker    # Celery 日志
docker-compose logs --tail=100 app > app.log  # 导出日志
```

### 5.2 资源监控

```bash
docker stats                     # 容器资源使用
docker-compose ps                # 服务状态
```

### 5.3 备份

```bash
# PostgreSQL
docker exec quant-platform-db pg_dump -U postgres quant_platform > backup.sql

# Redis
docker exec quant-platform-redis redis-cli BGSAVE
```

### 5.4 更新

```bash
git pull origin main
docker-compose build
docker-compose up -d
```

### 5.5 故障排除

```bash
docker-compose logs app          # 查看错误日志
docker-compose restart app       # 重启服务
docker-compose up -d --force-recreate  # 重新创建服务
```

---

## 6. 性能优化

### 数据库
- 配置连接池（SQLAlchemy pool_size=20, max_overflow=40）
- 为高频查询添加复合索引（参见 TDD 第 10 节）
- **索引迁移**：已有数据库执行 `python scripts/add_indexes.py` 添加复合索引
- 大表按 trade_date 分区

### Redis
- 配置 LRU 淘汰策略
- 设置合理内存限制
- 使用 Pipeline 批量操作

### Celery
- 配置 worker 并发数：`worker_concurrency=8`（建议 CPU 核数 × 2）
- 设置任务超时（回测 30min，因子计算 10min）
- 实现任务重试机制

#### Celery 任务清单

| 任务名 | 说明 | 触发时机 |
|--------|------|---------|
| sync_stock_daily | 日线数据同步 | 每日收盘后 |
| sync_stock_financial | 财务数据同步 | 每日收盘后 |
| sync_index_daily | 指数数据同步 | 每日收盘后 |
| sync_event_data | 事件数据同步 | 每日收盘后 |
| compute_factors | 因子计算 | 每日数据同步后 |
| compute_scores | 评分计算 | 每日因子计算后 |
| check_factor_health | 因子健康检查 | 每日评分后 |
| check_model_drift | 模型漂移检查 | 每日评分后 |
| generate_snapshot | 数据快照生成 | 每日数据同步后 |
| build_portfolio | 组合构建 | 每日评分后 |
| check_portfolio_risk | 组合风控检查 | 每日组合生成后 |
| run_backtest | 回测任务 | 用户触发 |

### 应用
- 启用 Gzip 压缩
- 配置 API 限流
- 热点查询使用 Redis 缓存

### V1.1 性能优化（新增）

#### 数据库复合索引
```bash
# 为已有数据库添加复合索引（支持 SQLite 和 PostgreSQL）
python scripts/add_indexes.py
```

新增索引：
- `stock_daily(ts_code, trade_date)` — 最关键，覆盖90%+查询
- `stock_financial(ts_code, end_date)` — 按股票+报告期查询
- `stock_financial(ann_date)` — 避免未来函数的关键查询
- `index_daily(index_code, trade_date)` — 指数+日期查询
- `index_components(index_code, trade_date)` — 成分股+日期查询
- `index_components(index_code, ts_code)` — 成分股+股票查询

#### 连接池配置
```python
# app/db/base.py
pool_size=20,      # 原10，提升并发处理能力
max_overflow=40,   # 原20，允许更多突发连接
```

#### Celery Worker 配置
```python
# app/core/celery_config.py
worker_concurrency=8,  # 原4，充分利用多核
```

#### 缓存配置
- `CacheService`: 通用缓存，容量2000，TTL 300s，LRU驱逐
- `factor_cache`: 因子专用缓存，容量5000，TTL 600s
- 回测预计算缓存：进程生命周期内有效

#### 并行化配置
- 数据同步：`ThreadPoolExecutor(max_workers=4)` IO密集并行
- IC计算：`ProcessPoolExecutor` CPU密集并行
- 批量写入：`bulk_save_objects` 替代逐行 `db.add()`

---

## 7. 配置文件部署

### 7.1 配置文件体系

V2采用YAML配置驱动，参数不写死代码：

| 配置文件 | 路径 | 说明 |
|---------|------|------|
| base.yaml | config/base.yaml | 基础配置（环境/日志/路径） |
| db.yaml | config/db.yaml | 数据库连接配置 |
| data.yaml | config/data.yaml | 数据源配置 |
| universe.yaml | config/universe.yaml | 股票池参数（上市天数180/成交额8000万/市值80亿/股价3元） |
| factors.yaml | config/factors.yaml | 因子模块配置（5模块权重/因子列表/预处理参数） |
| labels.yaml | config/labels.yaml | 标签配置（主标签/辅标签/截尾参数） |
| model.yaml | config/model.yaml | 模型配置（ML参数/融合权重/状态机阈值） |
| timing.yaml | config/timing.yaml | 择时配置（5信号权重/4档仓位/回撤保护阈值） |
| portfolio.yaml | config/portfolio.yaml | 组合配置（Top60/分层赋权/风险折扣/行业约束） |
| risk.yaml | config/risk.yaml | 风控配置（黑名单规则/风险惩罚规则/组合风控阈值） |
| backtest.yaml | config/backtest.yaml | 回测配置（滑点/手续费/稳健性测试参数） |
| monitoring.yaml | config/monitoring.yaml | 监控配置（告警阈值/自动响应规则） |
| production.yaml | config/production.yaml | 生产环境覆盖配置 |

### 7.2 数据快照存储配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 快照存储路径 | /data/snapshots/ | 每日快照Parquet文件 |
| 快照保留天数 | 90 | 超过90天的快照自动清理 |
| 快照格式 | Parquet | 列式存储，支持DuckDB分析 |
| DuckDB路径 | /data/analysis.duckdb | 本地分析数据库 |

### 7.3 监控告警服务配置

| 配置项 | 值 | 说明 |
|--------|-----|------|
| 健康检查间隔 | 5min | 因子/模型健康检查频率 |
| 告警推送方式 | WebSocket + Email | 实时推送 + 邮件通知 |
| 自动响应开关 | true | 生产环境开启自动响应 |
| 告警保留天数 | 180 | 告警日志保留 |

---

## 8. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| V1.3 | 2026-04-24 | 新增配置文件体系、数据快照存储配置、监控告警服务配置；新增Celery任务（事件同步/因子健康检查/模型漂移检查/快照生成/组合风控检查） |
| V1.2 | 2026-04-22 | 新增性能优化章节（复合索引/连接池/Worker并发/缓存/并行化） |
| V1.1 | 2026-04-20 | 新增Docker Compose部署、Nginx反向代理、SSL证书配置 |
| V1.0 | 2026-04-18 | 初始版本 |
