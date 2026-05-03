"""
滑点模型
========
计算市场冲击导致的滑点成本

滑点模型:
1. 固定滑点: 固定比例（例如0.1%）
2. 参与率滑点: 基于交易量占比和波动率的动态滑点

参与率滑点公式:
    slippage = base_spread + impact_coefficient * participation_rate * volatility

    其中:
    - base_spread: 基础价差（即使参与率极低也无法避免的买卖价差）
    - impact_coefficient: 市场冲击系数（Almgren-Chriss模型简化参数）
    - participation_rate: 参与率 = 交易金额 / 日成交额
    - volatility: 波动率
"""

from dataclasses import dataclass


@dataclass
class SlippageModel:
    """
    滑点模型

    Attributes:
        fixed_rate: 固定滑点费率
        impact_coefficient: 市场冲击系数
        base_spread: 基础价差
        use_participation_model: 是否使用参与率模型
    """

    fixed_rate: float = 0.001  # 固定滑点0.1%
    impact_coefficient: float = 0.3  # 市场冲击系数
    base_spread: float = 0.0005  # 基础价差 5bps
    use_participation_model: bool = True  # 默认使用参与率模型

    def calc_slippage(
        self,
        amount: float,
        daily_volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        """
        计算滑点成本

        Args:
            amount: 交易金额
            daily_volume: 日成交额
            volatility: 波动率

        Returns:
            滑点成本（金额）
        """
        if not self.use_participation_model:
            # 固定滑点
            return amount * self.fixed_rate

        # 参与率滑点模型
        if daily_volume is None or volatility is None or daily_volume <= 0:
            # 数据不足，回退到固定滑点
            return amount * self.fixed_rate

        # 计算参与率
        participation_rate = amount / daily_volume

        # 参与率滑点公式
        slippage_rate = self.base_spread + self.impact_coefficient * participation_rate * volatility

        return amount * slippage_rate

    def calc_slippage_rate(
        self,
        amount: float,
        daily_volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        """
        计算滑点费率

        Args:
            amount: 交易金额
            daily_volume: 日成交额
            volatility: 波动率

        Returns:
            滑点费率（比例）
        """
        if amount <= 0:
            return 0.0

        slippage = self.calc_slippage(amount, daily_volume, volatility)
        return slippage / amount

    def estimate_execution_price(
        self,
        base_price: float,
        amount: float,
        direction: str,
        daily_volume: float | None = None,
        volatility: float | None = None,
    ) -> float:
        """
        估算执行价格（考虑滑点）

        Args:
            base_price: 基准价格（例如收盘价）
            amount: 交易金额
            direction: 交易方向 ('buy' or 'sell')
            daily_volume: 日成交额
            volatility: 波动率

        Returns:
            预期执行价格
        """
        slippage_rate = self.calc_slippage_rate(amount, daily_volume, volatility)

        if direction == "buy":
            # 买入时价格上涨
            return base_price * (1 + slippage_rate)
        else:
            # 卖出时价格下跌
            return base_price * (1 - slippage_rate)

    def estimate_market_impact(
        self,
        amount: float,
        daily_volume: float,
        volatility: float,
    ) -> dict[str, float]:
        """
        估算市场冲击

        Args:
            amount: 交易金额
            daily_volume: 日成交额
            volatility: 波动率

        Returns:
            市场冲击分析字典
        """
        participation_rate = amount / daily_volume if daily_volume > 0 else 0.0
        slippage_rate = self.calc_slippage_rate(amount, daily_volume, volatility)
        slippage_amount = amount * slippage_rate

        return {
            "participation_rate": participation_rate,
            "slippage_rate": slippage_rate,
            "slippage_amount": slippage_amount,
            "base_spread_contribution": self.base_spread,
            "impact_contribution": self.impact_coefficient * participation_rate * volatility,
        }
