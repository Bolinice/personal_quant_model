# A股多因子增强策略平台 技术架构与数据库设计文档

---

## 0. 文档信息

| 项 | 内容 |
|---|---|
| 文档名称 | A股多因子增强策略平台 技术架构与数据库设计文档 |
| 文档版本 | V2.3 |
| 关联文档 | PRD V2.4、算法设计说明书 V2.1 |
| 文档状态 | 评审版 |
| 适用对象 | 技术负责人、后端研发、数据工程师、量化工程师、运维、测试 |
| 系统类型 | 中低频量化研究与策略交付平台 |
| 部署形态 | 单体优先，服务化预留 |

---

# 1. 文档目标

## 1.1 编写目的
本文档用于定义 A 股多因子增强策略平台的技术架构、模块拆分、服务边界、数据流、任务流、存储方案、核心数据库表结构、接口设计原则、部署建议与非功能实现方案，作为研发实施、联调、测试、运维和后续扩展的统一依据。

## 1.2 设计目标
系统设计目标如下：

- 支持 A 股中低频量化研究与策略交付闭环
- 支持点时数据回溯与回测复现
- 支持因子计算、模型打分、组合构建、回测、模拟、报告输出
- 支持商业化订阅、权限控制、API交付
- 支持后续扩展到机器学习增强、多租户、更多资产类型

---

# 2. 总体技术架构

## 2.1 架构原则
采用以下设计原则：

1. **研究与生产分层**
   - 研究环境允许灵活试验
   - 生产环境强调稳定、可审计、可回滚

2. **数据与计算解耦**
   - 原始数据存储与因子计算任务分离
   - 回测结果与生产信号分离

3. **任务驱动**
   - 因子计算、回测、调仓、报告均采用异步任务机制

4. **点时一致**
   - 所有历史查询、回测、股票池、因子、模型输出必须支持按日期回溯

5. **单体优先，服务化预留**
   - MVP 阶段可采用模块化单体
   - 后续拆分为独立服务

6. **配置驱动**
   - 参数不写死代码，YAML配置文件体系

7. **数据分层**
   - 原始层(raw)/清洗层(clean)/PIT层(pit)/研究特征层(feature)/策略结果层(score)/治理监控层(registry)

8. **先风控后收益**
   - 所有路径先过风控检查，再执行收益逻辑
   - 宁可少赚，不可多亏
   - 风控模块独立于收益模块，风控超阈可直接降仓/中止

---

## 2.2 总体架构图（逻辑）

可抽象为以下层次：

1. **接入层**
   - Web 管理后台
   - 客户前台
   - Open API
   - 内部管理 API

2. **业务服务层**
   - 用户与权限服务
   - 数据管理服务
   - 股票池服务
   - 因子服务
   - 模型服务
   - 回测服务
   - 组合服务
   - 风控服务
   - 模拟组合服务
   - 报告服务
   - 订阅与产品服务
   - 事件中心服务
   - 风险惩罚服务
   - 因子元数据与注册服务
   - 模型注册与实验管理服务
   - 数据快照服务

3. **任务调度层**
   - 日终数据同步任务
   - 因子计算任务
   - 模型打分任务
   - 回测任务
   - 调仓任务
   - 报告生成任务
   - 风控扫描任务
   - 事件数据同步任务
   - 因子健康检查任务
   - 模型漂移监控任务
   - 数据快照生成任务

4. **数据存储层**
   - 关系型数据库（PostgreSQL）
   - 分析型数据库（ClickHouse，可选）
   - 缓存（Redis）
   - 文件/对象存储（报告、图表、导出文件）

5. **基础设施层**
   - Docker
   - Linux 主机 / K8s（后续）
   - CI/CD
   - 日志监控告警

---

# 3. 模块拆分与职责

---

## 3.1 用户与权限模块
职责：
- 用户注册、登录、鉴权
- 角色权限控制
- 机构客户成员管理
- API Key 管理
- 操作审计

---

## 3.2 数据管理模块
职责：
- 行情数据同步
- 财务数据同步
- 指数成分同步
- 股票状态同步
- 交易日历维护
- 数据质量检查（DataQualityChecker）
- PIT前视偏差防护（PITManager）
- 幸存者偏差处理（SurvivorshipBiasHandler）
- 数据版本管理
- 事件数据同步（业绩预告/问询函/立案处罚/减持/股权质押等）
- 数据快照生成（每日snapshot_id）
- PIT严格版本管理（预告/快报/正式报表优先级、修订版本号）
- 分析师与北向资金PIT对齐

---

## 3.3 股票池模块
职责：
- 基础股票池生成
- 过滤规则配置
- 股票池快照保存
- 股票池回放
- 过滤原因记录
- 风险事件过滤
- 黑名单硬过滤

---

## 3.4 因子模块
职责：
- 因子定义管理
- 因子参数配置
- 因子计算任务
- 因子预处理
- 因子分析
- 因子结果存储
- 因子元数据管理（因子身份证：名称/逻辑/公式/来源/PIT/方向/覆盖率/状态/版本）
- 因子研究标准流程与上线闸门
- 统一预处理流水线（10步固定流程：缺失值处理→去极值(MAD)→标准化(Z-score)→中性化→相关性检查→共线性处理→IC检验→衰减分析→方向确认→上线评审）
- 因子模块重组（quality_growth/expectation/residual_momentum/flow_confirm/risk_penalty/experimental）

---

## 3.5 模型模块
职责：
- 多因子模型定义
- 因子权重配置
- 模型版本管理
- 模型打分任务
- 模型结果查询
- 模型发布管理
- 模块状态机（active/watch/degraded/disabled）
- 动态权重收缩
- ML增强排序（Ridge+LightGBM+规则fallback三路融合）
- 预测置信度体系
- 模型注册表（model_id/feature_set/label_version/snapshot_id/params/oof_metrics/status）

