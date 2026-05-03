"""
质量因子计算模块
================
包含:
- ROE (净资产收益率)
- ROA (总资产收益率)
- Gross Profit Margin (毛利率)
- Net Profit Margin (净利率)
- Current Ratio (流动比率)
"""

import pandas as pd
import numpy as np


def _safe_divide(numerator, denominator, eps: float = 1e-8):
    """安全除法"""
    denom = np.where(np.abs(denominator) < eps, np.nan, denominator)
    return numerator / denom


def calc_quality_factors(financial_df: pd.DataFrame) -> pd.DataFrame:
    """
    计算质量因子

    Args:
        financial_df: 财务数据，需包含相关财务指标

    Returns:
        质量因子DataFrame
    """
    # 确保financial_df的索引是ts_code
    if "ts_code" in financial_df.columns:
        financial_df = financial_df.set_index("ts_code")

    factors = pd.DataFrame(index=financial_df.index)

    # ROE: 净资产收益率 = 净利润 / 净资产
    if "net_profit" in financial_df.columns and "total_equity" in financial_df.columns:
        net_profit = financial_df["net_profit"]
        total_equity = financial_df["total_equity"]
        factors["roe"] = _safe_divide(net_profit, total_equity)
    elif "roe" in financial_df.columns:
        # 如果数据源已提供ROE
        factors["roe"] = financial_df["roe"]

    # ROA: 总资产收益率 = 净利润 / 总资产
    if "net_profit" in financial_df.columns and "total_assets" in financial_df.columns:
        net_profit = financial_df["net_profit"]
        total_assets = financial_df["total_assets"]
        factors["roa"] = _safe_divide(net_profit, total_assets)
    elif "roa" in financial_df.columns:
        factors["roa"] = financial_df["roa"]

    # Gross Profit Margin: 毛利率 = (营业收入 - 营业成本) / 营业收入
    if "revenue" in financial_df.columns and "operating_cost" in financial_df.columns:
        revenue = financial_df["revenue"]
        operating_cost = financial_df["operating_cost"]
        factors["gross_profit_margin"] = _safe_divide(revenue - operating_cost, revenue)
    elif "gross_profit_margin" in financial_df.columns:
        factors["gross_profit_margin"] = financial_df["gross_profit_margin"]

    # Net Profit Margin: 净利率 = 净利润 / 营业收入
    if "net_profit" in financial_df.columns and "revenue" in financial_df.columns:
        net_profit = financial_df["net_profit"]
        revenue = financial_df["revenue"]
        factors["net_profit_margin"] = _safe_divide(net_profit, revenue)
    elif "net_profit_margin" in financial_df.columns:
        factors["net_profit_margin"] = financial_df["net_profit_margin"]

    # Current Ratio: 流动比率 = 流动资产 / 流动负债
    if "current_assets" in financial_df.columns and "current_liabilities" in financial_df.columns:
        current_assets = financial_df["current_assets"]
        current_liabilities = financial_df["current_liabilities"]
        factors["current_ratio"] = _safe_divide(current_assets, current_liabilities)
    elif "current_ratio" in financial_df.columns:
        factors["current_ratio"] = financial_df["current_ratio"]

    return factors
