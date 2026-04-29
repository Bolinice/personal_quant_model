"""
数据同步异步任务
"""

from datetime import datetime

from app.core.celery_config import celery_app
from app.core.logging import logger


@celery_app.task(bind=True, max_retries=3, name="app.tasks.data_sync.run_daily_sync")
def run_daily_sync(self):
    """日终数据同步任务"""
    try:
        from app.db.base import SessionLocal
        from app.services.data_sync_service import DataSyncService

        db = SessionLocal()
        try:
            service = DataSyncService()
            trade_date = datetime.now(tz=datetime.timezone.utc).date()
            result = service.run_daily_pipeline(trade_date.strftime("%Y-%m-%d"))
            logger.info(f"Daily sync completed: {result}")
            return result
        finally:
            db.close()
    except Exception as exc:
        logger.error(f"Daily sync failed: {exc}")
        raise self.retry(exc=exc, countdown=300) from exc
