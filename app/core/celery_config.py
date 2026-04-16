from celery import Celery
from app.core.config import settings
from app.core.logging import logger

# 创建Celery实例
celery_app = Celery(
    "quant_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    includes=[
        "app.tasks.backtests",
    ]
)

# Celery配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000,
    worker_prefetch_multiplier=1,
    worker_concurrency=10,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    broker_connection_max_retries=10,
    broker_connection_retry_delay=5,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
)

@celery_app.task(bind=True, max_retries=3)
def cleanup_old_tasks(self):
    """清理过期任务"""
    try:
        # 这里可以添加清理逻辑
        logger.info("Cleaning up old tasks...")
        return "Cleanup completed"
    except Exception as exc:
        logger.error(f"Cleanup failed: {exc}")
        raise self.retry(exc=exc, countdown=60)

def setup_periodic_tasks(sender, **kwargs):
    """设置定时任务"""
    # 每天清理过期任务
    sender.add_periodic_task(
        3600 * 24,  # 每天
        cleanup_old_tasks.s(),
        name="cleanup-old-tasks"
    )

# 启动时的任务
celery_app.on_after_configure.connect(setup_periodic_tasks)

if __name__ == "__main__":
    celery_app.start()