# CPCV 使用指南

## 概述

Combinatorial Purged Cross-Validation (CPCV) 是一种专为金融时间序列设计的交叉验证方法，解决了传统交叉验证在量化策略回测中的三大问题：

1. **信息泄露 (Information Leakage)**: 训练集和测试集之间的时间重叠导致未来信息泄露
2. **样本重叠 (Sample Overlap)**: 标签计算依赖未来数据，导致训练样本与测试样本重叠
3. **过拟合 (Overfitting)**: 传统 K-Fold 在时间序列上容易过拟合

## 核心技术

### 1. Purging（清洗）

自动清除训练集中与测试集时间重叠的样本。

**原理**：如果训练样本的结束时间 `t1[i] >= test_start`，则该样本可能包含测试集信息，需要清除。

```python
from app.core.pure.cpcv import get_train_times

# 训练样本结束时间
t1 = pd.Series([10, 20, 30, 40, 50], index=[0, 1, 2, 3, 4])
# 测试集时间范围 [30, 40]
test_times = pd.Series([30, 40], index=[2, 3])

# 清洗后的训练集（只保留结束时间 < 30 的样本）
train_times = get_train_times(t1, test_times)
# 结果: index=[0, 1], values=[10, 20]
```

### 2. Embargo（禁运期）

在测试集后添加一段时间作为缓冲区，防止标签计算时使用了测试集之后的信息。

**原理**：如果标签是未来 N 天收益率，则需要至少 N 天的禁运期。

```python
from app.core.pure.cpcv import get_embargo_times

times = pd.Series([10, 20, 30, 40, 50], index=[0, 1, 2, 3, 4])
pct_embargo = 0.2  # 20% = 1个样本

# 禁运期结束时间
embargo_time = get_embargo_times(times, pct_embargo)
# 结果: 50（最后1个样本的时间）
```

### 3. Combinatorial（组合）

生成多个测试集组合，增加样本外评估的稳健性。

**原理**：从 N 个分割中选择 K 个作为测试集，共有 C(N, K) 种组合。

## 使用方法

### 方法 1: CombinatorialPurgedCV

适用于需要多个测试集组合的场景。

```python
from app.core.pure.cpcv import CombinatorialPurgedCV
import pandas as pd
import numpy as np

# 创建时间序列数据
dates = pd.date_range("2020-01-01", periods=252, freq="D")
X = pd.DataFrame({
    "factor1": np.random.randn(252),
    "factor2": np.random.randn(252),
}, index=dates)
y = pd.Series(np.random.randn(252) * 0.02, index=dates)

# 初始化 CPCV
cv = CombinatorialPurgedCV(
    n_splits=5,          # 总分割数
    n_test_splits=2,     # 每次组合使用的测试集数量
    pct_embargo=0.01,    # 禁运期百分比（1%）
)

# 交叉验证
for train_idx, test_idx in cv.split(X, y):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    
    # 训练模型
    # model.fit(X_train, y_train)
    # predictions = model.predict(X_test)
```

### 方法 2: PurgedKFold

适用于传统 K-Fold 场景，但加入了 Purging 和 Embargo。

```python
from app.core.pure.cpcv import PurgedKFold

# 初始化 PurgedKFold
cv = PurgedKFold(
    n_splits=5,          # 折数
    pct_embargo=0.01,    # 禁运期百分比
)

# 交叉验证
for train_idx, test_idx in cv.split(X, y):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    
    # 训练模型
```

## 集成到模型训练器

### 替换 TimeSeriesSplit

在 `app/core/model_trainer.py` 中，可以用 CPCV 替换 `TimeSeriesSplit`：

```python
from app.core.pure.cpcv import PurgedKFold

# 原代码
# from sklearn.model_selection import TimeSeriesSplit
# tscv = TimeSeriesSplit(n_splits=self.n_splits)

# 新代码
cv = PurgedKFold(n_splits=self.n_splits, pct_embargo=0.01)

# 使用方式相同
for train_idx, val_idx in cv.split(X):
    X_train, X_val = X[train_idx], X[val_idx]
    y_train, y_val = y[train_idx], y[val_idx]
    # ...
```

### 完整示例

