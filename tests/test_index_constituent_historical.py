#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
P0验证：指数成分历史回溯正确性

验证目标：
1. 检查指数成分表是否有历史时点字段
2. 验证指数成分查询是否使用历史时点
3. 确认回测时使用的是历史成分，而非当前成分

验证方法：
1. 检查 IndexConstituent 表结构
2. 检查指数成分查询方法
3. 验证回测引擎使用历史成分
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import IndexConstituent
from sqlalchemy import inspect


def print_section(title: str):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60 + "\n")


def check_index_constituent_table():
    """检查指数成分表结构"""
    print_section("检查 IndexConstituent 表结构")

    # 获取表结构
    inspector = inspect(IndexConstituent)
    columns = inspector.columns

    print("IndexConstituent 表字段：")
    for col in columns:
        print(f"  - {col.name}: {col.type}")

    # 检查关键字段
    column_names = [col.name for col in columns]

    required_fields = {
        "index_code": "指数代码",
        "stock_code": "股票代码",
        "in_date": "纳入日期",
        "out_date": "剔除日期",
    }

    print("\n关键字段检查：")
    all_present = True
    for field, desc in required_fields.items():
        if field in column_names:
            print(f"  ✅ {field} ({desc}) - 存在")
        else:
            print(f"  ❌ {field} ({desc}) - 缺失")
            all_present = False

    if all_present:
        print("\n✅ IndexConstituent 表包含历史时点字段")
        print("   - in_date: 股票纳入指数的日期")
        print("   - out_date: 股票从指数剔除的日期")
        return True
    else:
        print("\n❌ IndexConstituent 表缺少历史时点字段")
        return False


def check_index_constituent_query():
    """检查指数成分查询方法"""
    print_section("检查指数成分查询方法")

    # 搜索指数成分查询相关代码
    import subprocess

    print("搜索指数成分查询方法...")

    # 搜索 get_index_constituent 相关函数
    result = subprocess.run(
        ["grep", "-rn", "def.*get.*index.*constituent", "app/"],
        capture_output=True,
        text=True
    )

    if result.stdout:
        print("\n找到指数成分查询方法：")
        print(result.stdout)
    else:
        print("\n❌ 未找到指数成分查询方法")
        return False

    # 搜索 IndexConstituent 查询
    result = subprocess.run(
        ["grep", "-rn", "IndexConstituent.*filter", "app/"],
        capture_output=True,
        text=True
    )

    if result.stdout:
        print("\nIndexConstituent 查询位置：")
        for line in result.stdout.strip().split('\n')[:10]:  # 只显示前10个
            print(f"  {line}")

    return True


def check_backtest_usage():
    """检查回测引擎是否使用历史成分"""
    print_section("检查回测引擎使用历史成分")

    import subprocess

    # 搜索回测引擎中的指数成分使用
    print("搜索回测引擎中的指数成分查询...")

    result = subprocess.run(
        ["grep", "-rn", "get.*index.*constituent", "app/core/backtest/"],
        capture_output=True,
        text=True
    )

    if result.stdout:
        print("\n回测引擎中的指数成分查询：")
        print(result.stdout)
    else:
        print("\n⚠️  回测引擎中未找到指数成分查询")
        print("   可能使用其他方式获取股票池")

    # 搜索 universe 相关代码
    result = subprocess.run(
        ["grep", "-rn", "universe", "app/core/backtest/"],
        capture_output=True,
        text=True
    )

    if result.stdout:
        print("\n回测引擎中的股票池（universe）相关代码：")
        for line in result.stdout.strip().split('\n')[:10]:
            print(f"  {line}")


