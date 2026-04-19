"""
SQLite → PostgreSQL 数据迁移脚本
从 SQLite 批量迁移数据到 PostgreSQL，保留现有数据
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings
from app.core.logging import logger
from app.db.base import Base
import app.models  # noqa: F401

# SQLite 源数据库路径
SQLITE_PATH = "sqlite:///./quant_platform.db"

# 迁移顺序：基础表在前，关联表在后
# 大表放在最后，分批处理
TABLE_ORDER = [
    # 基础/配置表
    "roles",
    "users",
    "user_roles",
    "api_keys",
    "securities",
    "stock_basic",
    "stock_industry",
    "industry_classification",
    "index_basic",
    "index_components",
    "trading_calendar",
    "stock_status_daily",
    # 因子体系
    "factors",
    "factor_values",
    "factor_analysis",
    "factor_results",
    # 模型体系
    "models",
    "model_factor_weights",
    "model_scores",
    "model_performance",
    # 股票池
    "stock_pools",
    "stock_pool_snapshots",
    # 组合与择时
    "portfolios",
    "portfolio_positions",
    "rebalance_records",
    "timing_configs",
    "timing_signals",
    # 回测
    "backtests",
    "backtest_navs",
    "backtest_positions",
    "backtest_trades",
    "backtest_results",
    # 模拟组合
    "simulated_portfolios",
    "simulated_portfolio_positions",
    "simulated_portfolio_navs",
    # 产品与订阅
    "products",
    "product_reports",
    "subscription_plans",
    "subscriptions",
    "subscription_histories",
    "subscription_permissions",
    # 报告
    "reports",
    "report_templates",
    "report_schedules",
    # 系统日志
    "task_logs",
    "audit_logs",
    "alert_logs",
    "alert_rules",
    "notifications",
    # 大表放最后
    "stock_financial",
    "stock_daily",
    "index_daily",
]

# 大表分批大小
BATCH_SIZE = 5000
# 需要分批处理的大表
LARGE_TABLES = {"stock_daily", "stock_financial", "index_daily", "factor_values"}


def _get_boolean_columns(pg_inspector, table_name):
    """获取 PostgreSQL 表中类型为 BOOLEAN 的列名集合"""
    bool_cols = set()
    for col in pg_inspector.get_columns(table_name):
        col_type = str(col.get("type", "")).upper()
        if "BOOL" in col_type:
            bool_cols.add(col["name"])
    return bool_cols


def _get_integer_columns(pg_inspector, table_name):
    """获取 PostgreSQL 表中类型为 INTEGER 的列名集合（排除主键）"""
    int_cols = set()
    pk_cols = set()
    for col in pg_inspector.get_columns(table_name):
        if col.get("primary_key"):
            pk_cols.add(col["name"])
    for col in pg_inspector.get_columns(table_name):
        col_type = str(col.get("type", "")).upper()
        if "INT" in col_type and col["name"] not in pk_cols:
            int_cols.add(col["name"])
    return int_cols


def _convert_records(records, bool_columns, int_columns):
    """将 SQLite 的值转换为 PostgreSQL 兼容类型
    - 0/1 → bool (boolean 列)
    - 字符串数字 → int (integer 列)
    - 特殊映射: direction "desc"→1, "asc"→-1
    """
    # 语义映射：SQLite 中的字符串值 → PG 中的整数值
    VALUE_MAPS = {
        "direction": {"desc": 1, "asc": -1},
    }
    if not bool_columns and not int_columns:
        return records
    converted = []
    for rec in records:
        new_rec = {}
        for k, v in rec.items():
            if k in bool_columns and v is not None:
                new_rec[k] = bool(v)
            elif k in int_columns and v is not None and not isinstance(v, int):
                # 先尝试语义映射
                if k in VALUE_MAPS and str(v) in VALUE_MAPS[k]:
                    new_rec[k] = VALUE_MAPS[k][str(v)]
                else:
                    try:
                        new_rec[k] = int(v)
                    except (ValueError, TypeError):
                        new_rec[k] = v
            else:
                new_rec[k] = v
        converted.append(new_rec)
    return converted


def migrate():
    """执行数据迁移"""
    sqlite_engine = create_engine(SQLITE_PATH)
    pg_engine = create_engine(settings.DATABASE_URL)

    # 获取 SQLite 中的表列表
    sqlite_inspector = inspect(sqlite_engine)
    sqlite_tables = set(sqlite_inspector.get_table_names())

    # 获取 PostgreSQL 中的表列表
    pg_inspector = inspect(pg_engine)
    pg_tables = set(pg_inspector.get_table_names())

    logger.info(f"SQLite 表数: {len(sqlite_tables)}, PostgreSQL 表数: {len(pg_tables)}")

    total_rows = 0

    for table_name in TABLE_ORDER:
        if table_name not in sqlite_tables:
            logger.warning(f"  SKIP {table_name} (not in SQLite)")
            continue
        if table_name not in pg_tables:
            logger.warning(f"  SKIP {table_name} (not in PostgreSQL)")
            continue

        # 获取行数
        with sqlite_engine.connect() as conn:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()

        if count == 0:
            logger.info(f"  SKIP {table_name} (0 rows)")
            continue

        logger.info(f"  MIGRATING {table_name} ({count} rows)...")

        # 获取列信息
        pg_columns = [col["name"] for col in pg_inspector.get_columns(table_name)]
        sqlite_columns = [col["name"] for col in sqlite_inspector.get_columns(table_name)]

        # 只迁移两个数据库都有的列
        common_columns = [c for c in pg_columns if c in sqlite_columns]
        col_list = ", ".join(common_columns)

        # 获取 PostgreSQL 中的 boolean 列和 integer 列，用于类型转换
        bool_columns = _get_boolean_columns(pg_inspector, table_name)
        int_columns = _get_integer_columns(pg_inspector, table_name)

        if table_name in LARGE_TABLES and count > BATCH_SIZE:
            # 大表分批迁移
            migrated = _migrate_large_table(
                sqlite_engine, pg_engine, table_name, count, col_list, common_columns, bool_columns, int_columns
            )
        else:
            # 小表一次性迁移
            migrated = _migrate_small_table(
                sqlite_engine, pg_engine, table_name, col_list, common_columns, bool_columns, int_columns
            )

        total_rows += migrated
        logger.info(f"  DONE {table_name} ({migrated} rows)")

    # 修复所有序列值
    _fix_sequences(pg_engine)

    logger.info(f"\n迁移完成! 总计迁移 {total_rows} 行")


def _migrate_small_table(sqlite_engine, pg_engine, table_name, col_list, columns, bool_columns, int_columns):
    """迁移小表"""
    with sqlite_engine.connect() as src_conn:
        rows = src_conn.execute(text(f"SELECT {col_list} FROM {table_name}")).fetchall()

    if not rows:
        return 0

    # 转换为字典列表
    records = [dict(zip(columns, row)) for row in rows]
    records = _convert_records(records, bool_columns, int_columns)

    with pg_engine.connect() as dst_conn:
        dst_conn.execute(
            text(f"ALTER TABLE {table_name} DISABLE TRIGGER ALL"),
        )
        dst_conn.execute(
            text(f"INSERT INTO {table_name} ({col_list}) VALUES ({', '.join([':' + c for c in columns])})"),
            records,
        )
        dst_conn.execute(text(f"ALTER TABLE {table_name} ENABLE TRIGGER ALL"))
        dst_conn.commit()

    return len(records)


def _migrate_large_table(sqlite_engine, pg_engine, table_name, count, col_list, columns, bool_columns, int_columns):
    """分批迁移大表"""
    migrated = 0
    offset = 0

    # 使用 PostgreSQL COPY 更高效的方式：通过批量 INSERT
    insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({', '.join([':' + c for c in columns])})"

    with pg_engine.connect() as dst_conn:
        dst_conn.execute(text(f"ALTER TABLE {table_name} DISABLE TRIGGER ALL"))

        while offset < count:
            with sqlite_engine.connect() as src_conn:
                rows = src_conn.execute(
                    text(f"SELECT {col_list} FROM {table_name} LIMIT {BATCH_SIZE} OFFSET {offset}")
                ).fetchall()

            if not rows:
                break

            records = [dict(zip(columns, row)) for row in rows]
            records = _convert_records(records, bool_columns, int_columns)
            dst_conn.execute(text(insert_sql), records)
            dst_conn.commit()

            migrated += len(rows)
            offset += BATCH_SIZE
            logger.info(f"    {table_name}: {migrated}/{count}")

        dst_conn.execute(text(f"ALTER TABLE {table_name} ENABLE TRIGGER ALL"))
        dst_conn.commit()

    return migrated


def _fix_sequences(pg_engine):
    """修复 PostgreSQL 序列值，使自增 ID 从已有最大值继续"""
    pg_inspector = inspect(pg_engine)

    with pg_engine.connect() as conn:
        for table_name in pg_inspector.get_table_names():
            if table_name == "alembic_version":
                continue

            columns = pg_inspector.get_columns(table_name)
            for col in columns:
                if col.get("autoincrement") and col.get("primary_key"):
                    col_name = col["name"]
                    # 获取当前最大 ID
                    result = conn.execute(
                        text(f"SELECT COALESCE(MAX({col_name}), 0) FROM {table_name}")
                    ).scalar()

                    if result > 0:
                        seq_name = f"{table_name}_{col_name}_seq"
                        try:
                            conn.execute(
                                text(f"SELECT setval('{seq_name}', {result}, true)")
                            )
                        except Exception as e:
                            # 序列可能不存在或名称不同
                            logger.debug(f"  序列 {seq_name} 设置跳过: {e}")

        conn.commit()

    logger.info("序列值修复完成")


if __name__ == "__main__":
    print("开始 SQLite → PostgreSQL 数据迁移...")
    migrate()
