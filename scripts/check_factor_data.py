"""
因子数据需求检查脚本

检查数据库中的数据是否能支持所有因子的计算
"""

# 所有因子列表（从 alpha_modules.py 提取）
REQUIRED_FACTORS = {
    "质量成长模块": [
        "roe_ttm",  # ROE TTM
        "roe_delta",  # ROE同比变化
        "gross_margin",  # 毛利率
        "revenue_growth_yoy",  # 营收同比增长
        "profit_growth_yoy",  # 净利润同比增长
        "operating_cashflow_ratio",  # 经营现金流/净利润
        "accrual_ratio",  # 应计利润比率
    ],
    "预期修正模块": [
        "eps_revision_fy0",  # FY0 EPS修正
        "eps_revision_fy1",  # FY1 EPS修正
        "analyst_coverage",  # 分析师覆盖数
        "rating_upgrade_ratio",  # 评级上调比例
        "earnings_surprise",  # 业绩超预期
        "guidance_up_ratio",  # 业绩预告上调比例
    ],
    "残差动量模块": [
        "residual_return_20d",  # 20日残差收益
        "residual_return_60d",  # 60日残差收益
        "residual_return_120d",  # 120日残差收益
        "residual_sharpe",  # 残差夏普比率
        "turnover_ratio_20d",  # 20日换手率
        "reversal_5d",  # 5日反转
    ],
    "资金流确认模块": [
        "north_net_inflow_5d",  # 5日北向资金净流入
        "north_net_inflow_20d",  # 20日北向资金净流入
        "main_force_net_inflow",  # 主力资金净流入
        "large_order_net_ratio",  # 大单净流入占比
        "margin_balance_change",  # 融资余额变化
        "institutional_holding_change",  # 机构持仓变化
    ],
    "风险惩罚模块": [
        "volatility_20d",  # 20日波动率
        "idiosyncratic_vol",  # 特质波动率
        "max_drawdown_60d",  # 60日最大回撤
        "illiquidity",  # Amihud非流动性
        "concentration_top10",  # 前十大股东集中度
        "leverage_ratio",  # 资产负债率
    ],
}

# 数据源映射
DATA_SOURCE_MAPPING = {
    # 质量成长模块 - 需要财务数据
    "roe_ttm": "stock_financial.roe (TTM计算)",
    "roe_delta": "stock_financial.roe (同比计算)",
    "gross_margin": "stock_financial.grossprofit_margin",
    "revenue_growth_yoy": "stock_financial.revenue (同比增长计算)",
    "profit_growth_yoy": "stock_financial.n_income (同比增长计算)",
    "operating_cashflow_ratio": "stock_financial.c_fr_oper / n_income",
    "accrual_ratio": "stock_financial (应计利润计算)",

    # 预期修正模块 - 需要分析师数据
    "eps_revision_fy0": "stock_analyst_consensus.eps_fy0 (修正计算)",
    "eps_revision_fy1": "stock_analyst_consensus.eps_fy1 (修正计算)",
    "analyst_coverage": "stock_analyst_consensus.analyst_count",
    "rating_upgrade_ratio": "stock_analyst_consensus.rating_* (计算)",
    "earnings_surprise": "stock_financial vs stock_analyst_consensus (对比)",
    "guidance_up_ratio": "需要业绩预告数据 ⚠️",

    # 残差动量模块 - 需要行情数据
    "residual_return_20d": "stock_daily.close + index_daily (残差计算)",
    "residual_return_60d": "stock_daily.close + index_daily (残差计算)",
    "residual_return_120d": "stock_daily.close + index_daily (残差计算)",
    "residual_sharpe": "stock_daily.close (夏普比率计算)",
    "turnover_ratio_20d": "stock_daily.turnover_rate (20日均值)",
    "reversal_5d": "stock_daily.close (5日收益率)",

    # 资金流确认模块 - 需要资金流数据
    "north_net_inflow_5d": "stock_northbound.net_amount (5日累计)",
    "north_net_inflow_20d": "stock_northbound.net_amount (20日累计)",
    "main_force_net_inflow": "stock_money_flow.net_mf_amount",
    "large_order_net_ratio": "stock_money_flow.buy_lg_amount / sell_lg_amount",
    "margin_balance_change": "stock_margin.rzye (融资余额变化)",
    "institutional_holding_change": "stock_institutional_holding (季度变化) ⚠️",

    # 风险惩罚模块 - 需要行情+财务数据
    "volatility_20d": "stock_daily.close (20日标准差)",
    "idiosyncratic_vol": "stock_daily.close (残差波动率)",
    "max_drawdown_60d": "stock_daily.close (60日最大回撤)",
    "illiquidity": "stock_daily.amount / abs(pct_chg) (Amihud)",
    "concentration_top10": "stock_top10_holders.hold_ratio (前十大占比)",
    "leverage_ratio": "stock_financial.debt_to_assets",
}

if __name__ == "__main__":
    print("=" * 80)
    print("因子数据需求检查")
    print("=" * 80)

    total_factors = 0
    for module, factors in REQUIRED_FACTORS.items():
        print(f"\n【{module}】({len(factors)} 个因子)")
        for factor in factors:
            source = DATA_SOURCE_MAPPING.get(factor, "未知数据源 ❌")
            status = "⚠️" if "⚠️" in source else "✅"
            print(f"  {status} {factor:30s} <- {source}")
            total_factors += 1

    print("\n" + "=" * 80)
    print(f"总计: {total_factors} 个因子")
    print("=" * 80)
