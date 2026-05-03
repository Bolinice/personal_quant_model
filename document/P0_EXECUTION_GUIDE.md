# P0任务执行指南

## 📊 当前系统状态（2026-05-03）

### ✅ 已完成的修复
1. **PIT多版本去重逻辑** - 已修复并测试通过
2. **幸存者偏差修复** - 已修复并测试通过

### ⚠️ 需要执行的任务

根据诊断结果，发现以下问题：

1. **数据库字段缺失**
   - `stock_financial` 表缺少 `source_priority` 和 `revision_no` 字段
   - `stock_industry` 表缺少 `effective_date` 和 `expire_date` 字段

2. **数据完整性问题**
   - 退市股票数量为0（可能数据未同步或字段未填充）
   - 所有股票只有1条行业记录（缺少历史调整数据）
   - 未发现多版本财务数据（可能都是正式报告）

3. **数据现状**
   - 财务数据记录数: 34,122 条
   - 有行业分类的股票数: 5,517 只
   - 无未来数据（✅ 好）

---

## 🚀 快速执行方案

### 方案A：一键执行（推荐）

```bash
python scripts/run_p0_tasks.py
```

这个脚本会自动执行所有P0任务，包括：
- 数据库字段迁移
- 数据补充（可选）
- 验证测试
- 生成报告

### 方案B：分步执行

#### 第1步：数据库字段迁移（必须）
```bash
python scripts/migrate_add_pit_fields.py
```

**作用**：
- 为 `stock_financial` 表添加 `source_priority` 和 `revision_no` 字段
- 为 `stock_industry` 表添加 `effective_date` 和 `expire_date` 字段
- 创建相关索引

**预期结果**：
```
✅ StockFinancial表字段添加成功
✅ StockIndustry表字段添加成功
```

---

#### 第2步：标记财务数据优先级（必须）
```bash
python scripts/backfill_financial_priority.py mark
```

**作用**：
- 将现有的34,122条财务数据标记为 `source_priority=3`（正式报告）

**预期结果**：
```
已标记 34122 条正式报告
```

---

#### 第3步：同步行业分类历史（推荐）
```bash
python scripts/sync_industry_history.py sync
```

**作用**：
- 从Tushare或stock_basic表获取行业分类
- 填充 `effective_date` 字段

**注意**：
- 需要Tushare API token
- 如果Tushare无法获取历史调整数据，会使用stock_basic中的当前分类

**预期结果**：
```
已插入 5517 条行业分类记录
```

---

#### 第4步：验证数据完整性（推荐）
```bash
python scripts/sync_industry_history.py verify
```

**作用**：
- 检查字段是否添加成功
- 检查数据覆盖率
- 检查是否有历史调整记录

**预期结果**：
```
✅ 字段检查通过
覆盖率: 5517/5517 = 100%
⚠️  未发现行业调整历史（如果Tushare无历史数据）
```

---

#### 第5步：运行测试验证（必须）
```bash
# 验证PIT多版本去重
python -m pytest tests/test_pit_guard_multiversion.py -v

# 验证幸存者偏差修复
python -m pytest tests/test_survivorship_bias.py -v
```

**预期结果**：
```
7 passed (PIT多版本去重)
5 passed (幸存者偏差)
```

---

## 📋 可选任务（需要Tushare API）

### 创建业绩预告/快报表
```bash
python scripts/backfill_financial_priority.py create
```

**作用**：
- 创建 `stock_forecast` 表（业绩预告）
- 创建 `stock_express` 表（业绩快报）

### 同步业绩预告数据
```bash
python scripts/backfill_financial_priority.py sync_forecast
```

**作用**：
- 从Tushare获取2018年至今的业绩预告数据
- 插入到 `stock_forecast` 表

### 同步业绩快报数据
```bash
python scripts/backfill_financial_priority.py sync_express
```

**作用**：
- 从Tushare获取2018年至今的业绩快报数据
- 插入到 `stock_express` 表

---

## 🎯 执行后的验证

### 1. 重新运行诊断
```bash
python scripts/diagnose_p0.py
```

