# 量化模型系统优化计划 2026 Q2

## 📊 系统审查总结

**审查日期**: 2026-05-03  
**审查范围**: 数据库设计、算法架构、量化风险控制、系统性能、稳定性、可扩展性、实盘就绪度  
**综合评分**: 8.1/10（优秀）

### 核心优势 ✅
- 架构设计优秀，模块化清晰（Alpha模块5+1架构）
- 已做大量性能优化（N+1消除、向量化、并行化、缓存）
- PIT架构完善，有前视偏差防护意识
- 文档完整（28000+行代码，840+测试用例）
- 代码注释详尽，业务逻辑清晰

### 核心风险 ⚠️
- **Critical**: 存在多处隐蔽的前视偏差风险
- **Critical**: 幸存者偏差处理不完整
- **High**: 数据库性能瓶颈（大表未分区）
- **High**: 缺少实盘关键能力（偏差监控、容量测试）

---

## 🎯 P0 任务清单（功能正确性）— 2周内完成

### ✅ 任务1: 修复财务数据PIT多版本去重 [已完成]

**问题**: 同一报告期可能有"预告→快报→正式报告"三个版本，当前仅按ann_date去重，未考虑优先级

**影响**: 可能使用已被修正的旧数据，导致因子计算错误

**修复内容**:
- 修改 `app/core/pit_guard.py:71-82`
- 增加 `source_priority` 和 `revision_no` 的优先级排序
- 优先级：正式报告(3) > 业绩快报(2) > 业绩预告(1)
- 版本号：数值越大越新

**测试覆盖**:
- ✅ 7个测试用例全部通过
- ✅ 测试文件: `tests/test_pit_guard_multiversion.py`

**验证方法**:
```python
# 场景：某股票Q1有预告(4-15)、快报(4-28)、正式报告(4-30)
# 2023-04-29查询 → 应选快报
# 2023-05-01查询 → 应选正式报告
```

---

### ✅ 任务2: 修复退市股票幸存者偏差 [已完成]

**问题**: 当前代码排除所有已退市股票，但回测时应该包含"当时尚未退市"的股票

**影响**: 回测收益虚高（因为亏损退市的股票被排除了）

**修复内容**:
- 修改 `app/core/universe.py:95-104`
- 按 `delist_date` 时点过滤：只排除"在trade_date之前已退市"的股票
- 如果无 `delist_date` 字段，降级为排除所有 `list_status='D'` 的股票（次优方案）

**测试覆盖**:
- ✅ 5个测试用例全部通过
- ✅ 测试文件: `tests/test_survivorship_bias.py`

**验证方法**:
```python
# 场景：某股票2020-06-01退市
# 回测2019-12-31 → 应包含（当时尚未退市）
# 回测2020-07-01 → 应排除（已退市）
```

---

### 🔄 任务3: 验证行业分类历史时点正确性 [待执行]

**验证目标**: 确认因子中性化时使用的行业分类是历史时点的分类

**验证SQL**:
```sql
-- 检查是否保存了行业调整历史
SELECT ts_code, effective_date, expire_date, level1_name 
FROM market_industry_classification 
WHERE ts_code = '000001.SZ' 
ORDER BY effective_date;

-- 应该看到多条记录，如：
-- 000001.SZ | 2020-01-01 | 2021-06-30 | 金融
-- 000001.SZ | 2021-07-01 | NULL       | 银行
```

**如果只有一条记录，需要修复**:
```python
# app/core/factor_preprocess.py 中性化时
def neutralize_industry(factor: pd.Series, industry: pd.Series, trade_date: date):
    # 错误做法：
    # industry_map = get_current_industry()  # ❌ 用当前分类
    
    # 正确做法：
    industry_map = get_industry_at_date(trade_date)  # ✅ 用历史分类
```

**执行步骤**:
1. 运行验证SQL，检查数据完整性
2. 如果缺失历史数据，补充数据采集
3. 修改因子预处理代码，确保使用历史分类
4. 编写单元测试验证

---

