# A股多因子增强策略平台 - 使用指南

## 项目结构

```
personal_quant_model/
├── app/
│   ├── api/v1/           # API 路由
│   ├── core/             # 核心量化模块
│   │   ├── factor_engine.py       # 因子计算引擎
│   │   ├── factor_preprocess.py   # 因子预处理
│   │   ├── factor_analyzer.py     # 因子分析
│   │   ├── model_scorer.py        # 多因子评分
│   │   ├── timing_engine.py       # 择时信号
│   │   ├── portfolio_builder.py   # 组合构建
│   │   ├── backtest_engine.py     # A股回测引擎
│   │   └── performance_analyzer.py # 绩效分析
│   ├── data_sources/     # 数据源适配器
│   │   ├── base.py               # 数据源基类
│   │   ├── tushare_source.py     # Tushare 数据源
│   │   └── akshare_source.py     # AKShare 数据源
│   ├── models/           # 数据模型
│   ├── schemas/          # Pydantic Schemas
│   ├── services/         # 业务服务
│   │   └── data_sync_service.py  # 数据同步服务
│   └── middleware/       # 中间件
├── scripts/
│   ├── init_db.py        # 数据库初始化
│   ├── generate_sample_data.py  # 示例数据生成
│   ├── sync_data.py      # 真实数据同步
│   └── run_example.py    # 运行示例
└── document/
    └── PRD.md            # 产品需求文档
```

## 快速开始

### 1. 初始化数据库

```bash
# 创建表结构并生成默认数据
python scripts/init_db.py --seed
```

### 2. 配置数据源

编辑 `app/.env` 文件：

```env
# 数据源配置
# Tushare Token（注册 https://tushare.pro 获取）
TUSHARE_TOKEN=your_token_here

# 主数据源: tushare 或 akshare
PRIMARY_DATA_SOURCE=akshare
```

### 3. 同步真实数据

```bash
# 同步市场数据
python scripts/sync_data.py

# 或指定日期范围
python scripts/sync_data.py --start-date 2023-01-01 --end-date 2023-12-31
```

### 4. 运行示例

```bash
# 运行完整的策略流程示例
python scripts/run_example.py
```

### 5. 启动 API 服务

```bash
uvicorn app.main:app --reload
```

访问 http://localhost:8000/docs 查看 API 文档

## 数据源配置

### Tushare（推荐）

1. 注册账号: https://tushare.pro
2. 获取 Token
3. 配置 `.env`:
   ```env
   TUSHARE_TOKEN=your_token
   PRIMARY_DATA_SOURCE=tushare
   ```

### AKShare（免费）

无需注册，直接使用：
```env
PRIMARY_DATA_SOURCE=akshare
```

### 双数据源

系统支持同时配置两个数据源，当主数据源不可用时自动切换到备用数据源。

## 数据同步服务

```python
from app.services.data_sync_service import DataSyncService

# 创建同步服务
service = DataSyncService(
    primary_source='akshare',
    tushare_token='your_token'
)

# 同步交易日历
service.sync_trading_calendar('2023-01-01', '2023-12-31')

# 同步股票基础信息
service.sync_stock_basic()

# 同步股票日线
service.sync_stock_daily('600000.SH', '2023-01-01', '2023-12-31')

# 同步指数日线
service.sync_index_daily('000300.SH', '2023-01-01', '2023-12-31')

# 全量同步
service.sync_all('2023-01-01', '2023-12-31')
```

## 核心功能模块

### 因子计算引擎 (`factor_engine.py`)

支持的因子类型：
- **质量因子**: ROE, ROA, 毛利率, 净利率
- **估值因子**: PE(TTM), PB, PS(TTM)
- **动量因子**: 20日/60日/120日动量
- **成长因子**: 营收增长, 净利润增长
- **风险因子**: 20日/60日波动率
- **流动性因子**: 换手率, 成交额

```python
from app.core.factor_engine import FactorEngine

engine = FactorEngine()
value = engine.calculate_factor('ROE', '600000.SH', '2023-12-29')
```

### 因子预处理 (`factor_preprocess.py`)

- 缺失值处理（均值/中位数/行业均值填充）
- 去极值（MAD方法/分位数方法）
- 标准化（Z-score/排名/Min-Max）
- 中性化（行业/市值）

