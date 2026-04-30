"""
因子正交化使用示例

演示如何使用因子正交化模块进行：
1. 因子相关性分析
2. 冗余因子识别与剔除
3. 因子正交化
4. 因子独立性评估
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.factor_orthogonalization import (
    FactorOrthogonalizer,
    OrthogonalizationMethod,
)
from app.core.logging import logger


def generate_sample_factors(n_stocks: int = 500, n_days: int = 60) -> pd.DataFrame:
    """
    生成模拟因子数据

    模拟5个因子：
    - quality: 质量因子（独立）
    - growth: 成长因子（与quality中等相关）
    - momentum: 动量因子（独立）
    - value: 价值因子（与quality高相关，冗余）
    - liquidity: 流动性因子（独立）
    """
    np.random.seed(42)

    # 生成基础因子
    quality = np.random.randn(n_stocks * n_days)
    growth = quality * 0.4 + np.random.randn(n_stocks * n_days) * 0.9  # 中等相关
    momentum = np.random.randn(n_stocks * n_days)
    value = quality * 0.85 + np.random.randn(n_stocks * n_days) * 0.3  # 高相关（冗余）
    liquidity = np.random.randn(n_stocks * n_days)

    # 创建DataFrame
    factor_data = pd.DataFrame(
        {
            "quality": quality,
            "growth": growth,
            "momentum": momentum,
            "value": value,
            "liquidity": liquidity,
        }
    )

    return factor_data


def example_1_correlation_analysis():
    """示例1：因子相关性分析"""
    logger.info("=" * 60)
    logger.info("示例1：因子相关性分析")
    logger.info("=" * 60)

    # 生成模拟数据
    factor_data = generate_sample_factors()

    # 创建正交化器
    orthogonalizer = FactorOrthogonalizer()

    # 计算相关性矩阵
    corr_matrix = orthogonalizer.compute_factor_correlation(factor_data, method="pearson")

    logger.info("\n因子相关性矩阵（Pearson）：")
    logger.info(f"\n{corr_matrix.round(3)}")

    # 识别冗余因子对
    redundant_pairs = orthogonalizer.identify_redundant_factors(
        factor_data,
        corr_threshold=0.7,
    )

    logger.info(f"\n发现 {len(redundant_pairs)} 对冗余因子：")
    for pair in redundant_pairs:
        logger.info(
            f"  {pair.factor1} <-> {pair.factor2}: "
            f"Pearson={pair.pearson_corr:.3f}, Spearman={pair.spearman_corr:.3f}"
        )


def example_2_remove_redundant():
    """示例2：剔除冗余因子"""
    logger.info("\n" + "=" * 60)
    logger.info("示例2：剔除冗余因子")
    logger.info("=" * 60)

    # 生成模拟数据
    factor_data = generate_sample_factors()

    # 模拟IC值（value的IC较低）
    ic_values = {
        "quality": 0.05,
        "growth": 0.04,
        "momentum": 0.06,
        "value": 0.03,  # IC较低，应该被剔除
        "liquidity": 0.04,
    }

    # 创建正交化器
    orthogonalizer = FactorOrthogonalizer()

    # 识别冗余因子
    redundant_pairs = orthogonalizer.identify_redundant_factors(
        factor_data,
        ic_values=ic_values,
        corr_threshold=0.7,
    )

    # 根据IC选择要剔除的因子
    factors_to_remove = orthogonalizer.select_factors_by_ic(redundant_pairs, ic_values)

    logger.info(f"\n原始因子数量: {len(factor_data.columns)}")
    logger.info(f"冗余因子对数: {len(redundant_pairs)}")
    logger.info(f"要剔除的因子: {factors_to_remove}")

    # 剔除冗余因子
    cleaned_data = factor_data.drop(columns=list(factors_to_remove))
    logger.info(f"剔除后因子数量: {len(cleaned_data.columns)}")
    logger.info(f"保留的因子: {list(cleaned_data.columns)}")


def example_3_orthogonalization_methods():
    """示例3：不同正交化方法对比"""
    logger.info("\n" + "=" * 60)
    logger.info("示例3：不同正交化方法对比")
    logger.info("=" * 60)

    # 生成模拟数据（只用3个因子便于观察）
    factor_data = generate_sample_factors()
    factor_data = factor_data[["quality", "growth", "momentum"]]

    orthogonalizer = FactorOrthogonalizer()

    # 原始相关性
    original_corr = factor_data.corr()
    logger.info("\n原始因子相关性矩阵：")
    logger.info(f"\n{original_corr.round(3)}")

    # 方法1：Gram-Schmidt正交化
    logger.info("\n--- 方法1：Gram-Schmidt正交化 ---")
    result_gs = orthogonalizer.orthogonalize_gram_schmidt(factor_data)
    gs_corr = result_gs.orthogonal_factors.corr()
    logger.info(f"正交化后相关性矩阵：\n{gs_corr.round(3)}")

    # 方法2：回归残差法
    logger.info("\n--- 方法2：回归残差法（以quality为基准）---")
    result_reg = orthogonalizer.orthogonalize_regression(
        factor_data,
        base_factors=["quality"],
    )
    reg_corr = result_reg.orthogonal_factors.corr()
    logger.info(f"正交化后相关性矩阵：\n{reg_corr.round(3)}")

    # 方法3：PCA
    logger.info("\n--- 方法3：PCA正交化 ---")
    result_pca = orthogonalizer.orthogonalize_pca(factor_data, n_components=3)
    pca_corr = result_pca.orthogonal_factors.corr()
    logger.info(f"主成分相关性矩阵：\n{pca_corr.round(3)}")
    logger.info(f"方差解释比例：{result_pca.explained_variance.round(3)}")

    # 方法4：对称正交化
    logger.info("\n--- 方法4：对称正交化 ---")
    result_sym = orthogonalizer.orthogonalize_symmetric(factor_data)
    sym_corr = result_sym.orthogonal_factors.corr()
    logger.info(f"正交化后相关性矩阵：\n{sym_corr.round(3)}")


def example_4_independence_evaluation():
    """示例4：因子独立性评估"""
    logger.info("\n" + "=" * 60)
    logger.info("示例4：因子独立性评估")
    logger.info("=" * 60)

    # 生成模拟数据
    factor_data = generate_sample_factors()

    orthogonalizer = FactorOrthogonalizer()

    # 评估原始因子独立性
    logger.info("\n原始因子独立性评估：")
    metrics_before = orthogonalizer.evaluate_independence(factor_data)
    logger.info(f"  平均相关性: {metrics_before['mean_correlation']:.3f}")
    logger.info(f"  最大相关性: {metrics_before['max_correlation']:.3f}")
    logger.info(f"  平均VIF: {metrics_before['mean_vif']:.2f}")

    # 正交化后评估
    result = orthogonalizer.orthogonalize_regression(factor_data, base_factors=["quality"])
    logger.info("\n正交化后因子独立性评估：")
    metrics_after = orthogonalizer.evaluate_independence(result.orthogonal_factors)
    logger.info(f"  平均相关性: {metrics_after['mean_correlation']:.3f}")
    logger.info(f"  最大相关性: {metrics_after['max_correlation']:.3f}")
    logger.info(f"  平均VIF: {metrics_after['mean_vif']:.2f}")

    # 改善程度
    logger.info("\n独立性改善：")
    logger.info(
        f"  平均相关性降低: {(metrics_before['mean_correlation'] - metrics_after['mean_correlation']):.3f}"
    )
    logger.info(f"  最大相关性降低: {(metrics_before['max_correlation'] - metrics_after['max_correlation']):.3f}")
    logger.info(f"  平均VIF降低: {(metrics_before['mean_vif'] - metrics_after['mean_vif']):.2f}")


def example_5_complete_workflow():
    """示例5：完整工作流程"""
    logger.info("\n" + "=" * 60)
    logger.info("示例5：完整工作流程（去冗余 + 正交化）")
    logger.info("=" * 60)

    # 生成模拟数据
    factor_data = generate_sample_factors()

    # 模拟IC值
    ic_values = {
        "quality": 0.05,
        "growth": 0.04,
        "momentum": 0.06,
        "value": 0.03,  # IC较低
        "liquidity": 0.04,
    }

    orthogonalizer = FactorOrthogonalizer()

    # 完整流程
    processed_data, info = orthogonalizer.process_factors(
        factor_data,
        ic_values=ic_values,
        remove_redundant=True,
        orthogonalize=True,
        method=OrthogonalizationMethod.REGRESSION,
        corr_threshold=0.7,
    )

    # 输出结果
    logger.info(f"\n原始因子: {info['original_factors']}")
    logger.info(f"剔除的冗余因子: {info['removed_factors']}")
    logger.info(f"最终因子: {list(processed_data.columns)}")
    logger.info(f"正交化方法: {info['orthogonalization_method']}")

    logger.info("\n独立性对比：")
    logger.info("  处理前：")
    logger.info(f"    平均相关性: {info['independence_before']['mean_correlation']:.3f}")
    logger.info(f"    最大相关性: {info['independence_before']['max_correlation']:.3f}")
    logger.info(f"    平均VIF: {info['independence_before']['mean_vif']:.2f}")

    logger.info("  处理后：")
    logger.info(f"    平均相关性: {info['independence_after']['mean_correlation']:.3f}")
    logger.info(f"    最大相关性: {info['independence_after']['max_correlation']:.3f}")
    logger.info(f"    平均VIF: {info['independence_after']['mean_vif']:.2f}")


def main():
    """运行所有示例"""
    logger.info("因子正交化模块使用示例\n")

    # 示例1：相关性分析
    example_1_correlation_analysis()

    # 示例2：剔除冗余因子
    example_2_remove_redundant()

    # 示例3：不同正交化方法对比
    example_3_orthogonalization_methods()

    # 示例4：独立性评估
    example_4_independence_evaluation()

    # 示例5：完整工作流程
    example_5_complete_workflow()

    logger.info("\n" + "=" * 60)
    logger.info("所有示例运行完成！")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
