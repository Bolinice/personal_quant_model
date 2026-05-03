"""
补充财务数据的source_priority字段

从Tushare获取业绩预告和业绩快报数据，标记优先级：
- 业绩预告: source_priority = 1
- 业绩快报: source_priority = 2
- 正式报告: source_priority = 3 (默认值)

执行前提：
1. 已运行 migrate_add_pit_fields.py 添加字段
2. Tushare API token已配置
"""

import tushare as ts
from datetime import datetime, date
from sqlalchemy import text
from app.db.base import SessionLocal
from app.core.config import settings


def backfill_financial_priority():
    """补充财务数据优先级"""
    db = SessionLocal()

    try:
        # 初始化Tushare
        pro = ts.pro_api(settings.TUSHARE_TOKEN)

        print("开始补充财务数据优先级...")

        # 1. 获取所有正式报告（已存在的数据，标记为优先级3）
        print("\n1. 标记正式报告（优先级3）")
        result = db.execute(text("""
            UPDATE stock_financial
            SET source_priority = 3
            WHERE source_priority IS NULL OR source_priority = 0;
        """))
        db.commit()
        print(f"   已标记 {result.rowcount} 条正式报告")

        # 2. 获取业绩预告数据（优先级1）
        print("\n2. 获取业绩预告数据（优先级1）")
        # Tushare接口：forecast (业绩预告)
        # 注意：这个接口返回的是预告数据，需要插入到stock_financial表
        # 由于业绩预告数据结构不同，这里仅做示例
        print("   ⚠️  业绩预告数据结构与正式报告不同，需要单独处理")
        print("   建议：创建独立的 stock_forecast 表存储业绩预告")

        # 3. 获取业绩快报数据（优先级2）
        print("\n3. 获取业绩快报数据（优先级2）")
        # Tushare接口：express (业绩快报)
        print("   ⚠️  业绩快报数据结构与正式报告不同，需要单独处理")
        print("   建议：创建独立的 stock_express 表存储业绩快报")

        print("\n✅ 财务数据优先级补充完成")
        print("\n说明：")
        print("  - 当前所有财务数据已标记为优先级3（正式报告）")
        print("  - 业绩预告和快报需要从Tushare单独获取并插入")
        print("  - 建议创建独立表存储不同来源的数据")

    except Exception as e:
        db.rollback()
        print(f"❌ 补充失败: {e}")
        raise
    finally:
        db.close()


def create_forecast_and_express_tables():
    """创建业绩预告和业绩快报表（推荐方案）"""
    db = SessionLocal()

    try:
        # 创建业绩预告表
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_forecast (
                id SERIAL PRIMARY KEY,
                ts_code VARCHAR(20) NOT NULL,
                ann_date DATE NOT NULL COMMENT '公告日期',
                end_date DATE NOT NULL COMMENT '报告期',
                type VARCHAR(20) COMMENT '预告类型',
                p_change_min NUMERIC(12, 4) COMMENT '预告净利润变动幅度下限',
                p_change_max NUMERIC(12, 4) COMMENT '预告净利润变动幅度上限',
                net_profit_min NUMERIC(20, 4) COMMENT '预告净利润下限',
                net_profit_max NUMERIC(20, 4) COMMENT '预告净利润上限',
                summary TEXT COMMENT '预告摘要',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, ann_date, end_date)
            );

            CREATE INDEX IF NOT EXISTS ix_forecast_code_date
            ON stock_forecast(ts_code, end_date, ann_date);
        """))

        # 创建业绩快报表
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_express (
                id SERIAL PRIMARY KEY,
                ts_code VARCHAR(20) NOT NULL,
                ann_date DATE NOT NULL COMMENT '公告日期',
                end_date DATE NOT NULL COMMENT '报告期',
                revenue NUMERIC(20, 4) COMMENT '营业收入',
                operate_profit NUMERIC(20, 4) COMMENT '营业利润',
                total_profit NUMERIC(20, 4) COMMENT '利润总额',
                net_profit NUMERIC(20, 4) COMMENT '净利润',
                total_assets NUMERIC(20, 4) COMMENT '总资产',
                total_equity NUMERIC(20, 4) COMMENT '股东权益',
                roe NUMERIC(12, 4) COMMENT 'ROE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, ann_date, end_date)
            );

            CREATE INDEX IF NOT EXISTS ix_express_code_date
            ON stock_express(ts_code, end_date, ann_date);
        """))

        db.commit()
        print("✅ 业绩预告和业绩快报表创建成功")

    except Exception as e:
        db.rollback()
        print(f"❌ 创建表失败: {e}")
        raise
    finally:
        db.close()


