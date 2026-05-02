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
    return safe_divide(current - yoy_4q, np.abs(yoy_4q))


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


# ==================== 应计项因子 ====================


def calc_sloan_accrual(
    net_profit: pd.Series,
    operating_cash_flow: pd.Series,
    total_assets: pd.Series,
    total_assets_prev: pd.Series | None = None,
) -> pd.Series:
    """Sloan应计因子: (净利润 - 经营现金流) / 平均总资产

    Sloan(1996): 高应计企业未来盈利反转概率大，应计是盈利质量的反向指标。
    经营现金流比净利润更难操纵，二者差异反映盈余管理空间。

    Args:
        net_profit: 净利润
        operating_cash_flow: 经营现金流
        total_assets: 期末总资产
        total_assets_prev: 期初总资产（可选）

    Returns:
        Sloan应计序列
    """
    accruals = net_profit - operating_cash_flow
    if total_assets_prev is not None:
        avg_assets = (total_assets + total_assets_prev) / 2
    else:
        avg_assets = total_assets
    return safe_divide(accruals, avg_assets)


# ==================== 盈余质量因子 ====================


def calc_cash_flow_manipulation(net_profit: pd.Series, operating_cash_flow: pd.Series) -> pd.Series:
    """现金流操纵概率: |CFO - 净利润| / |净利润|

    CFO与净利严重偏离暗示可能存在盈余管理（如提前确认收入/延迟计提费用）。

    Args:
        net_profit: 净利润
        operating_cash_flow: 经营现金流

    Returns:
        现金流操纵概率序列
    """
    net_profit_abs = net_profit.abs().replace(0, np.nan)
    return safe_divide((operating_cash_flow - net_profit).abs(), net_profit_abs)


def calc_cfo_to_net_profit(operating_cash_flow: pd.Series, net_profit: pd.Series, clip_range: tuple[float, float] = (-5, 5)) -> pd.Series:
    """CFO/净利润: 现金流支撑度

    Args:
        operating_cash_flow: 经营现金流
        net_profit: 净利润
        clip_range: 截断范围，防止极端值

    Returns:
        CFO/净利润序列
    """
    net_profit_safe = net_profit.replace(0, np.nan)
    ratio = safe_divide(operating_cash_flow, net_profit_safe)
    return ratio.clip(*clip_range)


def calc_earnings_stability(net_profit_std: pd.Series, net_profit_mean: pd.Series, max_cv: float = 10.0) -> pd.Series:
    """盈利稳定性: 1/(1+CV)，CV为变异系数

    用近8季净利变异系数(CV)的变换，CV越小盈利越稳定。
    1/(1+CV)映射: CV=0→1(最稳定), CV→∞→0(极不稳定)

    Args:
        net_profit_std: 净利润标准差（多期）
        net_profit_mean: 净利润均值（多期）
        max_cv: CV最大值截断

    Returns:
        盈利稳定性序列
    """
    mean_abs = net_profit_mean.abs().replace(0, np.nan)
    cv = safe_divide(net_profit_std, mean_abs).clip(0, max_cv)
    return 1 / (1 + cv)


# ==================== 风险惩罚因子 ====================


def calc_goodwill_ratio(goodwill: pd.Series, total_equity: pd.Series) -> pd.Series:
    """商誉/净资产比率

    高商誉比=高并购溢价，A股商誉减值是年报季重大风险。

    Args:
        goodwill: 商誉
        total_equity: 净资产

    Returns:
        商誉比率序列
    """
    return safe_divide(goodwill, total_equity)


# ==================== 因子交互项 ====================


def calc_value_quality_interaction(ep_ttm: pd.Series, roe: pd.Series) -> pd.Series:
    """价值×质量交互项: EP × ROE

    低估值+高盈利质量的股票，即"便宜且优秀"的GARP策略内核。

    Args:
        ep_ttm: 市盈率倒数
        roe: 净资产收益率

    Returns:
        价值质量交互项序列
    """
    return ep_ttm * roe


def calc_size_momentum_interaction(market_cap: pd.Series, momentum: pd.Series) -> pd.Series:
    """规模×动量交互项: log(市值) × 动量

    捕捉大盘股动量效应，用log消除市值量纲差异。

    Args:
        market_cap: 总市值
        momentum: 动量因子值

    Returns:
        规模动量交互项序列
    """
    return np.log(market_cap) * momentum


# ==================== 北向资金因子 ====================


