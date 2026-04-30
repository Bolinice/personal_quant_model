"""模型漂移监控任务"""

from __future__ import annotations

import contextlib
from datetime import date, datetime

import numpy as np
import pandas as pd

from app.core.celery_config import celery_app
from app.core.factor_monitor import FactorMonitor
from app.core.logging import logger
from app.db.base import SessionLocal


def _create_task_log(db, task_type, task_name, run_id, params=None):
    from app.models.task_logs import TaskLog

    log = TaskLog(
        task_type=task_type,
        task_name=task_name,
        run_id=run_id,
        status="running",
        params_json=params,
        started_at=datetime.now(tz=datetime.timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _update_task_log(db, log, status, result=None, error=None):
    log.status = status
    log.ended_at = datetime.now(tz=datetime.timezone.utc)
    log.duration = (log.ended_at - log.started_at).total_seconds()
    if result:
        log.result_json = result
    if error:
        log.error_message = str(error)[:2000]
    db.commit()


@celery_app.task(bind=True, max_retries=3, name="app.tasks.model_drift_monitor.check_model_drift")
def check_model_drift(self, trade_date: str | None = None):
    """
    模型漂移监控

    - 预测分布漂移 (PSI)
    - KS检验
    - OOS偏差
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        from app.models.alert_logs import AlertLog
        from app.models.models import Model, ModelScore
        from app.models.monitor_model_health import MonitorModelHealth

        logger.info(f"开始模型漂移监控, run_id={run_id}")

        task_log = _create_task_log(db, "model_drift", "模型漂移监控", run_id, params={"trade_date": trade_date})

        if trade_date is None:
            calc_date = datetime.now(tz=datetime.timezone.utc).date()
        else:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date

        # 获取活跃模型
        active_models = db.query(Model).filter(Model.is_active).all()
        if not active_models:
            logger.warning("无活跃模型")
            _update_task_log(db, task_log, "success", result={"models_checked": 0})
            return {"status": "success", "models_checked": 0}

        monitor = FactorMonitor()
        n_anomaly = 0
        n_healthy = 0

        for model in active_models:
            # 获取当前日期的模型分数分布
            current_scores = (
                db.query(ModelScore.score)
                .filter(ModelScore.model_id == model.id, ModelScore.trade_date == calc_date)
                .all()
            )
            current_values = pd.Series([float(s[0]) for s in current_scores if s[0] is not None])

            if len(current_values) < 30:
                # 样本不足，标记为healthy但记录样本量
                record = MonitorModelHealth(
                    trade_date=calc_date,
                    model_id=str(model.id),
                    health_status="healthy",
                )
                db.add(record)
                n_healthy += 1
                continue

            # 获取参考分布（30天前的分数）
            from sqlalchemy import func

            ref_date_row = (
                db.query(func.max(ModelScore.trade_date))
                .filter(ModelScore.model_id == model.id, ModelScore.trade_date < calc_date)
                .first()
            )
            ref_date = ref_date_row[0] if ref_date_row and ref_date_row[0] else None

            ref_values = pd.Series()
            if ref_date:
                ref_scores = (
                    db.query(ModelScore.score)
                    .filter(ModelScore.model_id == model.id, ModelScore.trade_date == ref_date)
                    .all()
                )
                ref_values = pd.Series([float(s[0]) for s in ref_scores if s[0] is not None])

            # 计算PSI
            psi_val = 0.0
            if len(ref_values) >= 30:
                psi_val = monitor.psi(current_values, ref_values)

            # 计算KS
            ks_result = {"ks_statistic": 0, "p_value": 1.0, "is_significant": False}
            if len(ref_values) >= 30:
                ks_result = monitor.rolling_ks(current_values, ref_values)

            # 判定异常
            is_anomaly = psi_val >= 0.25 or ks_result.get("is_significant", False)

            # OOS偏差：当前分数均值与参考分数均值的差异
            oos_score = None
            if len(ref_values) >= 30:
                oos_score = float(current_values.mean() - ref_values.mean())

            # 健康状态
            if is_anomaly:
                status = "critical" if psi_val >= 0.25 else "warning"
                n_anomaly += 1
            else:
                status = "healthy"
                n_healthy += 1

            # 写入监控表
            record = MonitorModelHealth(
                trade_date=calc_date,
                model_id=str(model.id),
                prediction_drift=psi_val,
                feature_importance_drift=ks_result.get("ks_statistic"),
                oos_score=oos_score,
                health_status=status,
            )
            db.add(record)

            # 异常模型创建告警
            if is_anomaly:
                alert_msg = f"模型{model.name or model.id}漂移异常: PSI={psi_val:.4f}, KS={ks_result.get('ks_statistic', 0):.4f}"
                alert = AlertLog(
                    alert_type="performance",
                    severity="warning" if status == "warning" else "critical",
                    title=f"模型漂移异常: {model.name or model.id}",
                    message=alert_msg,
                    status="pending",
                )
                db.add(alert)

        db.commit()

        result_data = {
            "trade_date": str(calc_date),
            "models_checked": len(active_models),
            "n_healthy": n_healthy,
            "n_anomaly": n_anomaly,
        }
        _update_task_log(db, task_log, "success", result=result_data)

        logger.info(f"模型漂移监控完成: {n_healthy} healthy, {n_anomaly} anomaly")
        return {"status": "success", **result_data}

    except Exception as exc:
        logger.error(f"模型漂移监控失败: {exc}")
        with contextlib.suppress(Exception):
            _update_task_log(db, task_log, "failed", error=exc)
        raise self.retry(exc=exc, countdown=300) from exc
    finally:
        db.close()
