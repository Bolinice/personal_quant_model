"""
因子计算基础模块
================
包含:
- PIT过滤函数
- 因子分组定义
- 安全除法函数
- FactorCalculator主类
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from datetime import date

import numpy as np
import pandas as pd

from app.core.factor_preprocess import FactorPreprocessor
from app.core.performance import timer

if TYPE_CHECKING:
    pass


def _safe_divide(numerator, denominator, eps: float = 1e-8):
    """
    安全除法: 分母接近0时返回NaN，避免inf污染

    Args:
        numerator: 分子
        denominator: 分母
        eps: 阈值，分母绝对值小于此值时返回NaN

    Returns:
        除法结果
    """
    denom = np.where(np.abs(denominator) < eps, np.nan, denominator)
    return numerator / denom


def pit_filter(financial_df: pd.DataFrame, trade_date: date, ann_date_col: str = "ann_date") -> pd.DataFrame:
    """
    PIT (Point-in-Time) 过滤: 仅使用公告日 <= 交易日的财务数据
    消除财务数据的前瞻偏差

    对于同一股票同一报告期有多条记录的情况，取ann_date <= trade_date中最新的一条

    Args:
        financial_df: 财务数据DataFrame，需包含 ann_date 列和 ts_code 列
        trade_date: 当前交易日期
        ann_date_col: 公告日期列名

    Returns:
        过滤后的DataFrame
    """
    if financial_df.empty:
        return financial_df

    if ann_date_col not in financial_df.columns:
        import warnings
        warnings.warn(
            f"Financial data missing '{ann_date_col}' column, "
            "PIT filtering cannot be applied. This may introduce look-ahead bias.",
            UserWarning,
            stacklevel=2,
        )
        return financial_df

    # 确保日期类型一致
    ann_dates = pd.to_datetime(financial_df[ann_date_col])
    trade_dt = pd.to_datetime(trade_date)

    # 仅保留公告日 <= 交易日的记录
    mask = ann_dates <= trade_dt
    filtered = financial_df.loc[mask].copy()

    if filtered.empty:
        return filtered

    # 对于同一股票同一报告期，取最新的公告记录
    if "report_period" in filtered.columns:
        filtered = filtered.sort_values([ann_date_col], ascending=False)
        filtered = filtered.drop_duplicates(subset=["ts_code", "report_period"], keep="first")
    elif "end_date" in filtered.columns:
        filtered = filtered.sort_values([ann_date_col], ascending=False)
        filtered = filtered.drop_duplicates(subset=["ts_code", "end_date"], keep="first")

    return filtered


# 因子分组定义
FACTOR_GROUPS = {
    "valuation": {
        "name": "价值因子",
        "factors": ["ep_ttm", "bp", "sp_ttm", "dp", "cfp_ttm"],
    },
    "growth": {
        "name": "成长因子",
        "factors": ["yoy_revenue", "yoy_net_profit", "yoy_deduct_net_profit", "yoy_roe"],
    },
    "quality": {
        "name": "质量因子",
        "factors": ["roe", "roa", "gross_profit_margin", "net_profit_margin", "current_ratio"],
    },
    "momentum": {
        "name": "动量因子",
        "factors": ["ret_1m_reversal", "ret_3m_skip1", "ret_6m_skip1", "ret_12m_skip1"],
    },
    "volatility": {
        "name": "波动率因子",
        "factors": ["vol_20d", "vol_60d", "beta", "idio_vol"],
    },
    "liquidity": {
        "name": "流动性因子",
        "factors": ["turnover_20d", "turnover_60d", "amihud_20d", "zero_return_ratio"],
    },
    "alternative": {
        "name": "另类因子",
        "factors": ["north_net_buy_ratio", "north_holding_chg_5d", "analyst_revision_1m"],
    },
}


class FactorCalculator:
    """
    因子计算器主类

    职责:
    - 协调各个因子模块的计算
    - 提供统一的因子计算接口
    - 处理因子缺失和异常
    """

    def __init__(self):
        self.preprocessor = FactorPreprocessor()

    @timer
    def calc_factors(
        self,
        price_df: pd.DataFrame,
        financial_df: pd.DataFrame | None = None,
        moneyflow_df: pd.DataFrame | None = None,
        northbound_df: pd.DataFrame | None = None,
        analyst_df: pd.DataFrame | None = None,
        factor_names: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        计算因子

        Args:
            price_df: 价格数据
            financial_df: 财务数据
            moneyflow_df: 资金流数据
            northbound_df: 北向资金数据
            analyst_df: 分析师数据
            factor_names: 要计算的因子名称列表（None表示全部）

        Returns:
            因子DataFrame
        """
        from app.core.factors.valuation import calc_valuation_factors
        from app.core.factors.growth import calc_growth_factors
        from app.core.factors.quality import calc_quality_factors
        from app.core.factors.momentum import calc_momentum_factors
        from app.core.factors.volatility import calc_volatility_factors
        from app.core.factors.liquidity import calc_liquidity_factors
        from app.core.factors.alternative import calc_alternative_factors

        factors = pd.DataFrame(index=price_df.index)

        # 根据factor_names确定需要计算的因子组
        groups_to_calc = self._determine_groups(factor_names)

        # 价值因子
        if "valuation" in groups_to_calc and financial_df is not None:
            val_factors = calc_valuation_factors(price_df, financial_df)
            factors = factors.join(val_factors, how="left")

        # 成长因子
        if "growth" in groups_to_calc and financial_df is not None:
            growth_factors = calc_growth_factors(financial_df)
            factors = factors.join(growth_factors, how="left")

        # 质量因子
        if "quality" in groups_to_calc and financial_df is not None:
            quality_factors = calc_quality_factors(financial_df)
            factors = factors.join(quality_factors, how="left")

        # 动量因子
        if "momentum" in groups_to_calc:
            momentum_factors = calc_momentum_factors(price_df)
            factors = factors.join(momentum_factors, how="left")

        # 波动率因子
        if "volatility" in groups_to_calc:
            vol_factors = calc_volatility_factors(price_df)
            factors = factors.join(vol_factors, how="left")

        # 流动性因子
        if "liquidity" in groups_to_calc:
            liq_factors = calc_liquidity_factors(price_df)
            factors = factors.join(liq_factors, how="left")

        # 另类因子
        if "alternative" in groups_to_calc:
            alt_factors = calc_alternative_factors(
                price_df,
                moneyflow_df,
                northbound_df,
                analyst_df,
            )
            factors = factors.join(alt_factors, how="left")

        # 如果指定了factor_names，只返回这些因子
        if factor_names:
            available_factors = [f for f in factor_names if f in factors.columns]
            factors = factors[available_factors]

        return factors

    def _determine_groups(self, factor_names: list[str] | None) -> set[str]:
        """
        根据因子名称确定需要计算的因子组

        Args:
            factor_names: 因子名称列表

        Returns:
            因子组集合
        """
        if factor_names is None:
            # 计算所有因子组
            return set(FACTOR_GROUPS.keys())

        # 根据因子名称确定所属的组
        groups = set()
        for factor_name in factor_names:
            for group_name, group_info in FACTOR_GROUPS.items():
                if factor_name in group_info["factors"]:
                    groups.add(group_name)
                    break

        return groups
