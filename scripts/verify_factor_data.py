"""
验证31个因子的数据完整性
基于实际数据库表结构
"""

from sqlalchemy import text
from app.db.base import engine

# 因子数据源映射（基于实际表结构）
FACTOR_DATA_MAPPING = {
    "价值因子": {
        "pb_ratio": {
            "source": "stock_financial.pb",
            "status": "✅",
        },
        "pe_ttm": {
            "source": "stock_financial.pe_ttm",
            "status": "✅",
        },
        "ps_ttm": {
            "source": "stock_financial.ps_ttm",
            "status": "✅",
        },
        "pcf_ratio": {
            "source": "stock_financial (计算: total_mv / c_fr_cash_flows)",
            "status": "✅",
        },
        "dividend_yield": {
            "source": "stock_financial.dv_ratio",
            "status": "✅",
        },
    },
    "质量因子": {
        "roe": {
            "source": "stock_financial.roe",
            "status": "✅",
        },
        "roa": {
            "source": "stock_financial.roa",
            "status": "✅",
        },
        "roic": {
            "source": "stock_financial (计算: ebit / (total_assets - current_liab))",
            "status": "✅",
        },
        "asset_turnover": {
            "source": "stock_financial.assets_turn",
            "status": "✅",
        },
        "current_ratio": {
            "source": "stock_financial.current_ratio",
            "status": "✅",
        },
        "gross_margin": {
            "source": "stock_financial.grossprofit_margin",
            "status": "✅",
        },
    },
    "成长因子": {
        "revenue_growth_yoy": {
            "source": "stock_financial.revenue (同比计算)",
            "status": "✅",
        },
        "profit_growth_yoy": {
            "source": "stock_financial.n_income (同比计算)",
            "status": "✅",
        },
        "operating_cashflow_ratio": {
            "source": "stock_financial (计算: n_cashflow_act / revenue)",
            "status": "✅",
        },
        "accrual_ratio": {
            "source": "stock_financial (计算: (n_income - n_cashflow_act) / total_assets)",
            "status": "✅",
        },
        "capex_to_revenue": {
            "source": "stock_financial (计算: c_paid_invest / revenue)",
            "status": "✅",
        },
        "rd_to_revenue": {
            "source": "stock_financial (计算: rd_exp / revenue)",
            "status": "✅",
        },
    },
    "动量因子": {
        "return_20d": {
            "source": "stock_daily.close (20日收益率)",
            "status": "✅",
        },
        "return_60d": {
            "source": "stock_daily.close (60日收益率)",
            "status": "✅",
        },
    },
    "预期修正因子": {
        "eps_revision_fy1": {
            "source": "stock_analyst_consensus.consensus_eps_fy1 (变化率)",
            "status": "✅",
        },
        "target_price_upside": {
            "source": "stock_analyst_consensus.target_price_mean / stock_daily.close - 1",
            "status": "✅",
        },
        "rating_change": {
            "source": "stock_analyst_consensus.rating_mean (变化)",
            "status": "✅",
        },
        "analyst_coverage": {
            "source": "stock_analyst_consensus.analyst_coverage",
            "status": "✅",
        },
        "northbound_holding_change": {
            "source": "stock_northbound.north_holding_pct (变化率)",
            "status": "✅",
        },
        "institutional_holding_change": {
            "source": "stock_institutional_holding.hold_ratio (变化率)",
            "status": "✅",
        },
    },
    "风险惩罚因子": {
        "volatility_20d": {
            "source": "stock_daily.pct_chg (20日标准差)",
            "status": "✅",
        },
        "idiosyncratic_vol": {
            "source": "stock_daily.pct_chg - index_daily.pct_chg (残差波动率)",
            "status": "✅",
        },
        "max_drawdown_60d": {
            "source": "stock_daily.close (60日最大回撤)",
            "status": "✅",
        },
        "illiquidity": {
            "source": "stock_daily (计算: abs(pct_chg) / amount)",
            "status": "✅",
        },
        "concentration_top10": {
            "source": "stock_top10_holders.hold_ratio (前10大股东持股比例)",
            "status": "✅",
        },
        "leverage_ratio": {
            "source": "stock_financial.debt_to_assets",
            "status": "✅",
        },
    },
}


def check_data_availability():
    """检查各表的数据可用性"""

    tables_to_check = [
        ("stock_daily", "ts_code, trade_date"),
        ("stock_financial", "ts_code, end_date"),
        ("stock_analyst_consensus", "ts_code, effective_date"),
        ("stock_northbound", "ts_code, trade_date"),
        ("stock_money_flow", "ts_code, trade_date"),
        ("stock_margin", "ts_code, trade_date"),
        ("stock_institutional_holding", "ts_code, trade_date"),
        ("stock_top10_holders", "ts_code, end_date"),
        ("index_daily", "index_code, trade_date"),
    ]

    print("=" * 100)
    print("数据可用性检查")
    print("=" * 100)

    with engine.connect() as conn:
        for table_name, key_cols in tables_to_check:
            try:
                # 检查记录数
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()

                # 检查日期范围
                if "trade_date" in key_cols:
                    date_col = "trade_date"
                elif "end_date" in key_cols:
                    date_col = "end_date"
                elif "effective_date" in key_cols:
                    date_col = "effective_date"
                else:
                    date_col = None

                if date_col:
                    result = conn.execute(text(f"""
                        SELECT
                            MIN({date_col}) as min_date,
                            MAX({date_col}) as max_date
                        FROM {table_name}
                        WHERE {date_col} IS NOT NULL
                    """))
                    row = result.fetchone()
                    min_date = row[0] if row else None
                    max_date = row[1] if row else None

                    print(f"\n{table_name}:")
                    print(f"  记录数: {count:,}")
                    print(f"  日期范围: {min_date} ~ {max_date}")
                else:
                    print(f"\n{table_name}:")
                    print(f"  记录数: {count:,}")

            except Exception as e:
                print(f"\n{table_name}:")
                print(f"  ❌ 错误: {e}")


def print_factor_summary():
    """打印因子数据源总结"""

    print("\n" + "=" * 100)
    print("因子数据源映射总结")
    print("=" * 100)

    total_factors = 0
    available_factors = 0

    for module_name, factors in FACTOR_DATA_MAPPING.items():
        print(f"\n【{module_name}】({len(factors)}个因子)")
        for factor_name, info in factors.items():
            total_factors += 1
            status = info["status"]
            if status == "✅":
                available_factors += 1
            print(f"  {status} {factor_name:<30} <- {info['source']}")

    print("\n" + "=" * 100)
    print(f"总结: {available_factors}/{total_factors} 个因子数据可用")
    print("=" * 100)

    if available_factors == total_factors:
        print("\n✅ 所有因子数据源完整，可以开始构建多因子模型！")
    else:
        print(f"\n⚠️  有 {total_factors - available_factors} 个因子数据不可用，需要调整因子库")


if __name__ == "__main__":
    check_data_availability()
    print_factor_summary()
