"""模型漂移监控任务（优化版）

优化：批量查询所有模型的分数数据，消除N+1查询
"""

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


@celery_app.task(bind=True, max_retries=3, name="app.tasks.model_drift_monitor_optimized.check_model_drift")
def check_model_drift(self, trade_date: str | None = None):
    """
    模型漂移监控（优化版）

    - 预测分布漂移 (PSI)
    - KS检验
    - OOS偏差

    优化：批量查询所有模型的分数数据，消除N+1查询
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        from sqlalchemy import func

        from app.models.alert_logs import AlertLog
        from app.models.models import Model, ModelScore
        from app.models.monitor_model_health import MonitorModelHealth

        logger.info(f"开始模型漂移监控 (optimized), run_id={run_id}")

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

        model_ids = [m.id for m in active_models]

        # === 批量查询所有模型的当前分数（1次查询）===
        current_scores_list = (
            db.query(ModelScore.model_id, ModelScore.score)
            .filter(
                ModelScore.model_id.in_(model_ids),
                ModelScore.trade_date == calc_date
            )
            .all()
        )

        # 按模型ID分组
        current_scores_map = {}
        for model_id, score in current_scores_list:
            if model_id not in current_scores_map:
                current_scores_map[model_id] = []
            if score is not None:
                current_scores_map[model_id].append(float(score))

        # === 批量查询所有模型的参考日期（1次查询）===
        ref_dates_subq = (
            db.query(
                ModelScore.model_id,
                func.max(ModelScore.trade_date).label("max_date")
            )
            .filter(
                ModelScore.model_id.in_(model_ids),
                ModelScore.trade_date < calc_date
            )
            .group_by(ModelScore.model_id)
            .subquery()
        )

        ref_dates_list = db.query(ref_dates_subq).all()
        ref_dates_map = {row[0]: row[1] for row in ref_dates_list}

        # === 批量查询所有模型的参考分数（1次查询）===
        if ref_dates_map:
            # 构建 (model_id, ref_date) 对的查询条件
            from sqlalchemy import and_, or_

            conditions = [
                and_(
                    ModelScore.model_id == model_id,
                    ModelScore.trade_date == ref_date
                )
                for model_id, ref_date in ref_dates_map.items()
            ]

            ref_scores_list = (
                db.query(ModelScore.model_id, ModelScore.score)
                .filter(or_(*conditions))
                .all()
            )

            # 按模型ID分组
            ref_scores_map = {}
            for model_id, score in ref_scores_list:
                if model_id not in ref_scores_map:
                    ref_scores_map[model_id] = []
                if score is not None:
                    ref_scores_map[model_id].append(float(score))
        else:
            ref_scores_map = {}

        # === 处理每个模型（从内存中获取数据，无需查询）===
        monitor = FactorMonitor()
        n_anomaly = 0
        n_healthy = 0
        health_records = []
        alert_records = []

        for model in active_models:
            current_values = pd.Series(current_scores_map.get(model.id, []))

            if len(current_values) < 30:
                # 样本不足，标记为healthy但记录样本量
                health_records.append({
                    "trade_date": calc_date,
                    "model_id": str(model.id),
                    "health_status": "healthy",
                })
                n_healthy += 1
                continue

            # 获取参考分布
            ref_values = pd.Series(ref_scores_map.get(model.id, []))

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

            # 准备健康记录
            health_records.append({
                "trade_date": calc_date,
                "model_id": str(model.id),
                "prediction_drift": psi_val,
                "feature_importance_drift": ks_result.get("ks_statistic"),
                "oos_score": oos_score,
                "health_status": status,
            })

            # 异常模型准备告警记录
            if is_anomaly:
                alert_msg = f"模型{model.name or model.id}漂移异常: PSI={psi_val:.4f}, KS={ks_result.get('ks_statistic', 0):.4f}"
                alert_records.append({
                    "alert_type": "performance",
                    "severity": "warning" if status == "warning" else "critical",
                    "title": f"模型漂移异常: {model.name or model.id}",
                    "message": alert_msg,
                    "status": "pending",
                })

        # === 批量插入健康记录和告警记录 ===
        if health_records:
            db.bulk_insert_mappings(MonitorModelHealth, health_records)

        if alert_records:
            db.bulk_insert_mappings(AlertLog, alert_records)

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
