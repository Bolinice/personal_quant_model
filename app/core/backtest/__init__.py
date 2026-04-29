"""
A股回测引擎 — 模块化子包

子模块:
  cost_model — 交易成本模型 (TransactionCost)
  trading_rules — A股交易规则 (涨跌停/T+1/板块判断)
  events — 事件驱动架构 (Order/OrderBook/Event)
  validation — 统计验证 (Walk-Forward/蒙特卡洛/DSR/Bootstrap)
  metrics — 回测指标计算
  engine — 核心回测引擎 (ABShareBacktestEngine/EventDrivenBacktestEngine)

向后兼容: 所有公共API从本包直接导出
"""

from app.core.backtest_engine import (
    DEFAULT_COMMISSION_RATE,
    DEFAULT_SLIPPAGE_RATE,
    DEFAULT_STAMP_TAX_RATE,
    DEFAULT_TRANSFER_FEE_RATE,
    GEM_LIMIT,
    GEM_LIMIT_PCT,
    LOT_SIZE,
    MAIN_BOARD_LIMIT,
    MAIN_BOARD_LIMIT_PCT,
    MIN_COMMISSION,
    NORTH_LIMIT,
    NORTH_LIMIT_PCT,
    ST_LIMIT,
    ST_LIMIT_PCT,
    STAR_LIMIT,
    STAR_LIMIT_PCT,
    ABShareBacktestEngine,
    BacktestEvent,
    BacktestEventType,
    BacktestState,
    EventDrivenBacktestEngine,
    Order,
    OrderBook,
    OrderStatus,
    Position,
    SignalGenerator,
    TransactionCost,
)

__all__ = [
    "DEFAULT_COMMISSION_RATE",
    "DEFAULT_SLIPPAGE_RATE",
    "DEFAULT_STAMP_TAX_RATE",
    "DEFAULT_TRANSFER_FEE_RATE",
    "GEM_LIMIT",
    "GEM_LIMIT_PCT",
    "LOT_SIZE",
    "MAIN_BOARD_LIMIT",
    "MAIN_BOARD_LIMIT_PCT",
    "MIN_COMMISSION",
    "NORTH_LIMIT",
    "NORTH_LIMIT_PCT",
    "STAR_LIMIT",
    "STAR_LIMIT_PCT",
    "ST_LIMIT",
    "ST_LIMIT_PCT",
    "ABShareBacktestEngine",
    "BacktestEvent",
    "BacktestEventType",
    "BacktestState",
    "EventDrivenBacktestEngine",
    "Order",
    "OrderBook",
    "OrderStatus",
    "Position",
    "SignalGenerator",
    "TransactionCost",
]
