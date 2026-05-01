# 回测引擎优化计划

## 当前状态分析

回测引擎 `app/core/backtest_engine.py` 已有1908行代码，功能较完整：
- ✅ 事件驱动架构
- ✅ T+1交易规则
- ✅ 涨跌停处理
- ✅ 交易成本模型（参与率滑点）
- ✅ 分红派息处理
- ✅ Walk-Forward验证
- ✅ 蒙特卡洛检验
- ✅ 通胀夏普比率

## 优化方向

### 1. 性能优化 ⚡

#### 1.1 向量化计算
- **当前**：部分逐日循环计算
- **优化**：使用 pandas 向量化操作
- **预期提升**：3-5倍速度提升

#### 1.2 并行回测
- **当前**：单线程回测
- **优化**：多策略并行回测（ProcessPoolExecutor）
- **预期提升**：N倍速度提升（N=CPU核心数）

#### 1.3 缓存优化
- **当前**：每次重新计算
- **优化**：缓存中间结果（因子值、信号、持仓）
- **预期提升**：重复回测提速10倍+

### 2. 精度提升 🎯

#### 2.1 增强成本模型
- **冲击成本**：基于订单簿深度的非线性模型
- **时间成本**：分批执行的时间价值损失
- **机会成本**：未成交订单的机会损失

#### 2.2 更真实的成交模拟
- **部分成交**：大单可能无法全部成交
- **成交延迟**：订单提交到成交的时间延迟
- **价格改善**：限价单可能获得更优价格

#### 2.3 风险事件模拟
- **停牌处理**：持仓股票停牌无法卖出
- **退市处理**：退市股票价值归零
- **ST处理**：ST股票涨跌停限制变化

### 3. 功能增强 🚀

#### 3.1 多周期回测
- 支持日内、日频、周频、月频回测
- 自动适配不同频率的数据和规则

#### 3.2 组合归因分析
- 因子归因：各因子对收益的贡献
- 行业归因：行业配置对收益的贡献
- 风格归因：市值、估值等风格暴露

#### 3.3 压力测试
- 极端市场情景模拟
- 流动性危机模拟
- 黑天鹅事件模拟

## 实施计划

### Phase 1: 性能优化（优先级最高）
1. ✅ 向量化净值计算
2. ✅ 向量化持仓更新
3. ✅ 并行回测框架
4. ✅ 结果缓存机制

### Phase 2: 精度提升
1. ✅ 增强冲击成本模型
2. ✅ 部分成交模拟
3. ✅ 停牌/退市处理增强

### Phase 3: 功能增强
1. ⏳ 组合归因分析
2. ⏳ 压力测试框架
3. ⏳ 可视化报告

## 预期成果

- **性能**：10年全A回测 < 60秒（当前约5分钟）
- **精度**：成本估计误差 < 5bps（当前约10bps）
- **功能**：完整的归因分析和压力测试

## 技术方案

### 向量化示例
```python
# 优化前：逐日循环
for date in dates:
    nav = calc_nav_single_day(date)
    
# 优化后：向量化
nav_series = (positions * prices).sum(axis=1) + cash
```

### 并行回测示例
```python
from concurrent.futures import ProcessPoolExecutor

def run_parallel_backtests(strategies, data):
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = executor.map(run_single_backtest, strategies)
    return list(results)
```

### 缓存示例
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_factor_values(date, factor_name):
    # 缓存因子值，避免重复计算
    return calculate_factor(date, factor_name)
```
