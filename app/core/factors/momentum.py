"""
动量因子计算模块
================
包含:
- Ret 1M Reversal (1个月反转)
- Ret 3M Skip1 (跳过最近1月的3月动量)
- Ret 6M Skip1 (跳过最近1月的6月动量)
- Ret 12M Skip1 (跳过最近1月的12月动量)
- Residual Return (残差收益率动量)
"""

import pandas as pd
import numpy as np
from typing import Optional
from app.core.logging import logger


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


def calc_residual_returns(
    returns: pd.DataFrame,
    style_factors: pd.DataFrame,
    lookback_window: int = 60,
    min_periods: int = 30
) -> pd.DataFrame:
    """
    计算残差收益率（剥离风格因子后的纯alpha动量）

    残差收益率 = 实际收益率 - 风格因子回归预测收益率

    计算流程:
    1. 对每只股票，使用历史窗口进行时序回归: r_t = β * f_t + ε_t
       其中 r_t 是股票收益率，f_t 是风格因子收益率（size, value, momentum等）
    2. 计算残差 ε_t = r_t - β * f_t
    3. 累积残差得到残差收益率

    Args:
        returns: 股票收益率，shape=(T, N)，index=日期，columns=股票代码
        style_factors: 风格因子暴露，shape=(T, N, K)的MultiIndex DataFrame
                      level 0=日期，level 1=股票代码，columns=因子名
        lookback_window: 回归窗口长度（交易日）
        min_periods: 最小有效样本数

    Returns:
        残差收益率DataFrame，shape=(T, N)

    Example:
        >>> returns = pd.DataFrame(...)  # 日收益率
        >>> style_factors = pd.DataFrame(...)  # 风格因子暴露
        >>> residual_ret = calc_residual_returns(returns, style_factors, lookback_window=60)
    """
    if returns.empty or style_factors.empty:
        logger.warning("calc_residual_returns: empty input data")
        return pd.DataFrame()

    # 确保索引对齐
    common_dates = returns.index.intersection(style_factors.index.get_level_values(0).unique())
    if len(common_dates) < min_periods:
        logger.warning(f"calc_residual_returns: insufficient common dates ({len(common_dates)} < {min_periods})")
        return pd.DataFrame(index=returns.index, columns=returns.columns)

    # 初始化结果
    residuals = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)

    # 对每只股票进行时序回归
    for stock_code in returns.columns:
        if stock_code not in style_factors.index.get_level_values(1):
            continue

        try:
            # 提取该股票的收益率和因子暴露
            stock_returns = returns[stock_code].dropna()
            stock_factors = style_factors.xs(stock_code, level=1, drop_level=True)

            # 对齐日期
            common_idx = stock_returns.index.intersection(stock_factors.index)
            if len(common_idx) < min_periods:
                continue

            stock_returns = stock_returns.loc[common_idx]
            stock_factors = stock_factors.loc[common_idx]

            # 滚动窗口回归
            for i in range(lookback_window, len(common_idx)):
                current_date = common_idx[i]
                window_start = max(0, i - lookback_window)
                window_end = i

                # 回归窗口数据
                y_train = stock_returns.iloc[window_start:window_end].values
                X_train = stock_factors.iloc[window_start:window_end].values

                # 检查有效样本数
                valid_mask = ~(np.isnan(y_train) | np.any(np.isnan(X_train), axis=1))
                if valid_mask.sum() < min_periods:
                    continue

                y_train_valid = y_train[valid_mask]
                X_train_valid = X_train[valid_mask]

                # OLS回归: r = β * f + ε
                try:
                    # 添加截距项
                    X_with_const = np.column_stack([np.ones(len(X_train_valid)), X_train_valid])
                    beta = np.linalg.lstsq(X_with_const, y_train_valid, rcond=None)[0]

                    # 计算当前时点的残差
                    y_current = stock_returns.iloc[i]
                    X_current = stock_factors.iloc[i].values

                    if not (np.isnan(y_current) or np.any(np.isnan(X_current))):
                        X_current_with_const = np.concatenate([[1], X_current])
                        predicted = X_current_with_const @ beta
                        residual = y_current - predicted
                        residuals.loc[current_date, stock_code] = residual

                except np.linalg.LinAlgError:
                    # 回归失败，跳过
                    continue

        except Exception as e:
            logger.warning(f"calc_residual_returns: failed for {stock_code}: {str(e)}")
            continue

    return residuals


def calc_residual_momentum_factors(
    returns: pd.DataFrame,
    style_factors: pd.DataFrame,
    windows: list[int] = [20, 60, 120]
) -> pd.DataFrame:
    """
    计算残差动量因子（多周期）

    Args:
        returns: 股票日收益率，shape=(T, N)
        style_factors: 风格因子暴露，MultiIndex DataFrame
        windows: 动量计算窗口列表（交易日）

    Returns:
        残差动量因子DataFrame，columns=['residual_return_20d', 'residual_return_60d', ...]
    """
    # 计算残差收益率
    residual_returns = calc_residual_returns(returns, style_factors, lookback_window=60)

    if residual_returns.empty:
        return pd.DataFrame()

    # 计算不同周期的累积残差收益率
    factors = pd.DataFrame(index=residual_returns.index)

    for window in windows:
        # 累积残差收益率 = sum(residual_return[t-window:t])
        cumulative_residual = residual_returns.rolling(window=window, min_periods=int(window * 0.5)).sum()
        factors[f'residual_return_{window}d'] = cumulative_residual.mean(axis=1)

    # 计算残差夏普比率（20日窗口）
    residual_mean = residual_returns.rolling(window=20, min_periods=10).mean()
    residual_std = residual_returns.rolling(window=20, min_periods=10).std()
    residual_sharpe = residual_mean / (residual_std + 1e-8)  # 避免除零
    factors['residual_sharpe'] = residual_sharpe.mean(axis=1)

    return factors