---

## 3.6 市场状态检测模块 (Regime)

**业务原理**：不同市场环境下，不同Alpha模块的有效性不同。牛市里动量因子强，震荡市里价值因子强，暴跌时什么都不好使。Regime检测的目的是"知道当前市场适合哪类Alpha"，从而调整模块权重和仓位。

**4维度检测**：
- 趋势强度（指数MA排列、ADX）
- 市场宽度（上涨家数/下跌家数、创新高占比）
- 波动率水平（VIX类指标、历史波动率分位数）
- 流动性状态（成交额趋势、北向资金流向）

**4状态输出**：
- `risk_on`：强趋势+高宽度+低波动 → 进攻模式，动量/成长权重↑
- `trending`：有趋势+宽度尚可 → 标准模式，均衡权重
- `defensive`：弱趋势+低宽度+高波动 → 防御模式，价值/低波权重↑，仓位↓
- `mean_reverting`：震荡+低趋势 → 反转模式，反转/价值权重↑

输出同时用于：信号融合的Regime调权、择时仓位控制、组合风险约束调整。

## 3.7 择时与组合模块
职责：
- 择时信号生成（简化为风险预算，5信号4档仓位）
- 仓位控制
- 候选股筛选
- 权重分配
- 调仓单生成
- 调仓记录管理
- 分层赋权组合构建
- 风险折扣层
- 双轨制（研究/实盘）
- 换手控制

---

## 3.7 回测模块
职责：
- 回测任务配置
- 回测执行
- 成交模拟
- 回测结果存储
- 回测报告输出

---

## 3.8 模拟组合模块
职责：
- 模拟组合创建
- 调仓跟踪
- 净值更新
- 回测与模拟偏差分析

---

## 3.9 风控模块
职责：
- 暴露监控
- 回撤监控
- 换手监控
- 成交失败监控
- 模型失效监控
- 风险事件记录与告警
- 黑名单系统
- 风险惩罚规则引擎
- 组合风控（行业集中度/风格偏离/小盘暴露/高beta暴露/拥挤度）
- 极端情景保护
- 全链路5类监控（数据/因子/模型/组合/实盘）
- 自动响应机制

---

## 3.10 报告与订阅模块
职责：
- 产品管理
- 客户订阅管理
- 报告生成
- 组合建议交付
- API 输出
- 权限控制

---

# 4. 技术选型建议

---

## 4.1 后端
建议：
- Python + FastAPI

原因：
- 适合量化计算与服务结合
- 与研究代码复用成本低
- 支持异步接口和任务系统

---

## 4.2 数据库
### 主库
- PostgreSQL  
用于：
- 业务数据
- 配置数据
- 元数据
- 中小规模结果表

### 分析库（可选）
- ClickHouse  
用于：
- 大规模因子结果
- 大规模回测明细
- 高速查询分析

### 缓存
- Redis  
用于：
- 热点查询缓存
- 任务状态缓存
- 会话与令牌缓存

### 文件存储
- MinIO / OSS / S3  
用于：
- PDF 报告
- 图表文件
- 导出 CSV
- 回测附件

---

## 4.3 调度与异步任务
建议：
- Airflow / Prefect：定时调度
- Celery / RQ：异步任务执行

MVP 可先用：
- Cron + Celery  
后续升级：
- Airflow + Celery

---

## 4.4 前端
- 管理后台：React / Vue
- 客户前台：React / Vue
- 图表：ECharts / Plotly

---

## 4.5 部署
MVP：
- Docker Compose
- Nginx + FastAPI + PostgreSQL + Redis

后续：
- Kubernetes
- CI/CD 自动部署
- 灰度发布

---

# 5. 系统分层设计

---

## 5.1 接口层
包含：
- 后台管理 API
- 客户端 API
- Open API
- 内部任务 API

设计原则：
- RESTful 风格
- 统一鉴权
- 统一响应格式
- 支持分页、过滤、排序

---

## 5.2 业务层
封装业务逻辑：
- 股票池生成逻辑
- 因子处理逻辑
- 模型评分逻辑
- 组合构建逻辑
- 回测规则逻辑
- 风控规则逻辑

---

## 5.3 任务层
封装重计算任务：
- 数据同步
- 因子计算
- 模型打分
- 回测执行
- 组合生成
- 报告生成

要求：
- 可重试
- 可幂等
- 可追踪
- 可审计

---

## 5.4 数据访问层
职责：
- ORM / SQL封装
- 读写分离预留
- 版本控制支持
- 批量写入优化

---

# 6. 核心数据流设计

---

## 6.1 日终生产数据流
1. 同步交易日历
2. 同步股票日线、指数日线
3. 同步停牌/ST/涨跌停状态
4. 同步财务和指数成分数据
5. 同步事件数据（业绩预告/问询函/减持/质押等）
6. 执行数据质量检查
7. 生成数据快照
8. 生成股票池快照（含风险事件过滤）
9. 执行因子统一预处理流水线
10. 执行五大模块打分（质量成长/预期修正/残差动量/资金流确认/风险惩罚）
11. 执行信号融合（动态IC加权+Regime调权+高相关收缩）
12. 执行ML增强排序（可选）
13. 生成风险预算择时信号
14. 生成目标组合（分层赋权+风险折扣+行业约束）
15. 执行风控检查（黑名单+风险惩罚+组合风控）
16. 生成调仓建议
17. 执行因子健康检查与告警
18. 生成报告并推送订阅用户  

---

## 6.2 研究回测数据流
1. 用户创建回测任务  
2. 固定样本区间、股票池、模型参数、交易规则  
3. 调用回测引擎  
4. 写入回测结果、持仓、交易、指标  
5. 生成图表与报告  
6. 可复查和复现

---

