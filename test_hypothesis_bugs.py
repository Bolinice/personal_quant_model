#!/usr/bin/env python3
"""
测试 Hypothesis 发现的两个 bug：
1. winsorize_mad 在有重复值时可能改变非极值点值
2. standardize_zscore 在极端浮点值时可能破坏排序
"""

import numpy as np
import pandas as pd
import sys
sys.path.insert(0, '.')

from app.core.factor_preprocess import FactorPreprocessor

preprocessor = FactorPreprocessor()

print("=" * 60)
print("测试 Bug 1: winsorize_mad 改变非极值点")
print("=" * 60)

# 构造有大量重复值的数据
values = [1.0] * 50 + [2.0] * 50 + [100.0]  # 100.0 是极值
series = pd.Series(values)

print(f"原始数据: {len(values)} 个值")
print(f"  - 50个 1.0")
print(f"  - 50个 2.0")
print(f"  - 1个 100.0 (极值)")

median = series.median()
mad = np.median(np.abs(series - median)) * 1.4826
print(f"\nMedian: {median}")
print(f"MAD: {mad}")

if mad > 0:
    n_mad = 3.0
    lower = median - n_mad * mad
    upper = median + n_mad * mad
    print(f"边界: [{lower:.4f}, {upper:.4f}]")

    # 非极值点
    non_outlier_mask = (series >= lower) & (series <= upper)
    print(f"\n非极值点数量: {non_outlier_mask.sum()}")

result = preprocessor.winsorize_mad(series, n_mad=3.0)

# 检查非极值点是否被改变
non_outlier_mask = (series >= lower) & (series <= upper)
original_non_outliers = series[non_outlier_mask]
result_non_outliers = result[non_outlier_mask]

changed = ~np.isclose(original_non_outliers.values, result_non_outliers.values, rtol=1e-9)
if changed.any():
    print(f"\n❌ Bug 确认: {changed.sum()} 个非极值点被改变!")
    print(f"原始值样本: {original_non_outliers.values[:5]}")
    print(f"处理后样本: {result_non_outliers.values[:5]}")
else:
    print("\n✅ 非极值点未被改变")

print("\n" + "=" * 60)
print("测试 Bug 2: standardize_zscore 破坏排序")
print("=" * 60)

# 构造极端浮点值
values2 = [1e-10, 1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0, 1000.0, 1e4, 1e5, 1e6]
series2 = pd.Series(values2)

print(f"原始数据: {len(values2)} 个值，范围 [{min(values2):.2e}, {max(values2):.2e}]")
print(f"原始排序: {series2.values}")

result2 = preprocessor.standardize_zscore(series2)

print(f"\nZ-score 结果: {result2.values}")

# 检查排序是否保持
original_order = np.argsort(series2.values)
result_order = np.argsort(result2.values)

if not np.array_equal(original_order, result_order):
    print(f"\n❌ Bug 确认: 排序被破坏!")
    print(f"原始排序索引: {original_order}")
    print(f"结果排序索引: {result_order}")

    # 找出哪些位置反转了
    for i in range(len(original_order) - 1):
        orig_i = original_order[i]
        orig_j = original_order[i + 1]
        if result2.iloc[orig_i] > result2.iloc[orig_j]:
            print(f"  反转: 原始 {series2.iloc[orig_i]:.2e} < {series2.iloc[orig_j]:.2e}")
            print(f"       Z-score {result2.iloc[orig_i]:.6f} > {result2.iloc[orig_j]:.6f}")
else:
    print("\n✅ 排序保持不变")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
