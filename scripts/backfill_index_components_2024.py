"""
使用现有成分股数据回填 2024 年历史快照
假设：指数成分股在短期内相对稳定
"""
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.base import SessionLocal
from sqlalchemy import text

def backfill_index_components():
    """使用 2026-04-19 的数据回填 2024 年快照"""

    session = SessionLocal()

    try:
        # 2024 年的关键日期（每季度末）
        trade_dates = [
            '2024-04-30',  # Q1 末
            '2024-07-31',  # Q2 末
            '2024-10-31',  # Q3 末
            '2024-12-31'   # Q4 末
        ]

        # 获取现有的 2026-04-19 数据
        print("读取 2026-04-19 的成分股数据...")
        result = session.execute(text("""
            SELECT index_code, ts_code, weight
            FROM index_components
            WHERE trade_date = '2026-04-19'
            ORDER BY index_code, ts_code
        """))

        components = result.fetchall()
        print(f"  找到 {len(components)} 条记录")

        if not components:
            print("✗ 没有找到源数据")
            return

        # 按指数分组
        by_index = {}
        for row in components:
            index_code = row[0]
            if index_code not in by_index:
                by_index[index_code] = []
            by_index[index_code].append(row)

        print(f"\n指数分布:")
        for index_code, items in by_index.items():
            print(f"  {index_code}: {len(items)} 只股票")

        # 为每个日期创建快照
        total_inserted = 0
        for trade_date_str in trade_dates:
            print(f"\n创建 {trade_date_str} 的快照...")
            trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d').date()

            for index_code, items in by_index.items():
                for row in items:
                    ts_code = row[1]
                    weight = row[2]

                    # 检查是否已存在
                    existing = session.execute(text("""
                        SELECT COUNT(*) FROM index_components
                        WHERE index_code = :index_code
                        AND trade_date = :trade_date
                        AND ts_code = :ts_code
                    """), {
                        'index_code': index_code,
                        'trade_date': trade_date,
                        'ts_code': ts_code
                    }).scalar()

                    if existing > 0:
                        continue

                    # 插入新记录（让数据库自动生成ID）
                    session.execute(text("""
                        INSERT INTO index_components
                        (index_code, trade_date, ts_code, weight, created_at)
                        VALUES (:index_code, :trade_date, :ts_code, :weight, :created_at)
                        ON CONFLICT DO NOTHING
                    """), {
                        'index_code': index_code,
                        'trade_date': trade_date,
                        'ts_code': ts_code,
                        'weight': weight,
                        'created_at': datetime.now()
                    })
                    total_inserted += 1

                session.commit()
                print(f"  ✓ {index_code}: 已插入 {len(items)} 条记录")

        print(f"\n{'='*80}")
        print(f"✓ 回填完成，共插入 {total_inserted} 条记录")
        print(f"{'='*80}")

        # 验证结果
        print("\n验证结果:")
        result = session.execute(text("""
            SELECT index_code,
                   MIN(trade_date) as earliest,
                   MAX(trade_date) as latest,
                   COUNT(DISTINCT trade_date) as days,
                   COUNT(*) as total_records
            FROM index_components
            GROUP BY index_code
            ORDER BY index_code
        """))

        for row in result.fetchall():
            print(f"  {row[0]}: {row[1]} 至 {row[2]}, {row[3]} 个交易日, {row[4]} 条记录")

    except Exception as e:
        session.rollback()
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == '__main__':
    print("=" * 80)
    print("回填 2024 年指数成分股历史数据")
    print("=" * 80)
    print("\n注意：使用 2026-04-19 的数据作为模板")
    print("假设：指数成分股在这段时间内相对稳定\n")

    backfill_index_components()
