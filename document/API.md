# 一、《A股多因子增强策略平台 API 接口文档》

**文档版本**：V1.0  
**产品文档版本**：V2.0  
**适用范围**：MVP / V2.0  
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
  "code":0,
  "message": "success",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
```

###失败响应
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

# 2. 认证与用户接口

---

## 2.1 登录

### POST `/api/v1/auth/login`

#### 请求参数
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

## 2.2 获取当前用户信息

### GET `/api/v1/auth/me`

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "username": "admin",
    "real_name": "管理员",
    "email": "admin@test.com",
    "roles": ["admin"]
  }
}
```

---

## 2.3 退出登录

### POST `/api/v1/auth/logout`

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": true
}
```

---

## 2.4 用户列表

### GET `/api/v1/users`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| keyword | string | 否 | 用户名/姓名关键词 |
| status | string | 否 | active/disabled |

---

## 2.5 创建用户

### POST `/api/v1/users`

```json
{
  "username": "researcher1",
  "password": "123456",
  "real_name": "研究员A",
  "email": "a@test.com",
  "phone": "13800000000",
  "role_codes": ["researcher"]
}
```

---

# 3. 基础数据接口

---

## 3.1 股票列表

### GET `/api/v1/securities`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| keyword | string | 代码/名称 |
| board | string | 主板/创业板/科创板 |
| status | string | listed/delisted |
| is_st | bool | 是否 ST |
| page | int | 页码 |
| page_size | int | 每页数量 |

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "ts_code": "000001.SZ",
        "symbol": "000001",
        "name": "平安银行",
        "board": "main",
        "industry_name": "银行",
        "list_date": "1991-04-03",
        "status": "listed"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

---

## 3.2 股票日线行情

### GET `/api/v1/market/stock-daily`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| ts_code | string | 是 | 股票代码 |
| start_date | string | 是 | 开始日期 |
| end_date | string | 是 | 结束日期 |

---

## 3.3 指数日线行情

### GET `/api/v1/market/index-daily`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| index_code | string | 是 | 指数代码 |
| start_date | string | 是 | 开始日期 |
| end_date | string | 是 | 结束日期 |

---

## 3.4 交易日历

### GET `/api/v1/market/trading-calendar`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| start_date | string | 开始日期 |
| end_date | string | 结束日期 |
| is_open | bool | 是否开市 |

---

## 3.5 指数成分股

### GET `/api/v1/index-components`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| index_code | string | 是 | 如 CSI500 |
| trade_date | string | 是 | 查询日期 |

---

# 4. 股票池接口

---

## 4.1 股票池列表

### GET `/api/v1/stock-pools`

---

## 4.2 创建股票池

### POST `/api/v1/stock-pools`

```json
{
  "pool_code": "CSI500_MVP",
  "pool_name": "中证500增强股票池",
  "base_index_code": "CSI500",
  "filter_config": {
    "exclude_st": true,
    "exclude_suspended": true,
    "exclude_new_stock_days": 120,
    "min_avg_amount": 50000000
  },
  "description": "MVP使用股票池"
}
```

---

## 4.3 股票池快照查询

### GET `/api/v1/stock-pools/{pool_id}/snapshots`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 是 | 交易日 |
| eligible_only | bool | 否 | 是否仅返回可投资股票 |

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "security_id": 1,
      "ts_code": "000001.SZ",
      "name": "平安银行",
      "is_eligible": true,
      "exclude_reason": null
    }
  ]
}
```

---

# 5. 因子接口

---

## 5.1 因子定义列表

### GET `/api/v1/factors`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| category | string | quality/valuation/momentum |
| status | string | active/inactive |

---

## 5.2 创建因子定义

### POST `/api/v1/factors`

```json
{
  "factor_code": "roe",
  "factor_name": "净资产收益率",
  "category": "quality",
  "direction": "desc",
  "calc_expression": "financial_indicators.roe",
  "description": "质量因子ROE"
}
```

---

## 5.3 因子值查询

### GET `/api/v1/factors/{factor_id}/values`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 是 | 日期 |
| pool_id | int | 否 | 股票池ID |
| security_id | int | 否 | 股票ID |

---

## 5.4 触发因子计算任务

### POST `/api/v1/factor-jobs/run`

```json
{
  "trade_date": "2026-03-31",
  "pool_id": 1,
  "factor_ids": [1, 2, 3, 4]
}
```