def calc_north_net_buy_ratio(north_net_buy: pd.Series, daily_volume: pd.Series) -> pd.Series:
    """北向净买入占比: 北向净买入/日成交量

    衡量外资对个股的短期关注度。

    Args:
        north_net_buy: 北向净买入额
        daily_volume: 日成交量

    Returns:
        北向净买入占比序列
    """
    return safe_divide(north_net_buy, daily_volume)


def calc_north_holding_change(north_holding: pd.Series, period: int = 5) -> pd.Series:
    """北向持仓变化率

    Args:
        north_holding: 北向持仓量
        period: 回看天数

    Returns:
        北向持仓变化率序列
    """
    return north_holding.pct_change(period)


# ==================== 微观结构因子 ====================


def calc_large_order_ratio(large_order_volume: pd.Series, super_large_order_volume: pd.Series, total_volume: pd.Series) -> pd.Series:
    """大单成交占比: (大单+超大单)/总成交量

    Args:
        large_order_volume: 大单成交量
        super_large_order_volume: 超大单成交量
        total_volume: 总成交量

    Returns:
        大单成交占比序列
    """
    smart_money_vol = large_order_volume.fillna(0) + super_large_order_volume.fillna(0)
    return safe_divide(smart_money_vol, total_volume)


def calc_overnight_return(open_price: pd.Series, prev_close: pd.Series) -> pd.Series:
    """隔夜收益率: 今日开盘/昨收 - 1

    反映集合竞价和隔夜信息，A股隔夜收益有显著反转效应。

    Args:
        open_price: 开盘价
        prev_close: 前一日收盘价

    Returns:
        隔夜收益率序列
    """
    return safe_divide(open_price, prev_close) - 1


def calc_intraday_return(close: pd.Series, open_price: pd.Series) -> pd.Series:
    """日内收益率: 收盘/开盘 - 1

    Args:
        close: 收盘价
        open_price: 开盘价

    Returns:
        日内收益率序列
    """
    return safe_divide(close, open_price) - 1


def calc_vpin(abs_return: pd.Series, volume_ratio: pd.Series) -> pd.Series:
    """VPIN: 量价交互的知情交易概率指标

    |收益率| × 相对成交量，成交量放大+价格大幅变动=疑似知情交易。

    Args:
        abs_return: 绝对收益率
        volume_ratio: 相对成交量（当前成交量/均值）

    Returns:
        VPIN序列
    """
    return abs_return * volume_ratio