### 🔄 任务4: 验证IC计算无前视偏差 [待执行]

**验证目标**: 确认动态IC加权使用的IC值仅用历史数据计算

**检查代码**:
```python
# app/core/ensemble.py:132-157
# step2_dynamic_ic_weights 使用滚动IC调整权重
```

**风险点**:
- 如果T日的IC用了T日及之后的数据 → 前视偏差
- 正确做法：T日的IC应该用T-60至T-1日的历史数据

**修复建议**:
```python
def calculate_rolling_ic(factor_values, returns, trade_date, window=60):
    """计算滚动IC - 严格时点控制"""
    # 只使用历史数据：[trade_date - window, trade_date - 1]
    start_date = trade_date - timedelta(days=window)
    end_date = trade_date - timedelta(days=1)  # ⚠️ 不包含当日
    
    hist_factor = factor_values[(factor_values.index >= start_date) & 
                                  (factor_values.index <= end_date)]
    hist_return = returns[(returns.index >= start_date) & 
                          (returns.index <= end_date)]
    
    ic = hist_factor.corrwith(hist_return)
    return ic
```

**执行步骤**:
1. 检查IC计算的时间窗口
2. 打印IC计算使用的日期范围
3. 确保不包含T日及之后的数据
4. 编写单元测试验证

---

### 🔄 任务5: 验证残差动量因子无未来函数 [待执行]

**验证目标**: 确认残差收益计算时，回归用的Beta/风格因子是T-1日的

**检查代码**:
```python
# app/core/alpha_modules.py:185-213
# ResidualMomentumModule 使用残差收益
```

**风险点**:
- 如果用T日的因子去解释T日的收益 → 同期相关，不是预测
- 正确做法：用T-60至T-1日的数据估计beta，用T-1日的beta预测T日

**正确实现示例**:
```python
def calculate_residual_return(returns, market_return, size, value, trade_date):
    # 用T-60至T-1日的数据估计beta
    hist_window = 60
    start = trade_date - timedelta(days=hist_window)
    end = trade_date - timedelta(days=1)
    
    # 估计beta
    X = pd.DataFrame({
        'mkt': market_return[start:end],
        'size': size[start:end],
        'value': value[start:end]
    })
    y = returns[start:end]
    beta = LinearRegression().fit(X, y).coef_
    
    # 用T-1日的beta预测T日的期望收益
    expected_return = beta @ [market_return[trade_date-1], 
                               size[trade_date-1], 
                               value[trade_date-1]]
    
    # 残差 = 实际收益 - 期望收益
    residual = returns[trade_date] - expected_return
    return residual
```

**执行步骤**:
1. 阅读残差动量因子的计算逻辑
2. 确认回归窗口和因子时点
3. 如有问题，修复代码
4. 编写单元测试验证

---

### 🔄 任务6: 验证因子预处理顺序正确性 [待执行]

**验证目标**: 确认"中性化→标准化"的顺序正确执行，检查结果分布

**验证代码**:
```python
# 在 app/core/factor_preprocess.py 添加验证函数
def validate_preprocessing_result(processed_series: pd.Series, step_name: str):
    """验证预处理结果的统计特性"""
    stats = {
        'mean': processed_series.mean(),
        'std': processed_series.std(),
        'skew': processed_series.skew(),
        'kurt': processed_series.kurt()
    }
    
    # 标准化后应该满足：
    if step_name == 'standardize':
        assert abs(stats['mean']) < 0.01, f"Mean {stats['mean']} not close to 0"
        assert abs(stats['std'] - 1.0) < 0.01, f"Std {stats['std']} not close to 1"
    
    logger.info(f"Preprocessing validation [{step_name}]: {stats}")
    return stats
```

**执行步骤**:
1. 在预处理流程中添加验证点
2. 运行因子计算，检查日志输出
3. 确认均值≈0，标准差≈1
4. 如有偏差，检查预处理顺序

---

### 🔄 任务7: 验证指数成分历史回溯正确性 [待执行]

**验证目标**: 确认回测时使用的是历史成分股，而非当前成分

