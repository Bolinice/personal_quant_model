"""
成长因子计算模块
================
包含:
- YoY Revenue (营收同比增长率)
- YoY Net Profit (净利润同比增长率)
- YoY Deduct Net Profit (扣非净利润同比增长率)
- YoY ROE (ROE同比增长率)
"""

import pandas as pd
import numpy as np


def _safe_divide(numerator, denominator, eps: float = 1e-8):
    """安全除法"""
    denom = np.where(np.abs(denominator) < eps, np.nan, denominator)
    return numerator / denom


def calc_growth_factors(financial_df: pd.DataFrame) -> pd.DataFrame:
    """
    计算成长因子

    Args:
        financial_df: 财务数据，需包含 revenue, net_profit, deduct_net_profit, roe 等字段

    Returns:
        成长因子DataFrame
    """
    # 确保financial_df的索引是ts_code
    if "ts_code" in financial_df.columns:
        financial_df = financial_df.set_index("ts_code")

    factors = pd.DataFrame(index=financial_df.index)

    # YoY Revenue: 营收同比增长率
    if "revenue" in financial_df.columns:
        revenue = financial_df["revenue"]
        revenue_yoy = revenue.pct_change(periods=4)  # 假设按季度数据，4个季度=1年
        factors["yoy_revenue"] = revenue_yoy

    # YoY Net Profit: 净利润同比增长率
    if "net_profit" in financial_df.columns:
        net_profit = financial_df["net_profit"]
        net_profit_yoy = net_profit.pct_change(periods=4)
        factors["yoy_net_profit"] = net_profit_yoy

    # YoY Deduct Net Profit: 扣非净利润同比增长率
    if "deduct_net_profit" in financial_df.columns:
        deduct_net_profit = financial_df["deduct_net_profit"]
        deduct_net_profit_yoy = deduct_net_profit.pct_change(periods=4)
        factors["yoy_deduct_net_profit"] = deduct_net_profit_yoy

    # YoY ROE: ROE同比增长率
    if "roe" in financial_df.columns:
        roe = financial_df["roe"]
        roe_yoy = roe.diff(periods=4)  # ROE是比率，用差分而非百分比变化
        factors["yoy_roe"] = roe_yoy

    return factors