# ==================== 技术指标因子 ====================


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI相对强弱指标 (Wilder平滑法)

    Args:
        close: 收盘价序列
        period: 周期（默认14）

    Returns:
        RSI序列（0-100）
    """
    if len(close) < period + 1:
        return pd.Series(np.nan, index=close.index)

    price_diff = close.diff()
    gain = price_diff.clip(lower=0)
    loss = (-price_diff).clip(lower=0)

    # Wilder平滑: EMA with alpha=1/period
    wilder_alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=wilder_alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=wilder_alpha, adjust=False).mean()

    # 处理avg_loss为0的情况
    rs = pd.Series(np.nan, index=close.index)
    mask_zero_loss = (avg_loss == 0) & (avg_gain > 0)
    mask_normal = avg_loss > 0

    rs[mask_zero_loss] = np.inf  # 当loss=0且gain>0时，RS=无穷大，RSI=100
    rs[mask_normal] = avg_gain[mask_normal] / avg_loss[mask_normal]

    rsi = pd.Series(np.nan, index=close.index)
    rsi[mask_zero_loss] = 100.0
    rsi[mask_normal] = 100 - (100 / (1 + rs[mask_normal]))

    return rsi


def calc_bollinger_position(close: pd.Series, period: int = 20, num_std: float = 2.0) -> pd.Series:
    """布林带位置: (价格-中轨)/(2×标准差)

    标准化到[-1,1]，0.5=中轨，1=上轨2倍标准差。

    Args:
        close: 收盘价序列
        period: 移动平均周期
        num_std: 标准差倍数

    Returns:
        布林带位置序列（-1到1）
    """
    if len(close) < period:
        return pd.Series(np.nan, index=close.index)

    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    position = safe_divide(close - ma, num_std * std)
    return position.clip(-1, 1)


def calc_macd_signal(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    """MACD信号: (DIF-DEA)/close×100

    除以收盘价做归一化处理，乘100放大到百分比量级。

    Args:
        close: 收盘价序列
        fast: 快线周期
        slow: 慢线周期
        signal: 信号线周期

    Returns:
        MACD信号序列
    """
    if len(close) < slow + signal:
        return pd.Series(np.nan, index=close.index)

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()

    return safe_divide(dif - dea, close) * 100


def calc_obv_ratio(close: pd.Series, volume: pd.Series, period: int = 20, min_periods: int = 10) -> pd.Series:
    """OBV能量潮比率: OBV/20日OBV均值 - 1

    衡量成交量趋势强度。

    Args:
        close: 收盘价序列
        volume: 成交量序列
        period: 移动平均周期
        min_periods: 最小有效天数

    Returns:
        OBV比率序列（截断到[-3,3]）
    """
    if len(close) < period:
        return pd.Series(np.nan, index=close.index)

    daily_ret = close.pct_change()
    direction = np.sign(daily_ret).fillna(0)
    obv = (direction * volume).cumsum()
    obv_ma = obv.rolling(period, min_periods=min_periods).mean()

    ratio = safe_divide(obv, obv_ma) - 1
    return ratio.clip(-3, 3)


# ==================== 分析师因子 ====================


def calc_eps_revision(current_eps: pd.Series, prev_eps: pd.Series) -> pd.Series:
    """EPS修正幅度: (当前EPS - 前期EPS) / |前期EPS|

    Args:
        current_eps: 当前一致预期EPS
        prev_eps: 前期一致预期EPS（如1个月前）

    Returns:
        EPS修正幅度序列
    """
    return safe_divide(current_eps - prev_eps, prev_eps.abs())


def calc_rating_upgrade_ratio(current_rating: pd.Series, prev_rating: pd.Series) -> pd.Series:
    """评级上调比例: (前期评级 - 当前评级) / |前期评级|

    评级越低越好(1=强烈推荐, 5=卖出)，所以rating下降=上调。

    Args:
        current_rating: 当前平均评级
        prev_rating: 前期平均评级

    Returns:
        评级上调比例序列
    """
    return safe_divide(prev_rating - current_rating, prev_rating.abs())


def calc_earnings_surprise(actual_eps: pd.Series, expected_eps: pd.Series) -> pd.Series:
    """业绩超预期: (实际EPS - 预期EPS) / |预期EPS|

    Args:
        actual_eps: 实际EPS
        expected_eps: 预期EPS

    Returns:
        业绩超预期序列
    """
    return safe_divide(actual_eps - expected_eps, expected_eps.abs())


# ==================== A股特色因子 ====================


def calc_limit_up_down_ratio(pct_chg: pd.Series, limit_pct: float = 10.0, tolerance: float = 0.01) -> tuple[pd.Series, pd.Series]:
    """涨跌停占比: 判断是否涨停/跌停

    Args:
        pct_chg: 涨跌幅（百分比形式，如9.9表示9.9%）
        limit_pct: 涨跌停限制（默认10%）
        tolerance: 容差（默认0.01%）

    Returns:
        (涨停标记, 跌停标记) 元组
    """
    is_limit_up = (pct_chg >= limit_pct - tolerance).astype(float)
    is_limit_down = (pct_chg <= -(limit_pct - tolerance)).astype(float)
    return is_limit_up, is_limit_down


def calc_ipo_age(list_date: pd.Series, trade_date: pd.Series) -> pd.Series:
    """IPO年龄: (交易日期 - 上市日期) / 365.25

    Args:
        list_date: 上市日期
        trade_date: 交易日期

    Returns:
        IPO年龄序列（年）
    """
    list_dt = pd.to_datetime(list_date)
    trade_dt = pd.to_datetime(trade_date)
    age = (trade_dt - list_dt).dt.days / 365.25
    return age.clip(lower=0)


# ==================== 聪明钱因子 ====================


def calc_smart_money_ratio(large_order_volume: pd.Series, super_large_order_volume: pd.Series, total_volume: pd.Series) -> pd.Series:
    """聪明钱比率: (大单+超大单)/总成交量

    大单占比上升=聪明钱入场。

    Args:
        large_order_volume: 大单成交量
        super_large_order_volume: 超大单成交量
        total_volume: 总成交量

    Returns:
        聪明钱比率序列
    """
    smart_vol = large_order_volume.fillna(0) + super_large_order_volume.fillna(0)
    return safe_divide(smart_vol, total_volume)


def calc_margin_signal(margin_balance: pd.Series, period: int = 5) -> pd.Series:
    """融资融券信号: 融资余额变化率

    Args:
        margin_balance: 融资余额
        period: 回看天数

    Returns:
        融资余额变化率序列
    """
    return margin_balance.pct_change(period)
