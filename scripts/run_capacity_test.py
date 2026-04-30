#!/usr/bin/env python3
"""
容量测试脚本 - 评估策略在不同资金规模下的表现

用法:
    python scripts/run_capacity_test.py --start 2024-01-01 --end 2024-12-31
    python scripts/run_capacity_test.py --start 2024-01-01 --end 2024-12-31 --levels 1M,10M,50M,100M
"""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.backtest_engine import BacktestEngine
from app.core.capacity_test import CapacityTester
from app.core.cost_model import CostModel
from app.core.signal_generator import SignalGenerator
from app.database import get_session
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def parse_capital_levels(levels_str: str) -> list[float]:
    """解析资金规模字符串，如 '1M,10M,50M,100M'"""
    result = []
    for level in levels_str.split(","):
        level = level.strip().upper()
        if level.endswith("M"):
            result.append(float(level[:-1]) * 1_000_000)
        elif level.endswith("B"):
            result.append(float(level[:-1]) * 1_000_000_000)
        else:
            result.append(float(level))
    return result


def main():
    parser = argparse.ArgumentParser(description="运行策略容量测试")
    parser.add_argument("--start", required=True, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument(
        "--levels",
        default="1M,10M,50M,100M,500M,1B",
        help="资金规模列表，如 '1M,10M,50M' (默认: 1M,10M,50M,100M,500M,1B)",
    )
    parser.add_argument(
        "--universe",
        default="hs300",
        choices=["hs300", "zz500", "zz1000", "all"],
        help="股票池 (默认: hs300)",
    )
    parser.add_argument(
        "--output",
        default="data/capacity_test",
        help="输出目录 (默认: data/capacity_test)",
    )

    args = parser.parse_args()

    # 解析日期
    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()

    # 解析资金规模
    capital_levels = parse_capital_levels(args.levels)

    logger.info("=" * 80)
    logger.info("策略容量测试")
    logger.info("=" * 80)
    logger.info("测试期间: %s ~ %s", start_date, end_date)
    logger.info("股票池: %s", args.universe)
    logger.info("资金规模: %s", [f"{c/1e6:.0f}M" if c < 1e9 else f"{c/1e9:.1f}B" for c in capital_levels])
    logger.info("=" * 80)

    # 初始化组件
    session = get_session()
    cost_model = CostModel()
    backtest_engine = BacktestEngine(cost_model=cost_model)
    capacity_tester = CapacityTester(backtest_engine=backtest_engine)
    signal_generator = SignalGenerator(session=session)

    # 获取股票池
    if args.universe == "hs300":
        from app.models.market import IndexWeight

        weights = (
            session.query(IndexWeight.con_code)
            .filter(IndexWeight.index_code == "000300.SH")
            .distinct()
            .all()
        )
        universe = [w[0] for w in weights]
    elif args.universe == "zz500":
        from app.models.market import IndexWeight

        weights = (
            session.query(IndexWeight.con_code)
            .filter(IndexWeight.index_code == "000905.SH")
            .distinct()
            .all()
        )
        universe = [w[0] for w in weights]
    elif args.universe == "zz1000":
        from app.models.market import IndexWeight

        weights = (
            session.query(IndexWeight.con_code)
            .filter(IndexWeight.index_code == "000852.SH")
            .distinct()
            .all()
        )
        universe = [w[0] for w in weights]
    else:
        # 全市场
        from app.models.market import StockBasic

        stocks = session.query(StockBasic.ts_code).filter(StockBasic.list_status == "L").all()
        universe = [s[0] for s in stocks]

    logger.info("股票池规模: %d", len(universe))

    # 运行容量测试
    try:
        result = capacity_tester.run_capacity_test(
            signal_generator=signal_generator.generate_signals,
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            capital_levels=capital_levels,
        )

        # 打印报告
        capacity_tester.print_report(result)

        # 保存结果
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"capacity_test_{timestamp}.json"

        import json

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "test_config": {
                        "start_date": str(start_date),
                        "end_date": str(end_date),
                        "universe": args.universe,
                        "universe_size": len(universe),
                        "capital_levels": capital_levels,
                    },
                    "results": {
                        "optimal_capacity": result.optimal_capacity,
                        "capacity_decay_rate": result.capacity_decay_rate,
                        "capital_levels": result.capital_levels,
                        "returns": result.returns,
                        "sharpe_ratios": result.sharpe_ratios,
                        "turnovers": result.turnovers,
                        "avg_slippages": result.avg_slippages,
                    },
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        logger.info("结果已保存到: %s", output_file)

        # 生成可视化图表（如果安装了matplotlib）
        try:
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(2, 2, figsize=(12, 10))

            # 收益率曲线
            axes[0, 0].plot(
                [c / 1e6 for c in result.capital_levels],
                [r * 100 for r in result.returns],
                marker="o",
            )
            axes[0, 0].set_xlabel("资金规模 (M)")
            axes[0, 0].set_ylabel("年化收益率 (%)")
            axes[0, 0].set_title("容量衰减曲线")
            axes[0, 0].grid(True)

            # 夏普比率
            axes[0, 1].plot(
                [c / 1e6 for c in result.capital_levels],
                result.sharpe_ratios,
                marker="o",
                color="green",
            )
            axes[0, 1].set_xlabel("资金规模 (M)")
            axes[0, 1].set_ylabel("夏普比率")
            axes[0, 1].set_title("夏普比率 vs 资金规模")
            axes[0, 1].grid(True)

            # 换手率
            axes[1, 0].plot(
                [c / 1e6 for c in result.capital_levels],
                [t * 100 for t in result.turnovers],
                marker="o",
                color="orange",
            )
            axes[1, 0].set_xlabel("资金规模 (M)")
            axes[1, 0].set_ylabel("换手率 (%)")
            axes[1, 0].set_title("换手率 vs 资金规模")
            axes[1, 0].grid(True)

            # 平均滑点
            axes[1, 1].plot(
                [c / 1e6 for c in result.capital_levels],
                result.avg_slippages,
                marker="o",
                color="red",
            )
            axes[1, 1].set_xlabel("资金规模 (M)")
            axes[1, 1].set_ylabel("平均滑点 (bps)")
            axes[1, 1].set_title("滑点成本 vs 资金规模")
            axes[1, 1].grid(True)

            plt.tight_layout()
            chart_file = output_dir / f"capacity_test_{timestamp}.png"
            plt.savefig(chart_file, dpi=150)
            logger.info("图表已保存到: %s", chart_file)

        except ImportError:
            logger.warning("未安装matplotlib，跳过图表生成")

    except Exception as e:
        logger.error("容量测试失败: %s", e, exc_info=True)
        return 1

    finally:
        session.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
