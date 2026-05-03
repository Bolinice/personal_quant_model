"""
动量因子计算模块
================
包含:
- Ret 1M Reversal (1个月反转)
- Ret 3M Skip1 (跳过最近1月的3月动量)
- Ret 6M Skip1 (跳过最近1月的6月动量)
- Ret 12M Skip1 (跳过最近1月的12月动量)
"""

import pandas as pd
import numpy as np


def calc_momentum_factors(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    计算动量因子

    Args:
        price_df: 价格数据，需包含 close 字段

    Returns:
        动量因子DataFrame
    """
    factors = pd.DataFrame(index=price_df.index)

    if "close" not in price_df.columns:
        return factors

    # 按ts_code分组计算收益率
    if "ts_code" in price_df.columns:
        price_df = price_df.set_index("ts_code")

    close = price_df["close"]

    # Ret 1M Reversal: 最近1个月收益率（反转效应，方向=-1）
    # 短期涨多的股票往往会回调
    ret_1m = close.pct_change(periods=20)  # 20个交易日≈1个月
    factors["ret_1m_reversal"] = ret_1m

    # Ret 3M Skip1: 跳过最近1月的3月动量
    # 计算[t-60, t-20]的收益率，跳过最近20天避免短期反转干扰
    close_lag20 = close.shift(20)
    close_lag60 = close.shift(60)
    ret_3m_skip1 = (close_lag20 - close_lag60) / close_lag60
    factors["ret_3m_skip1"] = ret_3m_skip1

    # Ret 6M Skip1: 跳过最近1月的6月动量
    close_lag120 = close.shift(120)
    ret_6m_skip1 = (close_lag20 - close_lag120) / close_lag120
    factors["ret_6m_skip1"] = ret_6m_skip1

    # Ret 12M Skip1: 跳过最近1月的12月动量
    close_lag240 = close.shift(240)
    ret_12m_skip1 = (close_lag20 - close_lag240) / close_lag240
    factors["ret_12m_skip1"] = ret_12m_skip1

    return factors
