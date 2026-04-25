# 一、《A股多因子增强策略平台 API 接口文档》

**文档版本**：V1.3
**关联文档**：PRD V2.4、算法设计说明书 V2.1、技术架构与数据库设计 V2.3
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

## 3.6 数据质量检查

### GET `/api/v1/market/data-quality`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 是 | 交易日 |
| check_type | string | 否 | ohlc_consistency/pct_chg/volume/coverage/cross_validate |

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "trade_date": "2026-04-22",
    "total_stocks": 5200,
    "checked_stocks": 5180,
    "issues": [
      {
        "ts_code": "000001.SZ",
        "check_type": "ohlc_consistency",
        "detail": "high < max(open, close)"
      }
    ],
    "coverage_rate": 0.996
  }
}
```

---

## 3.7 PIT数据查询

### GET `/api/v1/market/pit-financials`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| ts_code | string | 否 | 股票代码 |
| as_of_date | string | 是 | 截止日期（仅返回该日期前公告的数据） |
| report_type | string | 否 | Q1/half_year/Q3/annual |

#### 说明
按公告日（ann_date）过滤财务数据，确保不使用未来信息。

---

## 3.8 幸存者偏差股票池

### GET `/api/v1/market/historical-stock-pool`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 是 | 交易日 |
| include_delisted | bool | 否 | 是否包含退市股（默认true） |

#### 说明
返回指定交易日实际存续的股票池，包含已退市股票，避免幸存者偏差。

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
| preprocess_pipeline | string | 预处理管线（standard=10步管线：缺失值处理→去极值MAD→标准化Z-score→中性化→…） |

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "factor_code": "roe",
        "factor_name": "净资产收益率",
        "category": "quality",
        "direction": "desc",
        "status": "active",
        "factor_group": "quality",
        "coverage_rate": 0.95,
        "ic_mean": 0.032,
        "ic_std": 0.045,
        "ir": 0.71,
        "last_updated": "2026-04-22"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

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

# 7. 择时与市场状态接口

---

## 7.1 计算择时信号

### POST `/api/v1/models/{model_id}/timing-signal`

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
    "model_id": 1,
    "trade_date": "2026-03-31",
    "signal": "bullish",
    "target_position": 1.0,
    "position_tier": "full",
    "position_options": {
      "defensive": 0.3,
      "neutral": 0.6,
      "offensive": 0.8,
      "full": 1.0
    },
    "drawdown_protection": {
      "current_drawdown": -0.02,
      "protection_active": false,
      "protection_threshold": -0.05
    }
  }
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

## 7.3 查询市场状态 (Regime)

### GET `/api/v1/monitor/regime`

#### 查询参数
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

## 7.4 查询日终流水线存档

### GET `/api/v1/models/{model_id}/daily-archive`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 是 | 交易日 |

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "trade_date": "2026-04-24",
    "target_weights": [],
    "final_score": {},
    "module_scores": {
      "quality_growth": {},
      "expectation": {},
      "residual_momentum": {},
      "flow_confirm": {},
      "risk_penalty": {}
    },
    "regime": "trending",
    "risk_exposure": {
      "industry_deviation": {},
      "style_exposure": {}
    }
  }
}
```

---

# 8. 组合与调仓接口

---

## 8.1 生成目标组合

### POST `/api/v1/models/{model_id}/portfolio/generate`

```json
{
  "trade_date": "2026-03-31",
  "method": "layered",
  "risk_discount": true
}
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 是 | 交易日 |
| method | string | 否 | 赋权模式：equal_weight（等权）/ layered（分层赋权）/ optimize（优化赋权），默认 equal_weight |
| risk_discount | bool | 否 | 是否启用风险折价（基于波动率/相关性调整权重），默认 false |

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
  "slippage_rate": 0.0005,
  "robustness_test": true,
  "stress_test": true,
  "attribution": "module"
}
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| model_id | int | 是 | 模型ID |
| job_name | string | 是 | 任务名称 |
| benchmark_code | string | 是 | 基准指数代码 |
| start_date | string | 是 | 回测开始日期 |
| end_date | string | 是 | 回测结束日期 |
| initial_capital | float | 是 | 初始资金 |
| commission_rate | float | 否 | 佣金费率 |
| stamp_tax_rate | float | 否 | 印花税费率 |
| slippage_rate | float | 否 | 滑点费率 |
| robustness_test | bool | 否 | 是否执行鲁棒性检验（多期滚动/参数敏感性/子样本稳定性），默认 false |
| stress_test | bool | 否 | 是否执行压力测试（极端行情/流动性危机/黑天鹅场景），默认 false |
| attribution | string | 否 | 归因分析维度：module（模块归因）/ industry（行业归因）/ style（风格归因）/ timing（择时归因），支持多选以逗号分隔 |

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
    "win_rate": 0.55,
    "profit_loss_ratio": 1.2,
    "cost_erosion_rate": 0.02,
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

# 16. 事件中心接口

---

## 16.1 查询事件列表

### GET `/api/v1/events`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| stock_id | int | 否 | 股票ID |
| event_type | string | 否 | 事件类型（earnings/regulatory/corporate/macro等） |
| severity | string | 否 | 严重程度（info/warning/critical） |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

---

## 16.2 获取事件详情

### GET `/api/v1/events/{event_id}`

---

## 16.3 查询风险标签

### GET `/api/v1/risk-flags`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 是 | 交易日 |
| stock_id | int | 否 | 股票ID |

---

## 16.4 查询当前黑名单列表

### GET `/api/v1/risk-flags/blacklist`

---

# 17. 因子元数据接口

---

## 17.1 查询因子元数据列表

### GET `/api/v1/factor-metadata`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| factor_group | string | 否 | 因子分组（price/fundamental/revision/capital_flow等） |
| status | string | 否 | 状态（active/inactive/candidate） |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

---

## 17.2 获取因子详情

### GET `/api/v1/factor-metadata/{factor_name}`

#### 说明
返回因子完整元数据，包含：
- 因子逻辑与公式
- 数据覆盖率
- IC统计（IC均值/IC标准差/IR/IC胜率）
- 预处理管线配置
- 分层回测收益

---

## 17.3 提交因子研究任务

### POST `/api/v1/factor-research`

```json
{
  "factor_name": "momentum_20d",
  "factor_expression": "close / close.shift(20) - 1",
  "factor_group": "price",
  "universe": "CSI500",
  "start_date": "2020-01-01",
  "end_date": "2025-12-31"
}
```

#### 说明
提交因子研究任务，系统执行7关闸门检查：
1. 数据覆盖率检查（>80%）
2. IC显著性检验（t值>2）
3. IC稳定性检验（IR>0.5）
4. 换手率检查（<50%）
5. 单调性检验（分层收益单调）
6. 正交性检验（与已有因子相关性<0.6）
7. 样本外检验（OOS IC衰减<30%）

#### 响应
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "fr_20260424_001",
    "status": "pending"
  }
}
```

