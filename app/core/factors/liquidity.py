"""
流动性因子计算模块
==================
包含:
- Turnover 20D (20日平均换手率)
- Turnover 60D (60日平均换手率)
- Amihud 20D (20日Amihud非流动性指标)
- Zero Return Ratio (零收益率比例)
"""

import pandas as pd
import numpy as np


def _safe_divide(numerator, denominator, eps: float = 1e-8):
    """安全除法"""
    denom = np.where(np.abs(denominator) < eps, np.nan, denominator)
    return numerator / denom


def calc_liquidity_factors(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    计算流动性因子

    Args:
        price_df: 价格数据，需包含 turnover_rate, volume, amount, pct_chg 等字段

    Returns:
        流动性因子DataFrame
    """
    factors = pd.DataFrame(index=price_df.index)

    # 按ts_code分组
    if "ts_code" in price_df.columns:
        price_df = price_df.set_index("ts_code")

    # Turnover 20D: 20日平均换手率
    if "turnover_rate" in price_df.columns:
        turnover_20d = price_df["turnover_rate"].rolling(window=20).mean()
        factors["turnover_20d"] = turnover_20d

    # Turnover 60D: 60日平均换手率
    if "turnover_rate" in price_df.columns:
        turnover_60d = price_df["turnover_rate"].rolling(window=60).mean()
        factors["turnover_60d"] = turnover_60d

    # Amihud 20D: Amihud非流动性指标 = |收益率| / 成交额
    # 值越大表示流动性越差
    if "pct_chg" in price_df.columns and "amount" in price_df.columns:
        abs_return = np.abs(price_df["pct_chg"] / 100)
        amount = price_df["amount"]
        amihud = _safe_divide(abs_return, amount)
        amihud_20d = amihud.rolling(window=20).mean()
        factors["amihud_20d"] = amihud_20d

    # Zero Return Ratio: 零收益率比例（20日内收益率为0的天数占比）
    # 值越大表示流动性越差
    if "pct_chg" in price_df.columns:
        zero_return = (price_df["pct_chg"] == 0).astype(int)
        zero_return_ratio = zero_return.rolling(window=20).mean()
        factors["zero_return_ratio"] = zero_return_ratio

    return factors