## 6.3 模拟组合数据流
1. 正式发布模型版本  
2. 定期生成新调仓建议  
3. 更新模拟持仓  
4. 更新净值  
5. 触发绩效分析与风控监控  
6. 输出客户可见内容

---

# 7. 数据库设计原则

---

## 7.1 总体原则
1. **业务表与计算结果表分离**
2. **原始数据与衍生数据分离**
3. **配置表与运行日志表分离**
4. **所有关键对象支持 version 字段**
5. **所有关键结果支持 as_of_date / trade_date**
6. **所有任务支持 task_id 与 run_id 追踪**
7. **原始数据与PIT数据分离**（raw_*/pit_*）
8. **数据快照与版本管理**（所有关键结果绑定snapshot_id）

---

##7.2 数据库划分建议
建议逻辑上划分以下 schema：

- `auth`：用户、角色、权限
- `market`：行情、财务、状态、指数、行业
- `research`：因子、模型、回测
- `portfolio`：组合、调仓、模拟
- `product`：策略产品、订阅、交付
- `risk`：风险事件、告警、监控
- `system`：任务、日志、配置
- `event`：事件中心、风险标签
- `registry`：因子注册、模型注册、实验注册、快照注册

---

# 8. 核心表设计

下面给核心表结构建议。字段不追求 100% 穷尽，但足够指导研发。

---

## 8.1 用户与权限相关

### 8.1.1 auth_users
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 用户ID |
| username | varchar | 用户名 |
| password_hash | varchar | 密码哈希 |
| email | varchar | 邮箱 |
| mobile | varchar | 手机号 |
| status | smallint | 状态 |
| user_type | varchar | admin / researcher / client |
| org_id | bigint | 所属机构 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

### 8.1.2 auth_roles
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 角色ID |
| role_name | varchar | 角色名 |
| role_code | varchar | 角色编码 |

### 8.1.3 auth_user_roles
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| user_id | bigint | 用户ID |
| role_id | bigint | 角色ID |

### 8.1.4 auth_api_keys
| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| user_id | bigint | 用户ID |
| api_key | varchar | API Key |
| secret_hash | varchar | Secret哈希 |
| status | smallint | 状态 |
| expired_at | timestamp | 过期时间 |

---

## 8.2 市场数据相关

### 8.2.1 market_stocks
股票主表

| 字段 | 类型 | 说明 |
|---|---|---|
| stock_id | bigint PK | 内部股票ID |
| ts_code | varchar | 股票代码 |
| symbol | varchar | 证券代码 |
| stock_name | varchar | 股票名称 |
| exchange | varchar | 交易所 |
| board | varchar | 板块 |
| list_date | date | 上市日期 |
| delist_date | date | 退市日期 |
| status | varchar | listed / delisted |
| created_at | timestamp | 创建时间 |

### 8.2.2 market_stock_daily
股票日线行情表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| stock_id | bigint | 股票ID |
| trade_date | date | 交易日 |
| open | numeric | 开盘价 |
| high | numeric | 最高价 |
| low | numeric | 最低价 |
| close | numeric | 收盘价 |
| pre_close | numeric | 前收 |
| volume | numeric | 成交量 |
| amount | numeric | 成交额 |
| turnover_rate | numeric | 换手率 |
| adj_factor | numeric | 复权因子 |
| is_limit_up | boolean | 是否涨停 |
| is_limit_down | boolean | 是否跌停 |
| is_suspended | boolean | 是否停牌 |
| created_at | timestamp | 创建时间 |

建议索引：
- `(stock_id, trade_date)` 唯一索引
- `(trade_date)` 普通索引

### 8.2.3 market_index_daily
指数日线表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| index_code | varchar | 指数代码 |
| trade_date | date | 交易日 |
| open | numeric | 开盘 |
| high | numeric | 最高 |
| low | numeric | 最低 |
| close | numeric | 收盘 |
| volume | numeric | 成交量 |
| amount | numeric | 成交额 |

### 8.2.4 market_trading_calendar
交易日历

| 字段 | 类型 | 说明 |
|---|---|---|
| trade_date | date PK | 日期 |
| is_open | boolean | 是否开市 |
| exchange | varchar | 交易所 |

### 8.2.5 market_stock_status_daily
股票状态日表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| stock_id | bigint | 股票ID |
| trade_date | date | 交易日 |
| is_st | boolean | 是否ST |
| is_star_st | boolean | 是否*ST |
| is_suspended | boolean | 是否停牌 |
| is_limit_up | boolean | 是否涨停 |
| is_limit_down | boolean | 是否跌停 |
| risk_flag | varchar | 风险标记 |

### 8.2. market_index_components
指数成分历史表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| index_code | varchar | 指数代码 |
| trade_date | date | 生效日期 |
| stock_id | bigint | 股票ID |
| weight | numeric | 权重 |

### 8.2.7 market_financials
财务指标宽表或主题表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| stock_id | bigint | 股票ID |
| report_period | date | 报告期 |
| announce_date | date | 公告日 |
| revenue | numeric | 营收 |
| net_profit | numeric | 净利润 |
| total_assets | numeric | 总资产 |
| total_equity | numeric | 净资产 |
| operating_cashflow | numeric | 经营现金流 |
| gross_margin | numeric | 毛利率 |
| roe | numeric | ROE |
| roa | numeric | ROA |
| pe_ttm | numeric | PE |
| pb | numeric | PB |
| ps_ttm | numeric | PS |
| asset_liability_ratio | numeric | 资产负债率 |
| created_at | timestamp | 创建时间 |

关键点：
- 必须保留 `announce_date`
- 查询时按 `announce_date <= as_of_date`

### 8.2.8 market_industry_classification
行业分类历史表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| stock_id | bigint | 股票ID |
| industry_system | varchar | 申万/中信 |
| level1_code | varchar | 一级行业编码 |
| level1_name | varchar | 一级行业名称 |
| level2_code | varchar | 二级行业编码 |
| level2_name | varchar | 二级行业名称 |
| effective_date | date | 生效日 |
| expire_date | date | 失效日 |

