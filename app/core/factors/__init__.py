"""
因子计算子包
============
将原factor_calculator.py (1456行) 拆分为8个模块

模块划分:
- base.py - 因子基类、工具函数、PIT过滤
- valuation.py - 价值因子 (EP, BP, SP, DP, CFP)
- growth.py - 成长因子 (营收增长、利润增长、ROE增长)
- quality.py - 质量因子 (ROE, ROA, 毛利率、净利率)
- momentum.py - 动量因子 (1M反转、3M/6M/12M动量)
- volatility.py - 波动率因子 (20D/60D波动率、Beta、特质波动)
- liquidity.py - 流动性因子 (换手率、Amihud、零收益率)
- alternative.py - 另类因子 (北向资金、分析师、微观结构)

使用示例:
    from app.core.factors import FactorCalculator

    calculator = FactorCalculator()
    factors = calculator.calc_factors(
        price_df=price_df,
        financial_df=financial_df,
        factor_names=['roe', 'roa', 'ret_3m_skip1']
    )
"""

from app.core.factors.base import FactorCalculator, pit_filter, FACTOR_GROUPS
from app.core.factors.valuation import calc_valuation_factors
from app.core.factors.growth import calc_growth_factors
from app.core.factors.quality import calc_quality_factors
from app.core.factors.momentum import calc_momentum_factors
from app.core.factors.volatility import calc_volatility_factors
from app.core.factors.liquidity import calc_liquidity_factors
from app.core.factors.alternative import calc_alternative_factors

__all__ = [
    # Main Calculator
    "FactorCalculator",
    # Utilities
    "pit_filter",
    "FACTOR_GROUPS",
    # Factor Calculators
    "calc_valuation_factors",
    "calc_growth_factors",
    "calc_quality_factors",
    "calc_momentum_factors",
    "calc_volatility_factors",
    "calc_liquidity_factors",
    "calc_alternative_factors",
]
