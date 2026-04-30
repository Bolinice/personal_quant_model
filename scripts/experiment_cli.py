"""
实验管理CLI工具

使用示例：
    # 列出所有实验
    python scripts/experiment_cli.py list

    # 查看实验详情
    python scripts/experiment_cli.py show exp_20260501_120000

    # 对比实验
    python scripts/experiment_cli.py compare exp_001 exp_002 exp_003

    # 查找最佳实验
    python scripts/experiment_cli.py best --metric sharpe_ratio

    # 删除实验
    python scripts/experiment_cli.py delete exp_20260501_120000

    # 导出实验
    python scripts/experiment_cli.py export exp_001 --output exp_001.json

    # 导入实验
    python scripts/experiment_cli.py import exp_001.json
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.experiment_manager import ExperimentManager
from app.core.logging import logger


def format_experiment(exp) -> str:
    """格式化实验信息"""
    lines = [
        f"实验ID: {exp.id}",
        f"名称: {exp.config.name}",
        f"描述: {exp.config.description}",
        f"标签: {', '.join(exp.config.tags)}",
        f"状态: {exp.status}",
        f"创建时间: {exp.created_at}",
    ]

    if exp.result:
        lines.extend([
            "",
            "=== 回测结果 ===",
            f"综合评分: {exp.result.get_score():.2f}",
            f"年化收益: {exp.result.annual_return:.2%}",
            f"夏普比率: {exp.result.sharpe_ratio:.2f}",
            f"最大回撤: {exp.result.max_drawdown:.2%}",
            f"卡玛比率: {exp.result.calmar_ratio:.2f}",
            f"波动率: {exp.result.volatility:.2%}",
            f"换手率: {exp.result.turnover_rate:.2f}",
            f"胜率: {exp.result.win_rate:.2%}",
            f"IC均值: {exp.result.ic_mean:.4f}",
            f"IC信息比率: {exp.result.ic_ir:.2f}",
            f"IC胜率: {exp.result.ic_win_rate:.2%}",
        ])

    if exp.error_message:
        lines.extend([
            "",
            f"错误信息: {exp.error_message}",
        ])

    return "\n".join(lines)


def cmd_list(args):
    """列出实验"""
    manager = ExperimentManager(experiment_dir=args.experiment_dir)

    experiments = manager.list_experiments(
        tags=args.tags,
        status=args.status,
        limit=args.limit,
    )

    if not experiments:
        print("没有找到实验")
        return

    print(f"找到 {len(experiments)} 个实验:\n")

    for exp in experiments:
        score = exp.result.get_score() if exp.result else 0
        print(f"[{exp.id}] {exp.config.name}")
        print(f"  状态: {exp.status} | 评分: {score:.2f} | 标签: {', '.join(exp.config.tags)}")
        if exp.result:
            print(f"  年化: {exp.result.annual_return:.2%} | 夏普: {exp.result.sharpe_ratio:.2f} | 回撤: {exp.result.max_drawdown:.2%}")
        print()


def cmd_show(args):
    """查看实验详情"""
    manager = ExperimentManager(experiment_dir=args.experiment_dir)

    exp = manager.get_experiment(args.exp_id)
    if not exp:
        print(f"实验不存在: {args.exp_id}")
        return

    print(format_experiment(exp))

    if args.config:
        print("\n=== 配置详情 ===")
        print(json.dumps(exp.config.to_dict(), indent=2, ensure_ascii=False))


def cmd_compare(args):
    """对比实验"""
    manager = ExperimentManager(experiment_dir=args.experiment_dir)

    comparison = manager.compare_experiments(
        exp_ids=args.exp_ids,
        metrics=args.metrics,
    )

    if not comparison["experiments"]:
        print("没有找到可对比的实验")
        return

    print("=== 实验对比 ===\n")

    # 打印实验列表
    print("实验列表:")
    for exp_data in comparison["experiments"]:
        print(f"  [{exp_data['id']}] {exp_data['name']} (评分: {exp_data['score']:.2f})")
    print()

    # 打印指标对比
    print("指标对比:")
    for metric, data in comparison["metrics"].items():
        best_exp = data["best_exp"]
        best_value = data["best_value"]
        print(f"\n{metric}:")
        print(f"  最佳: {best_exp} = {best_value:.4f}")

        for exp_data in comparison["experiments"]:
            if metric in exp_data:
                value = exp_data[metric]
                is_best = exp_data["id"] == best_exp
                marker = "★" if is_best else " "
                print(f"  {marker} [{exp_data['id']}] {value:.4f}")

    # 打印最佳实验
    if "overall" in comparison["best"]:
        print(f"\n综合最佳实验: {comparison['best']['overall']} (评分: {comparison['best']['score']:.2f})")


def cmd_best(args):
    """查找最佳实验"""
    manager = ExperimentManager(experiment_dir=args.experiment_dir)

    best_exp = manager.get_best_experiment(
        tags=args.tags,
        metric=args.metric,
    )

    if not best_exp:
        print("没有找到实验")
        return

    print(f"最佳实验 (按 {args.metric} 排序):\n")
    print(format_experiment(best_exp))


def cmd_delete(args):
    """删除实验"""
    manager = ExperimentManager(experiment_dir=args.experiment_dir)

    if not args.force:
        confirm = input(f"确认删除实验 {args.exp_id}? (y/N): ")
        if confirm.lower() != "y":
            print("取消删除")
            return

    manager.delete_experiment(args.exp_id)
    print(f"已删除实验: {args.exp_id}")


def cmd_export(args):
    """导出实验"""
    manager = ExperimentManager(experiment_dir=args.experiment_dir)

    manager.export_experiment(args.exp_id, args.output)
    print(f"已导出实验: {args.exp_id} -> {args.output}")


def cmd_import(args):
    """导入实验"""
    manager = ExperimentManager(experiment_dir=args.experiment_dir)

    exp = manager.import_experiment(args.input)
    print(f"已导入实验: {exp.id}")


def main():
    parser = argparse.ArgumentParser(description="实验管理CLI工具")
    parser.add_argument(
        "--experiment-dir",
        default="data/experiments",
        help="实验目录",
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # list命令
    list_parser = subparsers.add_parser("list", help="列出实验")
    list_parser.add_argument("--tags", nargs="+", help="标签过滤")
    list_parser.add_argument("--status", help="状态过滤")
    list_parser.add_argument("--limit", type=int, default=100, help="最大数量")

    # show命令
    show_parser = subparsers.add_parser("show", help="查看实验详情")
    show_parser.add_argument("exp_id", help="实验ID")
    show_parser.add_argument("--config", action="store_true", help="显示配置详情")

    # compare命令
    compare_parser = subparsers.add_parser("compare", help="对比实验")
    compare_parser.add_argument("exp_ids", nargs="+", help="实验ID列表")
    compare_parser.add_argument("--metrics", nargs="+", help="对比指标")

    # best命令
    best_parser = subparsers.add_parser("best", help="查找最佳实验")
    best_parser.add_argument("--tags", nargs="+", help="标签过滤")
    best_parser.add_argument("--metric", default="score", help="评价指标")

    # delete命令
    delete_parser = subparsers.add_parser("delete", help="删除实验")
    delete_parser.add_argument("exp_id", help="实验ID")
    delete_parser.add_argument("--force", action="store_true", help="强制删除")

    # export命令
    export_parser = subparsers.add_parser("export", help="导出实验")
    export_parser.add_argument("exp_id", help="实验ID")
    export_parser.add_argument("--output", required=True, help="输出文件")

    # import命令
    import_parser = subparsers.add_parser("import", help="导入实验")
    import_parser.add_argument("input", help="输入文件")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行命令
    commands = {
        "list": cmd_list,
        "show": cmd_show,
        "compare": cmd_compare,
        "best": cmd_best,
        "delete": cmd_delete,
        "export": cmd_export,
        "import": cmd_import,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