### 8.2.9 market_financials_pit
PIT财务表

| 字段 | 类型 | 说明 |
|---|---|---|
| stock_id | bigint | 股票ID |
| report_period | date | 报告期 |
| effective_date | date | 生效日期 |
| announce_date | date | 公告日 |
| source_priority | int | 来源优先级（正式>快报>预告） |
| revision_no | int | 修订版本号 |
| revenue | numeric | 营收 |
| net_profit | numeric | 净利润 |
| total_assets | numeric | 总资产 |
| total_equity | numeric | 净资产 |
| operating_cashflow | numeric | 经营现金流 |
| gross_margin | numeric | 毛利率 |
| roe | numeric | ROE |
| roa | numeric | ROA |
| pe_ttm | numeric | PE |
| pb | numeric | PB |
| ps_ttm | numeric | PS |
| asset_liability_ratio | numeric | 资产负债率 |
| snapshot_id | varchar | 快照ID |

PK: (stock_id, report_period, effective_date, revision_no)

### 8.2.10 market_analyst_estimates_pit
分析师PIT表

| 字段 | 类型 | 说明 |
|---|---|---|
| stock_id | bigint | 股票ID |
| effective_date | date | 生效日期 |
| consensus_eps_fy0 | numeric | 一致预期EPS(FY0) |
| consensus_eps_fy1 | numeric | 一致预期EPS(FY1) |
| analyst_coverage | int | 分析师覆盖数 |
| rating_mean | numeric | 平均评级 |
| snapshot_id | varchar | 快照ID |

PK: (stock_id, effective_date)

### 8.2.11 market_northbound_daily
北向资金表

| 字段 | 类型 | 说明 |
|---|---|---|
| trade_date | date | 交易日 |
| stock_id | bigint | 股票ID |
| net_buy | numeric | 净买入 |
| hold_change | numeric | 持股变化 |

PK: (trade_date, stock_id)

---

## 8.3 股票池相关

### 8.3.1 research_stock_pools
股票池定义表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | PK | 主键 |
| pool_name | varchar | 股票池名称 |
| pool_type | varchar | index / custom |
| benchmark_code | varchar | 基准代码 |
| filter_config | jsonb | 过滤配置 |
| status | varchar | 状态 |
| created_by | bigint | 创建人 |
| created_at | timestamp | 创建时间 |

### 8.3.2 research_stock_pool_snapshots
股票池快照表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| pool_id | bigint | 股票池ID |
| trade_date | date | 交易日 |
| stock_id | bigint | 股票ID |
| included | boolean | 是否纳入 |
| exclude_reason | varchar | 剔除原因 |
| snapshot_version | varchar | 快照版本 |

## 8.4 因子相关

### 8.4.1 research_factors
因子定义表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| factor_code | varchar | 因子编码 |
| factor_name | varchar | 因子名称 |
| factor_category | varchar | 质量/估值/动量等 |
| formula_desc | text | 公式描述 |
| parameter_config | jsonb | 参数配置 |
| direction | smallint | 1正向，-1反向 |
| status | varchar | 状态 |
| created_by | bigint | 创建人 |
| created_at | timestamp | 创建时间 |

### 8.4.2 research_factor_values
因子值结果表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| factor_id | bigint | 因子ID |
| stock_id | bigint | 股票ID |
| trade_date | date | 交易日 |
| raw_value | numeric | 原始值 |
| processed_value | numeric | 预处理后值 |
| neutralized_value | numeric | 中性化后值 |
| zscore_value | numeric | 标准化值 |
| coverage_flag | boolean | 是否有效 |
| run_id | varchar | 任务运行ID |
| created_at | timestamp | 创建时间 |

大表建议：
- PostgreSQL MVP 可先用
- 后续切 ClickHouse

索引建议：
- `(factor_id, trade_date, stock_id)`
- `(trade_date, stock_id)`

### 8.4.3 research_factor_analysis
因子分析结果表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| factor_id | bigint | 因子ID |
| analysis_type | varchar | IC / RankIC / group |
| start_date | date | 开始日期 |
| end_date | date | 结束日期 |
| benchmark_code | varchar | 基准 |
| result_json | jsonb | 分析结果 |
| report_path | varchar | 报告路径 |
| created_at | timestamp | 创建时间 |

---

## 8.5 模型相关

### 8.5.1 research_models
模型定义表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| model_name | varchar | 模型名称 |
| model_type | varchar | multifactor / ranker |
| stock_pool_id | bigint | 股票池ID |
| benchmark_code | varchar | 基准 |
| rebalance_freq | varchar | 调仓频率 |
| holding_count | int | 持仓数 |
| weighting_method | varchar | 等权/打分加权 |
| neutralize_config | jsonb | 中性化配置 |
| constraint_config | jsonb | 约束配置 |
| timing_config | jsonb | 择时配置 |
| status | varchar | draft/published |
| version | varchar | 版本 |
| created_by | bigint | 创建人 |
| created_at | timestamp | 创建时间 |

### 8.5.2 research_model_factor_weights
模型因子权重表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| model_id | bigint | 模型ID |
| factor_id | bigint | 因子ID |
| weight | numeric | 权重 |
| weight_source | varchar | manual/ic/ir |
| created_at | timestamp | 创建时间 |

### 8.5.3 research_model_scores
模型评分结果表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| model_id | bigint | 模型ID |
| trade_date | date | 交易日 |
| stock_id | bigint | 股票ID |
| total_score | numeric | 综合分 |
| factor_score_detail | jsonb | 因子明细 |
| rank_no | int | 排名 |
| run_id | varchar | 运行ID |
| created_at | timestamp | 创建时间 |

---

## 8.6 择时与组合相关

