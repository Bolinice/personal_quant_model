"""
另类因子计算模块
================
包含:
- 北向资金因子 (North Net Buy Ratio, North Holding Change)
- 分析师因子 (Analyst Revision, Analyst Coverage)
- 微观结构因子 (Large Order Ratio, Overnight Return)
"""

import pandas as pd
import numpy as np


def _safe_divide(numerator, denominator, eps: float = 1e-8):
    """安全除法"""
    denom = np.where(np.abs(denominator) < eps, np.nan, denominator)
    return numerator / denom


def calc_alternative_factors(
    price_df: pd.DataFrame,
    moneyflow_df: pd.DataFrame | None = None,
    northbound_df: pd.DataFrame | None = None,
    analyst_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    计算另类因子

    Args:
        price_df: 价格数据
        moneyflow_df: 资金流数据
        northbound_df: 北向资金数据
        analyst_df: 分析师数据

    Returns:
        另类因子DataFrame
    """
    factors = pd.DataFrame(index=price_df.index)

    # 北向资金因子
    if northbound_df is not None and not northbound_df.empty:
        if "ts_code" in northbound_df.columns:
            northbound_df = northbound_df.set_index("ts_code")

        # North Net Buy Ratio: 北向净买入占比
        if "net_buy" in northbound_df.columns and "amount" in price_df.columns:
            net_buy = northbound_df["net_buy"].reindex(price_df.index)
            amount = price_df["amount"]
            factors["north_net_buy_ratio"] = _safe_divide(net_buy, amount)

        # North Holding Change 5D: 北向持股变化（5日）
        if "holding" in northbound_df.columns:
            holding = northbound_df["holding"].reindex(price_df.index)
            holding_chg_5d = holding.pct_change(periods=5)
            factors["north_holding_chg_5d"] = holding_chg_5d

        # North Holding Pct: 北向持股占比
        if "holding_pct" in northbound_df.columns:
            factors["north_holding_pct"] = northbound_df["holding_pct"].reindex(price_df.index)

    # 分析师因子
    if analyst_df is not None and not analyst_df.empty:
        if "ts_code" in analyst_df.columns:
            analyst_df = analyst_df.set_index("ts_code")

        # Analyst Revision 1M: 分析师评级变化（1个月）
        if "rating" in analyst_df.columns:
            rating = analyst_df["rating"].reindex(price_df.index)
            rating_chg_1m = rating.diff(periods=20)
            factors["analyst_revision_1m"] = rating_chg_1m

        # Analyst Coverage: 分析师覆盖度
        if "analyst_count" in analyst_df.columns:
            factors["analyst_coverage"] = analyst_df["analyst_count"].reindex(price_df.index)

    # 微观结构因子（从资金流数据计算）
    if moneyflow_df is not None and not moneyflow_df.empty:
        if "ts_code" in moneyflow_df.columns:
            moneyflow_df = moneyflow_df.set_index("ts_code")

        # Large Order Ratio: 大单占比
        if "buy_lg_amount" in moneyflow_df.columns and "amount" in price_df.columns:
            buy_lg_amount = moneyflow_df["buy_lg_amount"].reindex(price_df.index)
            amount = price_df["amount"]
            factors["large_order_ratio"] = _safe_divide(buy_lg_amount, amount)

    # 隔夜收益率（从价格数据计算）
    if "open" in price_df.columns and "close" in price_df.columns:
        close_prev = price_df["close"].shift(1)
        open_curr = price_df["open"]
        overnight_return = _safe_divide(open_curr - close_prev, close_prev)
        factors["overnight_return"] = overnight_return

    return factors
