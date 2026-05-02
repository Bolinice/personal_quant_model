"""
因子计算纯函数 — 无副作用、无 IO、无数据库依赖

所有函数接收 numpy/pandas 数据结构，返回计算结果。
不修改输入，不产生副作用，可独立测试。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ==================== 辅助函数 ====================


def safe_divide(numerator: pd.Series | np.ndarray, denominator: pd.Series | np.ndarray, eps: float = 1e-8) -> pd.Series | np.ndarray:
    """安全除法: 分母接近0时返回NaN，避免inf污染

    Args:
        numerator: 分子
        denominator: 分母
        eps: 最小分母阈值

    Returns:
        除法结果，分母过小时为NaN
    """
    denom = np.where(np.abs(denominator) < eps, np.nan, denominator)
    return numerator / denom


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


def calc_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
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


def calc_bollinger_bands(
    close: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
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


# ==================== 动量因子 ====================


def calc_momentum_skip(close: pd.Series, skip_period: int = 20, lookback_period: int = 60) -> pd.Series:
    """跳月动量因子: 跳过最近N日，计算之前的收益率

    跳过最近1个月避免短期反转效应污染中长期动量信号。

    Args:
        close: 收盘价序列（单只股票或已按股票分组）
        skip_period: 跳过的天数（默认20天约1个月）
        lookback_period: 回看天数（默认60天约3个月）

    Returns:
        跳月动量值序列
    """
    close_skip = close.shift(skip_period)
    close_lookback = close.shift(lookback_period)
    return safe_divide(close_skip, close_lookback) - 1


def calc_reversal_1m(close: pd.Series, period: int = 20) -> pd.Series:
    """短期反转因子: 近1月收益率（用于反转策略）

    短期反转效应显著，涨多回撤，方向=-1。

    Args:
        close: 收盘价序列
        period: 回看天数（默认20天约1个月）

    Returns:
        短期收益率序列
    """
    return close.pct_change(period)


# ==================== 波动率因子 ====================


def calc_volatility_annualized(close: pd.Series, period: int = 20, min_periods: int = 10, trading_days: int = 252) -> pd.Series:
    """年化波动率因子

    Args:
        close: 收盘价序列
        period: 滚动窗口天数
        min_periods: 最小有效天数
        trading_days: 年交易日数（A股252天）

    Returns:
        年化波动率序列
    """
    daily_ret = close.pct_change()
    return daily_ret.rolling(period, min_periods=min_periods).std() * np.sqrt(trading_days)


# ==================== 流动性因子 ====================


def calc_turnover_mean(turnover_rate: pd.Series, period: int = 20, min_periods: int = 10) -> pd.Series:
    """平均换手率因子

    Args:
        turnover_rate: 换手率序列
        period: 滚动窗口天数
        min_periods: 最小有效天数

    Returns:
        平均换手率序列
    """
    return turnover_rate.rolling(period, min_periods=min_periods).mean()


def calc_amihud_illiquidity(close: pd.Series, amount: pd.Series, period: int = 20, min_periods: int = 10) -> pd.Series:
    """Amihud非流动性指标: |收益率|/成交额

    衡量单位成交额引起的价格变动，值越大说明流动性越差。

    Args:
        close: 收盘价序列
        amount: 成交额序列
        period: 滚动窗口天数
        min_periods: 最小有效天数

    Returns:
        Amihud非流动性指标序列
    """
    daily_ret = close.pct_change()
    amihud_daily = daily_ret.abs() / amount.replace(0, np.nan)
    return amihud_daily.rolling(period, min_periods=min_periods).mean()


def calc_zero_return_ratio(close: pd.Series, period: int = 20, min_periods: int = 10, threshold: float = 0.001) -> pd.Series:
    """零收益比例: |日收益|<阈值的天数占比

    衡量停牌/涨跌停/无成交的频率，值越大流动性越差。

    Args:
        close: 收盘价序列
        period: 滚动窗口天数
        min_periods: 最小有效天数
        threshold: 零收益阈值（默认0.1%）

    Returns:
        零收益比例序列
    """
    daily_ret = close.pct_change()
    zero_mask = daily_ret.abs() < threshold
    return zero_mask.rolling(period, min_periods=min_periods).mean()


# ==================== 估值因子 ====================


def calc_ep_ttm(net_profit: pd.Series, total_market_cap: pd.Series) -> pd.Series:
    """市盈率倒数（EP）: 净利润/总市值

    Args:
        net_profit: 净利润（TTM）
        total_market_cap: 总市值

    Returns:
        EP序列
    """
    return safe_divide(net_profit, total_market_cap)


def calc_bp(total_equity: pd.Series, total_market_cap: pd.Series) -> pd.Series:
    """市净率倒数（BP）: 净资产/总市值

    Args:
        total_equity: 净资产
        total_market_cap: 总市值

    Returns:
        BP序列
    """
    return safe_divide(total_equity, total_market_cap)


def calc_sp_ttm(revenue: pd.Series, total_market_cap: pd.Series) -> pd.Series:
    """市销率倒数（SP）: 营业收入/总市值

    Args:
        revenue: 营业收入（TTM）
        total_market_cap: 总市值

    Returns:
        SP序列
    """
    return safe_divide(revenue, total_market_cap)


def calc_cfp_ttm(operating_cash_flow: pd.Series, total_market_cap: pd.Series) -> pd.Series:
    """市现率倒数（CFP）: 经营现金流/总市值

    Args:
        operating_cash_flow: 经营现金流（TTM）
        total_market_cap: 总市值

    Returns:
        CFP序列
    """
    return safe_divide(operating_cash_flow, total_market_cap)


# ==================== 成长因子 ====================


def calc_yoy_growth(current: pd.Series, yoy_4q: pd.Series) -> pd.Series:
    """同比增长率: (当前值 - 4季度前值) / |4季度前值|

    使用4季度滚动消除季节性偏差。

    Args:
        current: 当前值
        yoy_4q: 4季度前的值

    Returns:
        同比增长率序列
    """
    return safe_divide(current - yoy_4q, yoy_4q.abs())


# ==================== 质量因子 ====================


def calc_roe(net_profit: pd.Series, total_equity: pd.Series, total_equity_prev: pd.Series | None = None) -> pd.Series:
    """净资产收益率（ROE）: 净利润/平均净资产

    使用期初期末平均净资产，避免增发/回购导致失真。

    Args:
        net_profit: 净利润
        total_equity: 期末净资产
        total_equity_prev: 期初净资产（可选）

    Returns:
        ROE序列
    """
    if total_equity_prev is not None:
        avg_equity = (total_equity + total_equity_prev) / 2
    else:
        # 无上期数据时用期末*0.9近似期初值
        avg_equity = (total_equity + total_equity * 0.9) / 2
    return safe_divide(net_profit, avg_equity)


def calc_roa(net_profit: pd.Series, total_assets: pd.Series, total_assets_prev: pd.Series | None = None) -> pd.Series:
    """总资产收益率（ROA）: 净利润/平均总资产

    Args:
        net_profit: 净利润
        total_assets: 期末总资产
        total_assets_prev: 期初总资产（可选）

    Returns:
        ROA序列
    """
    if total_assets_prev is not None:
        avg_assets = (total_assets + total_assets_prev) / 2
    else:
        avg_assets = total_assets
    return safe_divide(net_profit, avg_assets)


def calc_gross_profit_margin(gross_profit: pd.Series, revenue: pd.Series) -> pd.Series:
    """毛利率: 毛利润/营业收入

    Args:
        gross_profit: 毛利润
        revenue: 营业收入

    Returns:
        毛利率序列
    """
    return safe_divide(gross_profit, revenue)


def calc_net_profit_margin(net_profit: pd.Series, revenue: pd.Series) -> pd.Series:
    """净利率: 净利润/营业收入

    Args:
        net_profit: 净利润
        revenue: 营业收入

    Returns:
        净利率序列
    """
    return safe_divide(net_profit, revenue)


def calc_current_ratio(current_assets: pd.Series, current_liabilities: pd.Series) -> pd.Series:
    """流动比率: 流动资产/流动负债

    Args:
        current_assets: 流动资产
        current_liabilities: 流动负债

    Returns:
        流动比率序列
    """
    return safe_divide(current_assets, current_liabilities)
