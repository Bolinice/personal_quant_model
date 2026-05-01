# A股多因子增强策略平台 API 接口文档

**文档版本**：V2.0
**关联文档**：PRD V3.0、算法与工作流设计说明书 V3.0、技术架构与数据库设计 V3.0
**适用范围**：V3.0
**接口风格**：RESTful JSON API
**鉴权方式**：JWT Bearer Token
**字符编码**：UTF-8
**时间格式**：ISO 8601 或 `YYYY-MM-DD`

---

# 1. 接口规范

## 1.1 基础路径
```http
/api/v1
```

## 1.2 通用请求头
```http
Content-Type: application/json
Authorization: Bearer <access_token>
X-Request-Id: <uuid>
```

## 1.3 统一响应格式

### 成功响应
```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 分页响应
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

### 失败响应
```json
{
  "code": 40001,
  "message": "invalid parameter",
  "data": null
}
```

## 1.4 通用错误码

| 错误码 | 含义 |
|---|---|
| 0 | 成功 |
| 40001 | 参数错误 |
| 40002 | 缺少必要参数 |
| 40101 | 未登录或 token 无效 |
| 40301 | 无权限访问 |
| 40401 | 资源不存在 |
| 40901 | 数据冲突 |
| 42901 | 请求频率过高 |
| 50001 | 系统内部错误 |
| 50002 | 异步任务执行失败 |
| 50003 | 数据同步失败 |
| 50004 | 回测执行失败 |

---

# 2. 认证接口 `/api/v1/auth`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/login` | 登录，返回 access_token + refresh_token |
| POST | `/refresh` | 刷新令牌 |
| GET | `/me` | 获取当前用户信息 |
| POST | `/change-password` | 修改密码 |
| POST | `/api-keys` | 创建 API Key |
| POST | `/register` | 用户注册 |
| POST | `/forgot-password` | 忘记密码 |
| POST | `/reset-password` | 重置密码 |

### 2.1 登录

#### POST `/api/v1/auth/login`

```json
{
  "username": "admin",
  "password": "123456"
}
```

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "jwt_access_token",
    "refresh_token": "jwt_refresh_token",
    "expires_in": 7200,
    "user": {
      "id": 1,
      "username": "admin",
      "real_name": "管理员",
      "roles": ["admin"]
    }
  }
}
```

---

# 3. 用户接口 `/api/v1/users`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/` | 创建用户 |
| GET | `/` | 用户列表 |
| GET | `/{user_id}` | 用户详情 |
| PUT | `/{user_id}` | 更新用户 |

### 3.1 用户列表

#### GET `/api/v1/users`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| keyword | string | 否 | 用户名/姓名关键词 |

---

# 4. 证券接口 `/api/v1/securities`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 股票列表（支持 keyword/board/status/is_st 等筛选） |
| GET | `/{ts_code}` | 股票详情 |
| POST | `/` | 创建股票记录 |
| PUT | `/{ts_code}` | 更新股票记录 |
| DELETE | `/{ts_code}` | 删除股票记录 |

---

# 5. 市场数据接口 `/api/v1/market`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/stock-daily` | 股票日线行情查询（ts_code + start_date + end_date） |
| GET | `/index-daily` | 指数日线行情查询（index_code + start_date + end_date） |
| POST | `/stock-daily` | 股票日线数据写入 |
| POST | `/index-daily` | 指数日线数据写入 |

---

# 6. 数据质量接口 `/api/v1/data-quality`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/check` | 数据质量检查（trade_date + check_type） |
| GET | `/missing-days` | 缺失交易日检查 |
| GET | `/price-anomaly` | 价格异常检查 |
| GET | `/zero-volume` | 零成交量检查 |
| GET | `/financial-consistency` | 财务一致性检查 |

---

# 7. 股票池接口 `/api/v1/stock-pools`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 股票池列表 |
| GET | `/{pool_code}` | 股票池详情 |
| POST | `/` | 创建股票池 |
| PUT | `/{pool_id}` | 更新股票池 |
| GET | `/{pool_id}/snapshots` | 股票池快照查询 |
| POST | `/{pool_id}/snapshots` | 创建股票池快照 |

---

# 8. 因子接口 `/api/v1/factors`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 因子定义列表 |
| GET | `/{factor_id}` | 因子详情 |
| POST | `/` | 创建因子定义 |
| PUT | `/{factor_id}` | 更新因子定义 |
| GET | `/{factor_id}/values` | 因子值查询 |
| POST | `/{factor_id}/values` | 写入因子值 |
| POST | `/{factor_id}/calculate` | 触发因子计算 |
| POST | `/{factor_id}/preprocess` | 触发因子预处理 |
| GET | `/{factor_id}/analysis` | 因子分析 |
| POST | `/{factor_id}/analysis` | 执行因子分析 |

