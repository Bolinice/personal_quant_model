"""
事件驱动系统
============
回测事件、订单、订单簿的定义

从backtest_engine.py中提取:
- BacktestEventType (枚举)
- BacktestEvent (数据类)
- OrderStatus (枚举)
- Order (数据类)
- OrderBook (数据类)
"""

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any


# ==================== 事件类型 ====================


class BacktestEventType(StrEnum):
    """回测事件类型"""

    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"
    REBALANCE = "rebalance"
    FILL = "fill"
    RISK_CHECK = "risk_check"


@dataclass
class BacktestEvent:
    """回测事件"""

    event_type: BacktestEventType
    trade_date: date
    data: dict[str, Any] = field(default_factory=dict)


# ==================== 订单状态 ====================


class OrderStatus(StrEnum):
    """订单状态"""

    PENDING = "pending"
    FILLED = "filled"
    PARTIAL_FILLED = "partial_filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """
    订单 (目标权重→订单→成交的完整链路)

    Attributes:
        order_id: 订单ID
        ts_code: 股票代码
        direction: 买卖方向 ('buy' or 'sell')
        target_amount: 目标金额
        price: 价格
        trade_date: 交易日期
        status: 订单状态
        filled_amount: 已成交金额
        filled_price: 成交价格
        reject_reason: 拒绝原因
    """

    order_id: str
    ts_code: str
    direction: str  # 'buy' or 'sell'
    target_amount: float
    price: float
    trade_date: date
    status: OrderStatus = OrderStatus.PENDING
    filled_amount: float = 0.0
    filled_price: float = 0.0
    reject_reason: str = ""

    @property
    def filled_shares(self) -> int:
        """已成交股数"""
        return int(self.filled_amount / self.price) if self.price > 0 else 0


@dataclass
class OrderBook:
    """
    订单簿 - 管理当日所有订单

    Attributes:
        orders: 订单列表
        rejected_orders: 被拒绝的订单列表
    """

    orders: list[Order] = field(default_factory=list)
    rejected_orders: list[Order] = field(default_factory=list)

    def add_order(self, order: Order) -> None:
        """添加订单"""
        self.orders.append(order)

    def add_rejected(self, order: Order) -> None:
        """添加被拒绝的订单"""
        order.status = OrderStatus.REJECTED
        self.rejected_orders.append(order)

    def filled_orders(self) -> list[Order]:
        """获取已成交订单"""
        return [o for o in self.orders if o.status == OrderStatus.FILLED]

    def total_buy_amount(self) -> float:
        """总买入金额"""
        return sum(
            o.filled_amount
            for o in self.orders
            if o.direction == "buy" and o.status == OrderStatus.FILLED
        )

    def total_sell_amount(self) -> float:
        """总卖出金额"""
        return sum(
            o.filled_amount
            for o in self.orders
            if o.direction == "sell" and o.status == OrderStatus.FILLED
        )

    def clear(self) -> None:
        """清空订单簿"""
        self.orders.clear()
        self.rejected_orders.clear()

    def get_order_by_id(self, order_id: str) -> Order | None:
        """根据ID获取订单"""
        for order in self.orders:
            if order.order_id == order_id:
                return order
        return None

    def get_orders_by_status(self, status: OrderStatus) -> list[Order]:
        """根据状态获取订单"""
        return [o for o in self.orders if o.status == status]

    def get_orders_by_direction(self, direction: str) -> list[Order]:
        """根据方向获取订单"""
        return [o for o in self.orders if o.direction == direction]

    def summary(self) -> dict[str, Any]:
        """订单簿摘要"""
        return {
            "total_orders": len(self.orders),
            "filled_orders": len(self.filled_orders()),
            "rejected_orders": len(self.rejected_orders),
            "total_buy_amount": self.total_buy_amount(),
            "total_sell_amount": self.total_sell_amount(),
            "buy_orders": len(self.get_orders_by_direction("buy")),
            "sell_orders": len(self.get_orders_by_direction("sell")),
        }