#### 响应
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "job_id": 101,
    "status": "pending"
  }
}
```

---

## 5.5 因子分析摘要

### GET `/api/v1/factors/{factor_id}/analysis-summary`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| start_date | string | 开始日期 |
| end_date | string | 结束日期 |
| pool_id | int | 股票池ID |

#### 说明
MVP阶段可先返回基础统计：
- 覆盖率
- 均值
- 标准差
- 分位数

P1 再扩展 IC、分层收益。

---

# 6. 模型接口

---

## 6.1 模型列表

### GET `/api/v1/models`

---

## 6.2 创建模型

### POST `/api/v1/models`

```json
{
  "model_code": "CSI500_MULTI_FACTOR_V1",
  "model_name": "中证500多因子增强V1",
  "pool_id": 1,
  "rebalance_frequency": "monthly",
  "hold_count": 20,
  "weighting_method": "equal_weight",
  "timing_enabled": true,
  "timing_config": {
    "benchmark_code": "CSI500",
    "ma_window": 120,
    "below_ma_exposure": 0.5
  },
  "constraint_config": {
    "single_stock_max_weight": 0.1
  },
  "description": "MVP版本模型"
}
```

---

## 6.3 配置模型因子权重

### POST `/api/v1/models/{model_id}/factor-weights`

```json
{
  "weights": [
    { "factor_id": 1, "weight": 0.2 },
    { "factor_id": 2, "weight": 0.2 },
    { "factor_id": 3, "weight": 0.3 },
    { "factor_id": 4, "weight": 0.3 }
  ]
}
```

---

## 6.4 获取模型详情

### GET `/api/v1/models/{model_id}`

---

## 6.5 运行模型评分

### POST `/api/v1/models/{model_id}/score`

```json
{
  "trade_date": "2026-03-31"
}
```

#### 响应
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "model_id": 1,
    "trade_date": "2026-03-31",
    "selected_count": 20
  }
}
```

---

## 6.6 获取模型评分结果

### GET `/api/v1/models/{model_id}/scores`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 是 | 日期 |
| selected_only | bool | 否 | 是否仅显示入选股票 |

---

# 7. 择时接口

---

## 7.1 计算择时信号

### POST `/api/v1/models/{model_id}/timing-signal`

```json
{
  "trade_date": "2026-03-31"
}
```

---

## 7.2 查询择时信号

### GET `/api/v1/models/{model_id}/timing-signals`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| start_date | string | 是 | 开始日期 |
| end_date | string | 是 | 结束日期 |

---

# 8. 组合与调仓接口

---

## 8.1 生成目标组合

### POST `/api/v1/models/{model_id}/portfolio/generate`

```json
{
  "trade_date": "2026-03-31"
}
```

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "trade_date": "2026-03-31",
    "hold_count": 20,
    "target_exposure": 1.0
  }
}
```

---

## 8.2 查询组合持仓

### GET `/api/v1/models/{model_id}/portfolio/positions`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 是 | 日期 |

---

## 8.3 生成调仓记录

### POST `/api/v1/models/{model_id}/rebalance`

```json
{
  "trade_date": "2026-03-31"
}
```

---

## 8.4 查询调仓记录列表

### GET `/api/v1/models/{model_id}/rebalances`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| start_date | string | 开始日期 |
| end_date | string | 结束日期 |

---

## 8.5 查询调仓明细

### GET `/api/v1/rebalances/{rebalance_id}`

---

# 9. 回测接口

---

## 9.1 创建回测任务

### POST `/api/v1/backtests`

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

#### 响应
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "backtest_id": 1001,
    "status": "pending"
  }
}
```

---

## 9.2 回测任务列表

### GET `/api/v1/backtests`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| model_id | int | 模型ID |
| status | string | pending/running/success/failed |
| page | int | 页码 |
| page_size | int | 每页数量 |

---

## 9.3 回测任务详情

### GET `/api/v1/backtests/{backtest_id}`

---

## 9.4 回测结果摘要