### 8.6.1 portfolio_timing_signals
择时信号表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| model_id | bigint | 模型ID |
| trade_date | date | 交易日 |
| signal_value | numeric | 信号值 |
| target_exposure | numeric | 目标仓位 |
| signal_detail | jsonb | 信号细节 |
| created_at | timestamp | 创建时间 |

### 8.6.2 portfolio_target_portfolios
目标组合表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| model_id | bigint | 模型ID |
| trade_date | date | 交易日 |
| portfolio_version | varchar | 组合版本 |
| target_exposure | numeric | 目标仓位 |
| total_weight | numeric | 总权重 |
| generated_by_run_id | varchar | 任务ID |
| created_at | timestamp | 创建时间 |

### 8.6.3 portfolio_target_positions
目标持仓明细表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| portfolio_id | bigint | 目标组合ID |
| stock_id | bigint | 股票ID |
| target_weight | numeric | 目标权重 |
| score | numeric | 综合分 |
| industry_code | varchar | 行业 |
| liquidity_tag | varchar | 流动性标签 |
| remark | varchar | 备注 |

### 8.6.4 portfolio_rebalance_orders
调仓单表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| model_id | bigint | 模型ID |
| trade_date | date | 调仓日 |
| stock_id | bigint | 股票ID |
| action | varchar | buy/sell/hold |
| current_weight | numeric | 当前权重 |
| target_weight | numeric | 目标权重 |
| est_amount | numeric | 预估成交额 |
| est_cost | numeric | 预估成本 |
| order_status | varchar | pending/done/failed |
| failure_reason | varchar | 失败原因 |

---

## 8.7 回测相关

### 8.7.1 research_backtests
回测任务表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| backtest_name | varchar | 回测名称 |
| model_id | bigint | 模型ID |
| start_date | date | 开始日期 |
| end_date | date | 结束日期 |
| benchmark_code | varchar | 基准 |
| execution_mode | varchar | open/vwap |
| fee_config | jsonb | 费用配置 |
| slippage_config | jsonb | 滑点配置 |
| status | varchar | pending/running/success/failed |
| created_by | bigint | 创建人 |
| created_at | timestamp | 创建时间 |

### 8.7.2 research_backtest_navs
回测净值表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| backtest_id | bigint | 回测ID |
| trade_date | date | 交易日 |
| nav | numeric | 策略净值 |
| benchmark_nav | numeric | 基准净值 |
| excess_nav | numeric | 超额净值 |
| drawdown | numeric | 回撤 |

### 8.7.3 research_backtest_positions
回测持仓表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| backtest_id | bigint | 回测ID |
| trade_date | date | 交易日 |
| stock_id | bigint | 股票ID |
| weight | numeric | 权重 |
| shares | numeric | 股数 |
| market_value | numeric | 市值 |

### 8.7.4 research_backtest_trades
回测成交表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| backtest_id | bigint | 回测ID |
| trade_date | date | 成交日 |
| stock_id | bigint | 股票ID |
| action | varchar | buy/sell |
| price | numeric | 成交价 |
| volume | numeric | 成交量 |
| amount | numeric | 成交额 |
| fee | numeric | 费用 |
| slippage | numeric | 滑点 |
| trade_status | varchar | success/failed |
| fail_reason | varchar | 失败原因 |

### 8.7.5 research_backtest_metrics
回测指标汇总表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| backtest_id | bigint | 回测ID |
| annual_return | numeric | 年化收益 |
| annual_excess_return | numeric | 年化超额 |
| max_drawdown | numeric | 最大回撤 |
| sharpe | numeric | 夏普 |
| calmar | numeric | 卡玛 |
| info_ratio | numeric | 信息比率 |
| turnover | numeric | 换手率 |
| win_rate | numeric | 胜率 |
| metrics_json | jsonb | 扩展指标 |

---

## 8.8 模拟组合相关

### 8.8.1 portfolio_simulated_portfolios
模拟组合主表

| 字段 | | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| model_id | bigint | 模型ID |
| portfolio_name | varchar | 模拟组合名称 |
| benchmark_code | varchar | 基准 |
| start_date | date | 启动日期 |
| status | varchar | running/stopped |
| created_at | timestamp | 创建时间 |

### 8.8.2 portfolio_simulated_positions
模拟持仓表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| sim_portfolio_id | bigint | 模拟组合ID |
| trade_date | date | 交易日 |
| stock_id | bigint | 股票ID |
| weight | numeric | 权重 |
| shares | numeric | 股数 |
| market_value | numeric | 市值 |

### 8.8.3 portfolio_simulated_navs
模拟净值表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| sim_portfolio_id | bigint | 模拟组合ID |
| trade_date | date | 交易日 |
| nav | numeric | 净值 |
| benchmark_nav | numeric | 基准净值 |
| excess_nav | numeric | 超额净值 |
| drawdown | numeric | 回撤 |

---

## 8.9 产品与订阅相关

### 8.9.1 product_products
策略产品表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| product_name | varchar | 产品名称 |
| product_type | varchar | signal/report/api |
| model_id | bigint | 关联模型ID |
| display_name | varchar | 展示名称 |
| description | text | 产品说明 |
| risk_disclosure | text | 风险揭示 |
| status | varchar | draft/online/offline |
| created_at | timestamp | 创建时间 |

### 8.9.2 product_subscriptions
订阅表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| product_id | bigint | 产品ID |
| user_id | bigint | 用户ID |
| plan_type | varchar | month/quarter/year |
| start_date | date | 开始日期 |
| end_date | date | 结束日期 |
| status | varchar | active/expired/cancelled |
| created_at | timestamp | 创建时间 |

### 8.9.3 product_reports
报告表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| product_id | bigint | 产品ID |
| report_type | varchar | weekly/monthly/rebalance |
| report_date | date | 报告日期 |
| title | varchar | 标题 |
| file_path | varchar | 文件路径 |
| meta_json | jsonb | 扩展信息 |
| created_at | timestamp | 创建时间 |