def sync_forecast_data(start_date: str = '20180101', end_date: str = None):
    """从Tushare同步业绩预告数据"""
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')

    db = SessionLocal()
    pro = ts.pro_api(settings.TUSHARE_TOKEN)

    try:
        print(f"同步业绩预告数据: {start_date} ~ {end_date}")

        # 分年度获取（避免单次数据量过大）
        for year in range(int(start_date[:4]), int(end_date[:4]) + 1):
            year_start = f"{year}0101"
            year_end = f"{year}1231"

            print(f"  获取 {year} 年数据...")
            df = pro.forecast(
                start_date=year_start,
                end_date=year_end,
                fields='ts_code,ann_date,end_date,type,p_change_min,p_change_max,net_profit_min,net_profit_max,summary'
            )

            if df.empty:
                print(f"    无数据")
                continue

            # 插入数据库
            for _, row in df.iterrows():
                db.execute(text("""
                    INSERT INTO stock_forecast
                    (ts_code, ann_date, end_date, type, p_change_min, p_change_max,
                     net_profit_min, net_profit_max, summary)
                    VALUES (:ts_code, :ann_date, :end_date, :type, :p_change_min, :p_change_max,
                            :net_profit_min, :net_profit_max, :summary)
                    ON CONFLICT (ts_code, ann_date, end_date) DO UPDATE SET
                        type = EXCLUDED.type,
                        p_change_min = EXCLUDED.p_change_min,
                        p_change_max = EXCLUDED.p_change_max,
                        net_profit_min = EXCLUDED.net_profit_min,
                        net_profit_max = EXCLUDED.net_profit_max,
                        summary = EXCLUDED.summary;
                """), {
                    'ts_code': row['ts_code'],
                    'ann_date': row['ann_date'],
                    'end_date': row['end_date'],
                    'type': row['type'],
                    'p_change_min': row['p_change_min'],
                    'p_change_max': row['p_change_max'],
                    'net_profit_min': row['net_profit_min'],
                    'net_profit_max': row['net_profit_max'],
                    'summary': row['summary']
                })

            db.commit()
            print(f"    已插入 {len(df)} 条")

        print("✅ 业绩预告数据同步完成")

    except Exception as e:
        db.rollback()
        print(f"❌ 同步失败: {e}")
        raise
    finally:
        db.close()


def sync_express_data(start_date: str = '20180101', end_date: str = None):
    """从Tushare同步业绩快报数据"""
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')

    db = SessionLocal()
    pro = ts.pro_api(settings.TUSHARE_TOKEN)

    try:
        print(f"同步业绩快报数据: {start_date} ~ {end_date}")

        # 分年度获取
        for year in range(int(start_date[:4]), int(end_date[:4]) + 1):
            year_start = f"{year}0101"
            year_end = f"{year}1231"

            print(f"  获取 {year} 年数据...")
            df = pro.express(
                start_date=year_start,
                end_date=year_end,
                fields='ts_code,ann_date,end_date,revenue,operate_profit,total_profit,n_income,total_assets,total_hldr_eqy_exc_min_int,roe'
            )

            if df.empty:
                print(f"    无数据")
                continue

            # 插入数据库
            for _, row in df.iterrows():
                db.execute(text("""
                    INSERT INTO stock_express
                    (ts_code, ann_date, end_date, revenue, operate_profit, total_profit,
                     net_profit, total_assets, total_equity, roe)
                    VALUES (:ts_code, :ann_date, :end_date, :revenue, :operate_profit, :total_profit,
                            :net_profit, :total_assets, :total_equity, :roe)
                    ON CONFLICT (ts_code, ann_date, end_date) DO UPDATE SET
                        revenue = EXCLUDED.revenue,
                        operate_profit = EXCLUDED.operate_profit,
                        total_profit = EXCLUDED.total_profit,
                        net_profit = EXCLUDED.net_profit,
                        total_assets = EXCLUDED.total_assets,
                        total_equity = EXCLUDED.total_equity,
                        roe = EXCLUDED.roe;
                """), {
                    'ts_code': row['ts_code'],
                    'ann_date': row['ann_date'],
                    'end_date': row['end_date'],
                    'revenue': row['revenue'],
                    'operate_profit': row['operate_profit'],
                    'total_profit': row['total_profit'],
                    'net_profit': row['n_income'],
                    'total_assets': row['total_assets'],
                    'total_equity': row['total_hldr_eqy_exc_min_int'],
                    'roe': row['roe']
                })

            db.commit()
            print(f"    已插入 {len(df)} 条")

        print("✅ 业绩快报数据同步完成")

    except Exception as e:
        db.rollback()
        print(f"❌ 同步失败: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python backfill_financial_priority.py mark          # 标记现有数据为正式报告")
        print("  python backfill_financial_priority.py create        # 创建预告/快报表")
        print("  python backfill_financial_priority.py sync_forecast # 同步业绩预告")
        print("  python backfill_financial_priority.py sync_express  # 同步业绩快报")
        print("  python backfill_financial_priority.py all           # 执行全部")
        sys.exit(1)

    action = sys.argv[1]

    if action == 'mark':
        backfill_financial_priority()
    elif action == 'create':
        create_forecast_and_express_tables()
    elif action == 'sync_forecast':
        sync_forecast_data()
    elif action == 'sync_express':
        sync_express_data()
    elif action == 'all':
        print("=== 1. 标记现有数据 ===")
        backfill_financial_priority()
        print("\n=== 2. 创建预告/快报表 ===")
        create_forecast_and_express_tables()
        print("\n=== 3. 同步业绩预告 ===")
        sync_forecast_data()
        print("\n=== 4. 同步业绩快报 ===")
        sync_express_data()
        print("\n✅ 全部完成！")
    else:
        print(f"未知操作: {action}")
        sys.exit(1)
