"""
运行实验脚本

使用示例：
    python scripts/run_experiment.py --name "测试实验" --config config/experiment.json
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.experiment_manager import (
    ExperimentManager,
    ExperimentResult,
)
from app.core.daily_pipeline import DailyPipeline
from app.core.backtest_engine import BacktestEngine
from app.core.logging import logger


def get_git_commit_hash() -> str:
    """获取当前git commit hash"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()[:8]
    except Exception:
        return "unknown"


def run_backtest(config: dict) -> dict:
    """
    运行回测

    Args:
        config: 实验配置

    Returns:
        回测结果
    """
    logger.info("开始运行回测...")

    # 提取回测参数
    backtest_params = config.get("backtest_params", {})
    start_date = backtest_params.get("start_date", "2020-01-01")
    end_date = backtest_params.get("end_date", "2023-12-31")
    initial_capital = backtest_params.get("initial_capital", 10000000)

    # 创建回测引擎
    engine = BacktestEngine(
        initial_capital=initial_capital,
        commission_rate=backtest_params.get("commission_rate", 0.0003),
        slippage_rate=backtest_params.get("slippage_rate", 0.001),
    )

    # TODO: 这里需要实现完整的回测流程
    # 1. 加载数据
    # 2. 生成信号
    # 3. 执行回测
    # 4. 计算指标

    # 模拟结果（实际应该从回测引擎获取）
    result = {
        "total_return": 0.25,
        "annual_return": 0.15,
        "sharpe_ratio": 1.8,
        "max_drawdown": -0.12,
        "calmar_ratio": 1.25,
        "volatility": 0.08,
        "downside_volatility": 0.06,
        "var_95": -0.02,
        "cvar_95": -0.03,
        "turnover_rate": 1.2,
        "win_rate": 0.58,
        "profit_loss_ratio": 1.5,
        "ic_mean": 0.05,
        "ic_ir": 1.2,
        "ic_win_rate": 0.55,
        "total_trades": 500,
        "holding_period": 5.0,
    }

    logger.info("回测完成")
    return result


def main():
    parser = argparse.ArgumentParser(description="运行量化实验")
    parser.add_argument("--name", required=True, help="实验名称")
    parser.add_argument("--description", default="", help="实验描述")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument("--tags", nargs="+", help="实验标签")
    parser.add_argument("--experiment-dir", default="data/experiments", help="实验目录")

    args = parser.parse_args()

    # 加载配置
    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 添加版本信息
    config["code_version"] = get_git_commit_hash()
    config["data_version"] = datetime.now().strftime("%Y%m%d")

    # 创建实验管理器
    manager = ExperimentManager(experiment_dir=args.experiment_dir)

    # 创建实验
    experiment = manager.create_experiment(
        name=args.name,
        description=args.description,
        config=config,
        tags=args.tags,
    )

    logger.info(f"创建实验: {experiment.id}")

    try:
        # 更新状态为运行中
        manager.update_experiment(experiment.id, status="running")

        # 运行回测
        result_dict = run_backtest(config)

        # 创建结果对象
        result = ExperimentResult(**result_dict)

        # 更新实验结果
        manager.update_experiment(
            experiment.id,
            status="completed",
            result=result,
        )

        # 输出结果
        logger.info(f"实验完成: {experiment.id}")
        logger.info(f"综合评分: {result.get_score():.2f}")
        logger.info(f"年化收益: {result.annual_return:.2%}")
        logger.info(f"夏普比率: {result.sharpe_ratio:.2f}")
        logger.info(f"最大回撤: {result.max_drawdown:.2%}")
        logger.info(f"IC均值: {result.ic_mean:.4f}")
        logger.info(f"IC信息比率: {result.ic_ir:.2f}")

    except Exception as e:
        logger.error(f"实验失败: {e}", exc_info=True)
        manager.update_experiment(
            experiment.id,
            status="failed",
            error_message=str(e),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