---

## 8.10 风控与系统相关

### 8.10.1 risk_events
风险事件表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| event_type | varchar | drawdown/liquidity/model_drift |
| event_level | varchar | info/warn/critical |
| related_type | varchar | model/portfolio/task |
| related_id | bigint | 关联对象ID |
| trade_date | date | 交易日 |
| detail_json | jsonb | 详情 |
| status | varchar | open/closed |
| created_at | timestamp | 创建时间 |

### 8.10.2 system_task_runs
任务运行表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| task_type | varchar | data_sync/factor_calc/backtest |
| task_name | varchar | 任务名 |
| run_id | varchar | 运行ID |
| status | varchar | pending/running/success/failed |
| params_json | jsonb | 参数 |
| started_at | timestamp | 开始时间 |
| ended_at | timestamp | 结束时间 |
| error_msg | text | 错误信息 |

### 8.10.3 system_audit_logs
审计日志表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint PK | 主键 |
| user_id | bigint | 用户ID |
| action | varchar | 操作类型 |
| resource_type | varchar | 资源类型 |
| resource_id | bigint | 资源ID |
| detail_json | jsonb | 详情 |
| created_at | timestamp | 创建时间 |

---

## 8.11 事件中心相关

### 8.11.1 event_center
事件中心表

| 字段 | 类型 | 说明 |
|---|---|---|
| event_id | bigint PK | 事件ID |
| stock_id | bigint | 股票ID |
| event_type | varchar | 事件类型 |
| event_subtype | varchar | 事件子类型 |
| event_date | date | 事件日期 |
| effective_date | date | 生效日期 |
| expire_date | date | 失效日期 |
| severity | varchar | 严重程度 |
| score | numeric | 事件分数 |
| title | text | 标题 |
| content | text | 内容 |
| source | varchar | 来源 |
| snapshot_id | varchar | 快照ID |

### 8.11.2 risk_flag_daily
风险标签日表

| 字段 | 类型 | 说明 |
|---|---|---|
| trade_date | date | 交易日 |
| stock_id | bigint | 股票ID |
| blacklist_flag | boolean | 黑名单标记 |
| audit_issue_flag | boolean | 审计异常 |
| violation_flag | boolean | 违规标记 |
| pledge_high_flag | boolean | 高质押 |
| goodwill_high_flag | boolean | 高商誉 |
| earnings_warning_flag | boolean | 业绩预警 |
| reduction_flag | boolean | 减持标记 |
| cashflow_risk_flag | boolean | 现金流风险 |
| risk_penalty_score | numeric | 风险惩罚分 |

PK: (trade_date, stock_id)

---

## 8.12 治理与监控相关

### 8.12.1 data_snapshot_registry
数据快照注册表

| 字段 | 类型 | 说明 |
|---|---|---|
| snapshot_id | varchar PK | 快照ID |
| snapshot_date | date | 快照日期 |
| description | text | 描述 |
| source_version_json | text | 数据源版本 |
| created_at | timestamp | 创建时间 |

### 8.12.2 factor_metadata
因子元数据表

| 字段 | 类型 | 说明 |
|---|---|---|
| factor_name | varchar PK | 因子名 |
| factor_group | varchar | 因子组 |
| description | text | 描述 |
| formula | text | 公式 |
| source_table | varchar | 来源表 |
| pit_required | boolean | 是否PIT |
| direction | int | 方向 |
| frequency | varchar | 频率 |
| status | varchar | 状态(experimental/candidate/production/deprecated) |
| version | varchar | 版本 |
| created_at | timestamp | 创建时间 |

### 8.12.3 model_registry
模型注册表

| 字段 | 类型 | 说明 |
|---|---|---|
| model_id | varchar PK | 模型ID |
| model_name | varchar | 模型名 |
| model_type | varchar | 模型类型 |
| feature_set_version | varchar | 特征集版本 |
| label_version | varchar | 标签版本 |
| train_start | date | 训练开始 |
| train_end | date | 训练结束 |
| valid_start | date | 验证开始 |
| valid_end | date | 验证结束 |
| params_json | text | 超参数 |
| oof_metric_json | text | OOF指标 |
| status | varchar | 状态 |
| created_at | timestamp | 创建时间 |

### 8.12.4 experiment_registry
实验注册表

| 字段 | 类型 | 说明 |
|---|---|---|
| experiment_id | varchar PK | 实验ID |
| experiment_name | varchar | 实验名 |
| snapshot_id | varchar | 快照ID |
| config_version | varchar | 配置版本 |
| code_version | varchar | 代码版本 |
| result_summary | text | 结果摘要 |
| status | varchar | 状态 |
| created_at | timestamp | 创建时间 |

### 8.12.5 monitor_factor_health
因子健康监控表

| 字段 | 类型 | 说明 |
|---|---|---|
| trade_date | date | 交易日 |
| factor_name | varchar | 因子名 |
| coverage_rate | numeric | 覆盖率 |
| missing_rate | numeric | 缺失率 |
| ic_rolling | numeric | 滚动IC |
| psi | numeric | PSI |
| health_status | varchar | 健康状态 |

PK: (trade_date, factor_name)

### 8.12.6 monitor_model_health
模型健康监控表

| 字段 | 类型 | 说明 |
|---|---|---|
| trade_date | date | 交易日 |
| model_id | varchar | 模型ID |
| prediction_drift | numeric | 预测漂移 |
| feature_importance_drift | numeric | 特征重要性漂移 |
| oos_score | numeric | OOS分数 |
| health_status | varchar | 健康状态 |

PK: (trade_date, model_id)

### 8.12.7 alert_logs
告警日志表

