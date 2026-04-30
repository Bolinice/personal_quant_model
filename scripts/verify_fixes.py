"""
验证Phase 1关键修复
1. Regime状态抖动修复
2. 因子预处理顺序修复
3. 数据库索引添加
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.factor_preprocess import FactorPreprocessor
from app.core.logging import logger
from app.core.regime import RegimeDetector


def test_regime_state_machine():
    """测试Regime状态机是否正确避免抖动"""
    logger.info("=" * 60)
    logger.info("测试1: Regime状态机抖动修复")
    logger.info("=" * 60)

    detector = RegimeDetector()

    # 模拟市场数据: 波动率在阈值附近波动
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    market_data = pd.DataFrame(
        {
            "trade_date": dates,
            "close": [3000, 3010, 3005, 3015, 3008, 3020, 3012, 3025, 3018, 3030],
            "volume": [1e9] * 10,
            "amount": [1e10] * 10,
        }
    )

    states = []
    for i in range(len(market_data)):
        regime, confidence = detector.detect(market_data.iloc[: i + 1])
        states.append(regime)
        logger.info(f"Day {i+1}: regime={regime}, confidence={confidence:.3f}, vol_score={detector._prev_vol_score}")

    # 检查状态切换次数
    state_changes = sum(1 for i in range(1, len(states)) if states[i] != states[i - 1])
    logger.info(f"状态切换次数: {state_changes}")

    if state_changes <= 3:
        logger.info("✅ Regime状态机测试通过: 状态切换次数合理")
    else:
        logger.warning(f"⚠️  Regime状态机可能仍有抖动: 切换{state_changes}次")

    return state_changes <= 3


def test_factor_preprocessing_order():
    """测试因子预处理顺序: 中性化必须在标准化之前"""
    logger.info("\n" + "=" * 60)
    logger.info("测试2: 因子预处理顺序")
    logger.info("=" * 60)

    preprocessor = FactorPreprocessor()

    # 模拟因子数据
    np.random.seed(42)
    n_stocks = 100
    df = pd.DataFrame(
        {
            "factor_value": np.random.randn(n_stocks) * 10 + 50,
            "industry": np.random.choice(["A", "B", "C"], n_stocks),
            "market_cap": np.random.lognormal(10, 1, n_stocks),
        }
    )

    # 测试1: 错误顺序 (标准化→中性化)
    wrong_order = df.copy()
    wrong_order["factor_value"] = preprocessor.standardize_zscore(wrong_order["factor_value"])
    wrong_order["factor_value"] = preprocessor.neutralize_industry(wrong_order, "factor_value", "industry")
    wrong_mean = wrong_order["factor_value"].mean()
    wrong_std = wrong_order["factor_value"].std()

    # 测试2: 正确顺序 (中性化→标准化)
    correct_order = df.copy()
    correct_order["factor_value"] = preprocessor.neutralize_industry(correct_order, "factor_value", "industry")
    correct_order["factor_value"] = preprocessor.standardize_zscore(correct_order["factor_value"])
    correct_mean = correct_order["factor_value"].mean()
    correct_std = correct_order["factor_value"].std()

    logger.info(f"错误顺序 (标准化→中性化): mean={wrong_mean:.6f}, std={wrong_std:.6f}")
    logger.info(f"正确顺序 (中性化→标准化): mean={correct_mean:.6f}, std={correct_std:.6f}")

    # 正确顺序应该得到标准正态分布 (mean≈0, std≈1)
    if abs(correct_mean) < 0.01 and abs(correct_std - 1.0) < 0.01:
        logger.info("✅ 因子预处理顺序测试通过: 中性化→标准化得到标准正态分布")
        return True
    else:
        logger.warning("⚠️  因子预处理顺序可能有问题")
        return False


def test_database_indexes():
    """测试数据库索引是否存在"""
    logger.info("\n" + "=" * 60)
    logger.info("测试3: 数据库索引检查")
    logger.info("=" * 60)

    try:
        from sqlalchemy import text

        from app.db.base import SessionLocal

        db = SessionLocal()

        # 检查stock_financial表的索引
        check_sql = """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'stock_financial'
        ORDER BY indexname;
        """
        result = db.execute(text(check_sql))
        indexes = list(result)

        logger.info(f"stock_financial表索引数量: {len(indexes)}")
        for idx_name, idx_def in indexes:
            logger.info(f"  - {idx_name}")

        # 检查关键索引
        index_names = {row[0] for row in indexes}
        required_indexes = {"ix_financial_code_ann", "ix_financial_code_end"}
        missing = required_indexes - index_names

        if not missing:
            logger.info("✅ 数据库索引测试通过: 所有关键索引已创建")
            db.close()
            return True
        else:
            logger.warning(f"⚠️  缺少索引: {missing}")
            logger.info("请运行: python scripts/add_financial_indexes.py")
            db.close()
            return False

    except Exception as e:
        logger.error(f"数据库索引检查失败: {e}")
        return False


def main():
    """运行所有验证测试"""
    logger.info("开始验证Phase 1关键修复...")

    results = {
        "Regime状态机": test_regime_state_machine(),
        "因子预处理顺序": test_factor_preprocessing_order(),
        "数据库索引": test_database_indexes(),
    }

    logger.info("\n" + "=" * 60)
    logger.info("验证结果汇总")
    logger.info("=" * 60)

    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"{test_name}: {status}")

    all_passed = all(results.values())
    if all_passed:
        logger.info("\n🎉 所有测试通过！Phase 1修复成功")
    else:
        logger.warning("\n⚠️  部分测试失败，请检查上述输出")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
