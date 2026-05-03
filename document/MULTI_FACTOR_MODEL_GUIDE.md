# 多因子选股模型完整指南

## 概述

本项目实现了一个完整的多因子选股模型系统，整合了因子计算、预处理、合成、选股和组合构建的全流程。

## 系统架构

```
MultiFactorModel (核心类)
├── FactorCalculator (因子计算)
│   ├── 80+ 个因子
│   └── 21 个因子组
├── FactorPreprocessor (因子预处理)
│   ├── 去极值 (MAD/3σ)
│   ├── 标准化 (Z-score)
│   └── 中性化 (行业/市值)
├── 因子合成
│   ├── 等权法
│   ├── IC加权
│   ├── IR加权
│   └── 历史收益加权
├── 股票筛选
│   └── Top-N 选股
└── PortfolioBuilder (组合构建)
    ├── 等权分配
    ├── 风险平价
    └── 最小换手
```

## 核心功能

### 1. 因子计算

支持 21 个因子组，80+ 个因子：

**估值类 (Valuation)**
- PE_TTM, PB, PS_TTM, PCF_TTM
- EV_EBITDA, dividend_yield

**质量类 (Quality)**
- ROE_TTM, ROA_TTM, gross_margin
- operating_margin, net_margin
- asset_turnover, debt_to_equity

**成长类 (Growth)**
- revenue_growth_yoy, profit_growth_yoy
- eps_growth_yoy, operating_cashflow_growth

**动量类 (Momentum)**
- return_1m, return_3m, return_6m, return_12m
- volatility_20d, volatility_60d

**盈利质量 (Earnings Quality)**
- accrual_ratio, operating_cashflow_ratio
- earnings_quality_score

**风险惩罚 (Risk)**
- beta, idiosyncratic_vol
- max_drawdown_60d, illiquidity

**聪明钱 (Smart Money)**
- northbound_holding_ratio, northbound_flow_5d
- institutional_holding_ratio

**预期修正 (Expectation)**
- eps_revision_fy0, eps_revision_fy1
- analyst_coverage, rating_upgrade_ratio

### 2. 因子预处理

**去极值**
- MAD 法：中位数绝对偏差
- 3σ 法：3倍标准差

**标准化**
- Z-score 标准化
- 截面标准化

**中性化**
- 行业中性化：消除行业影响
- 市值中性化：消除市值影响

### 3. 因子合成

**等权法 (Equal Weight)**
```python
composite_score = mean(factor_scores)
```

**IC加权 (IC Weighting)**
```python
weight_i = IC_i / sum(|IC_j|)
composite_score = sum(weight_i * factor_i)
```

**IR加权 (Information Ratio)**
```python
weight_i = IR_i / sum(IR_j)
composite_score = sum(weight_i * factor_i)
```

**历史收益加权**
```python
weight_i = historical_return_i / sum(historical_return_j)
composite_score = sum(weight_i * factor_i)
```

### 4. 股票筛选

- Top-N 选股：选择综合得分最高的 N 只股票
- 排除列表：过滤 ST、停牌等股票
- 最小持仓数：保证组合分散度

### 5. 组合构建

**等权模式**
```python
weight_i = 1 / N
```

**风险平价**
```python
weight_i = (1/volatility_i) / sum(1/volatility_j)
```

**最小换手**
- 保留现有持仓
- 仅调整必要的股票
- 控制交易成本

## API 使用

### 1. 完整流程运行

```bash
POST /api/v1/multi-factor/run
```

**请求示例**
```json
{
  "ts_codes": ["000001.SZ", "600000.SH", ...],
  "trade_date": "2024-04-17",
  "total_value": 1000000.0,
  "current_holdings": {},
  "factor_groups": ["valuation", "quality", "growth", "momentum"],
  "weighting_method": "equal",
  "neutralize_industry": true,
  "neutralize_market_cap": true,
  "top_n": 60,
  "exclude_list": []
}
```

**响应示例**
```json
{
  "trade_date": "2024-04-17",
  "target_holdings": {
    "000001.SZ": 1000.0,
    "600000.SH": 1500.0
  },
  "trades": [
    {
      "ts_code": "000001.SZ",
      "action": "buy",
      "shares": 1000.0,
      "price": 10.5
    }
  ],
  "portfolio_value": 1000000.0,
  "position_count": 60
}
```

### 2. 分步执行

**计算因子**
```bash
POST /api/v1/multi-factor/calculate-factors
```

**预处理因子**
```bash
POST /api/v1/multi-factor/preprocess-factors
```

**合成因子**
```bash
POST /api/v1/multi-factor/composite-factors
```

**选择股票**
```bash
POST /api/v1/multi-factor/select-stocks
```

**构建组合**
```bash
POST /api/v1/multi-factor/build-portfolio
```

### 3. 获取配置

```bash
GET /api/v1/multi-factor/config
```

**响应示例**
```json
{
  "available_factor_groups": [
    "valuation", "quality", "growth", "momentum",
    "volatility", "liquidity", "earnings_quality",
    "risk", "smart_money", "expectation"
  ],
  "weighting_methods": ["equal", "ic", "ir", "historical_return"],
  "portfolio_modes": ["research", "production"],
  "default_top_n": 60,
  "default_lookback_days": 252
}
```

## Python SDK 使用

### 基本用法

