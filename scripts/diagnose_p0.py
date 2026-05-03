"""
P0任务快速诊断脚本

快速检查当前系统状态，给出具体的执行建议
"""

from sqlalchemy import text
from app.db.base import SessionLocal
from datetime import date


def check_database_fields():
    """检查数据库字段是否完整"""
    db = SessionLocal()
    issues = []

    try:
        print("\n【检查1】数据库字段完整性")
        print("-" * 60)

        # 检查StockFinancial表
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'stock_financial'
            AND column_name IN ('source_priority', 'revision_no', 'ann_date');
        """))
        financial_cols = [r[0] for r in result.fetchall()]

        print(f"StockFinancial表:")
        print(f"  ✅ ann_date: {'存在' if 'ann_date' in financial_cols else '❌ 缺失'}")
        print(f"  {'✅' if 'source_priority' in financial_cols else '❌'} source_priority: {'存在' if 'source_priority' in financial_cols else '缺失'}")
        print(f"  {'✅' if 'revision_no' in financial_cols else '❌'} revision_no: {'存在' if 'revision_no' in financial_cols else '缺失'}")

        if 'source_priority' not in financial_cols or 'revision_no' not in financial_cols:
            issues.append("需要运行: python scripts/migrate_add_pit_fields.py")

        # 检查StockBasic表
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'stock_basic'
            AND column_name IN ('delist_date', 'list_date');
        """))
        basic_cols = [r[0] for r in result.fetchall()]

        print(f"\nStockBasic表:")
        print(f"  ✅ list_date: {'存在' if 'list_date' in basic_cols else '❌ 缺失'}")
        print(f"  ✅ delist_date: {'存在' if 'delist_date' in basic_cols else '❌ 缺失'}")

        # 检查StockIndustry表
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'stock_industry'
            AND column_name IN ('effective_date', 'expire_date');
        """))
        industry_cols = [r[0] for r in result.fetchall()]

        print(f"\nStockIndustry表:")
        print(f"  {'✅' if 'effective_date' in industry_cols else '❌'} effective_date: {'存在' if 'effective_date' in industry_cols else '缺失'}")
        print(f"  {'✅' if 'expire_date' in industry_cols else '❌'} expire_date: {'存在' if 'expire_date' in industry_cols else '缺失'}")

        if 'effective_date' not in industry_cols or 'expire_date' not in industry_cols:
            issues.append("需要运行: python scripts/migrate_add_pit_fields.py")

        return len(issues) == 0, issues

    finally:
        db.close()


def check_data_completeness():
    """检查数据完整性"""
    db = SessionLocal()
    issues = []

    try:
        print("\n【检查2】数据完整性")
        print("-" * 60)

        # 检查财务数据覆盖率
        result = db.execute(text("""
            SELECT COUNT(*) FROM stock_financial WHERE ann_date IS NOT NULL;
        """))
        financial_count = result.scalar()
        print(f"财务数据记录数: {financial_count:,}")

        if financial_count == 0:
            issues.append("财务数据为空，需要运行数据同步")

        # 检查退市股票数据
        result = db.execute(text("""
            SELECT COUNT(*) FROM stock_basic WHERE delist_date IS NOT NULL;
        """))
        delisted_count = result.scalar()
        print(f"退市股票数量: {delisted_count}")

        # 检查行业分类数据
        result = db.execute(text("""
            SELECT COUNT(DISTINCT ts_code) FROM stock_industry;
        """))
        industry_count = result.scalar()
        print(f"有行业分类的股票数: {industry_count}")

        if industry_count == 0:
            issues.append("行业分类数据为空，需要运行: python scripts/sync_industry_history.py sync")

        # 检查行业历史调整记录
        result = db.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT ts_code FROM stock_industry
                GROUP BY ts_code
                HAVING COUNT(*) > 1
            ) t;
        """))
        multi_industry_count = result.scalar()
        print(f"有多条行业记录的股票数: {multi_industry_count}")

        if multi_industry_count == 0:
            issues.append("⚠️  所有股票只有1条行业记录，可能缺少历史调整数据")

        return len(issues) == 0, issues

    finally:
        db.close()


def check_pit_implementation():
    """检查PIT实现是否正确"""
    db = SessionLocal()
    issues = []

    try:
        print("\n【检查3】PIT实现验证")
        print("-" * 60)

        # 检查是否有未来数据
        result = db.execute(text("""
            SELECT COUNT(*) FROM stock_financial
            WHERE ann_date > CURRENT_DATE;
        """))
        future_count = result.scalar()

        if future_count > 0:
            print(f"❌ 发现 {future_count} 条未来数据（ann_date > 今天）")
            issues.append("数据库中存在未来数据，需要清理")
        else:
            print(f"✅ 无未来数据")

        # 检查同一报告期是否有多个版本
        result = db.execute(text("""
            SELECT ts_code, end_date, COUNT(*) as cnt
            FROM stock_financial
            GROUP BY ts_code, end_date
            HAVING COUNT(*) > 1
            LIMIT 5;
        """))
        multi_version = result.fetchall()

        if multi_version:
            print(f"✅ 发现多版本数据（示例）:")
            for ts_code, end_date, cnt in multi_version:
                print(f"   {ts_code} {end_date}: {cnt}条记录")
        else:
            print(f"⚠️  未发现多版本数据，可能所有数据都是正式报告")

        return len(issues) == 0, issues

    finally:
        db.close()


def main():
    """主函数"""
    print("="*60)
    print("P0任务快速诊断")
    print("="*60)

    all_passed = True
    all_issues = []

    # 检查1: 数据库字段
    passed, issues = check_database_fields()
    all_passed = all_passed and passed
    all_issues.extend(issues)

    # 检查2: 数据完整性
    passed, issues = check_data_completeness()
    all_passed = all_passed and passed
    all_issues.extend(issues)

    # 检查3: PIT实现
    passed, issues = check_pit_implementation()
    all_passed = all_passed and passed
    all_issues.extend(issues)

    # 总结
    print("\n" + "="*60)
    print("诊断总结")
    print("="*60)

    if all_passed and len(all_issues) == 0:
        print("✅ 所有检查通过！")
        print("\n下一步建议:")
        print("  1. 运行完整测试: python -m pytest tests/test_pit_guard_multiversion.py tests/test_survivorship_bias.py -v")
        print("  2. 运行完整回测，对比修复前后的IC/收益差异")
        print("  3. 开始P1性能优化任务")
    else:
        print(f"⚠️  发现 {len(all_issues)} 个问题需要处理:\n")
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")

        print("\n推荐执行顺序:")
        print("  1. python scripts/migrate_add_pit_fields.py")
        print("  2. python scripts/backfill_financial_priority.py mark")
        print("  3. python scripts/sync_industry_history.py sync")
        print("  4. python scripts/sync_industry_history.py verify")
        print("\n或者一键执行:")
        print("  python scripts/run_p0_tasks.py")


if __name__ == '__main__':
    main()