def analyze_historical_correctness():
    """分析历史时点正确性"""
    print_section("历史时点正确性分析")

    print("标准查询逻辑：")
    print("""
在 T 日回测时，应该查询在 T 日属于指数成分的股票：

正确查询：
    IndexConstituent.query.filter(
        IndexConstituent.index_code == index_code,
        IndexConstituent.in_date <= trade_date,      # 已纳入
        (IndexConstituent.out_date.is_(None) |       # 未剔除
         IndexConstituent.out_date > trade_date)     # 或剔除日期在未来
    ).all()

错误查询1：不考虑时间
    IndexConstituent.query.filter(
        IndexConstituent.index_code == index_code
    ).all()  # ❌ 会包含未来才纳入的股票

错误查询2：只考虑纳入日期
    IndexConstituent.query.filter(
        IndexConstituent.index_code == index_code,
        IndexConstituent.in_date <= trade_date
    ).all()  # ❌ 会包含已经剔除的股票
    """)

    print("\n潜在前视偏差风险：")
    print("""
风险1：使用当前成分而非历史成分
  错误示例：
    # 在2020年回测时，使用2024年的指数成分
    constituents = get_current_index_constituents('000300.SH')

  正确示例：
    # 使用2020年的历史成分
    constituents = get_index_constituents('000300.SH', date='2020-01-01')

风险2：未考虑成分变动
  错误示例：
    # 只在回测开始时获取一次成分
    constituents = get_index_constituents(index_code, start_date)
    for date in date_range:
        backtest(constituents, date)  # ❌ 成分不会更新

  正确示例：
    # 每个调仓日重新获取成分
    for date in rebalance_dates:
        constituents = get_index_constituents(index_code, date)
        backtest(constituents, date)  # ✅ 使用当日成分

风险3：幸存者偏差
  错误示例：
    # 只查询当前仍在指数中的股票
    constituents = IndexConstituent.query.filter(
        out_date.is_(None)
    ).all()  # ❌ 排除了历史上被剔除的股票

  正确示例：
    # 查询历史上任何时点在指数中的股票
    constituents = get_index_constituents(index_code, date)
    """)


def check_repository_layer():
    """检查 Repository 层的指数成分查询"""
    print_section("检查 Repository 层")

    import subprocess

    # 搜索 repository 中的指数成分查询
    result = subprocess.run(
        ["find", "app/", "-name", "*repository*.py"],
        capture_output=True,
        text=True
    )

    if result.stdout:
        print("Repository 文件：")
        for file in result.stdout.strip().split('\n'):
            print(f"  - {file}")

        # 检查是否有指数成分相关的 repository
        result = subprocess.run(
            ["grep", "-rn", "index.*constituent", "app/repositories/"],
            capture_output=True,
            text=True
        )

        if result.stdout:
            print("\nRepository 中的指数成分查询：")
            print(result.stdout)
        else:
            print("\n⚠️  Repository 中未找到指数成分查询")
    else:
        print("⚠️  未找到 Repository 层")


def main():
    """主函数"""
    print("=" * 60)
    print("P0验证：指数成分历史回溯正确性")
    print("=" * 60)

    # 1. 检查表结构
    has_historical_fields = check_index_constituent_table()

    # 2. 检查查询方法
    check_index_constituent_query()

    # 3. 检查回测使用
    check_backtest_usage()

    # 4. 分析历史正确性
    analyze_historical_correctness()

    # 5. 检查 Repository 层
    check_repository_layer()

    # 总结
    print_section("验证总结")

    if has_historical_fields:
        print("✅ IndexConstituent 表包含历史时点字段（in_date, out_date）")
        print("✅ 具备实现历史时点查询的基础")
        print("\n建议：")
        print("1. 检查所有指数成分查询是否正确使用 in_date 和 out_date")
        print("2. 确保回测引擎在每个调仓日重新获取成分")
        print("3. 验证不存在幸存者偏差")
    else:
        print("❌ IndexConstituent 表缺少历史时点字段")
        print("❌ 无法实现历史时点查询")
        print("\n建议：")
        print("1. 添加 in_date 和 out_date 字段")
        print("2. 迁移历史数据")
        print("3. 修改查询逻辑")

    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
