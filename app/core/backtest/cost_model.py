"""
交易成本模型
============
计算买入/卖出的交易成本

从backtest_engine.py中提取并增强:
- TransactionCost (数据类)
- calc_buy_cost() - 计算买入成本
- calc_sell_cost() - 计算卖出成本

A股交易成本构成:
1. 佣金 (commission): 双边收取，万2.5，最低5元
2. 印花税 (stamp_tax): 单边收取（仅卖出），千1
3. 过户费 (transfer_fee): 双边收取，十万分之一
4. 滑点 (slippage): 市场冲击成本
"""

from dataclasses import dataclass
import numpy as np

# A股交易成本常量
DEFAULT_COMMISSION_RATE = 0.00025  # 万2.5
DEFAULT_STAMP_TAX_RATE = 0.001  # 千1（仅卖出）
DEFAULT_TRANSFER_FEE_RATE = 0.00001  # 十万分之一
DEFAULT_SLIPPAGE_RATE = 0.001  # 固定滑点0.1%
MIN_COMMISSION = 5.0  # 最低佣金5元


@dataclass
class TransactionCost:
    """
    交易成本模型

    Attributes:
        commission_rate: 佣金费率
        stamp_tax_rate: 印花税费率
        transfer_fee_rate: 过户费率
        slippage_rate: 固定滑点费率
        min_commission: 最低佣金
        impact_coefficient: 市场冲击系数（参与率滑点模型）
        base_spread: 基础价差（参与率滑点模型）
    """

    commission_rate: float = DEFAULT_COMMISSION_RATE
    stamp_tax_rate: float = DEFAULT_STAMP_TAX_RATE
    transfer_fee_rate: float = DEFAULT_TRANSFER_FEE_RATE
    slippage_rate: float = DEFAULT_SLIPPAGE_RATE
    min_commission: float = MIN_COMMISSION
    # 参与率滑点参数
    impact_coefficient: float = 0.3  # 市场冲击系数
    base_spread: float = 0.0005  # 基础价差 5bps

    def calc_buy_cost(
        self,
        amount: float,
        daily_volume: float | None = None,
        volatility: float | None = None,
    ) -> dict[str, float]:
        """
        计算买入成本

        Args:
            amount: 买入金额
            daily_volume: 日成交额（用于参与率滑点模型）
            volatility: 波动率（用于参与率滑点模型）

        Returns:
            成本明细字典
        """
        amount = float(amount)  # Convert Decimal to float

        # 1. 佣金（最低5元）
        commission = max(amount * self.commission_rate, self.min_commission)

        # 2. 过户费
        transfer_fee = amount * self.transfer_fee_rate

        # 3. 滑点
        if daily_volume is not None and volatility is not None and daily_volume > 0:
            # 参与率滑点模型
            participation_rate = amount / daily_volume
            slippage = amount * (
                self.base_spread + self.impact_coefficient * volatility * np.sqrt(participation_rate)
            )
        else:
            # 固定滑点
            slippage = amount * self.slippage_rate

        # 总成本
        total_cost = commission + transfer_fee + slippage

        return {
            "commission": round(commission, 2),
            "stamp_tax": 0.0,  # 买入无印花税
            "transfer_fee": round(transfer_fee, 2),
            "slippage": round(slippage, 2),
            "total_cost": round(total_cost, 2),
            "cost_rate": total_cost / amount if amount > 0 else 0.0,
        }

    def calc_sell_cost(
        self,
        amount: float,
        daily_volume: float | None = None,
        volatility: float | None = None,
    ) -> dict[str, float]:
        """
        计算卖出成本

        Args:
            amount: 卖出金额
            daily_volume: 日成交额（用于参与率滑点模型）
            volatility: 波动率（用于参与率滑点模型）

        Returns:
            成本明细字典
        """
        amount = float(amount)  # Convert Decimal to float

        # 1. 佣金（最低5元）
        commission = max(amount * self.commission_rate, self.min_commission)

        # 2. 印花税（仅卖出收取）
        stamp_tax = amount * self.stamp_tax_rate

        # 3. 过户费
        transfer_fee = amount * self.transfer_fee_rate

        # 4. 滑点
        if daily_volume is not None and volatility is not None and daily_volume > 0:
            # 参与率滑点模型
            participation_rate = amount / daily_volume
            slippage = amount * (
                self.base_spread + self.impact_coefficient * volatility * np.sqrt(participation_rate)
            )
        else:
            # 固定滑点
            slippage = amount * self.slippage_rate

        # 总成本
        total_cost = commission + stamp_tax + transfer_fee + slippage

        return {
            "commission": round(commission, 2),
            "stamp_tax": round(stamp_tax, 2),
            "transfer_fee": round(transfer_fee, 2),
            "slippage": round(slippage, 2),
            "total_cost": round(total_cost, 2),
            "cost_rate": total_cost / amount if amount > 0 else 0.0,
        }

    def calc_total_cost(
        self,
        buy_amount: float,
        sell_amount: float,
        buy_volume: float | None = None,
        sell_volume: float | None = None,
        volatility: float | None = None,
    ) -> dict[str, float]:
        """
        计算总交易成本（买入+卖出）

        Args:
            buy_amount: 买入金额
            sell_amount: 卖出金额
            buy_volume: 买入股票日成交额
            sell_volume: 卖出股票日成交额
            volatility: 波动率

        Returns:
            总成本明细字典
        """
        buy_cost = self.calc_buy_cost(buy_amount, buy_volume, volatility)
        sell_cost = self.calc_sell_cost(sell_amount, sell_volume, volatility)

        return {
            "buy_cost": buy_cost["total_cost"],
            "sell_cost": sell_cost["total_cost"],
            "total_cost": buy_cost["total_cost"] + sell_cost["total_cost"],
            "buy_cost_rate": buy_cost["cost_rate"],
            "sell_cost_rate": sell_cost["cost_rate"],
            "total_cost_rate": (buy_cost["total_cost"] + sell_cost["total_cost"])
            / (buy_amount + sell_amount)
            if (buy_amount + sell_amount) > 0
            else 0.0,
        }
