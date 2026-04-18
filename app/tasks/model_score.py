"""
模型打分异步任务
"""
from app.core.celery_config import celery_app
from app.core.logging import logger


@celery_app.task(bind=True, max_retries=3, name="app.tasks.model_score.run_daily_model_score")
def run_daily_model_score(self):
    """日终模型打分任务"""
    try:
        logger.info("Daily model scoring started")
        # TODO: 实现模型打分逻辑
        logger.info("Daily model scoring completed")
        return {"status": "success"}
    except Exception as exc:
        logger.error(f"Model scoring failed: {exc}")
        raise self.retry(exc=exc, countdown=300)