| 字段 | 类型 | 说明 |
|---|---|---|
| alert_id | bigint PK | 告警ID |
| alert_time | timestamp | 告警时间 |
| alert_type | varchar | 告警类型 |
| severity | varchar | 严重程度 |
| object_type | varchar | 对象类型 |
| object_name | varchar | 对象名 |
| message | text | 消息 |
| resolved_flag | boolean | 是否已解决 |

---

# 9. 表关系说明

核心关系如下：

- `auth_users` 1:N `product_subscriptions`
- `research_stock_pools` 1:N `research_stock_pool_snapshots`
- `research_factors` 1:N `research_factor_values`
- `research_models` 1:N `research_model_factor_weights`
- `research_models` 1:N `research_model_scores`
- `research_models` 1:N `portfolio_timing_signals`
- `research_models` 1:N `portfolio_target_portfolios`
- `portfolio_target_portfolios` 1:N `portfolio_target_positions`
- `research_models` 1:N `research_backtests`
- `research_backtests` 1:N `research_backtest_navs`
- `research_backtests` 1:N `research_backtest_positions`
- `research_backtests` 1:N `research_backtest_trades`
- `research_models` 1:N `portfolio_simulated_portfolios`
- `product_products` N:1 `research_models`
- `product_products` 1:N `product_reports`
- `event_center` N:1 `market_stocks`
- `risk_flag_daily` N:1 `market_stocks`
- `factor_metadata` 1:N `research_factor_values`
- `model_registry` 1:N `research_model_scores`
- `data_snapshot_registry` referenced by all key result tables

---

# 10. 索引与性能设计建议

## 10.1 高频查询索引
重点索引：
- 行情表：`(ts_code, trade_date)` 复合索引（最关键，覆盖90%+查询）、`(trade_date)` 单列索引
- 财务表：`(ts_code, end_date)` 复合索引、`(ann_date)` 公告日期索引（避免未来函数关键查询）
- 指数日线表：`(index_code, trade_date)` 复合索引
- 指数成分表：`(index_code, trade_date)` 复合索引、`(index_code, ts_code)` 复合索引
- 因子值表：`(factor_id, trade_date, stock_id)` 复合索引
- 模型分数表：`(model_id, trade_date, rank_no)`
- 回测净值表：`(backtest_id, trade_date)`
- 模拟净值表：`(sim_portfolio_id, trade_date)`

> **V2.0 更新**：新增 `stock_daily(ts_code, trade_date)`、`stock_financial(ts_code, end_date)`、`stock_financial(ann_date)`、`index_daily(index_code, trade_date)`、`index_components(index_code, trade_date)`、`index_components(index_code, ts_code)` 六个复合索引。迁移脚本：`scripts/add_indexes.py`

## 10.2 分区建议
大表按 `trade_date` 月分区或年分区：
- `market_stock_daily`
- `research_factor_values`
- `research_model_scores`
- `research_backtest_positions`
- `research_backtest_trades`

## 10.3 冷热分层
- 热数据：近 1~2 年
- 冷数据：历史归档
- 回测明细与因子明细可归档到分析库

## 10.4 性能优化（V2.0）

### 10.4.1 N+1查询消除
| 模块 | 优化前 | 优化后 |
|------|--------|--------|
| `model_scorer.calculate_scores()` | 每因子单独查 Factor + FactorValue (26+次) | 批量 `IN` 查询 (2次) |
| `model_scorer._build_factor_ic_data()` | 同上 | 批量查询 |
| `model_scorer._get_forward_return_data()` | 逐股票循环计算前瞻收益 | 向量化 `groupby().shift()` |
| `factor_engine._get_forward_returns()` | 逐股票循环 | 向量化 `groupby().shift()` + `pivot` |
| `factor_engine.calc_factor_decay()` | 每lag一次DB查询 (20次) | 一次查询 + 向量化计算各lag |
| 数据同步脚本 | 逐行 `SELECT` 检查存在性再 `INSERT` | 批量 `IN` 查询已存在键 + `bulk_save_objects` |

### 10.4.2 并行化
| 场景 | 实现 |
|------|------|
| IC计算 | `ProcessPoolExecutor` 并行计算各日期截面因子 |
| 数据同步 | `ThreadPoolExecutor` (4线程) 并行同步股票数据 |
| Celery Worker | `worker_concurrency=8` (原4) |

### 10.4.3 缓存
| 缓存 | 容量 | TTL | 用途 |
|------|------|-----|------|
| `CacheService` (通用) | 2000 | 300s | 热点查询 |
| `factor_cache` (因子专用) | 5000 | 600s | 因子值、IC分析结果 |
| 回测因子预计算缓存 | 无限 | 进程生命周期 | 避免回测时重复计算截面因子 |

缓存特性：TTL + LRU驱逐 + 命中率统计

### 10.4.4 回测优化
- `price_data` 构建：`itertuples` 替代 `iterrows` (5-10x加速)
- 调仓日因子预计算：回测前一次性计算所有调仓日因子，缓存供 `signal_generator` 使用
- 因子截面计算：向量化 `unstack` + `groupby` 替代逐股票循环

### 10.4.5 连接池
- `pool_size`: 10 → 20
- `max_overflow`: 20 → 40

---

# 11. 服务接口设计原则

## 11.1 统一返回格式
建议：
```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "request_id": "xxx"
}
```

