"""
添加复合索引 - 性能优化
为 stock_daily, stock_financial, index_daily, index_components 添加复合索引
适用于已有数据库的增量迁移
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.logging import logger


INDEXES = [
    # stock_daily: 最关键的复合索引，覆盖 WHERE ts_code = ? AND trade_date = ? 查询
    {
        "name": "ix_sd_code_date",
        "table": "stock_daily",
        "columns": "ts_code, trade_date",
        "sql": "CREATE INDEX IF NOT EXISTS ix_sd_code_date ON stock_daily (ts_code, trade_date)",
    },
    # stock_financial: 按股票+报告期查询
    {
        "name": "ix_sf_code_end_date",
        "table": "stock_financial",
        "columns": "ts_code, end_date",
        "sql": "CREATE INDEX IF NOT EXISTS ix_sf_code_end_date ON stock_financial (ts_code, end_date)",
    },
    # stock_financial: 按公告日期查询（避免未来函数的关键查询）
    {
        "name": "ix_sf_ann_date",
        "table": "stock_financial",
        "columns": "ann_date",
        "sql": "CREATE INDEX IF NOT EXISTS ix_sf_ann_date ON stock_financial (ann_date)",
    },
    # index_daily: 按指数+日期查询
    {
        "name": "ix_id_code_date",
        "table": "index_daily",
        "columns": "index_code, trade_date",
        "sql": "CREATE INDEX IF NOT EXISTS ix_id_code_date ON index_daily (index_code, trade_date)",
    },
    # index_components: 按指数+日期查询成分股
    {
        "name": "ix_ic_code_date",
        "table": "index_components",
        "columns": "index_code, trade_date",
        "sql": "CREATE INDEX IF NOT EXISTS ix_ic_code_date ON index_components (index_code, trade_date)",
    },
    # index_components: 按指数+股票查询
    {
        "name": "ix_ic_code_stock",
        "table": "index_components",
        "columns": "index_code, ts_code",
        "sql": "CREATE INDEX IF NOT EXISTS ix_ic_code_stock ON index_components (index_code, ts_code)",
    },
]


def add_indexes():
    """添加复合索引"""
    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # 获取已有索引
        existing = set()
        if "sqlite" in settings.DATABASE_URL:
            rows = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )).fetchall()
            existing = {r[0] for r in rows}
        else:
            rows = conn.execute(text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
            )).fetchall()
            existing = {r[0] for r in rows}

        for idx in INDEXES:
            if idx["name"] in existing:
                print(f"  SKIP {idx['name']} (already exists)")
                continue

            print(f"  CREATE {idx['name']} ON {idx['table']} ({idx['columns']})...")
            conn.execute(text(idx["sql"]))
            conn.commit()
            print(f"  DONE {idx['name']}")

    print("\n索引添加完成!")


if __name__ == "__main__":
    print("添加复合索引...")
    add_indexes()
