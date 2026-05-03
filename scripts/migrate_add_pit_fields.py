"""
数据库迁移：添加PIT和行业历史支持字段

执行顺序：
1. 添加字段
2. 从Tushare补充历史数据
3. 验证数据完整性
"""

from sqlalchemy import text
from app.db.base import SessionLocal


def upgrade_stock_financial():
    """为StockFinancial表添加版本管理字段"""
    db = SessionLocal()
    try:
        # 添加source_priority字段（1=预告, 2=快报, 3=正式报告）
        db.execute(text("""
            ALTER TABLE stock_financial
            ADD COLUMN IF NOT EXISTS source_priority INTEGER DEFAULT 3;
        """))
        db.execute(text("""
            COMMENT ON COLUMN stock_financial.source_priority IS '数据来源优先级: 1=业绩预告, 2=业绩快报, 3=正式报告';
        """))

        # 添加revision_no字段（修订版本号，0=初版）
        db.execute(text("""
            ALTER TABLE stock_financial
            ADD COLUMN IF NOT EXISTS revision_no INTEGER DEFAULT 0;
        """))
        db.execute(text("""
            COMMENT ON COLUMN stock_financial.revision_no IS '修订版本号: 0=初版, 1=修订1, 2=修订2...';
        """))

        # 添加索引
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_financial_priority
            ON stock_financial(ts_code, end_date, source_priority DESC, revision_no DESC);
        """))

        db.commit()
        print("✅ StockFinancial表字段添加成功")

    except Exception as e:
        db.rollback()
        print(f"❌ StockFinancial表字段添加失败: {e}")
    finally:
        db.close()


def upgrade_stock_industry():
    """为StockIndustry表添加历史时点字段"""
    db = SessionLocal()
    try:
        # 添加effective_date字段（生效日期）
        db.execute(text("""
            ALTER TABLE stock_industry
            ADD COLUMN IF NOT EXISTS effective_date DATE;
        """))
        db.execute(text("""
            COMMENT ON COLUMN stock_industry.effective_date IS '行业分类生效日期';
        """))

        # 添加expire_date字段（失效日期）
        db.execute(text("""
            ALTER TABLE stock_industry
            ADD COLUMN IF NOT EXISTS expire_date DATE;
        """))
        db.execute(text("""
            COMMENT ON COLUMN stock_industry.expire_date IS '行业分类失效日期（NULL表示当前有效）';
        """))

        # 添加索引
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_industry_effective
            ON stock_industry(ts_code, effective_date, expire_date);
        """))

        db.commit()
        print("✅ StockIndustry表字段添加成功")

    except Exception as e:
        db.rollback()
        print(f"❌ StockIndustry表字段添加失败: {e}")
    finally:
        db.close()


def verify_fields():
    """验证字段是否添加成功"""
    db = SessionLocal()
    try:
        # 验证StockFinancial
        result = db.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'stock_financial'
            AND column_name IN ('source_priority', 'revision_no');
        """))
        financial_cols = result.fetchall()
        print(f"\n=== StockFinancial新增字段 ===")
        for col in financial_cols:
            print(f"  {col[0]}: {col[1]}")

        # 验证StockIndustry
        result = db.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'stock_industry'
            AND column_name IN ('effective_date', 'expire_date');
        """))
        industry_cols = result.fetchall()
        print(f"\n=== StockIndustry新增字段 ===")
        for col in industry_cols:
            print(f"  {col[0]}: {col[1]}")

    finally:
        db.close()


if __name__ == '__main__':
    print("开始数据库迁移...")
    print("\n1. 升级StockFinancial表")
    upgrade_stock_financial()

    print("\n2. 升级StockIndustry表")
    upgrade_stock_industry()

    print("\n3. 验证字段")
    verify_fields()

    print("\n✅ 数据库迁移完成！")
    print("\n下一步：")
    print("  1. 运行 scripts/backfill_financial_priority.py 补充财务数据优先级")
    print("  2. 运行 scripts/sync_industry_history.py 补充行业分类历史")