---

# 9. 因子元数据接口 `/api/v1/factor-metadata`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/factor-metadata` | 因子元数据列表（支持 factor_group/status 筛选） |
| GET | `/factor-metadata/{factor_name}` | 因子元数据详情（含逻辑/公式/IC统计/预处理配置） |
| POST | `/factor-research` | 提交因子研究任务（7关闸门检查） |
| GET | `/factor-research/{task_id}` | 查询因子研究结果 |

---

# 10. 模型接口 `/api/v1/models`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 模型列表 |
| GET | `/{model_id}` | 模型详情 |
| POST | `/` | 创建模型 |
| PUT | `/{model_id}` | 更新模型 |
| GET | `/{model_id}/factor-weights` | 获取模型因子权重 |
| POST | `/{model_id}/factor-weights` | 设置模型因子权重 |
| PUT | `/{model_id}/factor-weights` | 更新模型因子权重 |
| GET | `/{model_id}/scores` | 获取模型评分结果 |
| POST | `/{model_id}/score` | 运行模型评分 |
| GET | `/{model_id}/performance` | 模型绩效 |

---

# 11. 模型注册接口 `/api/v1/model-registry`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `` | 模型注册列表（支持 model_type/status 筛选） |
| GET | `/{model_id}` | 模型注册详情（含参数/OOF指标/特征集/版本历史） |
| POST | `` | 注册新模型 |

---

# 12. 择时接口 `/api/v1/timing`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/signals` | 查询择时信号 |
| POST | `/signals` | 计算择时信号 |
| GET | `/config` | 获取择时配置 |
| POST | `/config` | 设置择时配置 |
| PUT | `/config` | 更新择时配置 |
| POST | `/ma-signal` | 计算MA择时信号 |
| POST | `/breadth-signal` | 计算市场宽度信号 |
| POST | `/volatility-signal` | 计算波动率信号 |

---

# 13. 组合接口 `/api/v1/portfolios`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 组合列表 |
| POST | `/` | 创建组合 |
| GET | `/{portfolio_id}/positions` | 组合持仓 |
| POST | `/{portfolio_id}/positions` | 写入组合持仓 |
| GET | `/rebalances` | 调仓记录列表 |
| POST | `/research-snapshot` | 生成研究快照（合规用语） |
| POST | `/change-observation` | 生成结构变化观察（合规用语） |

---

# 14. 回测接口 `/api/v1/backtests`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 回测任务列表 |
| GET | `/{backtest_id}` | 回测任务详情 |
| POST | `/` | 创建回测任务 |
| PUT | `/{backtest_id}` | 更新回测任务 |
| GET | `/{backtest_id}/results` | 回测结果 |
| POST | `/{backtest_id}/run` | 运行回测 |
| POST | `/{backtest_id}/cancel` | 取消回测 |

### 14.1 创建回测任务

#### POST `/api/v1/backtests`

```json
{
  "model_id": 1,
  "job_name": "CSI500_MF_V1_2020_2025",
  "benchmark_code": "CSI500",
  "start_date": "2020-01-01",
  "end_date": "2025-12-31",
  "initial_capital": 1000000,
  "commission_rate": 0.0003,
  "stamp_tax_rate": 0.001,
  "slippage_rate": 0.0005
}
```

---

# 15. 模拟组合接口 `/api/v1/simulated-portfolios`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 模拟组合列表 |
| POST | `/` | 创建模拟组合 |
| GET | `/{portfolio_id}/positions` | 模拟组合持仓 |
| POST | `/{portfolio_id}/positions` | 写入模拟组合持仓 |
| GET | `/{portfolio_id}/navs` | 模拟组合净值 |
| POST | `/{portfolio_id}/nav` | 写入模拟组合净值 |
| PUT | `/{portfolio_id}` | 更新模拟组合 |

---

# 16. 产品接口 `/api/v1/products`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/pricing-overview` | 定价概览 |
| GET | `/plans` | 套餐列表 |
| GET | `/pricing-matrix` | 定价矩阵 |
| GET | `/upgrade-packages` | 升级套餐 |
| GET | `/` | 产品列表 |
| POST | `/` | 创建产品 |
| GET | `/{product_id}` | 产品详情 |
| PUT | `/{product_id}` | 更新产品 |
| GET | `/{product_id}/reports` | 产品报告列表 |
| POST | `/{product_id}/reports` | 创建产品报告 |
| POST | `/{product_id}/generate-report` | 生成产品报告 |

