#!/usr/bin/env python3
"""验证参与率滑点模型是否正确启用"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import date
from app.core.backtest_engine import ABShareBacktestEngine, BacktestState


def test_slippage_model():
    """测试参与率滑点模型"""
    print("=" * 60)
    print("测试参与率滑点模型")
    print("=" * 60)

    # 创建回测引擎
    engine = ABShareBacktestEngine(
        commission_rate=0.0003,
        stamp_tax_rate=0.001,
        slippage_rate=0.0005,
    )

    # 创建初始状态
    state = BacktestState(cash=1000000.0, initial_capital=1000000.0)

    # 测试场景1：小单买入（参与率低，滑点小）
    print("\n场景1：小单买入（10万元，日成交额1亿）")
    stock_data_small = {
        "close": 10.0,
        "volume": 10000000,  # 1000万股 * 10元 = 1亿日成交额
        "volatility": 0.02,
    }

    success = engine.execute_buy(
        state=state,
        ts_code="000001.SZ",
        target_amount=100000,  # 10万元
        price=10.0,
        trade_date=date(2024, 1, 2),
        stock_data=stock_data_small,
    )

    if success and state.trade_records:
        record = state.trade_records[-1]
        participation_rate = 100000 / 100000000  # 0.1%
        print(f"  参与率: {participation_rate:.4%}")
        print(f"  成交金额: {record['amount']:.2f}")
        print(f"  佣金: {record['commission']:.2f}")
        print(f"  滑点: {record['slippage']:.2f}")
        print(f"  总成本: {record['total_cost']:.2f}")
        print(f"  成本率: {record['total_cost']/record['amount']:.4%}")

    # 测试场景2：大单买入（参与率高，滑点大）
    print("\n场景2：大单买入（1000万元，日成交额1亿）")
    state2 = BacktestState(cash=20000000.0, initial_capital=20000000.0)
    stock_data_large = {
        "close": 10.0,
        "volume": 10000000,  # 1亿日成交额
        "volatility": 0.02,
    }

    success = engine.execute_buy(
        state=state2,
        ts_code="000001.SZ",
        target_amount=10000000,  # 1000万元
        price=10.0,
        trade_date=date(2024, 1, 2),
        stock_data=stock_data_large,
    )

    if success and state2.trade_records:
        record = state2.trade_records[-1]
        participation_rate = 10000000 / 100000000  # 10%
        print(f"  参与率: {participation_rate:.4%}")
        print(f"  成交金额: {record['amount']:.2f}")
        print(f"  佣金: {record['commission']:.2f}")
        print(f"  滑点: {record['slippage']:.2f}")
        print(f"  总成本: {record['total_cost']:.2f}")
        print(f"  成本率: {record['total_cost']/record['amount']:.4%}")

    # 测试场景3：无成交量数据（回退到固定滑点）
    print("\n场景3：无成交量数据（回退到固定滑点）")
    state3 = BacktestState(cash=1000000.0, initial_capital=1000000.0)

    success = engine.execute_buy(
        state=state3,
        ts_code="000001.SZ",
        target_amount=100000,
        price=10.0,
        trade_date=date(2024, 1, 2),
        stock_data=None,  # 无数据
    )

    if success and state3.trade_records:
        record = state3.trade_records[-1]
        print(f"  成交金额: {record['amount']:.2f}")
        print(f"  佣金: {record['commission']:.2f}")
        print(f"  滑点: {record['slippage']:.2f}")
        print(f"  总成本: {record['total_cost']:.2f}")
        print(f"  成本率: {record['total_cost']/record['amount']:.4%}")

    # 验证结果
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)

    if len(state.trade_records) > 0 and len(state2.trade_records) > 0:
        small_cost_rate = state.trade_records[-1]['total_cost'] / state.trade_records[-1]['amount']
        large_cost_rate = state2.trade_records[-1]['total_cost'] / state2.trade_records[-1]['amount']

        print(f"小单成本率: {small_cost_rate:.4%}")
        print(f"大单成本率: {large_cost_rate:.4%}")

        if large_cost_rate > small_cost_rate:
            print("✅ PASS: 大单成本率高于小单，参与率滑点模型正常工作")
            return True
        else:
            print("❌ FAIL: 大单成本率应高于小单")
            return False
    else:
        print("❌ FAIL: 交易执行失败")
        return False


if __name__ == "__main__":
    success = test_slippage_model()
    sys.exit(0 if success else 1)
