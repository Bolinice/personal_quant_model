"""
添加财务数据表复合索引
优化查询性能: stock_financial表添加(ts_code, ann_date)和(ts_code, end_date)复合索引
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.core.logging import logger
from app.db.base import SessionLocal


def add_financial_indexes():
    """添加财务数据表复合索引"""
    db = SessionLocal()
    try:
        # 检查索引是否已存在
        check_sql = """
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'stock_financial'
        AND indexname IN ('ix_financial_code_ann', 'ix_financial_code_end');
        """
        result = db.execute(text(check_sql))
        existing = {row[0] for row in result}

        indexes_to_create = []
        if "ix_financial_code_ann" not in existing:
            indexes_to_create.append(
                "CREATE INDEX CONCURRENTLY ix_financial_code_ann ON stock_financial (ts_code, ann_date);"
            )
        if "ix_financial_code_end" not in existing:
            indexes_to_create.append(
                "CREATE INDEX CONCURRENTLY ix_financial_code_end ON stock_financial (ts_code, end_date);"
            )

        if not indexes_to_create:
            logger.info("所有索引已存在，无需创建")
            return

        # 使用CONCURRENTLY避免锁表
        for sql in indexes_to_create:
            logger.info(f"创建索引: {sql}")
            # CONCURRENTLY需要autocommit模式
            db.connection().connection.set_isolation_level(0)
            db.execute(text(sql))
            logger.info("索引创建成功")

        logger.info("所有索引创建完成")

    except Exception as e:
        logger.error(f"创建索引失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("开始添加财务数据表索引...")
    add_financial_indexes()
    logger.info("索引添加完成")