---

# 17. 订阅接口 `/api/v1/subscriptions`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/plans` | 订阅套餐列表 |
| POST | `/check-access` | 检查访问权限 |
| POST | `/subscribe` | 创建订阅 |
| GET | `/my/subscriptions` | 我的订阅 |
| POST | `/` | 创建订阅记录 |
| PUT | `/{subscription_id}` | 更新订阅 |
| GET | `/{subscription_id}/histories` | 订阅历史 |
| POST | `/{subscription_id}/history` | 创建订阅历史记录 |
| GET | `/{subscription_id}/permissions` | 订阅权限 |
| POST | `/{subscription_id}/permissions` | 设置订阅权限 |
| POST | `/{subscription_id}/renew` | 续订 |
| POST | `/{subscription_id}/check-permission` | 检查订阅权限 |

---

# 18. 报告接口 `/api/v1/reports`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 报告列表 |
| GET | `/{report_id}` | 报告详情 |
| POST | `/` | 创建报告 |
| PUT | `/{report_id}` | 更新报告 |
| DELETE | `/{report_id}` | 删除报告 |
| GET | `/templates/` | 报告模板列表 |
| GET | `/templates/{template_id}` | 报告模板详情 |
| POST | `/templates/` | 创建报告模板 |
| PUT | `/templates/{template_id}` | 更新报告模板 |
| DELETE | `/templates/{template_id}` | 删除报告模板 |
| GET | `/schedules/` | 报告调度列表 |
| GET | `/schedules/{schedule_id}` | 报告调度详情 |
| POST | `/schedules/` | 创建报告调度 |
| PUT | `/schedules/{schedule_id}` | 更新报告调度 |
| DELETE | `/schedules/{schedule_id}` | 删除报告调度 |
| POST | `/generate/{report_id}` | 生成报告 |
| POST | `/schedules/{schedule_id}/run` | 执行调度报告 |

---

# 19. 策略接口 `/api/v1/strategies`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 策略列表 |
| GET | `/{strategy_id}` | 策略详情 |
| POST | `/` | 创建策略 |
| PUT | `/{strategy_id}` | 更新策略 |
| POST | `/{strategy_id}/publish` | 发布策略 |
| POST | `/{strategy_id}/archive` | 归档策略 |

---

# 20. 事件中心接口 `/api/v1/events`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `` | 事件列表（支持 stock_id/event_type/severity/date 筛选） |
| GET | `/{event_id}` | 事件详情 |
| GET | `/risk-flags` | 风险标签查询（trade_date + stock_id） |
| GET | `/risk-flags/blacklist` | 当前黑名单列表 |

---

# 21. 实验接口 `/api/v1/experiments`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `` | 实验列表 |
| GET | `/{experiment_id}` | 实验详情 |

---

# 22. 数据快照接口 `/api/v1/snapshots`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `` | 快照列表 |
| GET | `/{snapshot_id}` | 快照详情（含数据源版本/代码版本/配置版本） |
| POST | `` | 手动触发快照生成 |

---

# 23. 监控告警接口 `/api/v1/monitor`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/factor-health` | 因子健康状态（IC/IR/PSI/覆盖率） |
| GET | `/model-health` | 模型健康状态（预测漂移/特征重要性/OOS偏差） |
| GET | `/portfolio` | 组合监控（行业暴露/风格暴露/拥挤度/换手率） |
| GET | `/live-tracking` | 实盘偏差监控（成交偏差/成本偏差/回撤） |
| GET | `/alerts` | 告警列表 |
| PUT | `/alerts/{alert_id}/resolve` | 标记告警已解决 |
| GET | `/regime` | 市场状态查询（Regime） |

### 23.1 市场状态 (Regime)

