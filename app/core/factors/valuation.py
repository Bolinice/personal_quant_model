"""
价值因子计算模块
================
包含:
- EP (盈利收益率)
- BP (账面市值比)
- SP (营收市值比)
- DP (股息率)
- CFP (现金流市值比)
"""

import pandas as pd
import numpy as np


def _safe_divide(numerator, denominator, eps: float = 1e-8):
    """安全除法"""
    denom = np.where(np.abs(denominator) < eps, np.nan, denominator)
    return numerator / denom


def calc_valuation_factors(
    price_df: pd.DataFrame,
    financial_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    计算价值因子

    Args:
        price_df: 价格数据，需包含 close, total_mv 等字段
        financial_df: 财务数据，需包含 net_profit, total_assets, revenue, div_cash, cash_flow 等字段

    Returns:
        价值因子DataFrame
    """
    factors = pd.DataFrame(index=price_df.index)

    # 确保financial_df的索引是ts_code
    if "ts_code" in financial_df.columns:
        financial_df = financial_df.set_index("ts_code")

    # EP_TTM: 盈利收益率 = 净利润(TTM) / 总市值
    if "net_profit" in financial_df.columns and "total_mv" in price_df.columns:
        net_profit = financial_df["net_profit"].reindex(price_df.index)
        total_mv = price_df["total_mv"]
        factors["ep_ttm"] = _safe_divide(net_profit, total_mv)

    # BP: 账面市值比 = 净资产 / 总市值
    if "total_assets" in financial_df.columns and "total_mv" in price_df.columns:
        total_assets = financial_df["total_assets"].reindex(price_df.index)
        total_mv = price_df["total_mv"]
        factors["bp"] = _safe_divide(total_assets, total_mv)

    # SP_TTM: 营收市值比 = 营业收入(TTM) / 总市值
    if "revenue" in financial_df.columns and "total_mv" in price_df.columns:
        revenue = financial_df["revenue"].reindex(price_df.index)
        total_mv = price_df["total_mv"]
        factors["sp_ttm"] = _safe_divide(revenue, total_mv)

    # DP: 股息率 = 现金分红 / 总市值
    if "div_cash" in financial_df.columns and "total_mv" in price_df.columns:
        div_cash = financial_df["div_cash"].reindex(price_df.index)
        total_mv = price_df["total_mv"]
        factors["dp"] = _safe_divide(div_cash, total_mv)

    # CFP_TTM: 现金流市值比 = 经营现金流(TTM) / 总市值
    if "cash_flow" in financial_df.columns and "total_mv" in price_df.columns:
        cash_flow = financial_df["cash_flow"].reindex(price_df.index)
        total_mv = price_df["total_mv"]
        factors["cfp_ttm"] = _safe_divide(cash_flow, total_mv)

    return factors
