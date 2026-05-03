# P0验证报告：残差动量因子无未来函数

## 验证信息

- **验证日期**: 2026-05-04
- **验证人**: Claude (Opus 4.7)
- **验证脚本**: `tests/test_residual_momentum.py`
- **验证结果**: ❌ **失败 - 因子未实现**

---

## 验证目标

验证残差动量因子（residual_return_20d/60d/120d）的计算逻辑：
1. 检查残差收益率因子是否已实现
2. 确认残差收益率计算时只使用历史数据
3. 验证风格因子回归不包含未来信息

---

## 验证结果

### ❌ 严重问题：残差收益率因子未实现

**问题描述**:
- `ResidualMomentumModule` 在 `app/core/alpha_modules.py` 中定义了因子配置
- 但在整个代码库中未找到残差收益率的计算实现
- 因子只有配置，没有计算逻辑

**影响范围**:
- **严重程度**: 🔴 高
- **影响模块**: ResidualMomentumModule
- **影响因子**: 
  - `residual_return_20d` (权重 0.25)
  - `residual_return_60d` (权重 0.30)
  - `residual_return_120d` (权重 0.15)
- **总权重占比**: 70% (0.25 + 0.30 + 0.15)

**实际后果**:
1. ResidualMomentumModule 无法正常工作
2. 如果在回测中使用该模块，会因缺少因子数据而失败
3. 因子权重配置无法生效

---

## 详细分析

### 1. 因子定义检查

**位置**: `app/core/alpha_modules.py:191-206`

```python
class ResidualMomentumModule(AlphaModule):
    """
    残差动量模块
    
    因子列表:
      - residual_return_20d: 20日残差收益率 (方向+)
      - residual_return_60d: 60日残差收益率 (方向+)
      - residual_return_120d: 120日残差收益率 (方向+)
      ...
    """
    
    def __init__(self):
        factors = {
            "residual_return_20d": {"direction": 1, "weight": 0.25},
            "residual_return_60d": {"direction": 1, "weight": 0.30},
            "residual_return_120d": {"direction": 1, "weight": 0.15},
            ...
        }
```

**结论**: ✅ 因子定义存在，配置合理

---

### 2. 因子计算实现检查

**搜索范围**: 整个 `app/` 目录

**搜索结果**:
```bash
# 搜索残差收益率计算函数
$ grep -rn "def.*residual_return" app/
# 无结果

# 搜索 app/core/factors/ 中的残差相关代码
$ grep -rn "residual.*return" app/core/factors/
# 无结果

# 检查 momentum.py
$ grep -n "residual" app/core/factors/momentum.py
# 无结果
```

**结论**: ❌ 未找到任何残差收益率计算实现

---

### 3. 依赖模块检查

#### 3.1 RiskModel 检查

**位置**: `app/core/risk_model.py`

**可用方法**:
- `barra_factor_exposure()` - 计算Barra风格因子暴露
- `barra_factor_return()` - 计算Barra因子收益率
- `estimate_factor_covariance()` - 估计因子协方差矩阵
- `estimate_idiosyncratic_variance()` - 估计特质方差

**结论**: ✅ RiskModel 存在，提供了风格因子回归所需的基础功能

**问题**: ⚠️ 但未找到调用 RiskModel 计算残差收益率的代码

---

#### 3.2 FactorCalculator 检查

**位置**: `app/core/factor_calculator.py`

**搜索结果**:
```bash
$ grep -n "residual" app/core/factor_calculator.py
# 无结果
```

**结论**: ❌ FactorCalculator 中没有残差相关方法

---

### 4. 因子计算模块结构

**目录**: `app/core/factors/`

**现有模块**:
- `momentum.py` - 动量因子（普通动量，无残差动量）
- `valuation.py` - 估值因子
- `quality.py` - 质量因子
- `growth.py` - 成长因子
- `liquidity.py` - 流动性因子
- `volatility.py` - 波动率因子
- `alternative.py` - 另类因子

**结论**: ❌ 没有专门的残差动量计算模块

---

## 残差收益率计算原理

### 标准计算流程

```
1. 计算风格因子暴露
   ├─ 使用 T-1 日及之前的数据
   ├─ 计算 size, value, momentum 等因子
   └─ ⚠️ 不能使用 T 日数据

2. 风格因子回归
   ├─ 使用历史窗口（如过去60日）
   ├─ 回归模型: r_i,t = β_i * f_t + ε_i,t
   └─ ⚠️ 回归窗口应该是 [T-60, T-1]

3. 计算残差收益率
   ├─ residual_return_i,T = r_i,T - (β_i * f_T)
   ├─ r_i,T: T日实际收益率
   ├─ β_i: 历史回归得到的因子暴露
   └─ f_T: T日因子收益率
```

### 潜在前视偏差风险

| 风险类型 | 错误示例 | 正确示例 |
|---------|---------|---------|
| **使用T日数据计算因子暴露** | `size_T = log(market_cap_T)` | `size_T = log(market_cap_{T-1})` |
| **回归窗口包含未来数据** | `returns[T-59:T+1]` | `returns[T-60:T]` |
| **使用未来的因子收益率** | `factor_return(T)` | `factor_return(T-1)` |

