"""
数据同步异步任务 - 使用统一异常处理和重试机制
"""

from datetime import datetime

from app.core.celery_config import celery_app
from app.core.logging import logger
from app.core.retry import CELERY_RETRY_CONFIG
from app.core.exceptions import DataSourceException, DatabaseException


@celery_app.task(
    bind=True,
    name="app.tasks.data_sync.run_daily_sync",
    **CELERY_RETRY_CONFIG,  # 使用统一的重试配置
)
def run_daily_sync(self):
    """
    日终数据同步任务

    自动重试配置:
    - 最大重试次数: 3次
    - 重试间隔: 60秒起，指数退避
    - 可重试异常: DataSourceException, DatabaseException
    """
    try:
        from app.core.config import settings
        from app.db.base import SessionLocal
        from app.services.data_sync_service import DataSyncService

        db = SessionLocal()
        try:
            service = DataSyncService(
                primary_source=settings.PRIMARY_DATA_SOURCE,
                tushare_token=settings.TUSHARE_TOKEN if settings.TUSHARE_TOKEN else None,
                tushare_proxy_url=settings.TUSHARE_PROXY_URL if settings.TUSHARE_PROXY_URL else None,
            )
            trade_date = datetime.now(tz=datetime.timezone.utc).date()
            result = service.run_daily_pipeline(trade_date.strftime("%Y-%m-%d"))
            logger.info(f"Daily sync completed: {result}")
            return result
        finally:
            db.close()
    except (DataSourceException, DatabaseException) as exc:
        # 这些异常会被Celery自动重试
        logger.warning(f"Daily sync failed (will retry): {exc}")
        raise
    except Exception as exc:
        # 其他异常不重试，直接失败
        logger.error(f"Daily sync failed (no retry): {exc}")
        raise


@celery_app.task(
    bind=True,
    name="app.tasks.data_sync.sync_stock_daily",
    **CELERY_RETRY_CONFIG,
)
def sync_stock_daily(self, ts_code: str, start_date: str, end_date: str):
    """
    同步单只股票日线数据

    Args:
        ts_code: 股票代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
    """
    try:
        from app.core.config import settings
        from app.db.base import SessionLocal
        from app.services.data_sync_service import DataSyncService

        db = SessionLocal()
        try:
            service = DataSyncService(
                primary_source=settings.PRIMARY_DATA_SOURCE,
                tushare_token=settings.TUSHARE_TOKEN if settings.TUSHARE_TOKEN else None,
            )
            result = service.sync_stock_daily(ts_code, start_date, end_date)
            logger.info(f"Synced {ts_code} daily data: {result}")
            return result
        finally:
            db.close()
    except (DataSourceException, DatabaseException) as exc:
        logger.warning(f"Sync {ts_code} failed (will retry): {exc}")
        raise
    except Exception as exc:
        logger.error(f"Sync {ts_code} failed (no retry): {exc}")
        raise


@celery_app.task(
    bind=True,
    name="app.tasks.data_sync.sync_financial_data",
    **CELERY_RETRY_CONFIG,
)
def sync_financial_data(self, ts_code: str, start_date: str, end_date: str):
    """
    同步单只股票财务数据

    Args:
        ts_code: 股票代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
    """
    try:
        from app.core.config import settings
        from app.db.base import SessionLocal
        from app.services.data_sync_service import DataSyncService

        db = SessionLocal()
        try:
            service = DataSyncService(
                primary_source=settings.PRIMARY_DATA_SOURCE,
                tushare_token=settings.TUSHARE_TOKEN if settings.TUSHARE_TOKEN else None,
            )
            result = service.sync_financial_data(ts_code, start_date, end_date)
            logger.info(f"Synced {ts_code} financial data: {result}")
            return result
        finally:
            db.close()
    except (DataSourceException, DatabaseException) as exc:
        logger.warning(f"Sync {ts_code} financial failed (will retry): {exc}")
        raise
    except Exception as exc:
        logger.error(f"Sync {ts_code} financial failed (no retry): {exc}")
        raise