**验证SQL**:
```sql
-- 检查沪深300成分股调整历史
SELECT index_code, trade_date, COUNT(DISTINCT ts_code) as stock_count
FROM market_index_components
WHERE index_code = '000300.SH'
GROUP BY index_code, trade_date
ORDER BY trade_date DESC
LIMIT 10;

-- 应该看到每次调整的记录（每半年一次）
-- 如果只有一条记录，说明没有保存历史
```

**如果缺失历史，需要补充数据采集**:
```python
# scripts/sync_index_components_history.py
def sync_index_components_history(index_code, start_date, end_date):
    """补充指数成分股历史数据"""
    pro = ts.pro_api()
    
    # 获取所有调整日期
    trade_dates = get_trade_cal(start_date, end_date)
    
    for trade_date in trade_dates:
        # 查询该日期的成分股
        df = pro.index_weight(
            index_code=index_code,
            trade_date=trade_date
        )
        
        # 保存到数据库
        save_to_db(df)
```

**执行步骤**:
1. 运行验证SQL，检查数据完整性
2. 如果缺失，运行数据补充脚本
3. 验证回测代码使用历史成分
4. 编写单元测试

---

## 📋 P1 任务清单（性能优化）— 4周内完成

### 任务8: 数据库大表分区 🚀 [3天]

**问题**: `stock_daily` 表预计数亿行，查询慢

**方案**: 按 `trade_date` 月度分区

**实施步骤**:
```sql
-- 1. 创建分区表（新表）
CREATE TABLE stock_daily_partitioned (
    LIKE stock_daily INCLUDING ALL
) PARTITION BY RANGE (trade_date);

-- 2. 创建分区（按月）
CREATE TABLE stock_daily_2024_01 PARTITION OF stock_daily_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- ... 继续创建其他月份

-- 3. 迁移数据
INSERT INTO stock_daily_partitioned SELECT * FROM stock_daily;

-- 4. 重命名表
ALTER TABLE stock_daily RENAME TO stock_daily_old;
ALTER TABLE stock_daily_partitioned RENAME TO stock_daily;
```

**预期收益**: 查询性能提升5-10倍

---

### 任务9: 优化数据加载方式 🚀 [2天]

**问题**: `daily_pipeline.py` 使用 `mappings().all()` 一次加载所有数据到内存

**优化方案**:
```python
# app/core/daily_pipeline.py:263-276 修改为：
@staticmethod
def _load_table(...):
    # 使用pandas.read_sql替代ORM（性能更好）
    df = pd.read_sql(
        stmt,
        session.bind,
        parse_dates=[date_col]
    )
    return df if not df.empty else None
```

**预期收益**: 数据加载速度提升2-3倍

---

### 任务10: 实现因子计算分批处理 💾 [3天]

**问题**: 30+因子 × 5000股票 × 250天 = 峰值内存1-2GB

**优化方案**: 分批计算（每批1000只股票）

**预期收益**: 峰值内存降低50-70%

---

### 任务11: 实现回测并行化 ⚡ [2天]

**方案**: 多策略/多参数回测时并行执行

**预期收益**: 4核心机器上，4个策略并行回测时间缩短至原来的30%

---

### 任务12: 添加数据质量监控 📊 [2天]