---

## 解决方案

### 方案1：实现残差收益率计算（推荐）

**实现位置**: `app/core/factors/momentum.py`

**核心函数**:
```python
def calc_residual_return(
    returns: pd.DataFrame,
    factor_exposures: pd.DataFrame,
    lookback_window: int = 60
) -> pd.DataFrame:
    """
    计算残差收益率
    
    Args:
        returns: 股票收益率，shape=(T, N)
        factor_exposures: 风格因子暴露，shape=(T, N, K)
        lookback_window: 回归窗口长度
    
    Returns:
        残差收益率，shape=(T, N)
    
    实现要点:
    1. 对每只股票进行时序回归
    2. 使用滚动窗口 [t-lookback_window, t-1]
    3. 计算残差: ε_i,t = r_i,t - (β_i * f_t)
    4. 确保只使用历史数据
    """
    residuals = pd.DataFrame(index=returns.index, columns=returns.columns)
    
    for stock in returns.columns:
        for t in range(lookback_window, len(returns)):
            # 1. 获取历史窗口数据
            hist_returns = returns.iloc[t-lookback_window:t, stock]
            hist_exposures = factor_exposures.iloc[t-lookback_window:t, stock, :]
            
            # 2. 回归: r = β * f + ε
            from sklearn.linear_model import LinearRegression
            model = LinearRegression()
            model.fit(hist_exposures, hist_returns)
            
            # 3. 计算残差
            current_exposure = factor_exposures.iloc[t, stock, :]
            predicted_return = model.predict(current_exposure.reshape(1, -1))
            residual = returns.iloc[t, stock] - predicted_return[0]
            
            residuals.iloc[t, stock] = residual
    
    return residuals


def calc_residual_return_20d(data: pd.DataFrame) -> pd.Series:
    """20日残差收益率"""
    returns = data['close'].pct_change()
    factor_exposures = get_factor_exposures(data)  # 需要实现
    residuals = calc_residual_return(returns, factor_exposures, lookback_window=60)
    return residuals.rolling(20).sum()


def calc_residual_return_60d(data: pd.DataFrame) -> pd.Series:
    """60日残差收益率"""
    returns = data['close'].pct_change()
    factor_exposures = get_factor_exposures(data)
    residuals = calc_residual_return(returns, factor_exposures, lookback_window=120)
    return residuals.rolling(60).sum()


def calc_residual_return_120d(data: pd.DataFrame) -> pd.Series:
    """120日残差收益率"""
    returns = data['close'].pct_change()
    factor_exposures = get_factor_exposures(data)
    residuals = calc_residual_return(returns, factor_exposures, lookback_window=240)
    return residuals.rolling(120).sum()
```

**依赖函数**:
```python
def get_factor_exposures(data: pd.DataFrame) -> pd.DataFrame:
    """
    获取风格因子暴露
    
    使用 RiskModel.barra_factor_exposure() 计算
    
    因子包括:
    - size: 市值因子
    - value: 估值因子
    - momentum: 动量因子
    - volatility: 波动率因子
    - liquidity: 流动性因子
    """
    from app.core.risk_model import RiskModel
    
    risk_model = RiskModel()
    exposures = risk_model.barra_factor_exposure(data)
    
    return exposures
```

**集成到 FactorCalculator**:
```python
# app/core/factor_calculator.py

from app.core.factors.momentum import (
    calc_residual_return_20d,
    calc_residual_return_60d,
    calc_residual_return_120d
)

class FactorCalculator:
    def __init__(self):
        self.factor_funcs = {
            # ... 现有因子
            "residual_return_20d": calc_residual_return_20d,
            "residual_return_60d": calc_residual_return_60d,
            "residual_return_120d": calc_residual_return_120d,
        }
```

**优点**:
- ✅ 完整实现残差动量因子
- ✅ 利用现有的 RiskModel 基础设施
- ✅ 符合学术和业界标准

**缺点**:
- ⚠️ 实现复杂度较高
- ⚠️ 计算开销较大（需要对每只股票进行回归）
- ⚠️ 需要充分测试以确保无前视偏差

---

### 方案2：使用简化版动量因子（快速方案）

**背景**: `momentum.py` 中已有多个动量因子

**现有因子**:
```python
# app/core/factors/momentum.py

def calc_ret_3m_skip1(data: pd.DataFrame) -> pd.Series:
    """3个月动量（跳过最近1月）"""
    return data['close'].pct_change(60).shift(20)

def calc_ret_6m_skip1(data: pd.DataFrame) -> pd.Series:
    """6个月动量（跳过最近1月）"""
    return data['close'].pct_change(120).shift(20)

def calc_ret_12m_skip1(data: pd.DataFrame) -> pd.Series:
    """12个月动量（跳过最近1月）"""
    return data['close'].pct_change(240).shift(20)
```