**期望结果**：
```
✅ 所有检查通过！
```

### 2. 测试PIT过滤
```python
from app.core.pit_guard import pit_filter_df
import pandas as pd
from datetime import date

# 构造测试数据
df = pd.DataFrame({
    'ts_code': ['000001.SZ'] * 3,
    'report_period': [date(2023, 3, 31)] * 3,
    'ann_date': [date(2023, 4, 15), date(2023, 4, 28), date(2023, 4, 30)],
    'source_priority': [1, 2, 3],
    'net_profit': [100, 105, 110]
})

# 测试：2023-04-29应该选快报
result = pit_filter_df(df, date(2023, 4, 29))
assert len(result) == 1
assert result.iloc[0]['source_priority'] == 2
print("✅ PIT过滤测试通过")
```

### 3. 测试幸存者偏差修复
```python
from app.core.universe import UniverseBuilder
import pandas as pd
from datetime import date

builder = UniverseBuilder()

# 构造测试数据：某股票2020-06-01退市
stock_basic = pd.DataFrame({
    'ts_code': ['000001.SZ'],
    'list_status': ['D'],
    'delist_date': [date(2020, 6, 1)],
    'list_date': [date(2010, 1, 1)]
})

price_df = pd.DataFrame({
    'ts_code': ['000001.SZ'] * 20,
    'trade_date': [date(2019, 12, i) for i in range(1, 21)],
    'close': [10.0] * 20,
    'amount': [1e8] * 20
})

# 测试：2019年应该包含
universe = builder.build(
    trade_date=date(2019, 12, 31),
    stock_basic_df=stock_basic,
    price_df=price_df,
    min_list_days=0,
    min_daily_amount=0,
    min_price=0,
    exclude_delist=True
)

assert '000001.SZ' in universe
print("✅ 幸存者偏差修复测试通过")
```

---

## 📊 预期改进效果

### 功能正确性
- ✅ 消除财务数据版本混用导致的前视偏差
- ✅ 消除退市股票导致的幸存者偏差
- ✅ 支持行业分类历史时点回溯（如果有历史数据）

### 回测准确性
- **预期IC提升**: 5-15%（如果之前存在偏差）
- **回测收益**: 更真实，不再虚高
- **因子有效性**: 更准确的评估

---

## ⚠️ 注意事项

### 1. 数据库备份
执行迁移前，建议备份数据库：
```bash
pg_dump -U postgres -d quant_db > backup_$(date +%Y%m%d).sql
```

### 2. Tushare API限制
- 业绩预告/快报数据需要Tushare积分
- 如果积分不足，可以跳过可选任务
- 核心功能（PIT去重、幸存者偏差）不依赖Tushare

### 3. 行业分类历史
- Tushare可能没有完整的行业调整历史
- 如果无法获取，系统会使用当前分类作为默认值
- 这不会影响核心功能，但可能影响行业中性化的准确性

### 4. 退市股票数据
- 当前退市股票数量为0，可能是：
  - 数据未同步
  - `delist_date` 字段未填充
  - 数据库中只有在市股票
- 建议检查数据源，确保包含退市股票的历史数据

---

## 🔄 下一步计划

### P0任务完成后
1. **全面回测验证**
   - 运行完整回测（2018-2023）
   - 对比修复前后的IC/收益差异
   - 记录改进效果

2. **剩余P0验证任务**
   - 验证IC计算无前视偏差
   - 验证残差动量因子时点
   - 验证因子预处理顺序
   - 验证指数成分历史回溯

3. **开始P1性能优化**
   - 数据库大表分区（性能提升5-10倍）
   - 优化数据加载方式（速度提升2-3倍）
   - 实现回测并行化（4核心加速至30%）

---

## 📞 需要帮助？

如果遇到问题：
1. 查看详细日志：`document/P0_EXECUTION_LOG.txt`
2. 重新运行诊断：`python scripts/diagnose_p0.py`
3. 查看优化计划：`document/OPTIMIZATION_PLAN_2026Q2.md`

---

**最后更新**: 2026-05-03  
**状态**: P0任务 2/7 已完成，5/7 待执行
