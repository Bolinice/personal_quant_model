"""
风险计算纯函数 — 无副作用、无 IO、无数据库依赖

所有函数接收 numpy/pandas 数据结构，返回计算结果。
"""

import numpy as np
import pandas as pd


def calc_ic(factor_values: pd.Series, return_values: pd.Series) -> float:
    """计算因子IC (Pearson相关系数)

    Args:
        factor_values: 横截面因子值
        return_values: 对应的前瞻收益

    Returns:
        IC值，无效时返回 NaN
    """
    valid = factor_values.notna() & return_values.notna()
    if valid.sum() < 10:
        return np.nan
    return factor_values[valid].corr(return_values[valid])


def calc_rank_ic(factor_values: pd.Series, return_values: pd.Series) -> float:
    """计算因子RankIC (Spearman秩相关系数)

    Args:
        factor_values: 横截面因子值
        return_values: 对应的前瞻收益

    Returns:
        RankIC值，无效时返回 NaN
    """
    valid = factor_values.notna() & return_values.notna()
    if valid.sum() < 10:
        return np.nan
    return factor_values[valid].rank().corr(return_values[valid].rank())


def calc_rolling_ic(
    factor_df: pd.DataFrame,
    return_df: pd.DataFrame,
    factor_col: str,
    return_col: str,
    window: int = 20,
) -> pd.Series:
    """计算滚动IC

    Args:
        factor_df: 含 trade_date, factor_col 的 DataFrame
        return_df: 含 trade_date, return_col 的 DataFrame
        factor_col: 因子列名
        return_col: 收益列名
        window: 滚动窗口

    Returns:
        滚动IC序列
    """
    merged = pd.merge(factor_df[["trade_date", factor_col]], return_df[["trade_date", return_col]], on="trade_date")
    merged["ic"] = merged.apply(lambda row: calc_ic(row[factor_col], row[return_col]) if isinstance(row[factor_col], pd.Series) else np.nan, axis=1)
    return merged["ic"].rolling(window).mean()


def calc_max_drawdown(nav: pd.Series) -> float:
    """计算最大回撤

    Args:
        nav: 净值序列

    Returns:
        最大回撤（正值，如 0.15 表示 15% 回撤）
    """
    cummax = nav.cummax()
    drawdown = (cummax - nav) / cummax
    return drawdown.max()


def calc_sharpe_ratio(returns: pd.Series, annual_factor: int = 252) -> float:
    """计算Sharpe比率

    Args:
        returns: 日收益率序列
        annual_factor: 年化因子（默认252个交易日）

    Returns:
        年化Sharpe比率
    """
    if returns.std() == 0 or returns.std() is np.nan:
        return 0.0
    return returns.mean() / returns.std() * np.sqrt(annual_factor)


def calc_calmar_ratio(returns: pd.Series, annual_factor: int = 252) -> float:
    """计算Calmar比率（年化收益/最大回撤）

    Args:
        returns: 日收益率序列
        annual_factor: 年化因子

    Returns:
        Calmar比率
    """
    nav = (1 + returns).cumprod()
    mdd = calc_max_drawdown(nav)
    if mdd == 0:
        return 0.0
    annual_return = (1 + returns.mean()) ** annual_factor - 1
    return annual_return / mdd


def calc_sortino_ratio(returns: pd.Series, annual_factor: int = 252) -> float:
    """计算Sortino比率（仅惩罚下行波动）

    Args:
        returns: 日收益率序列
        annual_factor: 年化因子

    Returns:
        年化Sortino比率
    """
    downside = returns[returns < 0]
    if downside.empty or downside.std() == 0:
        return 0.0
    return returns.mean() / downside.std() * np.sqrt(annual_factor)


def calc_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """计算VaR (Value at Risk)

    Args:
        returns: 日收益率序列
        confidence: 置信水平

    Returns:
        VaR值（负值，如 -0.02 表示 2% 损失）
    """
    return returns.quantile(1 - confidence)


def calc_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """计算CVaR (Conditional VaR / Expected Shortfall)

    Args:
        returns: 日收益率序列
        confidence: 置信水平

    Returns:
        CVaR值
    """
    var = calc_var(returns, confidence)
    return returns[returns <= var].mean()


def calc_psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    """计算PSI (Population Stability Index)

    衡量两个分布的稳定性。PSI < 0.1 稳定，0.1-0.25 轻微变化，> 0.25 显著变化。

    Args:
        reference: 参考分布
        current: 当前分布
        bins: 分箱数

    Returns:
        PSI值
    """
    _, edges = np.histogram(reference, bins=bins)
    ref_hist = np.histogram(reference, bins=edges)[0].astype(float)
    cur_hist = np.histogram(current, bins=edges)[0].astype(float)

    # 避免除零
    ref_hist = np.where(ref_hist == 0, 0.0001, ref_hist)
    cur_hist = np.where(cur_hist == 0, 0.0001, cur_hist)

    ref_pct = ref_hist / ref_hist.sum()
    cur_pct = cur_hist / cur_hist.sum()

    psi = np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct))
    return psi
