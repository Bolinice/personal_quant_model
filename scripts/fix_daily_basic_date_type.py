"""
修复 stock_daily_basic.trade_date 列类型: String(8) → Date

运行方式:
  python scripts/fix_daily_basic_date_type.py

步骤:
1. 添加临时列 trade_date_new (Date类型)
2. 将 String(8) 格式的 trade_date 转换为 Date 写入新列
3. 删除旧列 trade_date
4. 将 trade_date_new 重命名为 trade_date
5. 重建索引
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.db.base import engine


def main():
    with engine.begin() as conn:
        # 检查当前列类型
        result = conn.execute(text("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'stock_daily_basic' AND column_name = 'trade_date'
        """)).fetchone()

        if result is None:
            print("表 stock_daily_basic 不存在，跳过")
            return

        current_type = result[0]
        print(f"当前 trade_date 类型: {current_type}")

        if current_type == "date":
            print("已经是 Date 类型，无需迁移")
            return

        print("开始迁移 trade_date: character varying → date")

        # Step 1: 添加临时列
        print("  [1/5] 添加临时列 trade_date_new...")
        conn.execute(text("""
            ALTER TABLE stock_daily_basic
            ADD COLUMN IF NOT EXISTS trade_date_new DATE
        """))

        # Step 2: 转换数据
        print("  [2/5] 转换数据格式...")
        conn.execute(text("""
            UPDATE stock_daily_basic
            SET trade_date_new = TO_DATE(trade_date, 'YYYYMMDD')
            WHERE trade_date IS NOT NULL AND trade_date_new IS NULL
        """))

        # 检查转换结果
        null_count = conn.execute(text("""
            SELECT COUNT(*) FROM stock_daily_basic
            WHERE trade_date IS NOT NULL AND trade_date_new IS NULL
        """)).fetchone()[0]
        print(f"  未转换行数: {null_count}")

        # Step 3: 删除旧列
        print("  [3/5] 删除旧列 trade_date...")
        conn.execute(text("""
            ALTER TABLE stock_daily_basic DROP COLUMN trade_date
        """))

        # Step 4: 重命名新列
        print("  [4/5] 重命名 trade_date_new → trade_date...")
        conn.execute(text("""
            ALTER TABLE stock_daily_basic RENAME COLUMN trade_date_new TO trade_date
        """))

        # Step 5: 重建索引
        print("  [5/5] 重建索引...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sdb_trade_date
            ON stock_daily_basic (trade_date)
        """))

        # 添加 NOT NULL 约束
        conn.execute(text("""
            ALTER TABLE stock_daily_basic ALTER COLUMN trade_date SET NOT NULL
        """))

        print("迁移完成!")


if __name__ == "__main__":
    main()
