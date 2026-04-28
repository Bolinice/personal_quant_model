"""
组合优化纯函数 — 无副作用、无 IO、无数据库依赖

所有函数接收权重/约束参数，返回优化后的权重。
"""

import numpy as np
import pandas as pd


def equal_weight(codes: list[str]) -> dict[str, float]:
    """等权组合

    Args:
        codes: 股票代码列表

    Returns:
        等权权重字典
    """
    n = len(codes)
    if n == 0:
        return {}
    w = 1.0 / n
    return {code: w for code in codes}


def ic_weighted(ic_values: dict[str, float], min_weight: float = 0.01) -> dict[str, float]:
    """IC加权组合

    权重 ∝ max(IC, 0)，负IC因子权重设为最小值。

    Args:
        ic_values: 因子名 → IC值 的映射
        min_weight: 最小权重（避免零权重）

    Returns:
        归一化权重字典
    """
    if not ic_values:
        return {}

    raw_weights = {k: max(v, 0) + min_weight for k, v in ic_values.items()}
    total = sum(raw_weights.values())
    if total == 0:
        return equal_weight(list(ic_values.keys()))

    return {k: v / total for k, v in raw_weights.items()}


def apply_position_limits(
    weights: dict[str, float],
    max_single: float = 0.10,
    max_sector: float = 0.40,
    sector_map: dict[str, str] | None = None,
) -> dict[str, float]:
    """应用持仓限制并重新归一化

    Args:
        weights: 原始权重
        max_single: 单股最大权重
        max_sector: 单行业最大权重
        sector_map: 股票 → 行业 映射

    Returns:
        限制后并归一化的权重
    """
    if not weights:
        return {}

    # 单股权重限制
    result = {k: min(v, max_single) for k, v in weights.items()}

    # 行业集中度限制
    if sector_map:
        sector_weights: dict[str, float] = {}
        for code, weight in result.items():
            sector = sector_map.get(code, "unknown")
            sector_weights[sector] = sector_weights.get(sector, 0) + weight

        for sector, sw in sector_weights.items():
            if sw > max_sector:
                # 按比例收缩该行业所有股票权重
                shrink = max_sector / sw
                for code in result:
                    if sector_map.get(code, "unknown") == sector:
                        result[code] *= shrink

    # 归一化
    total = sum(result.values())
    if total > 0:
        result = {k: v / total for k, v in result.items()}

    return result


def apply_turnover_constraint(
    new_weights: dict[str, float],
    old_weights: dict[str, float],
    max_turnover: float = 0.30,
) -> dict[str, float]:
    """换手率约束: 限制单次调仓的换手率

    当换手率超过阈值时，按比例向旧权重收缩。

    Args:
        new_weights: 目标权重
        old_weights: 当前权重
        max_turnover: 最大换手率

    Returns:
        约束后的权重
    """
    if not new_weights:
        return {}

    all_codes = set(new_weights) | set(old_weights)
    turnover = 0.0
    for code in all_codes:
        turnover += abs(new_weights.get(code, 0) - old_weights.get(code, 0))
    turnover /= 2  # 单边换手率

    if turnover <= max_turnover:
        return new_weights

    # 向旧权重收缩: w = (1-α) * w_old + α * w_new, 使换手率 = max_turnover
    shrink = max_turnover / turnover if turnover > 0 else 0
    result = {}
    for code in all_codes:
        old_w = old_weights.get(code, 0)
        new_w = new_weights.get(code, 0)
        result[code] = (1 - shrink) * old_w + shrink * new_w

    # 归一化
    total = sum(result.values())
    if total > 0:
        result = {k: v / total for k, v in result.items()}

    return result


def apply_lot_size_constraint(
    weights: dict[str, float],
    total_capital: float,
    prices: dict[str, float],
    lot_size: int = 100,
) -> dict[str, float]:
    """交易单位约束: 调整权重使持仓为100股整数倍

    Args:
        weights: 目标权重
        total_capital: 总资金
        prices: 股票 → 当前价格 映射
        lot_size: 最小交易单位（A股=100）

    Returns:
        调整后的权重
    """
    result = {}
    for code, weight in weights.items():
        price = prices.get(code, 0)
        if price <= 0:
            result[code] = 0
            continue

        target_shares = total_capital * weight / price
        actual_shares = int(target_shares / lot_size) * lot_size
        if actual_shares < lot_size:
            result[code] = 0  # 不足一手，放弃
        else:
            result[code] = actual_shares * price / total_capital

    # 归一化
    total = sum(result.values())
    if total > 0:
        result = {k: v / total for k, v in result.items()}

    return result
