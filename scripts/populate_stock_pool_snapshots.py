"""
填充股票池快照数据
从 index_components 表读取指数成分股数据，填充到 stock_pool_snapshots 表
"""
from app.db.base import SessionLocal
from sqlalchemy import text
from datetime import datetime
import json

def populate_snapshots():
    session = SessionLocal()

    try:
        # 指数代码映射到股票池ID
        index_to_pool = {
            '000300.SH': 1,  # HS300
            '000905.SH': 2,  # ZZ500
            '000852.SH': 3,  # ZZ1000
        }

        # 获取每个指数的所有交易日期
        for index_code, pool_id in index_to_pool.items():
            print(f"\n处理 {index_code} (pool_id={pool_id})...")

            # 获取该指数的所有交易日期
            result = session.execute(text(f"""
                SELECT DISTINCT trade_date FROM index_components
                WHERE index_code = :index_code
                ORDER BY trade_date
            """), {'index_code': index_code})

            trade_dates = [row[0] for row in result.fetchall()]

            if not trade_dates:
                print(f"  未找到 {index_code} 的成分股数据")
                continue

            print(f"  找到 {len(trade_dates)} 个交易日")

            for trade_date in trade_dates:
                print(f"  处理 {trade_date}...")

                # 获取该日期的所有成分股
                result = session.execute(text(f"""
                    SELECT ts_code, weight
                    FROM index_components
                    WHERE index_code = :index_code AND trade_date = :trade_date
                    ORDER BY weight DESC
                """), {'index_code': index_code, 'trade_date': trade_date})

                constituents = result.fetchall()

                # 检查是否已存在该日期的快照
                existing = session.execute(text("""
                    SELECT COUNT(*) FROM stock_pool_snapshots
                    WHERE pool_id = :pool_id AND trade_date = :trade_date
                """), {'pool_id': pool_id, 'trade_date': trade_date}).scalar()

                if existing > 0:
                    print(f"    快照已存在，跳过")
                    continue

                # 构建securities JSON数据
                securities = [
                    {'ts_code': ts_code, 'weight': float(weight)}
                    for ts_code, weight in constituents
                ]

                # 插入快照数据
                session.execute(text("""
                    INSERT INTO stock_pool_snapshots
                    (pool_id, trade_date, securities, eligible_count, created_at)
                    VALUES (:pool_id, :trade_date, :securities, :eligible_count, :created_at)
                """), {
                    'pool_id': pool_id,
                    'trade_date': trade_date,
                    'securities': json.dumps(securities),
                    'eligible_count': len(constituents),
                    'created_at': datetime.now()
                })

                session.commit()
                print(f"    ✓ 已插入快照记录，包含 {len(constituents)} 只股票")

        # 验证结果
        print("\n验证结果:")
        result = session.execute(text("""
            SELECT pool_id, trade_date, eligible_count
            FROM stock_pool_snapshots
            ORDER BY pool_id, trade_date
        """))

        for row in result.fetchall():
            print(f"  pool_id={row[0]}, date={row[1]}, count={row[2]}")

    except Exception as e:
        session.rollback()
        print(f"错误: {e}")
        raise
    finally:
        session.close()

if __name__ == '__main__':
    populate_snapshots()
    print("\n✓ 股票池快照数据填充完成")
