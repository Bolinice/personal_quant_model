"""事件数据同步任务"""

from __future__ import annotations

import contextlib
from datetime import date, datetime, timedelta

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


# 事件类型到Tushare API的映射
EVENT_SYNC_CONFIG = {
    "earnings_preview": {
        "api_name": "fina_forecast",
        "severity": "info",
        "title_template": "业绩预告: {ts_code}",
    },
    "reduction": {
        "api_name": "stk_reduce",
        "severity": "warning",
        "title_template": "减持公告: {ts_code}",
    },
    "pledge": {
        "api_name": "pledge",
        "severity": "warning",
        "title_template": "股权质押: {ts_code}",
    },
    "repurchase": {
        "api_name": "repurchase",
        "severity": "info",
        "title_template": "回购公告: {ts_code}",
    },
    "unlock": {
        "api_name": "share_float",
        "severity": "warning",
        "title_template": "限售解禁: {ts_code}",
    },
}


def _sync_event_type(db, source, event_type: str, config: dict, trade_date: date) -> int:
    """同步单类事件数据，返回写入记录数"""
    from app.models.event_center import EventCenter
    from app.models.market import StockBasic

    api_name = config["api_name"]
    severity = config["severity"]
    title_template = config["title_template"]

    try:
        # 调用Tushare pro API
        pro = source.pro
        api_func = getattr(pro, api_name, None)
        if api_func is None:
            logger.warning(f"Tushare API {api_name} 不可用")
            return 0

        date_str = trade_date.strftime("%Y%m%d")
        df = api_func(trade_date=date_str)

        if df is None or df.empty:
            return 0

        # 获取股票ID映射
        ts_codes = df["ts_code"].unique().tolist() if "ts_code" in df.columns else []
        stock_map = {}
        if ts_codes:
            stocks = db.query(StockBasic).filter(StockBasic.ts_code.in_(ts_codes)).all()
            stock_map = {s.ts_code: s.id for s in stocks}

        n_records = 0
        for _, row in df.iterrows():
            ts_code = row.get("ts_code", "")
            stock_id = stock_map.get(ts_code)
            if not stock_id:
                continue

            title = title_template.format(ts_code=ts_code)

            # 构建事件内容
            content_parts = []
            for col in row.index:
                if col != "ts_code" and pd.notna(row[col]):
                    content_parts.append(f"{col}: {row[col]}")
            content = "; ".join(content_parts[:10])  # 限制长度

            record = EventCenter(
                stock_id=stock_id,
                event_type=event_type,
                event_date=trade_date,
                severity=severity,
                title=title,
                content=content,
                source="tushare",
            )
            db.add(record)
            n_records += 1

        return n_records

    except Exception as e:
        logger.warning(f"同步事件类型 {event_type} 失败: {e}")
        return 0


@celery_app.task(bind=True, max_retries=3, name="app.tasks.event_sync.sync_event_data")
def sync_event_data(self, trade_date: str | None = None):
    """
    同步事件数据(业绩预告/问询函/立案处罚/减持/股权质押等)

    数据源: Tushare
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        import pandas as pd

        from app.core.config import settings
        from app.data_sources.tushare_source import TushareSource

        logger.info(f"开始同步事件数据, run_id={run_id}")

        task_log = _create_task_log(db, "event_sync", "事件数据同步", run_id, params={"trade_date": trade_date})

        if trade_date is None:
            calc_date = datetime.now(tz=datetime.timezone.utc).date() - timedelta(days=1)
        else:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date

        source = TushareSource(token=settings.TUSHARE_TOKEN, proxy_url=settings.TUSHARE_PROXY_URL)
        sync_results = {}

        # 同步各类事件
        for event_type, config in EVENT_SYNC_CONFIG.items():
            n = _sync_event_type(db, source, event_type, config, calc_date)
            sync_results[event_type] = n

        # 问询函/立案处罚: Tushare暂无直接API，记录为不可用
        for unavailable_type in ["regulatory_inquiry", "regulatory_penalty"]:
            sync_results[unavailable_type] = -1  # -1 表示数据暂不可用

        db.commit()

        total = sum(v for v in sync_results.values() if v > 0)
        result_data = {
            "trade_date": str(calc_date),
            "sync_results": sync_results,
            "total_events": total,
        }
        _update_task_log(db, task_log, "success", result=result_data)

        logger.info(f"事件数据同步完成: {total} events")
        return {"status": "success", **result_data}

    except Exception as exc:
        logger.error(f"事件数据同步失败: {exc}")
        with contextlib.suppress(Exception):
            _update_task_log(db, task_log, "failed", error=exc)
        raise self.retry(exc=exc, countdown=300) from exc
    finally:
        db.close()