### GET `/api/v1/backtests/{backtest_id}/result`

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_return": 1.23,
    "annual_return": 0.18,
    "benchmark_return": 0.12,
    "excess_return": 0.06,
    "max_drawdown": -0.21,
    "sharpe": 1.12,
    "calmar": 0.86,
    "information_ratio": 0.65,
    "turnover_rate": 1.8,
    "report_path": "/reports/backtest_1001.pdf"
  }
}
```

---

## 9.5 回测净值序列

### GET `/api/v1/backtests/{backtest_id}/navs`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| start_date | string | 开始日期 |
| end_date | string | 结束日期 |

---

## 9.6 回测交易明细

### GET `/api/v1/backtests/{backtest_id}/trades`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| page | int | 页码 |
| page_size | int | 每页数量 |

---

## 9.7 取消回测任务

### POST `/api/v1/backtests/{backtest_id}/cancel`

---

# 10. 模拟组合接口

---

## 10.1 创建模拟组合

### POST `/api/v1/simulated-portfolios`

```json
{
  "model_id": 1,
  "name": "中证500多因子模拟组合",
  "benchmark_code": "CSI500",
  "start_date": "2026-01-01",
  "initial_capital": 1000000
}
```

---

## 10.2 模拟组合列表

### GET `/api/v1/simulated-portfolios`

---

## 10.3 模拟组合详情

### GET `/api/v1/simulated-portfolios/{portfolio_id}`

---

## 10.4 模拟组合净值

### GET `/api/v1/simulated-portfolios/{portfolio_id}/navs`

---

## 10.5 模拟组合持仓

### GET `/api/v1/simulated-portfolios/{portfolio_id}/positions`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| trade_date | string | 日期 |

---

# 11. 产品与订阅接口

---

## 11.1 策略产品列表

### GET `/api/v1/products`

---

## 11.2 创建策略产品

### POST `/api/v1/products`

```json
{
  "model_id": 1,
  "product_code": "CSI500_ENHANCED_V1",
  "product_name": "中证500增强策略V1",
  "description": "基于质量、估值、动量因子的增强策略",
  "risk_level": "medium"
}
```

---

## 11.3 套餐列表

### GET `/api/v1/subscription-plans`

---

## 11.4 创建订阅

### POST `/api/v1/subscriptions`

```json
{
  "user_id": 10,
  "product_id": 1,
  "plan_id": 2,
  "start_time": "2026-04-01T00:00:00"
}
```

---

## 11.5 我的订阅

### GET `/api/v1/my/subscriptions`

---

## 11.6 产品报告列表

### GET `/api/v1/products/{product_id}/reports`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| report_type | string | weekly/monthly/backtest |
| start_date | string | 开始日期 |
| end_date | string | 结束日期 |

---

## 11.7 产品当前组合

### GET `/api/v1/products/{product_id}/current-portfolio`

#### 权限
- 仅订阅用户可访问

---

## 11.8 产品历史调仓

### GET `/api/v1/products/{product_id}/rebalances`

---

# 12. 任务与告警接口

---

## 12.1 任务日志列表

### GET `/api/v1/task-logs`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| task_type | string | data_sync/factor_calc/backtest |
| status | string | success/failed/running |
| page | int | 页码 |
| page_size | int | 每页数量 |

---

## 12.2 告警日志列表

### GET `/api/v1/alert-logs`

---

## 12.3 手动发送测试告警

### POST `/api/v1/alert-logs/test`

```json
{
  "level": "warning",
  "title": "测试告警",
  "content": "这是一条测试告警"
}
```

---

# 13. 通知接口

---

## 13.1 通知列表

### GET `/api/v1/notifications`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| is_read | bool | 是否已读 |
| notification_type | string | system/risk/rebalance/report |
| page | int | 页码 |
| page_size | int | 每页数量 |

---

## 13.2 标记通知已读

### PUT `/api/v1/notifications/{notification_id}/read`

---

## 13.3 批量标记已读

### PUT `/api/v1/notifications/read-all`

---

# 14. 策略接口

---

## 14.1 策略列表

### GET `/api/v1/strategies`

#### 查询参数
| 参数 | 类型 | 说明 |
|---|---|---|
| status | string | draft/published/archived |
| page | int | 页码 |
| page_size | int | 每页数量 |

---

## 14.2 创建策略

### POST `/api/v1/strategies`

```json
{
  "name": "中证500增强策略V1",
  "model_id": 1,
  "description": "基于质量、估值、动量因子的增强策略"
}
```

---

# 15. 绩效分析接口

---

## 15.1 回测绩效分析

### GET `/api/v1/performance/backtests/{backtest_id}/analysis`

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "returns": {
      "total_return": 1.23,
      "annual_return": 0.18,
      "excess_return": 0.06
    },
    "risk": {
      "max_drawdown": -0.21,
      "volatility": 0.15,
      "sharpe": 1.12,
      "calmar": 0.86,
      "information_ratio": 0.65
    },
    "attribution": {
      "industry_contribution": {},
      "style_contribution": {}
    }
  }
}
```

---

## 15.2 模拟组合绩效分析

### GET `/api/v1/performance/simulated-portfolios/{portfolio_id}/analysis`

---

# 16. 权限建议

## 16.1 管理员
- 全部接口

## 16.2 研究员
- 数据查询
- 因子
- 模型
- 回测
- 模拟组合
- 报告生成

## 16.3 客户
- 我的订阅
- 产品详情
- 当前组合
- 历史调仓
- 报告查看

---

# 17. API 开发优先级

## P0
- 认证
- 股票/指数数据查询
- 股票池
- 因子
- 模型
- 择时
- 组合/调仓
- 回测
- 模拟组合
- 产品/订阅
- 报告查看

## P1
- 任务日志
- 告警日志
- 因子分析接口
- 管理端统计接口

---
