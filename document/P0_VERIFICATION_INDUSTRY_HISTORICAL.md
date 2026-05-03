# P0验证报告：行业分类历史时点正确性

**验证日期**: 2026-05-04  
**验证任务**: 确认因子中性化时使用历史时点的行业分类  
**状态**: ❌ 发现严重问题

---

## 📊 验证结果

### ❌ 发现的严重问题

#### 问题1：数据库表结构不支持历史追踪

**位置**: `app/models/market/stock_industry.py`

**问题描述**:
- `StockIndustry` 表缺少 `effective_date` 和 `expire_date` 字段
- 当前字段：`ts_code, industry_name, industry_code, level, standard, created_at`
- 无法追踪行业分类的历史变化

**影响**:
- 无法记录行业调整历史（如股票从金融业调整到科技业）
- 回测时可能使用错误的行业分类
- 因子中性化结果不准确

**风险等级**: 🔴 高

**示例场景**:
```
某股票A：
- 2020年：属于金融业
- 2022年：调整到科技业

回测2021年时：
- 错误：使用科技业分类（当前分类）
- 正确：应该使用金融业分类（历史分类）
```

---

#### 问题2：中性化代码未考虑历史时点

**位置**: `app/core/factor_preprocess.py:401`

**问题描述**:
```python
def neutralize_industry(self, df, value_col, industry_col):
    # ❌ 没有 trade_date 参数
    # ❌ 直接使用 df[industry_col]，假设行业分类已正确
    # ⚠️  依赖调用方提供正确的历史行业分类
```

**影响**:
- 无法根据交易日期选择正确的行业分类
- 依赖调用方提供正确的历史数据
- 没有验证机制确保行业分类的时点正确性

**风险等级**: 🟡 中

---

## 🔍 详细分析

### 当前实现的问题

**1. 数据库层面**
```
StockIndustry 表：
├─ ts_code (股票代码)
├─ industry_name (行业名称)
├─ industry_code (行业代码)
├─ level (层级)
├─ standard (标准)
└─ created_at (创建时间)

❌ 缺少：
├─ effective_date (生效日期)
└─ expire_date (失效日期)
```

**2. 代码层面**
```python
# 当前实现
def neutralize_industry(self, df, value_col, industry_col):
    industries = pd.get_dummies(df[industry_col], drop_first=True)
    # 直接使用 df[industry_col]，无法验证时点正确性

# 应该的实现
def neutralize_industry(self, df, value_col, industry_col, trade_date=None):
    if trade_date is not None:
        # 验证或查询 trade_date 时点的行业分类
        pass
```

**3. 调用链分析**
```
因子计算 → preprocess() → neutralize_industry()
                ↓
            传入 df（包含 industry_col）
                ↓
            ⚠️  假设 df 中的行业分类是正确的历史时点
            ⚠️  没有验证机制
```

---

## 📋 改进方案

### 方案1：数据库层面支持（推荐）⭐

**优点**: 
- 从源头解决问题
- 支持完整的历史追踪
- 可以查询任意时点的行业分类

**实施步骤**:

1. **修改表结构**
```sql
ALTER TABLE stock_industry
ADD COLUMN effective_date DATE NOT NULL DEFAULT '1990-01-01',
ADD COLUMN expire_date DATE;

-- 添加索引
CREATE INDEX idx_industry_time 
ON stock_industry(ts_code, effective_date, expire_date);

-- 添加注释
COMMENT ON COLUMN stock_industry.effective_date IS '生效日期';
COMMENT ON COLUMN stock_industry.expire_date IS '失效日期（NULL表示当前有效）';
```

2. **数据迁移**
```python
# 将现有数据标记为当前有效
UPDATE stock_industry
SET effective_date = '1990-01-01',
    expire_date = NULL;
```

3. **修改数据同步逻辑**
```python
def sync_industry_classification(ts_code, new_industry, change_date):
    """同步行业分类变更"""
    # 1. 将旧记录的 expire_date 设置为 change_date
    old_record = db.query(StockIndustry).filter(
        StockIndustry.ts_code == ts_code,
        StockIndustry.expire_date == None
    ).first()
    
    if old_record:
        old_record.expire_date = change_date
    
    # 2. 插入新记录
    new_record = StockIndustry(
        ts_code=ts_code,
        industry_name=new_industry,
        effective_date=change_date,
        expire_date=None
    )
    db.add(new_record)
    db.commit()
```

