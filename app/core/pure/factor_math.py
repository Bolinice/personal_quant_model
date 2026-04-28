"""
因子计算纯函数 — 无副作用、无 IO、无数据库依赖

所有函数接收 numpy/pandas 数据结构，返回计算结果。
不修改输入，不产生副作用，可独立测试。
"""

import numpy as np
import pandas as pd


def calc_momentum(close: pd.Series, period: int = 20) -> pd.Series:
    """动量因子: 过去N日收益率

    Args:
        close: 收盘价序列（按股票分组后传入单只股票）
        period: 回看天数

    Returns:
        动量值序列
    """
    return close.pct_change(period)


def calc_reversal(close: pd.Series, period: int = 5) -> pd.Series:
    """反转因子: 短期收益率的负值

    Args:
        close: 收盘价序列
        period: 回看天数

    Returns:
        反转因子值（负动量）
    """
    return -close.pct_change(period)


def calc_volatility(close: pd.Series, period: int = 20) -> pd.Series:
    """波动率因子: 过去N日收益率标准差

    Args:
        close: 收盘价序列
        period: 回看天数

    Returns:
        波动率序列
    """
    returns = close.pct_change()
    return returns.rolling(period).std()


def calc_turnover_ratio(volume: pd.Series, turnover: pd.Series, period: int = 20) -> pd.Series:
    """换手率因子: 过去N日平均换手率

    Args:
        volume: 成交量序列（未使用，保持接口一致）
        turnover: 换手率序列
        period: 回看天数

    Returns:
        平均换手率序列
    """
    return turnover.rolling(period).mean()


def calc_price_volume_corr(close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
    """量价相关因子: 过去N日价格变化与成交量的相关系数

    Args:
        close: 收盘价序列
        volume: 成交量序列
        period: 回看天数

    Returns:
        相关系数序列
    """
    returns = close.pct_change()
    return returns.rolling(period).corr(volume)


def calc_high_low_ratio(high: pd.Series, low: pd.Series, period: int = 20) -> pd.Series:
    """振幅因子: 过去N日(最高价-最低价)/收盘价 均值

    Args:
        high: 最高价序列
        low: 最低价序列
        period: 回看天数

    Returns:
        振幅序列
    """
    amplitude = (high - low) / (high + low) * 2
    return amplitude.rolling(period).mean()


def calc_ema(series: pd.Series, span: int) -> pd.Series:
    """指数移动平均

    Args:
        series: 输入序列
        span: EMA跨度

    Returns:
        EMA序列
    """
    return series.ewm(span=span, adjust=False).mean()


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD指标

    Args:
        close: 收盘价序列
        fast: 快线周期
        slow: 慢线周期
        signal: 信号线周期

    Returns:
        (DIF, DEA, MACD柱) 三元组
    """
    ema_fast = calc_ema(close, fast)
    ema_slow = calc_ema(close, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    macd_bar = 2 * (dif - dea)
    return dif, dea, macd_bar


def calc_bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """布林带

    Args:
        close: 收盘价序列
        period: 移动平均周期
        num_std: 标准差倍数

    Returns:
        (上轨, 中轨, 下轨) 三元组
    """
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def winsorize_mad(series: pd.Series, n: float = 3.0) -> pd.Series:
    """MAD去极值

    基于中位数绝对偏差的去极值方法，比3-sigma更稳健。

    Args:
        series: 输入序列
        n: MAD倍数阈值

    Returns:
        去极值后的序列
    """
    median = series.median()
    mad = (series - median).abs().median() * 1.4826  # 1.4826使MAD与正态σ一致
    lower = median - n * mad
    upper = median + n * mad
    return series.clip(lower=lower, upper=upper)


def zscore_normalize(series: pd.Series) -> pd.Series:
    """Z-score标准化

    Args:
        series: 输入序列

    Returns:
        标准化后的序列
    """
    std = series.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std