```python
from app.core.factor_preprocess import FactorPreprocessor

preprocessor = FactorPreprocessor()
processed = preprocessor.preprocess(factor_values)
```

### 因子分析 (`factor_analyzer.py`)

- IC分析、Rank IC
- 分层回测（分组收益）
- 多空收益分析
- 因子衰减分析
- 因子相关性分析

```python
from app.core.factor_analyzer import FactorAnalyzer

analyzer = FactorAnalyzer()
result = analyzer.analyze_factor(factor_id, start_date, end_date)
```

### 多因子评分 (`model_scorer.py`)

- 等权加权
- 人工权重加权
- IC/ICIR加权
- Top N 选股

```python
from app.core.model_scorer import MultiFactorScorer

scorer = MultiFactorScorer()
scores = scorer.calculate_scores(model_id, trade_date)
portfolio = scorer.generate_portfolio_weights(scores, top_n=50)
```

### 择时信号 (`timing_engine.py`)

- 均线择时
- 市场宽度择时
- 波动率择时
- 回撤触发择时
- 多信号融合

```python
from app.core.timing_engine import TimingSignalCalculator

calculator = TimingSignalCalculator()
signal = calculator.calculate_timing_signal(model_id, trade_date)
```

### 组合构建 (`portfolio_builder.py`)

- Top N 选股
- 等权/评分加权
- 行业约束
- 仓位限制
- 调仓生成

```python
from app.core.portfolio_builder import PortfolioBuilder

builder = PortfolioBuilder()
portfolio = builder.build_portfolio(model_id, trade_date, top_n=50)
rebalance = builder.generate_rebalance(current_positions, target_portfolio, trade_date)
```

### A股回测引擎 (`backtest_engine.py`)

支持的A股特性：
- T+1 交易限制
- 涨跌停限制（主板10%/创业板科创板20%）
- 停牌处理
- 交易成本（佣金/印花税/过户费）
- 100股整数倍交易单位

```python
from app.core.backtest_engine import ABShareBacktestEngine

engine = ABShareBacktestEngine()
result = engine.run_backtest(backtest_id)
```

### 绩效分析 (`performance_analyzer.py`)

收益指标：总收益、年化收益、超额收益
风险指标：波动率、最大回撤、VaR、CVaR
风险调整收益：夏普比率、索提诺比率、卡玛比率、信息比率
归因分析：行业归因、风格归因

```python
from app.core.performance_analyzer import PerformanceAnalyzer

analyzer = PerformanceAnalyzer()
metrics = analyzer.analyze_performance(nav_series, benchmark_nav)
```

## API 接口

| 模块 | 接口 | 说明 |
|------|------|------|
| 因子管理 | `/api/v1/factors` | 因子CRUD |
| 因子计算 | `/api/v1/factors/{id}/calculate` | 计算因子值 |
| 因子分析 | `/api/v1/factors/{id}/ic-analysis` | IC分析 |
| 模型管理 | `/api/v1/models` | 模型CRUD |
| 组合生成 | `/api/v1/models/{id}/portfolio/generate` | 生成目标组合 |
| 回测管理 | `/api/v1/backtests` | 回测CRUD |
| 运行回测 | `/api/v1/backtests/{id}/run` | 执行回测 |
| 绩效分析 | `/api/v1/performance/backtests/{id}/analysis` | 绩效指标 |

## 完整策略流程

```
1. 数据准备
   └── 同步市场数据、财务数据

2. 因子计算
   └── 计算各类因子值

3. 因子预处理
   └── 去极值 → 标准化 → 中性化

4. 因子分析
   └── IC分析 → 分层回测 → 因子筛选

5. 模型构建
   └── 设置因子权重 → 构建多因子模型

6. 组合生成
   └── 计算评分 → Top N选股 → 权重分配

7. 择时信号
   └── 均线/波动率/市场宽度 → 仓位控制

8. 回测验证
   └── A股规则回测 → 绩效分析

9. 模拟运行
   └── 模拟组合跟踪

10. 信号输出
    └── 调仓建议 → 客户订阅
```

## 下一步

1. **完善因子库**: 添加更多因子类型和计算逻辑
2. **优化回测**: 添加更精确的交易模拟和滑点模型
3. **风控模块**: 完善风险监控和告警功能
4. **前端界面**: 开发管理后台和客户端页面