**新建表**:
```sql
CREATE TABLE data_quality_log (
    id BIGSERIAL PRIMARY KEY,
    check_date DATE NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    check_type VARCHAR(20) NOT NULL,  -- coverage/outlier/consistency/pit
    severity VARCHAR(10) NOT NULL,    -- info/warning/critical
    affected_count INT,
    affected_stocks TEXT[],
    detail JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**监控内容**:
- 覆盖率检查（缺失率>30%告警）
- PIT违规检查（ann_date > trade_date）
- 异常值检查（超出合理范围）
- 一致性检查（OHLC逻辑一致性）

---

## 📋 P2 任务清单（长期改进）— 2-3个月

### 任务13: 实现样本外验证框架 [5天]

**目标**: 防止过拟合

**方案**: Walk-Forward验证
- 训练集（2018-2020）→ 测试集（2021）
- 训练集（2019-2021）→ 测试集（2022）
- 训练集（2020-2022）→ 测试集（2023）

**监控指标**:
- 如果测试集IC < 训练集IC × 0.7 → 过拟合严重

---

### 任务14: 实现实盘偏差监控 [3天]

**目标**: 监控回测与实盘的差异

**监控指标**:
- 收益偏差 > 0.5% → 告警
- 成交率 < 90% → 告警
- 滑点偏差 > 预期 → 告警

---

### 任务15: 简化模型复杂度 [5天]

**目标**: 先用10个核心因子验证，再逐步增加

**核心因子选择**:
- 质量成长（3个）: roe_ttm, revenue_growth_yoy, operating_cashflow_ratio
- 预期修正（2个）: eps_revision_fy0, earnings_surprise
- 残差动量（2个）: residual_return_60d, residual_sharpe
- 资金流（2个）: north_net_inflow_20d, main_force_net_inflow
- 风险（1个）: volatility_20d

**验证流程**:
1. 用10个核心因子回测2018-2023
2. 记录IC、IR、年化收益、夏普
3. 逐步添加其他因子，观察边际贡献
4. 如果新因子IC提升<0.01，不纳入

---

## 📊 优化效果预期

### 功能正确性（P0）
- ✅ 消除前视偏差风险
- ✅ 消除幸存者偏差
- ✅ 回测结果更可信
- **预期IC提升**: 5-15%（如果之前存在偏差）

### 性能优化（P1）
- ✅ 数据加载速度：提升2-3倍
- ✅ 因子计算内存：降低50-70%
- ✅ 回测速度：提升3-4倍（并行化）
- ✅ 数据库查询：提升5-10倍（分区）
- **日终流水线总耗时**: 从60分钟降至20分钟

### 长期改进（P2）
- ✅ 过拟合风险降低
- ✅ 实盘偏差可监控
- ✅ 模型更稳健

---

## 🎯 执行时间表

### 第1-2周：P0任务（功能正确性）✅ 部分完成
- ✅ Day 1-2: 修复PIT多版本去重
- ✅ Day 3: 修复退市股票偏差
- 🔄 Day 4: 验证行业分类时点
- 🔄 Day 5: 验证IC计算时点
- 🔄 Day 6: 验证残差动量时点
- 🔄 Day 7: 验证预处理顺序
- 🔄 Day 8: 验证指数成分历史
- 🔄 Day 9-10: 全面回测验证，对比修复前后的IC/收益差异

### 第3-6周：P1任务（性能优化）
- Week 3: 数据库分区（收益最大）
- Week 4: 优化数据加载 + 分批计算
- Week 5: 回测并行化
- Week 6: 数据质量监控

### 第7-12周：P2任务（长期改进）
- Week 7-8: 样本外验证框架
- Week 9: 实盘偏差监控
- Week 10-12: 简化模型复杂度

---

## 📝 已完成工作总结

### 2026-05-03 完成
1. ✅ **修复财务数据PIT多版本去重**
   - 文件: `app/core/pit_guard.py`
   - 测试: `tests/test_pit_guard_multiversion.py` (7个测试全部通过)
   - 影响: 消除财务数据版本混用导致的前视偏差

2. ✅ **修复退市股票幸存者偏差**
   - 文件: `app/core/universe.py`
   - 测试: `tests/test_survivorship_bias.py` (5个测试全部通过)
   - 影响: 回测收益更真实，不再虚高

---

## 🔗 相关文档

- [系统审查报告](./SYSTEM_AUDIT_2026Q2.md) - 详细审查结果
- [优化历程](./OPTIMIZATION_HISTORY.md) - 历史优化记录
- [技术架构文档](./TDD.md) - 数据库设计
- [算法设计文档](./ADD.md) - 算法逻辑

---

## 📞 联系方式

如有问题，请联系：
- 项目负责人: [待填写]
- 技术支持: [待填写]