#### GET `/api/v1/monitor/regime`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 否 | 交易日（默认最近交易日） |

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "trade_date": "2026-04-24",
    "regime": "trending",
    "regime_detail": {
      "trend_strength": 0.65,
      "breadth": 0.58,
      "volatility_level": "medium",
      "size_gap": 0.02
    },
    "module_weight_adjustment": {
      "quality_growth": 0.30,
      "expectation": 0.25,
      "residual_momentum": 0.30,
      "flow_confirm": 0.15
    }
  }
}
```

---

# 24. 告警日志接口 `/api/v1/alert-logs`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 告警日志列表 |
| GET | `/{log_id}` | 告警日志详情 |
| POST | `/` | 创建告警日志 |
| PUT | `/{log_id}` | 更新告警日志 |
| DELETE | `/{log_id}` | 删除告警日志 |
| POST | `/risk-monitor/{portfolio_id}` | 触发风险监控告警 |
| POST | `/performance-monitor/{portfolio_id}` | 触发绩效监控告警 |
| POST | `/trigger-all/{portfolio_id}` | 触发所有监控告警 |

---

# 25. 任务日志接口 `/api/v1/task-logs`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 任务日志列表 |
| GET | `/{log_id}` | 任务日志详情 |
| POST | `/` | 创建任务日志 |
| PUT | `/{log_id}` | 更新任务日志 |
| DELETE | `/{log_id}` | 删除任务日志 |

---

# 26. 通知接口 `/api/v1/notifications`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 通知列表 |
| GET | `/unread-count` | 未读通知数量 |
| PUT | `/{notification_id}/read` | 标记通知已读 |
| PUT | `/read-all` | 批量标记已读 |

---

# 27. 绩效分析接口 `/api/v1/performance`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/backtests/{backtest_id}/analysis` | 回测绩效分析 |
| GET | `/backtests/{backtest_id}/industry-exposure` | 行业暴露分析 |
| GET | `/backtests/{backtest_id}/style-exposure` | 风格暴露分析 |
| POST | `/backtests/{backtest_id}/generate-report` | 生成绩效报告 |
| GET | `/simulated-portfolios/{portfolio_id}/analysis` | 模拟组合绩效分析 |

---

# 28. 风险测评接口 `/api/v1/risk-assessment`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/questions` | 获取风险测评问卷 |
| POST | `/submit` | 提交风险测评结果 |
| GET | `/latest` | 获取最新风险测评结果 |

---

# 29. 内容管理接口 `/api/v1/content`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/pages` | 内容页面列表 |
| GET | `/pages/{page}` | 页面内容 |
| GET | `/pages/{page}/sections/{section}` | 页面区块内容 |
| POST | `/blocks` | 创建内容块 |
| PUT | `/blocks/{block_id}` | 更新内容块 |
| POST | `/check-text` | 合规文案检查 |

---

# 30. 用量统计接口 `/api/v1/usage`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 用量统计 |
| GET | `/check` | 检查用量限制 |

---

# 31. 权限建议

## 31.1 管理员
- 全部接口

## 31.2 研究员
- 数据查询、因子、模型、回测、模拟组合、报告生成

## 31.3 客户
- 我的订阅、产品详情、组合查看、报告查看

---

# 32. API 模块总览

| 模块 | 前缀 | 端点数 | 说明 |
|---|---|---|---|
| 认证 | `/auth` | 8 | 登录/注册/令牌/密码 |
| 用户 | `/users` | 4 | 用户管理 |
| 证券 | `/securities` | 5 | 股票数据 |
| 市场 | `/market` | 4 | 行情数据 |
| 数据质量 | `/data-quality` | 5 | 数据质量检查 |
| 股票池 | `/stock-pools` | 6 | 股票池管理 |
| 因子 | `/factors` | 10 | 因子定义/计算/分析 |
| 因子元数据 | `/factor-metadata` | 4 | 因子身份证/研究 |
| 模型 | `/models` | 10 | 模型管理/评分 |
| 模型注册 | `/model-registry` | 3 | ML模型注册 |
| 择时 | `/timing` | 7 | 择时信号/配置 |
| 组合 | `/portfolios` | 6 | 组合/调仓 |
| 回测 | `/backtests` | 7 | 回测任务/结果 |
| 模拟组合 | `/simulated-portfolios` | 7 | 模拟跟踪 |
| 产品 | `/products` | 11 | 产品/定价 |
| 订阅 | `/subscriptions` | 12 | 订阅管理 |
| 报告 | `/reports` | 16 | 报告/模板/调度 |
| 策略 | `/strategies` | 6 | 策略管理 |
| 事件 | `/events` | 4 | 事件/风险标签 |
| 实验 | `/experiments` | 2 | 实验管理 |
| 快照 | `/snapshots` | 3 | 数据快照 |
| 监控 | `/monitor` | 7 | 健康状态/告警/Regime |
| 告警日志 | `/alert-logs` | 8 | 告警记录 |
| 任务日志 | `/task-logs` | 5 | 任务记录 |
| 通知 | `/notifications` | 4 | 通知管理 |
| 绩效 | `/performance` | 5 | 绩效分析 |
| 风险测评 | `/risk-assessment` | 3 | 风险问卷 |
| 内容 | `/content` | 6 | 内容管理/合规检查 |
| 用量 | `/usage` | 2 | 用量统计 |

**总端点数**：29个模块，约150个端点

---