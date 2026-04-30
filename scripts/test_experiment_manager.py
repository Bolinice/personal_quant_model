"""
测试实验管理平台

测试内容：
1. 创建实验
2. 更新实验状态
3. 查询实验
4. 对比实验
5. 删除实验
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.experiment_manager import (
    ExperimentManager,
    ExperimentConfig,
    ExperimentResult,
)
from app.core.logging import logger


def test_create_experiment():
    """测试创建实验"""
    logger.info("=== 测试1: 创建实验 ===")

    manager = ExperimentManager(experiment_dir="data/experiments_test")

    # 创建测试配置
    config = {
        "strategy_params": {
            "universe": "hs300",
            "top_n": 30,
        },
        "factor_params": {
            "quality_growth": {"weight": 0.3},
            "momentum": {"weight": 0.3},
            "money_flow": {"weight": 0.4},
        },
        "backtest_params": {
            "start_date": "2020-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 10000000,
        },
    }

    # 创建实验
    exp = manager.create_experiment(
        name="测试实验1",
        description="这是一个测试实验",
        config=config,
        tags=["test", "baseline"],
    )

    logger.info(f"✓ 创建实验成功: {exp.id}")
    logger.info(f"  名称: {exp.config.name}")
    logger.info(f"  状态: {exp.status}")
    logger.info(f"  标签: {exp.config.tags}")

    return exp.id


def test_update_experiment(exp_id: str):
    """测试更新实验"""
    logger.info("\n=== 测试2: 更新实验状态 ===")

    manager = ExperimentManager(experiment_dir="data/experiments_test")

    # 更新为运行中
    manager.update_experiment(exp_id, status="running")
    exp = manager.get_experiment(exp_id)
    logger.info(f"✓ 更新状态为running: {exp.status}")

    # 添加结果
    result = ExperimentResult(
        total_return=0.25,
        annual_return=0.15,
        sharpe_ratio=1.8,
        max_drawdown=-0.12,
        calmar_ratio=1.25,
        volatility=0.08,
        downside_volatility=0.06,
        var_95=-0.02,
        cvar_95=-0.03,
        turnover_rate=1.2,
        win_rate=0.58,
        profit_loss_ratio=1.5,
        ic_mean=0.05,
        ic_ir=1.2,
        ic_win_rate=0.55,
        total_trades=500,
        holding_period=5.0,
    )

    manager.update_experiment(exp_id, status="completed", result=result)
    exp = manager.get_experiment(exp_id)
    logger.info(f"✓ 更新状态为completed")
    logger.info(f"  综合评分: {exp.result.get_score():.2f}")
    logger.info(f"  年化收益: {exp.result.annual_return:.2%}")
    logger.info(f"  夏普比率: {exp.result.sharpe_ratio:.2f}")


def test_query_experiments():
    """测试查询实验"""
    logger.info("\n=== 测试3: 查询实验 ===")

    manager = ExperimentManager(experiment_dir="data/experiments_test")

    # 创建更多测试实验
    for i in range(2, 5):
        config = {
            "strategy_params": {"universe": "hs300", "top_n": 30 + i * 5},
            "factor_params": {"quality_growth": {"weight": 0.3 + i * 0.05}},
        }

        result = ExperimentResult(
            total_return=0.20 + i * 0.05,
            annual_return=0.12 + i * 0.03,
            sharpe_ratio=1.5 + i * 0.2,
            max_drawdown=-0.15 + i * 0.01,
            calmar_ratio=1.0 + i * 0.15,
            volatility=0.08,
            downside_volatility=0.06,
            var_95=-0.02,
            cvar_95=-0.03,
            turnover_rate=1.2,
            win_rate=0.55 + i * 0.02,
            profit_loss_ratio=1.5,
            ic_mean=0.04 + i * 0.01,
            ic_ir=1.0 + i * 0.15,
            ic_win_rate=0.55,
            total_trades=500,
            holding_period=5.0,
        )

        exp = manager.create_experiment(
            name=f"测试实验{i}",
            description=f"测试实验{i}的描述",
            config=config,
            tags=["test", f"variant{i}"],
        )

        manager.update_experiment(exp.id, status="completed", result=result)

    # 查询所有实验
    experiments = manager.list_experiments(limit=10)
    logger.info(f"✓ 查询到 {len(experiments)} 个实验")

    # 按标签查询
    test_exps = manager.list_experiments(tags=["test"])
    logger.info(f"✓ 标签'test'的实验: {len(test_exps)} 个")

    # 查询最佳实验
    best_exp = manager.get_best_experiment(metric="sharpe_ratio")
    logger.info(f"✓ 最佳实验(夏普比率): {best_exp.config.name}")
    logger.info(f"  夏普比率: {best_exp.result.sharpe_ratio:.2f}")

    return [exp.id for exp in experiments]


def test_compare_experiments(exp_ids: list):
    """测试对比实验"""
    logger.info("\n=== 测试4: 对比实验 ===")

    manager = ExperimentManager(experiment_dir="data/experiments_test")

    # 对比前3个实验
    comparison = manager.compare_experiments(
        exp_ids=exp_ids[:3],
        metrics=["annual_return", "sharpe_ratio", "max_drawdown", "ic_mean"],
    )

    logger.info(f"✓ 对比 {len(comparison['experiments'])} 个实验")

    for metric, data in comparison["metrics"].items():
        logger.info(f"  {metric}: 最佳={data['best_exp']} (值={data['best_value']:.4f})")

    logger.info(f"  综合最佳: {comparison['best']['overall']} (评分={comparison['best']['score']:.2f})")


def test_export_import(exp_id: str):
    """测试导出导入"""
    logger.info("\n=== 测试5: 导出导入实验 ===")

    manager = ExperimentManager(experiment_dir="data/experiments_test")

    # 导出实验
    export_path = "data/experiments_test/export_test.json"
    manager.export_experiment(exp_id, export_path)
    logger.info(f"✓ 导出实验: {export_path}")

    # 导入实验
    imported_exp = manager.import_experiment(export_path)
    logger.info(f"✓ 导入实验: {imported_exp.id}")
    logger.info(f"  名称: {imported_exp.config.name}")

    # 清理
    Path(export_path).unlink()


def test_delete_experiment(exp_id: str):
    """测试删除实验"""
    logger.info("\n=== 测试6: 删除实验 ===")

    manager = ExperimentManager(experiment_dir="data/experiments_test")

    manager.delete_experiment(exp_id)
    logger.info(f"✓ 删除实验: {exp_id}")

    # 验证删除
    exp = manager.get_experiment(exp_id)
    if exp is None:
        logger.info("✓ 验证删除成功")
    else:
        logger.error("✗ 删除失败，实验仍然存在")


def cleanup():
    """清理测试数据"""
    logger.info("\n=== 清理测试数据 ===")

    test_dir = Path("data/experiments_test")
    if test_dir.exists():
        import shutil
        shutil.rmtree(test_dir)
        logger.info("✓ 清理完成")


def main():
    try:
        # 测试1: 创建实验
        exp_id = test_create_experiment()

        # 测试2: 更新实验
        test_update_experiment(exp_id)

        # 测试3: 查询实验
        exp_ids = test_query_experiments()

        # 测试4: 对比实验
        test_compare_experiments(exp_ids)

        # 测试5: 导出导入
        test_export_import(exp_id)

        # 测试6: 删除实验
        test_delete_experiment(exp_id)

        logger.info("\n" + "=" * 50)
        logger.info("所有测试通过! ✓")
        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return False

    finally:
        # 清理测试数据
        cleanup()

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
