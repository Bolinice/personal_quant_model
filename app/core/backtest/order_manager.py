"""
订单管理器
==========
负责订单生成、执行、拒绝逻辑

职责:
- 根据目标权重生成订单
- 检查订单合法性（涨跌停、停牌、手数）
- 执行订单（模拟成交）
- 处理订单拒绝
"""

from datetime import date
from typing import Any
import uuid

import pandas as pd

from app.core.backtest.event_system import Order, OrderBook, OrderStatus
from app.core.backtest.cost_model import TransactionCost
from app.core.backtest.slippage import SlippageModel

# A股交易规则常量
LOT_SIZE = 100  # 最小交易单位100股
MAIN_BOARD_LIMIT_PCT = 10.0  # 主板涨跌停10%
GEM_LIMIT_PCT = 20.0  # 创业板涨跌停20%
STAR_LIMIT_PCT = 20.0  # 科创板涨跌停20%
ST_LIMIT_PCT = 5.0  # ST涨跌停5%


class OrderManager:
    """
    订单管理器

    Attributes:
        cost_model: 交易成本模型
        slippage_model: 滑点模型
        order_book: 订单簿
    """

    def __init__(
        self,
        cost_model: TransactionCost | None = None,
        slippage_model: SlippageModel | None = None,
    ):
        self.cost_model = cost_model or TransactionCost()
        self.slippage_model = slippage_model or SlippageModel()
        self.order_book = OrderBook()

    def generate_orders(
        self,
        target_weights: dict[str, float],
        current_positions: dict[str, float],
        portfolio_value: float,
        price_data: pd.DataFrame,
        trade_date: date,
    ) -> list[Order]:
        """
        根据目标权重生成订单

        Args:
            target_weights: 目标权重 {ts_code: weight}
            current_positions: 当前持仓 {ts_code: shares}
            portfolio_value: 组合总价值
            price_data: 价格数据（包含close, pct_chg等）
            trade_date: 交易日期

        Returns:
            订单列表
        """
        orders = []

        # 计算当前持仓权重
        current_weights = {}
        for ts_code, shares in current_positions.items():
            if ts_code in price_data.index:
                price = price_data.loc[ts_code, "close"]
                current_weights[ts_code] = (shares * price) / portfolio_value

        # 合并所有股票（目标+当前）
        all_codes = set(target_weights.keys()) | set(current_weights.keys())

        for ts_code in all_codes:
            target_weight = target_weights.get(ts_code, 0.0)
            current_weight = current_weights.get(ts_code, 0.0)
            weight_diff = target_weight - current_weight

            # 权重变化小于阈值，跳过
            if abs(weight_diff) < 0.0001:
                continue

            # 获取价格
            if ts_code not in price_data.index:
                continue

            price = price_data.loc[ts_code, "close"]
            target_amount = abs(weight_diff * portfolio_value)

            # 生成订单
            order = Order(
                order_id=str(uuid.uuid4()),
                ts_code=ts_code,
                direction="buy" if weight_diff > 0 else "sell",
                target_amount=target_amount,
                price=price,
                trade_date=trade_date,
            )

            orders.append(order)

        return orders

    def execute_order(
        self,
        order: Order,
        price_data: pd.DataFrame,
        market_data: pd.DataFrame | None = None,
    ) -> Order:
        """
        执行订单（模拟成交）

        Args:
            order: 订单
            price_data: 价格数据
            market_data: 市场数据（成交量、波动率等）

        Returns:
            执行后的订单
        """
        ts_code = order.ts_code

        # 检查价格数据
        if ts_code not in price_data.index:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "价格数据缺失"
            self.order_book.add_rejected(order)
            return order

        # 检查涨跌停
        if self._is_limit_up_or_down(ts_code, price_data, order.direction):
            order.status = OrderStatus.REJECTED
            order.reject_reason = "涨跌停限制"
            self.order_book.add_rejected(order)
            return order

        # 检查停牌
        if self._is_suspended(ts_code, price_data):
            order.status = OrderStatus.REJECTED
            order.reject_reason = "停牌"
            self.order_book.add_rejected(order)
            return order

        # 计算成交价格（考虑滑点）
        base_price = price_data.loc[ts_code, "close"]
        daily_volume = market_data.loc[ts_code, "amount"] if market_data is not None and ts_code in market_data.index else None
        volatility = market_data.loc[ts_code, "volatility"] if market_data is not None and ts_code in market_data.index else None

        filled_price = self.slippage_model.estimate_execution_price(
            base_price=base_price,
            amount=order.target_amount,
            direction=order.direction,
            daily_volume=daily_volume,
            volatility=volatility,
        )

        # 计算成交股数（向下取整到100股）
        filled_shares = int(order.target_amount / filled_price / LOT_SIZE) * LOT_SIZE

        if filled_shares == 0:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "金额不足100股"
            self.order_book.add_rejected(order)
            return order

        # 成交
        order.status = OrderStatus.FILLED
        order.filled_amount = filled_shares * filled_price
        order.filled_price = filled_price

        self.order_book.add_order(order)
        return order

    def _is_limit_up_or_down(
        self,
        ts_code: str,
        price_data: pd.DataFrame,
        direction: str,
    ) -> bool:
        """
        检查是否涨跌停

        Args:
            ts_code: 股票代码
            price_data: 价格数据
            direction: 交易方向

        Returns:
            是否涨跌停
        """
        if "pct_chg" not in price_data.columns:
            return False

        pct_chg = price_data.loc[ts_code, "pct_chg"]

        # 判断板块
        if ts_code.startswith("688"):
            limit_pct = STAR_LIMIT_PCT
        elif ts_code.startswith("300"):
            limit_pct = GEM_LIMIT_PCT
        elif "ST" in ts_code or "st" in ts_code:
            limit_pct = ST_LIMIT_PCT
        else:
            limit_pct = MAIN_BOARD_LIMIT_PCT

        # 买入时检查涨停，卖出时检查跌停
        if direction == "buy":
            return pct_chg >= limit_pct * 0.99  # 允许0.01%误差
        else:
            return pct_chg <= -limit_pct * 0.99

    def _is_suspended(self, ts_code: str, price_data: pd.DataFrame) -> bool:
        """
        检查是否停牌

        Args:
            ts_code: 股票代码
            price_data: 价格数据

        Returns:
            是否停牌
        """
        # 如果有成交量字段，成交量为0表示停牌
        if "volume" in price_data.columns:
            volume = price_data.loc[ts_code, "volume"]
            return volume == 0 or pd.isna(volume)

        return False

    def clear_order_book(self) -> None:
        """清空订单簿"""
        self.order_book.clear()

    def get_order_summary(self) -> dict[str, Any]:
        """获取订单摘要"""
        return self.order_book.summary()