---

## 17.4 查询因子研究结果

### GET `/api/v1/factor-research/{task_id}`

---

# 18. 模型注册接口

---

## 18.1 查询模型列表

### GET `/api/v1/model-registry`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| model_type | string | 否 | 模型类型（linear/tree/nn/ensemble等） |
| status | string | 否 | 状态（candidate/champion/retired） |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

---

## 18.2 获取模型详情

### GET `/api/v1/model-registry/{model_id}`

#### 说明
返回模型完整信息，包含：
- 模型参数配置
- OOF（Out-of-Fold）指标
- 特征集与特征重要性
- 训练样本区间
- 版本历史

---

## 18.3 注册新模型

### POST `/api/v1/model-registry`

```json
{
  "model_name": "XGB_CSI500_V2",
  "model_type": "tree",
  "hyperparameters": {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.05
  },
  "feature_set": ["roe", "ep", "momentum_20d", "volatility_20d"],
  "training_period": {
    "start_date": "2018-01-01",
    "end_date": "2025-12-31"
  },
  "oof_metrics": {
    "ic": 0.045,
    "ir": 0.82,
    "rank_ic": 0.052
  }
}
```

---

## 18.4 查询实验列表

### GET `/api/v1/experiments`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| model_type | string | 否 | 模型类型筛选 |
| status | string | 否 | 状态筛选 |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

---

## 18.5 获取实验详情

### GET `/api/v1/experiments/{experiment_id}`

---

# 19. 数据快照接口

---

## 19.1 查询快照列表

### GET `/api/v1/snapshots`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

---

## 19.2 获取快照详情

### GET `/api/v1/snapshots/{snapshot_id}`

#### 说明
返回快照完整信息，包含：
- 数据源版本（Tushare/AKShare数据时间戳）
- 代码版本（Git commit hash）
- 配置版本（因子配置/模型参数快照）
- 生成时间与耗时

---

## 19.3 手动触发快照生成

### POST `/api/v1/snapshots`

```json
{
  "snapshot_type": "daily",
  "description": "手动触发的日终快照"
}
```

#### 响应
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "snapshot_id": "snap_20260424_001",
    "status": "pending"
  }
}
```

---

# 20. 监控告警接口

---

## 20.1 查询因子健康状态

### GET `/api/v1/monitor/factor-health`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| trade_date | string | 否 | 交易日（默认最近交易日） |
| factor_group | string | 否 | 因子分组筛选 |

#### 说明
返回因子健康指标：IC、IR、PSI（群体稳定性指数）、覆盖率。

---

## 20.2 查询模型健康状态

### GET `/api/v1/monitor/model-health`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| model_id | int | 否 | 模型ID |
| trade_date | string | 否 | 交易日 |

#### 说明
返回模型健康指标：预测漂移、特征重要性变化、OOS偏差。

---

## 20.3 查询组合监控

### GET `/api/v1/monitor/portfolio`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| model_id | int | 否 | 模型ID |
| trade_date | string | 否 | 交易日 |

#### 说明
返回组合监控指标：行业暴露、风格暴露、拥挤度、换手率。

---

## 20.4 查询实盘偏差监控

### GET `/api/v1/monitor/live-tracking`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| model_id | int | 否 | 模型ID |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |

#### 说明
返回实盘偏差监控指标：成交偏差、成本偏差、回撤。

---

## 20.5 查询告警列表

### GET `/api/v1/monitor/alerts`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| severity | string | 否 | 严重程度（info/warning/critical） |
| type | string | 否 | 告警类型（factor/model/portfolio/data） |
| resolved | bool | 否 | 是否已解决 |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

---

## 20.6 标记告警已解决

### PUT `/api/v1/monitor/alerts/{alert_id}/resolve`

#### 响应示例
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "alert_id": 101,
    "resolved": true,
    "resolved_at": "2026-04-24T10:30:00"
  }
}
```

---

# 21. 权限建议

## 21.1 管理员
- 全部接口

## 21.2 研究员
- 数据查询
- 因子
- 模型
- 回测
- 模拟组合
- 报告生成

## 21.3 客户
- 我的订阅
- 产品详情
- 当前组合
- 历史调仓
- 报告查看

---

# 22. API 开发优先级

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