```python
from app.core.pure.cpcv import PurgedKFold
import lightgbm as lgb
import pandas as pd
import numpy as np

def train_with_cpcv(X: pd.DataFrame, y: pd.Series, n_splits: int = 5):
    """使用 CPCV 训练模型"""
    
    # 初始化 CPCV
    cv = PurgedKFold(n_splits=n_splits, pct_embargo=0.02)
    
    # 存储 OOF 预测
    oof_predictions = np.full(len(y), np.nan)
    
    # 交叉验证
    for fold_idx, (train_idx, val_idx) in enumerate(cv.split(X)):
        print(f"Fold {fold_idx + 1}/{n_splits}")
        
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        # 训练模型
        model = lgb.LGBMRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.05,
            random_state=42,
        )
        model.fit(X_train, y_train)
        
        # OOF 预测
        val_pred = model.predict(X_val)
        oof_predictions[val_idx] = val_pred
        
        # 计算 IC
        ic = np.corrcoef(val_pred, y_val)[0, 1]
        print(f"  Validation IC: {ic:.4f}")
    
    # 全量重训练
    final_model = lgb.LGBMRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.05,
        random_state=42,
    )
    final_model.fit(X, y)
    
    return final_model, oof_predictions
```

## 参数选择指南

### n_splits

- **推荐值**: 5-10
- **说明**: 分割数越多，训练集越大，但计算成本越高
- **权衡**: 
  - 小值（3-5）：快速验证，适合探索阶段
  - 大值（8-10）：更稳健的评估，适合最终验证

### n_test_splits

- **推荐值**: 1-2
- **说明**: 每次组合使用的测试集数量
- **权衡**:
  - 1: 类似 TimeSeriesSplit，计算快
  - 2+: 更多组合，评估更稳健，但计算慢

### pct_embargo

- **推荐值**: 0.01-0.05（1%-5%）
- **说明**: 禁运期百分比，相对于测试集大小
- **计算方法**:
  - 如果标签是未来 N 天收益率
  - 测试集大小为 M 个样本
  - 则 `pct_embargo = N / M`
- **示例**:
  - 标签: 未来 5 天收益率
  - 测试集: 100 天
  - 禁运期: `5 / 100 = 0.05`

## 与 TimeSeriesSplit 的对比

| 特性 | TimeSeriesSplit | CPCV |
|------|----------------|------|
| 信息泄露防护 | ❌ 无 | ✅ Purging |
| 标签泄露防护 | ❌ 无 | ✅ Embargo |
| 组合测试集 | ❌ 无 | ✅ Combinatorial |
| 计算成本 | 低 | 中等 |
| 评估稳健性 | 中等 | 高 |

## 实际案例

### 案例 1: 因子 IC 预测

```python
from app.core.pure.cpcv import PurgedKFold
import pandas as pd

# 加载因子数据
factor_df = pd.read_parquet("factors.parquet")  # shape: (252, 50)
returns = pd.read_parquet("returns.parquet")    # shape: (252,)

# CPCV 验证
cv = PurgedKFold(n_splits=5, pct_embargo=0.02)

ic_scores = []
for train_idx, test_idx in cv.split(factor_df):
    # 训练集
    X_train = factor_df.iloc[train_idx]
    y_train = returns.iloc[train_idx]
    
    # 测试集
    X_test = factor_df.iloc[test_idx]
    y_test = returns.iloc[test_idx]
    
    # 简单线性组合
    weights = X_train.corrwith(y_train)
    predictions = (X_test * weights).sum(axis=1)
    
    # 计算 IC
    ic = predictions.corr(y_test)
    ic_scores.append(ic)

print(f"Mean IC: {np.mean(ic_scores):.4f}")
print(f"Std IC: {np.std(ic_scores):.4f}")
```

### 案例 2: Walk-Forward 回测

```python
from app.core.pure.cpcv import CombinatorialPurgedCV

# 模拟 Walk-Forward
cv = CombinatorialPurgedCV(
    n_splits=10,         # 10个时间窗口
    n_test_splits=1,     # 每次测试1个窗口
    pct_embargo=0.05,    # 5%禁运期
)

for i, (train_idx, test_idx) in enumerate(cv.split(factor_df)):
    print(f"Window {i + 1}")
    print(f"  Train: {len(train_idx)} samples")
    print(f"  Test: {len(test_idx)} samples")
    
    # 训练和测试
    # ...
```

## 注意事项

1. **第一个分割会被跳过**: 由于 Purging 逻辑，第一个分割通常没有训练数据（所有数据都在测试集之后），会被自动跳过。

2. **数据量要求**: CPCV 需要足够的历史数据。建议至少 200+ 个时间点。

3. **计算成本**: Combinatorial 模式会增加计算成本。如果只需要简单验证，使用 `n_test_splits=1`。

4. **标签计算**: 确保标签的计算方式与 `pct_embargo` 参数匹配，避免信息泄露。

## 参考文献

- Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. Chapter 7: Cross-Validation in Finance.
- Bailey, D. H., Borwein, J., Lopez de Prado, M., & Zhu, Q. J. (2014). *Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance*. Notices of the AMS, 61(5), 458-471.

## 相关文档

- [模型训练器文档](../app/core/model_trainer.py)
- [在线学习模块](../app/core/online_learning.py)
- [回测完整性检查](../app/core/backtest_integrity.py)