4. **修改查询逻辑**
```python
def get_industry_at_date(ts_code, trade_date):
    """查询指定日期的行业分类"""
    return db.query(StockIndustry).filter(
        StockIndustry.ts_code == ts_code,
        StockIndustry.effective_date <= trade_date,
        (StockIndustry.expire_date > trade_date) | 
        (StockIndustry.expire_date == None)
    ).first()
```

---

### 方案2：代码层面验证（次选）

**优点**: 
- 不需要修改数据库
- 快速实施

**缺点**: 
- 依赖调用方提供正确数据
- 无法从源头解决问题

**实施步骤**:

1. **添加 trade_date 参数**
```python
def neutralize_industry(
    self, 
    df: pd.DataFrame, 
    value_col: str, 
    industry_col: str,
    trade_date: date | None = None
) -> pd.Series:
    """
    行业中性化
    
    Args:
        trade_date: 交易日期，用于验证行业分类的时点正确性
    """
    # 添加验证
    if trade_date is not None:
        # 验证 df 中的行业分类是否为 trade_date 时点的
        # 或者从数据库查询 trade_date 时点的行业分类
        logger.info(f"Neutralizing with industry classification at {trade_date}")
    
    # 原有逻辑...
```

2. **添加文档说明**
```python
"""
⚠️  重要：调用方必须确保 df[industry_col] 包含的是 trade_date 时点的行业分类

错误示例：
    df['industry'] = get_current_industry()  # ❌ 使用当前分类
    
正确示例：
    df['industry'] = get_industry_at_date(trade_date)  # ✅ 使用历史分类
"""
```

---

### 方案3：文档和规范（临时方案）

**优点**: 
- 立即可实施
- 提高团队意识

**缺点**: 
- 依赖人工遵守
- 容易出错

**实施步骤**:

1. **在文档中明确说明**
2. **添加代码审查检查点**
3. **添加运行时告警**

---

## 🎯 验证结论

### 问题严重性

| 问题 | 风险等级 | 影响范围 | 紧急程度 |
|------|---------|---------|---------|
| 数据库表结构不支持历史追踪 | 🔴 高 | 所有使用行业中性化的因子 | 高 |
| 中性化代码未考虑历史时点 | 🟡 中 | 因子预处理流程 | 中 |

### 潜在影响

**对回测结果的影响**:
- 如果行业分类发生变化，回测结果可能不准确
- IC 可能被高估（使用了未来信息）
- 因子有效性评估可能失真

**对实盘的影响**:
- 实盘使用当前分类，影响较小
- 但历史回测与实盘的一致性无法保证

---

## 📝 立即行动

### 高优先级（本周完成）

1. **✅ 完成验证** - 已完成
2. **⏳ 修改数据库表结构** - 待执行
   - 添加 `effective_date` 和 `expire_date` 字段
   - 创建索引
   - 迁移现有数据

3. **⏳ 修改数据同步逻辑** - 待执行
   - 支持行业分类历史记录
   - 同步历史变更数据

### 中优先级（下周完成）

1. **修改中性化代码**
   - 添加 `trade_date` 参数
   - 添加时点验证逻辑

2. **添加查询函数**
   - `get_industry_at_date(ts_code, trade_date)`
   - 支持批量查询

3. **更新文档**
   - 说明行业分类的时点要求
   - 提供正确使用示例

---

## 🎉 总结

本次验证发现了行业分类历史时点的严重问题：

### 核心发现
❌ **数据库表结构不支持历史追踪**
- 缺少 `effective_date` 和 `expire_date` 字段
- 无法记录行业调整历史
- 风险等级：高

❌ **中性化代码未考虑历史时点**
- 没有 `trade_date` 参数
- 依赖调用方提供正确数据
- 风险等级：中

### 建议方案
⭐ **推荐方案1：数据库层面支持**
- 从源头解决问题
- 支持完整的历史追踪
- 实施成本：中等

---

**验证人**: Claude Opus 4.7  
**验证日期**: 2026-05-04  
**测试文件**: `tests/test_industry_historical.py`  
**风险等级**: 🔴 高
