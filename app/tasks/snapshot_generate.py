"""数据快照生成任务"""

from __future__ import annotations

import json
import subprocess
from datetime import date, datetime

from app.core.celery_config import celery_app
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


def _get_git_commit_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()[:8]
    except Exception:
        return "unknown"


@celery_app.task(bind=True, max_retries=3, name="app.tasks.snapshot_generate.generate_snapshot")
def generate_snapshot(self, trade_date: str | None = None):
    """
    生成每日数据快照

    - 快照ID: snap_YYYYMMDD_xxxxxxxx
    - 记录数据源版本/代码版本/配置版本
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        from app.models.data_snapshot_registry import DataSnapshotRegistry
        from app.models.factors import Factor
        from app.models.market import StockDaily
        from app.models.models import Model

        logger.info(f"开始生成数据快照, run_id={run_id}")

        task_log = _create_task_log(db, "snapshot", "数据快照生成", run_id, params={"trade_date": trade_date})

        if trade_date is None:
            calc_date = datetime.now(tz=datetime.timezone.utc).date()
        else:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date

        # 1. 收集代码版本
        code_version = _get_git_commit_hash()

        # 2. 收集数据源版本信息
        source_version = {}
        latest_stock = db.query(StockDaily.trade_date).order_by(StockDaily.trade_date.desc()).first()
        if latest_stock:
            source_version["stock_daily_latest"] = str(latest_stock[0])

        # 3. 收集配置快照
        active_factors = db.query(Factor).filter(Factor.is_active).all()
        active_models = db.query(Model).filter(Model.is_active).all()

        config_snapshot = {
            "active_factors": [
                {"factor_code": f.factor_code, "factor_name": f.factor_name, "category": f.category}
                for f in active_factors
            ],
            "active_models": [
                {"model_code": m.model_code, "model_name": m.name, "holding_count": getattr(m, "holding_count", 50)}
                for m in active_models
            ],
        }

        # 4. 生成快照ID
        snapshot_id = f"snap_{calc_date.strftime('%Y%m%d')}_{code_version}"

        # 5. 写入快照表
        existing = db.query(DataSnapshotRegistry).filter(DataSnapshotRegistry.snapshot_id == snapshot_id).first()
        if existing:
            logger.info(f"快照已存在: {snapshot_id}, 跳过")
            _update_task_log(db, task_log, "success", result={"snapshot_id": snapshot_id, "status": "skipped"})
            return {"status": "success", "snapshot_id": snapshot_id, "skipped": True}

        snapshot = DataSnapshotRegistry(
            snapshot_id=snapshot_id,
            snapshot_date=calc_date,
            description=f"每日数据快照 {calc_date}",
            source_version_json=json.dumps(source_version, ensure_ascii=False),
            code_version=code_version,
        )
        db.add(snapshot)
        db.commit()

        result = {
            "snapshot_id": snapshot_id,
            "trade_date": str(calc_date),
            "code_version": code_version,
            "n_active_factors": len(active_factors),
            "n_active_models": len(active_models),
        }
        _update_task_log(db, task_log, "success", result=result)

        logger.info(f"数据快照生成完成: {snapshot_id}")
        return {"status": "success", **result}

    except Exception as exc:
        logger.error(f"数据快照生成失败: {exc}")
        with contextlib.suppress(Exception):
            _update_task_log(db, task_log, "failed", error=exc)
        raise self.retry(exc=exc, countdown=300) from exc
    finally:
        db.close()


import contextlib