## 11.2 分页格式
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
```

## 11.3 幂等要求
以下接口需保证幂等：
- 因子计算触发
- 模型打分触发
- 回测任务创建
- 调仓任务生成
- 报告生成

---

# 12. 任务流设计

## 12.1 日终任务链
建议顺序：

1. `data_sync_calendar`
2. `data_sync_market`
3. `data_sync_status`
4. `data_sync_financial`
5. `data_sync_event`
6. `data_quality_check`
7. `data_snapshot_generate`
8. `stock_pool_snapshot_generate`
9. `factor_preprocess_pipeline`
10. `module_score_run`（quality_growth/expectation/residual_momentum/flow_confirm/risk_penalty）
11. `signal_fusion_run`（dynamic_IC + regime_adjust + high_corr_shrinkage）
12. `ml_enhanced_rank`（optional）
13. `risk_budget_timing_signal`
14. `target_portfolio_generate`（hierarchical_weight + risk_discount + industry_constraint）
15. `risk_check_run`（blacklist + risk_penalty + portfolio_risk_control）
16. `rebalance_order_generate`
17. `factor_health_check`
18. `report_generate_and_notify`

## 12.2 回测任务链
1. 参数校验
2. 回测任务入队
3. 执行回测
4. 写入明细
5. 汇总指标
6. 生成图表与报告
7. 更新状态

 12.3 失败处理
- 支持自动重试
- 超过阈值进入人工处理
- 保留错误日志与输入参数
- 支持从指定节点重跑

---

# 13. 安全与权限设计

## 13.1 权限模型
建议 RBAC：
- admin
- researcher
- pm
- risk_manager
- client
- org_admin

## 13.2 数据权限
- 客户仅能访问已订阅产品
- 研究员仅能访问授权研究空间
- 机构客户支持组织级隔离

## 13.3 安全控制
- JWT / Session 鉴权
- API Key + Secret
- 密码加盐哈希
- 敏感字段加密
- 关键操作审计

---

# 14. 日志、监控与告警

## 14.1 日志分类
- 访问日志
- 业务日志
- 任务日志
- 错误日志
- 审计日志

## 14.2 监控指标
- API 响应时间
- 数据同步成功率
- 因子任务成功率
- 回测任务成功率
- 报告生成耗时
- 每日任务完成时点
- 因子健康监控（IC/IR/PSI/覆盖率）
- 模型漂移监控（预测分布漂移/特征重要性变化）
- 组合风控监控（行业暴露/风格暴露/拥挤度）
- 实盘偏差监控（理想vs实际成交）

## 14.3 告警场景
- 数据同步失败
- 回测任务失败
- 因子任务超时
- 调仓任务失败
- 风险事件触发
- 客户交付失败

---

# 15. 部署建议

## 15.1 MVP部署
建议单机或 2~3 台机器部署：

- Nginx
- FastAPI 服务
- Celery Worker
- PostgreSQL
- Redis
- MinIO

## 15.2 生产部署
建议拆分：
- API服务
- 任务服务
- 数据服务
- 报告服务
- 调度服务

并配套：
- 负载均衡
- 对象存储
- 备份恢复
- 监控告警系统

---

# 16. 数据备份与恢复

## 16.1 备份范围
- PostgreSQL 全量 + 增量
- 对象存储报告文件
- Redis 非必须长期备份
- 配置文件和密钥

## 16.2 恢复要求
- 支持按日恢复
- 支持单表恢复
- 支持历史任务重放
- 支持关键报告追溯

---

# 17. 研发落地建议

## 17.1 MVP优先实现
优先级建议：

### P0
- 市场数据表
- 股票池
- 因子定义与因子值表
- 模型定义与评分表
- 回测主流程
- 模拟组合主流程
- 风险事件表
- 产品和订阅表
- 事件中心表
- 风险标签表
- 因子元数据表
- 模型注册表
- 数据快照注册表

### P1
- ClickHouse 分析库
- 多租户隔离
- 审批流
- 更复杂的任务编排

### P2
- 已支持ML增强排序（Ridge+LightGBM+规则fallback）
- 实时信号推送
- 更细粒度风控引擎

## 17.2 开发顺序建议
1. 数据底座  
2. 股票池与因子  
3. 模型与回测  
4. 组合与模拟  
5. 风控与报告  
6. 订阅与API  

---

# 18. 结论

本技术架构与数据库设计文档定义了 A 股多因子增强策略平台的核心技术实现框架。  
整体设计遵循以下方向：

- 先满足中低频量化平台 MVP 落地
- 保证点时一致、回测可复现、结果可追踪
- 保证研究、生产、交付三条链路可打通
- 保留服务化、机器学习增强、多租户扩展空间

---

# 19. 版本历史

| 版本 | 日期 | 主要变更 |
|---|---|---|
| V1.0 | 2026-03 | 初始版本 |
| V2.0 | 2026-04 | 新增性能优化（N+1消除、并行化、缓存、连接池）、回测优化、复合索引 |
| V2.1 | 2026-04 | 完善模块拆分、补充数据流与任务链 |
| V2.2 | 2026-04 | 新增事件中心/风险标签/因子元数据/模型注册/实验注册/快照注册/因子健康监控/模型健康监控/告警日志等表；新增PIT财务表/分析师PIT表/北向资金表；架构原则增加配置驱动与数据分层；业务服务层增加事件中心/风险惩罚/因子元数据注册/模型注册实验管理/数据快照服务；任务调度层增加事件同步/因子健康检查/模型漂移监控/快照生成任务；数据管理模块增加事件同步/快照/PIT版本管理/分析师北向对齐；股票池模块增加风险事件过滤/黑名单硬过滤；因子模块增加元数据管理/研究流程/统一预处理/模块重组；模型模块增加状态机/动态权重收缩/ML增强排序/置信度/注册表；择时简化为风险预算，组合增加分层赋权/风险折扣/双轨制/换手控制；风控模块增加黑名单/风险惩罚/组合风控/极端保护/全链路监控/自动响应；日终流水线更新为18步；数据库增加event/registry schema；表关系增加新表关联；监控指标增加因子/模型/组合/实盘四类监控；MVP P0增加五张新表；P2更新ML增强排序 |
| V2.3 | 2026-04-24 | 基于业务逻辑详解迭代完善：架构原则新增"先风控后收益"原则；新增3.6市场状态检测模块(Regime)详细设计（4维度检测+4状态输出+业务原理）；择时与组合模块编号顺延为3.7 |
