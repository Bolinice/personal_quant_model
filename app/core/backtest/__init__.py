"""
回测子包
========
将原backtest_engine.py (1921行) 拆分为多个模块

模块划分:
- event_system.py - 事件驱动系统 (BacktestEvent, OrderStatus, Order, OrderBook)
- cost_model.py - 交易成本模型 (TransactionCost) [已更新]
- slippage.py - 滑点模型 (参与率滑点) [已更新]
- order_manager.py - 订单管理 (订单生成、执行、拒绝) [新增]
- validators.py - 回测验证器 (Walk-Forward, 蒙特卡洛) [待创建]
- engine.py - 核心回测引擎 (ABShareBacktestEngine) [待更新]

使用示例:
    from app.core.backtest import ABShareBacktestEngine

    engine = ABShareBacktestEngine(
        initial_capital=1_000_000,
        commission_rate=0.00025,
    )

    results = engine.run(
        signal_generator=my_signal_func,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
"""

from app.core.backtest.event_system import (
    BacktestEvent,
    BacktestEventType,
    Order,
    OrderBook,
    OrderStatus,
)
from app.core.backtest.cost_model import TransactionCost
from app.core.backtest.slippage import SlippageModel
from app.core.backtest.order_manager import OrderManager

__all__ = [
    # Event System
    "BacktestEvent",
    "BacktestEventType",
    "Order",
    "OrderBook",
    "OrderStatus",
    # Cost Model
    "TransactionCost",
    # Slippage Model
    "SlippageModel",
    # Order Manager
    "OrderManager",
]