**替代方案**:
```python
# 在 ResidualMomentumModule 中使用简化版动量因子

class ResidualMomentumModule(AlphaModule):
    def __init__(self):
        factors = {
            # 使用简单动量替代残差动量
            "ret_3m_skip1": {"direction": 1, "weight": 0.25},   # 替代 residual_return_20d
            "ret_6m_skip1": {"direction": 1, "weight": 0.30},   # 替代 residual_return_60d
            "ret_12m_skip1": {"direction": 1, "weight": 0.15},  # 替代 residual_return_120d
            
            # 保留其他因子
            "residual_sharpe": {"direction": 1, "weight": 0.20},
            "turnover_ratio_20d": {"direction": -1, "weight": 0.05},
            "max_drawdown_20d": {"direction": -1, "weight": 0.05},
        }
```

**优点**:
- ✅ 快速解决问题
- ✅ 利用现有实现
- ✅ 简单动量因子已经跳过最近1月，避免短期反转

**缺点**:
- ❌ 不是真正的残差动量
- ❌ 无法剥离风格因子影响
- ❌ 因子效果可能不如残差动量

---

### 方案3：标记为待实现（临时方案）

**修改位置**: `app/core/alpha_modules.py`

```python
class ResidualMomentumModule(AlphaModule):
    """
    残差动量模块
    
    ⚠️ 注意：残差收益率因子（residual_return_20d/60d/120d）尚未实现
    
    TODO:
    1. 实现残差收益率计算函数
    2. 集成到 FactorCalculator
    3. 验证无前视偏差
    
    临时方案：使用简单动量因子替代
    """
    
    def __init__(self):
        # 临时使用简单动量因子
        factors = {
            "ret_3m_skip1": {"direction": 1, "weight": 0.25},
            "ret_6m_skip1": {"direction": 1, "weight": 0.30},
            "ret_12m_skip1": {"direction": 1, "weight": 0.15},
            "residual_sharpe": {"direction": 1, "weight": 0.20},
            "turnover_ratio_20d": {"direction": -1, "weight": 0.05},
            "max_drawdown_20d": {"direction": -1, "weight": 0.05},
        }
        super().__init__("residual_momentum", factors)
```

**优点**:
- ✅ 明确标记问题
- ✅ 提供临时解决方案
- ✅ 不影响其他模块

**缺点**:
- ❌ 没有真正解决问题
- ❌ 需要后续实现

---

## 建议

### 短期建议（本周内）

1. **采用方案2（简化版动量因子）**
   - 修改 `ResidualMomentumModule` 使用简单动量因子
   - 添加注释说明这是临时方案
   - 确保回测可以正常运行

2. **更新文档**
   - 在 `alpha_modules.py` 中添加 TODO 注释
   - 在项目文档中记录这个技术债务

### 中期建议（1-2周内）

3. **实现残差收益率计算**
   - 在 `app/core/factors/momentum.py` 中实现 `calc_residual_return()`
   - 实现 `calc_residual_return_20d/60d/120d()`
   - 集成到 `FactorCalculator`

4. **验证实现正确性**
   - 编写单元测试
   - 验证无前视偏差
   - 对比简单动量和残差动量的效果

### 长期建议

5. **优化计算性能**
   - 使用向量化计算替代循环
   - 缓存因子暴露计算结果
   - 考虑使用 Numba 或 Cython 加速

6. **扩展残差因子体系**
   - 实现残差波动率因子
   - 实现残差换手率因子
   - 构建完整的残差因子库

---

## 验证清单

- [x] 检查因子定义是否存在
- [x] 搜索因子计算实现
- [x] 检查依赖模块（RiskModel）
- [x] 检查因子计算器集成
- [x] 分析潜在前视偏差风险
- [ ] 实现残差收益率计算（待完成）
- [ ] 编写单元测试（待完成）
- [ ] 验证无前视偏差（待完成）

---

## 相关文件

- **因子定义**: `app/core/alpha_modules.py:191-206`
- **动量因子**: `app/core/factors/momentum.py`
- **风险模型**: `app/core/risk_model.py`
- **因子计算器**: `app/core/factor_calculator.py`
- **验证脚本**: `tests/test_residual_momentum.py`

---

## 总结

### 核心问题

❌ **残差收益率因子（residual_return_20d/60d/120d）未实现**

- 只有配置，没有计算逻辑
- ResidualMomentumModule 无法正常工作
- 影响因子权重占比 70%

### 风险等级

🔴 **高风险**

- 如果在回测中使用该模块，会因缺少因子数据而失败
- 因子权重配置无法生效
- 可能导致策略表现与预期不符

### 推荐方案

**短期**: 采用方案2（使用简化版动量因子替代）  
**中期**: 采用方案1（实现完整的残差收益率计算）  
**长期**: 构建完整的残差因子体系

### 下一步行动

1. ✅ 完成验证报告（本文档）
2. ⏭️ 修改 ResidualMomentumModule 使用简单动量因子
3. ⏭️ 继续完成其他 P0 验证任务
4. ⏭️ 规划残差收益率因子的实现

---

**验证完成时间**: 2026-05-04  
**验证状态**: ❌ 失败 - 因子未实现  
**需要修复**: 是