```python
from datetime import date
from sqlalchemy.orm import Session
from app.core.multi_factor_model import MultiFactorModel, FactorWeightingMethod

# 创建模型实例
model = MultiFactorModel(
    db=db,
    factor_groups=["valuation", "quality", "growth"],
    weighting_method=FactorWeightingMethod.IC,
    neutralize_industry=True,
    neutralize_market_cap=True
)

# 运行模型
result = model.run(
    ts_codes=["000001.SZ", "600000.SH"],
    trade_date=date(2024, 4, 17),
    total_value=1000000.0,
    top_n=60
)

print(f"选中 {len(result['target_holdings'])} 只股票")
print(f"需要执行 {len(result['trades'])} 笔交易")
```

### 分步执行

```python
# 1. 计算因子
factor_df = model.calculate_factors(
    ts_codes=ts_codes,
    trade_date=trade_date,
    lookback_days=252
)

# 2. 预处理
processed_df = model.preprocess_factors(factor_df)

# 3. 合成
composite_df = model.composite_factors(processed_df)

# 4. 选股
selected_df = model.select_stocks(composite_df, top_n=60)

# 5. 构建组合
portfolio = model.build_portfolio(
    selected_df,
    total_value=1000000.0,
    current_holdings={}
)
```

## 配置说明

### 因子组选择

```python
# 使用所有因子组
model = MultiFactorModel(db=db, factor_groups=None)

# 使用特定因子组
model = MultiFactorModel(
    db=db,
    factor_groups=["valuation", "quality", "growth", "momentum"]
)
```

### 加权方法

```python
from app.core.multi_factor_model import FactorWeightingMethod

# 等权
model = MultiFactorModel(db=db, weighting_method=FactorWeightingMethod.EQUAL)

# IC加权
model = MultiFactorModel(db=db, weighting_method=FactorWeightingMethod.IC)

# IR加权
model = MultiFactorModel(db=db, weighting_method=FactorWeightingMethod.IR)

# 历史收益加权
model = MultiFactorModel(db=db, weighting_method=FactorWeightingMethod.HISTORICAL_RETURN)
```

### 中性化选项

```python
# 行业和市值中性化
model = MultiFactorModel(
    db=db,
    neutralize_industry=True,
    neutralize_market_cap=True
)

# 仅行业中性化
model = MultiFactorModel(
    db=db,
    neutralize_industry=True,
    neutralize_market_cap=False
)

# 不做中性化
model = MultiFactorModel(
    db=db,
    neutralize_industry=False,
    neutralize_market_cap=False
)
```

## 测试

运行完整测试：

```bash
python scripts/test_multi_factor_model.py
```

测试输出示例：
```
================================================================================
多因子选股模型测试
================================================================================

[1] 获取测试股票池...
   ✓ 获取到 100 只股票
   ✓ 交易日期: 2024-04-17

[2] 初始化多因子模型...
   ✓ 可用因子组: 21 个

[3] 计算因子...
   ✓ 计算完成: 50 只股票, 35 个因子
   ✓ 因子列表: ['pe_ttm', 'pb', 'ps_ttm', ...]

[4] 因子预处理...
   ✓ 预处理完成: 50 只股票

[5] 因子合成...
   ✓ 合成完成: 50 只股票
   ✓ 得分范围: [-2.1234, 3.4567]

[6] 股票筛选...
   ✓ 选出 30 只股票

[7] 组合构建...
   ✓ 目标持仓: 30 只股票
   ✓ 交易数量: 30 笔
   ✓ 组合总值: 1,000,000.00

[8] 持仓详情（前5只）:
   1. 000001.SZ: 1000 股
   2. 600000.SH: 1500 股
   ...

================================================================================
✓ 多因子模型测试完成！
================================================================================
```

## 性能优化

### 1. 向量化计算

所有因子计算使用 Pandas 向量化操作，避免循环。

### 2. 批量数据加载

一次性加载所需的所有数据，减少数据库查询次数。

### 3. 缓存机制

- 因子数据缓存
- 行业分类缓存
- 市值数据缓存

### 4. 并行计算

支持多进程并行计算因子（可选）。

## 最佳实践

### 1. 因子选择

- 选择低相关性的因子组
- 定期评估因子有效性
- 剔除失效因子

### 2. 参数调优

- 回测不同的 top_n 值
- 测试不同的加权方法
- 评估中性化效果

### 3. 风险控制

- 设置行业权重上限
- 控制个股权重上限
- 监控组合换手率

### 4. 回测验证

- 使用历史数据回测
- 计算夏普比率、最大回撤
- 分析因子贡献度

## 后续优化方向

1. **机器学习集成**
   - XGBoost/LightGBM 因子合成
   - 神经网络预测
   - 强化学习组合优化

2. **高频因子**
   - 日内动量
   - 订单流因子
   - 微观结构因子

3. **另类数据**
   - 舆情因子
   - 卫星数据
   - 供应链数据

4. **实时更新**
   - 实时因子计算
   - 动态调仓
   - 风险预警

5. **性能优化**
   - GPU 加速
   - 分布式计算
   - 增量更新

## 相关文档

- [因子计算文档](./FACTOR_CALCULATION_COMPLETION.md)
- [因子数据验证](./FACTOR_DATA_VERIFICATION.md)
- [回测引擎文档](./BACKTEST_ENGINE.md)
- [组合构建文档](./PORTFOLIO_BUILDER.md)

## 技术支持

如有问题，请查看：
- API 文档: http://localhost:8000/docs
- 项目仓库: [GitHub链接]
- 问题反馈: [Issues链接]
