"""
从 Tushare 获取指数成分股数据（使用 index_member 接口）
"""
import sys
from pathlib import Path
from datetime import date, datetime
import time

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.base import SessionLocal
from app.core.config import settings
from sqlalchemy import text
import pandas as pd

def fetch_index_members_from_tushare():
    """从 Tushare 获取指数成分股数据"""

    # 初始化 Tushare
    try:
        import tushare as ts
        ts.set_token(settings.TUSHARE_TOKEN)
        pro = ts.pro_api()
        print("✓ Tushare API 初始化成功")
    except Exception as e:
        print(f"✗ Tushare 初始化失败: {e}")
        return

    session = SessionLocal()

    try:
        # 定义要获取的指数
        indexes = {
            '000300.SH': 'HS300',
            '000905.SH': 'ZZ500',
            '000852.SH': 'ZZ1000'
        }

        # 使用 2024 年的几个关键日期
        trade_dates = [
            '20240430',  # 2024年4月底
            '20240731',  # 2024年7月底
            '20241031',  # 2024年10月底
            '20241231'   # 2024年底
        ]

        total_inserted = 0

        for index_code, index_name in indexes.items():
            print(f"\n处理 {index_name} ({index_code})...")

            try:
                # 调用 Tushare API 获取指数成分股
                df = pro.index_member(index_code=index_code)

                if df.empty:
                    print(f"  ⚠️  无数据")
                    continue

                print(f"  获取到 {len(df)} 只成分股")

                # 为每个日期创建快照
                for trade_date_str in trade_dates:
                    trade_date = datetime.strptime(trade_date_str, '%Y%m%d').date()
                    print(f"  创建 {trade_date} 的快照...")

                    # 插入数据库
                    for _, row in df.iterrows():
                        # 检查是否已存在
                        existing = session.execute(text("""
                            SELECT COUNT(*) FROM index_components
                            WHERE index_code = :index_code
                            AND trade_date = :trade_date
                            AND ts_code = :ts_code
                        """), {
                            'index_code': index_code,
                            'trade_date': trade_date,
                            'ts_code': row['con_code']
                        }).scalar()

                        if existing > 0:
                            continue

                        # 插入新记录（权重设为均等）
                        session.execute(text("""
                            INSERT INTO index_components
                            (index_code, trade_date, ts_code, weight, created_at)
                            VALUES (:index_code, :trade_date, :ts_code, :weight, :created_at)
                        """), {
                            'index_code': index_code,
                            'trade_date': trade_date,
                            'ts_code': row['con_code'],
                            'weight': 1.0 / len(df),  # 均等权重
                            'created_at': datetime.now()
                        })
                        total_inserted += 1

                    session.commit()
                    print(f"    ✓ 已插入 {len(df)} 条记录")

                # API 限流
                time.sleep(0.5)

            except Exception as e:
                print(f"  ✗ 获取失败: {e}")
                session.rollback()
                continue

        print(f"\n{'='*80}")
        print(f"✓ 数据获取完成，共插入 {total_inserted} 条记录")
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
    print("从 Tushare 获取指数成分股数据（index_member 接口）")
    print("=" * 80)
    print("\n注意：此接口返回当前成分股，我们将为多个日期创建快照\n")

    fetch_index_members_from_tushare()
