"""
数据库表和字段完整性检查

检查数据库中是否存在所需的表和字段
"""

import sys
from sqlalchemy import inspect, text

from app.db.base import engine

# 所需的表和关键字段
REQUIRED_TABLES = {
    "stock_daily": [
        "ts_code", "trade_date", "open", "high", "low", "close",
        "pre_close", "change", "pct_chg", "vol", "amount",
        "turnover_rate", "turnover_rate_f", "volume_ratio"
    ],
    "stock_financial": [
        "ts_code", "ann_date", "end_date",
        "total_revenue", "operating_revenue", "net_profit",
        "revenue_yoy", "net_profit_yoy", "operating_cash_flow",
        "total_assets", "total_equity", "total_liabilities",
        "roe", "roa", "gross_profit_margin", "debt_to_assets",
        "revenue_ttm", "net_profit_ttm", "ocf_ttm"
    ],
    "stock_analyst_consensus": [
        "ts_code", "trade_date",
        "eps_fy0", "eps_fy1", "eps_fy2",
        "analyst_count", "rating_buy", "rating_hold", "rating_sell"
    ],
    "stock_northbound": [
        "ts_code", "trade_date", "net_amount", "buy_amount", "sell_amount"
    ],
    "stock_money_flow": [
        "ts_code", "trade_date",
        "buy_sm_amount", "buy_md_amount", "buy_lg_amount", "buy_elg_amount",
        "sell_sm_amount", "sell_md_amount", "sell_lg_amount", "sell_elg_amount",
        "net_mf_amount"
    ],
    "stock_margin": [
        "ts_code", "trade_date", "rzye", "rqye", "rzmre", "rqmcl"
    ],
    "stock_institutional_holding": [
        "ts_code", "end_date", "hold_ratio", "hold_amount"
    ],
    "stock_top10_holders": [
        "ts_code", "end_date", "holder_name", "hold_ratio"
    ],
    "index_daily": [
        "ts_code", "trade_date", "close", "pct_chg"
    ],
}

def check_database():
    """检查数据库表和字段"""
    print("=" * 80)
    print("数据库表和字段完整性检查")
    print("=" * 80)

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    total_tables = len(REQUIRED_TABLES)
    missing_tables = []
    incomplete_tables = []

    for table_name, required_fields in REQUIRED_TABLES.items():
        print(f"\n【{table_name}】")

        if table_name not in existing_tables:
            print(f"  ❌ 表不存在")
            missing_tables.append(table_name)
            continue

        # 检查字段
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        missing_fields = [f for f in required_fields if f not in columns]

        if missing_fields:
            print(f"  ⚠️ 表存在，但缺少字段:")
            for field in missing_fields:
                print(f"     - {field}")
            incomplete_tables.append(table_name)
        else:
            print(f"  ✅ 表存在，所有必需字段完整 ({len(required_fields)} 个字段)")

        # 检查数据量
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                print(f"     数据量: {count:,} 条")
        except Exception as e:
            print(f"     数据量查询失败: {e}")

    # 总结
    print("\n" + "=" * 80)
    print("检查总结")
    print("=" * 80)
    print(f"总表数: {total_tables}")
    print(f"✅ 完整的表: {total_tables - len(missing_tables) - len(incomplete_tables)}")
    print(f"⚠️ 不完整的表: {len(incomplete_tables)}")
    print(f"❌ 缺失的表: {len(missing_tables)}")

    if missing_tables:
        print(f"\n缺失的表: {', '.join(missing_tables)}")

    if incomplete_tables:
        print(f"\n不完整的表: {', '.join(incomplete_tables)}")

    print("=" * 80)

    # 返回状态码
    if missing_tables or incomplete_tables:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(check_database())
