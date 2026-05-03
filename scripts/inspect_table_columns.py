"""
检查数据库表的实际列名
"""

from sqlalchemy import inspect
from app.db.base import engine

TABLES_TO_INSPECT = [
    "stock_daily",
    "stock_analyst_consensus",
    "stock_northbound",
    "stock_money_flow",
    "stock_margin",
    "stock_institutional_holding",
    "index_daily",
]

def inspect_tables():
    """检查表的实际列名"""
    inspector = inspect(engine)

    for table_name in TABLES_TO_INSPECT:
        print(f"\n{'='*80}")
        print(f"表: {table_name}")
        print('='*80)

        try:
            columns = inspector.get_columns(table_name)
            print(f"列数: {len(columns)}\n")

            for col in columns:
                col_type = str(col['type'])
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                print(f"  {col['name']:<30} {col_type:<20} {nullable}")

        except Exception as e:
            print(f"  ❌ 错误: {e}")

if __name__ == "__main__":
    inspect_tables()
