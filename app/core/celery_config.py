"""
Celery任务调度配置
实现ADD 4.3节: 异步任务调度 + 日终任务链
"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings
from app.core.logging import logger

# 创建Celery实例
celery_app = Celery(
    "quant_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    includes=[
        "app.tasks.backtests",
        "app.tasks.data_sync",
        "app.tasks.factor_calc",
        "app.tasks.model_score",
        "app.tasks.risk_check",
        "app.tasks.report_generate",
    ],
)

# Celery配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1小时超时
    task_soft_time_limit=3000,  # 50分钟软超时
    worker_prefetch_multiplier=1,
    worker_concurrency=8,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    broker_connection_max_retries=10,
    broker_connection_retry_delay=5,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
)

# ==================== 定时任务配置 (ADD 6.1节) ====================

celery_app.conf.beat_schedule = {
    # 日终数据同步 (ADD 6.1节: 步骤1-5)
    "daily-data-sync": {
        "task": "app.tasks.data_sync.run_daily_sync",
        "schedule": crontab(hour=15, minute=30),  # 15:30收盘后
    },
    # 因子计算 (ADD 6.1节: 步骤6)
    "daily-factor-calc": {
        "task": "app.tasks.factor_calc.run_daily_factor_calc",
        "schedule": crontab(hour=16, minute=0),
    },
    # 模型打分 (ADD 6.1节: 步骤7-8)
    "daily-model-score": {
        "task": "app.tasks.model_score.run_daily_model_score",
        "schedule": crontab(hour=16, minute=30),
    },
    # 风控检查 (ADD 6.1节: 步骤9-11)
    "daily-risk-check": {
        "task": "app.tasks.risk_check.run_daily_risk_check",
        "schedule": crontab(hour=17, minute=0),
    },
    # 报告生成 (ADD 6.1节: 步骤12)
    "daily-report-generate": {
        "task": "app.tasks.report_generate.run_daily_report_generate",
        "schedule": crontab(hour=17, minute=30),
    },
    # 清理过期任务
    "cleanup-old-tasks": {
        "task": "app.core.celery_config.cleanup_old_tasks",
        "schedule": crontab(hour=2, minute=0),  # 凌晨2点
    },
}


@celery_app.task(bind=True, max_retries=3)
def cleanup_old_tasks(self):
    """清理过期任务"""
    try:
        from app.db.base import SessionLocal
        from app.models.task_logs import TaskLog
        from datetime import datetime, timedelta

        db = SessionLocal()
        try:
            # 清理30天前的任务日志
            cutoff = datetime.now() - timedelta(days=30)
            deleted = db.query(TaskLog).filter(
                TaskLog.created_at < cutoff,
                TaskLog.status.in_(["success", "failed"]),
            ).delete()
            db.commit()
            logger.info(f"Cleaned up {deleted} old task records")
            return f"Deleted {deleted} records"
        finally:
            db.close()
    except Exception as exc:
        logger.error(f"Cleanup failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


if __name__ == "__main__":
    celery_app.start()
