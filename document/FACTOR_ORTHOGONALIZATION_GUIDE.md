# 因子正交化与去冗余模块使用指南

## 概述

因子正交化模块 (`app/core/factor_orthogonalization.py`) 提供了完整的因子相关性分析、冗余因子识别与剔除、因子正交化功能，帮助提升因子组合的独立性和效率。

## 核心功能

### 1. 因子相关性分析
- Pearson 相关性
- Spearman 相关性
- IC 序列相关性

### 2. 冗余因子识别与剔除
- 自动识别高相关因子对（阈值可配置）
- 根据 IC 值选择保留哪个因子
- 支持批量剔除冗余因子

### 3. 因子正交化方法
- **Gram-Schmidt 正交化**：经典正交化方法，保持第一个因子不变
- **回归残差法**：对基准因子组回归取残差，保留增量信息
- **PCA 正交化**：主成分分析，完全正交但失去可解释性
- **对称正交化**：所有因子地位平等的正交化

### 4. 因子独立性评估
- 平均相关性
- 最大相关性
- VIF（方差膨胀因子）

## 快速开始

### 基础用法

```python
from app.core.factor_orthogonalization import FactorOrthogonalizer
import pandas as pd

# 创建正交化器
orthogonalizer = FactorOrthogonalizer()

# 准备因子数据（DataFrame，columns为因子名）
factor_data = pd.DataFrame({
    'factor1': [...],
    'factor2': [...],
    'factor3': [...],
})

# 计算相关性矩阵
corr_matrix = orthogonalizer.compute_factor_correlation(factor_data)
print(corr_matrix)
```

### 识别冗余因子

```python
# 识别冗余因子对（相关性 > 0.7）
redundant_pairs = orthogonalizer.identify_redundant_factors(
    factor_data,
    corr_threshold=0.7,
)

# 根据 IC 选择要剔除的因子
ic_values = {
    'factor1': 0.05,
    'factor2': 0.03,  # IC 较低
    'factor3': 0.06,
}

factors_to_remove = orthogonalizer.select_factors_by_ic(
    redundant_pairs,
    ic_values,
)

# 剔除冗余因子
cleaned_data = factor_data.drop(columns=list(factors_to_remove))
```

### 因子正交化

```python
from app.core.factor_orthogonalization import OrthogonalizationMethod

# 方法1：Gram-Schmidt 正交化
result = orthogonalizer.orthogonalize_gram_schmidt(factor_data)
orthogonal_factors = result.orthogonal_factors

# 方法2：回归残差法（推荐用于保留因子可解释性）
result = orthogonalizer.orthogonalize_regression(
    factor_data,
    base_factors=['factor1'],  # 以 factor1 为基准
)

# 方法3：PCA（推荐用于降维）
result = orthogonalizer.orthogonalize_pca(
    factor_data,
    n_components=3,  # 保留3个主成分
)

# 方法4：对称正交化
result = orthogonalizer.orthogonalize_symmetric(factor_data)
```

### 完整工作流程

```python
# 一键完成：去冗余 + 正交化
processed_data, info = orthogonalizer.process_factors(
    factor_data,
    ic_values=ic_values,
    remove_redundant=True,      # 是否剔除冗余因子
    orthogonalize=True,          # 是否正交化
    method=OrthogonalizationMethod.REGRESSION,  # 正交化方法
    corr_threshold=0.7,          # 冗余判断阈值
)

# 查看处理信息
print(f"原始因子: {info['original_factors']}")
print(f"剔除的因子: {info['removed_factors']}")
print(f"最终因子: {list(processed_data.columns)}")
print(f"独立性改善: {info['independence_before']} -> {info['independence_after']}")
```

## 实际应用场景

### 场景1：多因子选股前的因子预处理

```python
# 在多因子选股前，先对因子进行去冗余和正交化
# 提升因子组合的独立性，避免信息重复

# 1. 计算各因子的 IC
ic_values = calculate_factor_ic(factor_data, returns)

# 2. 去冗余 + 正交化
processed_factors, info = orthogonalizer.process_factors(
    factor_data,
    ic_values=ic_values,
    remove_redundant=True,
    orthogonalize=True,
    method=OrthogonalizationMethod.REGRESSION,
)

# 3. 使用处理后的因子进行选股
scores = compute_composite_score(processed_factors)
```

