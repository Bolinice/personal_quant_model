#!/usr/bin/env python
"""检查数据库迁移状态"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import engine
from sqlalchemy import text, inspect

def main():
    print("=== 数据库状态检查 ===\n")

    with engine.connect() as conn:
        # 检查alembic版本
        result = conn.execute(text('SELECT version_num FROM alembic_version'))
        version = result.fetchone()
        print(f"当前Alembic版本: {version[0] if version else 'None'}")

        # 检查stock_industry表结构
        inspector = inspect(engine)
        columns = inspector.get_columns('stock_industry')
        col_names = [col['name'] for col in columns]

        print(f"\nstock_industry表字段数: {len(col_names)}")
        print(f"字段列表: {', '.join(col_names)}")

        has_effective = 'effective_date' in col_names
        has_expire = 'expire_date' in col_names

        print(f"\n✓ effective_date字段: {'存在' if has_effective else '不存在'}")
        print(f"✓ expire_date字段: {'存在' if has_expire else '不存在'}")

        if has_effective and has_expire:
            print("\n✅ 迁移已成功应用")
        else:
            print("\n❌ 迁移未应用，需要执行 alembic upgrade head")

        # 检查索引
        indexes = inspector.get_indexes('stock_industry')
        print(f"\n索引数量: {len(indexes)}")
        for idx in indexes:
            print(f"  - {idx['name']}: {idx['column_names']}")

if __name__ == '__main__':
    main()
