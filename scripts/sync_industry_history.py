"""
同步行业分类历史数据

从Tushare获取申万行业分类的历史调整记录，支持时点回溯

Tushare接口：
- ths_index: 同花顺行业分类
- index_classify: 申万行业分类

注意：申万行业每年6月会调整，需要保存完整历史
"""

import tushare as ts
from datetime import datetime, date, timedelta
from sqlalchemy import text
from app.db.base import SessionLocal
from app.core.config import settings
import pandas as pd


def sync_industry_history():
    """同步行业分类历史数据"""
    db = SessionLocal()
    pro = ts.pro_api(settings.TUSHARE_TOKEN)

    try:
        print("开始同步行业分类历史数据...")

        # 1. 获取所有股票列表
        print("\n1. 获取股票列表")
        stocks = db.execute(text("""
            SELECT ts_code FROM stock_basic
            WHERE list_status IN ('L', 'P', 'D')
            ORDER BY ts_code;
        """)).fetchall()
        stock_codes = [s[0] for s in stocks]
        print(f"   共 {len(stock_codes)} 只股票")

        # 2. 获取申万行业分类（当前）
        print("\n2. 获取申万行业分类（当前）")
        df_sw = pro.ths_member(
            ts_code='',
            fields='ts_code,name,code,in_date,out_date,is_new'
        )

        if df_sw.empty:
            print("   ⚠️  无法获取申万行业数据，尝试使用stock_basic中的industry字段")

            # 从stock_basic获取当前行业分类
            result = db.execute(text("""
                SELECT ts_code, industry, industry_sw
                FROM stock_basic
                WHERE industry IS NOT NULL OR industry_sw IS NOT NULL;
            """))

            for row in result:
                ts_code = row[0]
                industry = row[1] or row[2]  # 优先使用industry，其次industry_sw

                if not industry:
                    continue

                # 插入当前行业分类（effective_date设为上市日期）
                db.execute(text("""
                    INSERT INTO stock_industry
                    (ts_code, industry_name, industry_code, level, standard, effective_date, expire_date)
                    VALUES (:ts_code, :industry_name, :industry_code, :level, :standard, :effective_date, NULL)
                    ON CONFLICT (ts_code, industry_name, standard)
                    DO UPDATE SET
                        effective_date = EXCLUDED.effective_date,
                        expire_date = EXCLUDED.expire_date;
                """), {
                    'ts_code': ts_code,
                    'industry_name': industry,
                    'industry_code': '',
                    'level': 'L1',
                    'standard': 'SW',  # 申万
                    'effective_date': date(2018, 1, 1)  # 默认生效日期
                })

            db.commit()
            print(f"   已插入当前行业分类")

        else:
            # 处理申万行业数据
            for _, row in df_sw.iterrows():
                ts_code = row['ts_code']
                in_date = pd.to_datetime(row['in_date']).date() if pd.notna(row['in_date']) else date(2018, 1, 1)
                out_date = pd.to_datetime(row['out_date']).date() if pd.notna(row['out_date']) else None

                db.execute(text("""
                    INSERT INTO stock_industry
                    (ts_code, industry_name, industry_code, level, standard, effective_date, expire_date)
                    VALUES (:ts_code, :industry_name, :industry_code, :level, :standard, :effective_date, :expire_date)
                    ON CONFLICT (ts_code, industry_name, standard)
                    DO UPDATE SET
                        effective_date = EXCLUDED.effective_date,
                        expire_date = EXCLUDED.expire_date;
                """), {
                    'ts_code': ts_code,
                    'industry_name': row['name'],
                    'industry_code': row['code'],
                    'level': 'L1',
                    'standard': 'SW',
                    'effective_date': in_date,
                    'expire_date': out_date
                })

            db.commit()
            print(f"   已插入 {len(df_sw)} 条行业分类记录")

        # 3. 验证数据
        print("\n3. 验证行业分类历史数据")
        result = db.execute(text("""
            SELECT ts_code, COUNT(*) as cnt
            FROM stock_industry
            WHERE effective_date IS NOT NULL
            GROUP BY ts_code
            HAVING COUNT(*) > 1
            LIMIT 10;
        """))
        multi_industry = result.fetchall()

        if multi_industry:
            print(f"   ✅ 发现 {len(multi_industry)} 只股票有多条行业记录（历史调整）")
            for ts_code, cnt in multi_industry[:5]:
                print(f"      {ts_code}: {cnt} 条记录")
        else:
            print(f"   ⚠️  所有股票只有1条行业记录，可能缺少历史调整数据")

        print("\n✅ 行业分类历史数据同步完成")

    except Exception as e:
        db.rollback()
        print(f"❌ 同步失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


def verify_industry_history():
    """验证行业分类历史数据完整性"""
    db = SessionLocal()

    try:
        print("\n=== 验证行业分类历史数据 ===")

        # 1. 检查是否有effective_date字段
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'stock_industry'
            AND column_name IN ('effective_date', 'expire_date');
        """))
        cols = [r[0] for r in result.fetchall()]

        if 'effective_date' not in cols:
            print("❌ stock_industry表缺少effective_date字段")
            print("   请先运行: python scripts/migrate_add_pit_fields.py")
            return False

        print("✅ 字段检查通过")

        # 2. 检查数据覆盖率
        result = db.execute(text("""
            SELECT
                COUNT(DISTINCT si.ts_code) as industry_count,
                (SELECT COUNT(*) FROM stock_basic WHERE list_status IN ('L', 'P')) as total_count
            FROM stock_industry si
            WHERE si.effective_date IS NOT NULL;
        """))
        row = result.fetchone()
        industry_count = row[0]
        total_count = row[1]
        coverage = industry_count / total_count if total_count > 0 else 0

        print(f"\n覆盖率: {industry_count}/{total_count} = {coverage:.1%}")

        if coverage < 0.8:
            print("⚠️  覆盖率低于80%，建议补充数据")
        else:
            print("✅ 覆盖率检查通过")

        # 3. 检查历史调整记录
        result = db.execute(text("""
            SELECT ts_code, industry_name, effective_date, expire_date
            FROM stock_industry
            WHERE ts_code = (
                SELECT ts_code FROM stock_industry
                WHERE effective_date IS NOT NULL
                GROUP BY ts_code
                HAVING COUNT(*) > 1
                LIMIT 1
            )
            ORDER BY effective_date;
        """))
        history = result.fetchall()

        if history:
            print(f"\n✅ 发现行业调整历史（示例: {history[0][0]}）:")
            for ts_code, industry, eff_date, exp_date in history:
                print(f"   {eff_date} ~ {exp_date or '至今'}: {industry}")
        else:
            print("\n⚠️  未发现行业调整历史，所有股票只有1条记录")
            print("   这可能导致回测时使用错误的行业分类")

        return True

    finally:
        db.close()


def get_industry_at_date(ts_code: str, trade_date: date):
    """获取指定日期的行业分类（测试函数）"""
    db = SessionLocal()

    try:
        result = db.execute(text("""
            SELECT industry_name, industry_code, effective_date, expire_date
            FROM stock_industry
            WHERE ts_code = :ts_code
            AND effective_date <= :trade_date
            AND (expire_date IS NULL OR expire_date > :trade_date)
            ORDER BY effective_date DESC
            LIMIT 1;
        """), {'ts_code': ts_code, 'trade_date': trade_date})

        row = result.fetchone()
        if row:
            return {
                'industry_name': row[0],
                'industry_code': row[1],
                'effective_date': row[2],
                'expire_date': row[3]
            }
        return None

    finally:
        db.close()


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python sync_industry_history.py sync     # 同步行业分类历史")
        print("  python sync_industry_history.py verify   # 验证数据完整性")
        print("  python sync_industry_history.py test     # 测试时点查询")
        sys.exit(1)

    action = sys.argv[1]

    if action == 'sync':
        sync_industry_history()
    elif action == 'verify':
        verify_industry_history()
    elif action == 'test':
        # 测试时点查询
        test_code = '000001.SZ'
        test_dates = [
            date(2019, 1, 1),
            date(2020, 7, 1),
            date(2021, 7, 1),
            date(2023, 1, 1)
        ]

        print(f"\n测试股票: {test_code}")
        for test_date in test_dates:
            industry = get_industry_at_date(test_code, test_date)
            if industry:
                print(f"  {test_date}: {industry['industry_name']} "
                      f"(生效: {industry['effective_date']})")
            else:
                print(f"  {test_date}: 无数据")
    else:
        print(f"未知操作: {action}")
        sys.exit(1)