### 场景2：新因子研发时的增量信息检验

```python
# 检验新因子相对于现有因子是否有增量信息

# 1. 将新因子对现有因子组回归
result = orthogonalizer.orthogonalize_regression(
    pd.concat([existing_factors, new_factor], axis=1),
    base_factors=existing_factors.columns.tolist(),
)

# 2. 检查新因子的残差是否有预测能力
new_factor_residual = result.orthogonal_factors[new_factor.name]
ic_residual = calculate_ic(new_factor_residual, returns)

if abs(ic_residual) > 0.02:
    print("新因子有增量信息，建议纳入因子库")
else:
    print("新因子无增量信息，与现有因子冗余")
```

### 场景3：因子库定期维护

```python
# 定期检查因子库中的因子独立性，剔除失效或冗余因子

# 1. 评估当前因子库独立性
metrics = orthogonalizer.evaluate_independence(factor_data)
print(f"平均相关性: {metrics['mean_correlation']:.3f}")
print(f"平均VIF: {metrics['mean_vif']:.2f}")

# 2. 如果独立性较差（平均相关性 > 0.3 或 VIF > 3），进行清理
if metrics['mean_correlation'] > 0.3 or metrics['mean_vif'] > 3:
    processed_data, info = orthogonalizer.process_factors(
        factor_data,
        ic_values=ic_values,
        remove_redundant=True,
        orthogonalize=False,  # 只去冗余，不正交化
        corr_threshold=0.7,
    )
    print(f"剔除了 {len(info['removed_factors'])} 个冗余因子")
```

## 参数说明

### 相关性阈值 (corr_threshold)
- **0.7**（默认）：高相关，适合严格去冗余
- **0.8**：非常高相关，保留更多因子
- **0.6**：中等相关，更激进的去冗余

### 正交化方法选择

| 方法 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| Gram-Schmidt | 保持第一个因子不变 | 顺序敏感 | 有明确主因子的情况 |
| 回归残差法 | 保留因子可解释性 | 需要指定基准因子 | **推荐**：日常因子处理 |
| PCA | 完全正交，降维 | 失去可解释性 | 降维、特征提取 |
| 对称正交化 | 所有因子地位平等 | 失去原始含义 | 理论研究 |

## 性能指标

### 独立性评估指标

- **平均相关性**：
  - < 0.1：优秀
  - 0.1 - 0.3：良好
  - 0.3 - 0.5：一般
  - \> 0.5：较差

- **VIF（方差膨胀因子）**：
  - < 2：无多重共线性
  - 2 - 5：轻度多重共线性
  - 5 - 10：中度多重共线性
  - \> 10：严重多重共线性

## 注意事项

1. **正交化会改变因子的经济含义**：如果需要保持因子可解释性，建议使用回归残差法，并谨慎选择基准因子

2. **去冗余需要 IC 值**：剔除冗余因子时，需要提供各因子的 IC 值，以便选择保留 IC 更高的因子

3. **数据质量**：正交化前应先进行因子预处理（去极值、标准化），确保数据质量

4. **样本量要求**：VIF 计算需要足够的样本量（建议 > 100），样本量过小会导致结果不稳定

5. **定期更新**：因子相关性会随时间变化，建议定期（如每季度）重新评估因子独立性

## 示例脚本

完整的使用示例请参考：`scripts/example_factor_orthogonalization.py`

运行示例：
```bash
python scripts/example_factor_orthogonalization.py
```

## 测试

运行单元测试：
```bash
pytest tests/core/test_factor_orthogonalization.py -v
```

## 参考文献

1. Lopez de Prado, M. (2018). Advances in Financial Machine Learning. Wiley.
2. Chincarini, L. B., & Kim, D. (2006). Quantitative Equity Portfolio Management. McGraw-Hill.
3. Grinold, R. C., & Kahn, R. N. (2000). Active Portfolio Management. McGraw-Hill.
