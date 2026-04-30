#!/usr/bin/env python3
"""
配置中心管理CLI

用法:
    # 查看配置
    python scripts/config_manager.py get backtest.costs.commission_rate
    python scripts/config_manager.py list backtest.costs

    # 修改配置
    python scripts/config_manager.py set backtest.costs.commission_rate 0.0003 --author admin

    # 版本管理
    python scripts/config_manager.py versions
    python scripts/config_manager.py rollback 20240424_120000

    # 导出配置
    python scripts/config_manager.py export config_backup.yaml

    # 重新加载
    python scripts/config_manager.py reload
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config_center import get_config_center
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def cmd_get(args):
    """获取配置值"""
    config_center = get_config_center()
    value = config_center.get(args.key)

    if value is None:
        print(f"配置不存在: {args.key}")
        return 1

    print(f"{args.key} = {value}")
    return 0


def cmd_list(args):
    """列出配置段"""
    config_center = get_config_center()

    if args.section:
        # 获取指定段
        keys = args.section.split(".")
        config = config_center.get_all()
        for k in keys:
            if isinstance(config, dict) and k in config:
                config = config[k]
            else:
                print(f"配置段不存在: {args.section}")
                return 1
    else:
        # 获取所有配置
        config = config_center.get_all()

    # 打印配置
    _print_config(config, indent=0)
    return 0


def _print_config(config, indent=0):
    """递归打印配置"""
    if isinstance(config, dict):
        for key, value in config.items():
            if isinstance(value, dict):
                print("  " * indent + f"{key}:")
                _print_config(value, indent + 1)
            else:
                print("  " * indent + f"{key}: {value}")
    else:
        print("  " * indent + str(config))


def cmd_set(args):
    """设置配置值"""
    config_center = get_config_center()

    # 类型转换
    value = args.value
    try:
        # 尝试转换为数字
        if "." in value:
            value = float(value)
        else:
            value = int(value)
    except ValueError:
        # 尝试转换为布尔值
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        # 否则保持字符串

    try:
        config_center.set(args.key, value, author=args.author)
        print(f"配置已更新: {args.key} = {value}")
        return 0
    except Exception as e:
        print(f"配置更新失败: {e}")
        return 1


def cmd_versions(args):
    """查看版本历史"""
    config_center = get_config_center()
    versions = config_center.get_version_history(limit=args.limit)

    if not versions:
        print("无版本历史")
        return 0

    print(f"{'版本':<20} {'时间':<20} {'作者':<15} {'描述'}")
    print("-" * 80)
    for v in reversed(versions):
        print(f"{v.version:<20} {v.timestamp[:19]:<20} {v.author:<15} {v.description}")

    return 0


def cmd_rollback(args):
    """回滚到指定版本"""
    config_center = get_config_center()

    try:
        config_center.rollback(args.version)
        print(f"配置已回滚到版本: {args.version}")
        return 0
    except Exception as e:
        print(f"回滚失败: {e}")
        return 1


def cmd_export(args):
    """导出配置"""
    config_center = get_config_center()

    try:
        config_center.export_config(args.output)
        print(f"配置已导出到: {args.output}")
        return 0
    except Exception as e:
        print(f"导出失败: {e}")
        return 1


def cmd_reload(args):
    """重新加载配置"""
    config_center = get_config_center()

    try:
        config_center.reload()
        print("配置已重新加载")
        return 0
    except Exception as e:
        print(f"重新加载失败: {e}")
        return 1


def cmd_validate(args):
    """验证配置"""
    config_center = get_config_center()
    config = config_center.get_all()

    errors = []

    # 验证交易成本
    costs = config.get("backtest", {}).get("costs", {})
    if costs:
        for key in ["commission_rate", "stamp_tax_rate", "slippage_rate"]:
            value = costs.get(key)
            if value is not None and not (0 <= value <= 0.01):
                errors.append(f"backtest.costs.{key} 超出范围 [0, 0.01]: {value}")

    # 验证风险参数
    risk = config.get("risk", {})
    if risk:
        max_position = risk.get("max_position")
        if max_position is not None and not (0 < max_position <= 1):
            errors.append(f"risk.max_position 超出范围 (0, 1]: {max_position}")

    if errors:
        print("配置验证失败:")
        for error in errors:
            print(f"  - {error}")
        return 1
    else:
        print("配置验证通过")
        return 0


def main():
    parser = argparse.ArgumentParser(description="配置中心管理工具")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # get 命令
    parser_get = subparsers.add_parser("get", help="获取配置值")
    parser_get.add_argument("key", help="配置键（点号分隔）")

    # list 命令
    parser_list = subparsers.add_parser("list", help="列出配置")
    parser_list.add_argument("section", nargs="?", help="配置段（可选）")

    # set 命令
    parser_set = subparsers.add_parser("set", help="设置配置值")
    parser_set.add_argument("key", help="配置键（点号分隔）")
    parser_set.add_argument("value", help="配置值")
    parser_set.add_argument("--author", default="admin", help="修改者（默认: admin）")

    # versions 命令
    parser_versions = subparsers.add_parser("versions", help="查看版本历史")
    parser_versions.add_argument("--limit", type=int, default=10, help="显示数量（默认: 10）")

    # rollback 命令
    parser_rollback = subparsers.add_parser("rollback", help="回滚到指定版本")
    parser_rollback.add_argument("version", help="版本号")

    # export 命令
    parser_export = subparsers.add_parser("export", help="导出配置")
    parser_export.add_argument("output", help="输出文件路径")

    # reload 命令
    parser_reload = subparsers.add_parser("reload", help="重新加载配置")

    # validate 命令
    parser_validate = subparsers.add_parser("validate", help="验证配置")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 执行命令
    commands = {
        "get": cmd_get,
        "list": cmd_list,
        "set": cmd_set,
        "versions": cmd_versions,
        "rollback": cmd_rollback,
        "export": cmd_export,
        "reload": cmd_reload,
        "validate": cmd_validate,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
