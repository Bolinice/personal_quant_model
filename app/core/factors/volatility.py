"""
波动率因子计算模块
==================
包含:
- Vol 20D (20日波动率)
- Vol 60D (60日波动率)
- Beta (市场Beta)
- Idio Vol (特质波动率)
"""

import pandas as pd
import numpy as np


def calc_volatility_factors(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    计算波动率因子

    Args:
        price_df: 价格数据，需包含 close, pct_chg 等字段

    Returns:
        波动率因子DataFrame
    """
    factors = pd.DataFrame(index=price_df.index)

    # 按ts_code分组
    if "ts_code" in price_df.columns:
        price_df = price_df.set_index("ts_code")

    # 计算日收益率
    if "pct_chg" in price_df.columns:
        returns = price_df["pct_chg"] / 100  # 转换为小数形式
    elif "close" in price_df.columns:
        returns = price_df["close"].pct_change()
    else:
        return factors

    # Vol 20D: 20日波动率（年化）
    vol_20d = returns.rolling(window=20).std() * np.sqrt(252)
    factors["vol_20d"] = vol_20d

    # Vol 60D: 60日波动率（年化）
    vol_60d = returns.rolling(window=60).std() * np.sqrt(252)
    factors["vol_60d"] = vol_60d

    # Beta: 市场Beta（需要市场收益率数据，这里简化处理）
    # 实际应该用个股收益率对市场收益率做回归
    # 这里暂时用波动率作为代理
    factors["beta"] = vol_20d / vol_20d.mean()

    # Idio Vol: 特质波动率（残差波动率）
    # 实际应该是回归后的残差标准差
    # 这里简化为总波动率减去系统波动率
    factors["idio_vol"] = vol_20d * 0.8  # 简化处理

    return factors
