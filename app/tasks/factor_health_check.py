"""因子健康检查任务"""

from __future__ import annotations

import contextlib
from datetime import date, datetime

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

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


def _build_module_ic_map(db, calc_date: date, lookback: int = 60) -> dict[str, pd.Series]:
    """构建模块IC映射: {module_name: ic_series}"""
    from app.core.alpha_modules import MODULE_REGISTRY
    from app.models.factors import Factor, FactorValue
    from app.models.market import StockDaily

    module_ic_map = {}

    # 获取最近lookback个交易日
    recent_dates = (
        db.query(StockDaily.trade_date)
        .filter(StockDaily.trade_date <= calc_date)
        .distinct()
        .order_by(StockDaily.trade_date.desc())
        .limit(lookback)
        .all()
    )
    date_list = sorted([d[0] for d in recent_dates])

    if len(date_list) < 10:
        return module_ic_map

    # 按模块分组因子
    module_factors = {}
    for module_name, module in MODULE_REGISTRY.items():
        if module_name == "risk_penalty":
            continue
        factor_codes = list(module.FACTOR_CONFIG.keys()) if hasattr(module, "FACTOR_CONFIG") else []
        module_factors[module_name] = factor_codes

    # 查询因子定义
    all_factor_codes = [c for codes in module_factors.values() for c in codes]
    factor_defs = db.query(Factor).filter(Factor.factor_code.in_(all_factor_codes)).all()
    factor_id_map = {f.factor_code: f.id for f in factor_defs}

    # 查询因子值
    factor_ids = list(factor_id_map.values())
    if not factor_ids:
        return module_ic_map

    fv_rows = (
        db.query(FactorValue)
        .filter(
            FactorValue.factor_id.in_(factor_ids),
            FactorValue.trade_date.in_(date_list),
        )
        .all()
    )

    if not fv_rows:
        return module_ic_map

    fv_df = pd.DataFrame(
        [
            {
                "factor_id": r.factor_id,
                "trade_date": r.trade_date,
                "security_id": r.security_id,
                "value": float(r.value) if r.value is not None else np.nan,
            }
            for r in fv_rows
        ]
    )

    # 查询次日收益
    next_dates = date_list[1:] + [date_list[-1]]  # 最后一日无次日收益
    stock_rows = (
        db.query(StockDaily.ts_code, StockDaily.trade_date, StockDaily.pct_chg)
        .filter(StockDaily.trade_date.in_(date_list))
        .all()
    )
    stock_df = pd.DataFrame(
        [
            {
                "ts_code": r.ts_code,
                "trade_date": r.trade_date,
                "pct_chg": float(r.pct_chg) if r.pct_chg is not None else np.nan,
            }
            for r in stock_rows
        ]
    )

    if stock_df.empty:
        return module_ic_map

    # 按模块计算截面IC
    for module_name, factor_codes in module_factors.items():
        ic_values = []
        ic_dates = []

        module_factor_ids = [factor_id_map[c] for c in factor_codes if c in factor_id_map]
        if not module_factor_ids:
            continue

        module_fv = fv_df[fv_df["factor_id"].isin(module_factor_ids)]
        if module_fv.empty:
            continue

        # 按日期取模块平均因子值
        module_scores = module_fv.groupby(["trade_date", "security_id"])["value"].mean().reset_index()

        for i, dt in enumerate(date_list[:-1]):
            day_scores = module_scores[module_scores["trade_date"] == dt]
            next_dt = date_list[i + 1]
            next_returns = stock_df[stock_df["trade_date"] == next_dt][["ts_code", "pct_chg"]]

            if day_scores.empty or next_returns.empty:
                continue

            merged = day_scores.merge(next_returns, left_on="security_id", right_on="ts_code", how="inner")
            if len(merged) < 30:
                continue

            try:
                ic, _ = spearmanr(merged["value"].dropna(), merged.loc[merged["value"].notna(), "pct_chg"])
                if not np.isnan(ic):
                    ic_values.append(ic)
                    ic_dates.append(dt)
            except Exception:
                continue

        if ic_values:
            module_ic_map[module_name] = pd.Series(ic_values, index=ic_dates)

    return module_ic_map


@celery_app.task(bind=True, max_retries=3, name="app.tasks.factor_health_check.check_factor_health")
def check_factor_health(self, trade_date: str | None = None):
    """
    因子健康检查

    - IC漂移检测
    - PSI分布漂移
    - 覆盖率检查
    - 模块相关性检查
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        from app.models.alert_logs import AlertLog
        from app.models.monitor_factor_health import MonitorFactorHealth

        logger.info(f"开始因子健康检查, run_id={run_id}")

        task_log = _create_task_log(db, "factor_health", "因子健康检查", run_id, params={"trade_date": trade_date})

        if trade_date is None:
            calc_date = datetime.now(tz=datetime.timezone.utc).date()
        else:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date

        # 构建模块IC映射
        module_ic_map = _build_module_ic_map(db, calc_date)

        # 调用 FactorMonitor 健康检查
        monitor = FactorMonitor()
        health_results = monitor.check_all_modules(module_ic_map)

        # 写入 MonitorFactorHealth 表
        n_healthy = 0
        n_unhealthy = 0

        for module_name, result in health_results.items():
            details = result.get("details", {})
            is_healthy = result.get("is_healthy", True)

            # 确定健康状态
            if is_healthy:
                status = "healthy"
                n_healthy += 1
            else:
                alerts = result.get("alerts", [])
                if any("critical" in str(a).lower() for a in alerts):
                    status = "critical"
                else:
                    status = "warning"
                n_unhealthy += 1

            # 写入监控表
            record = MonitorFactorHealth(
                trade_date=calc_date,
                factor_name=module_name,
                coverage_rate=details.get("coverage"),
                ic_rolling=details.get("ic_drift", {}).get("ic_recent"),
                ic_mean=details.get("ic_mean"),
                icir=details.get("ir"),
                psi=details.get("psi"),
                health_status=status,
            )
            db.add(record)

            # 不健康因子创建告警
            if not is_healthy:
                for alert_msg in result.get("alerts", []):
                    alert = AlertLog(
                        alert_type="data",
                        severity="warning" if status == "warning" else "critical",
                        title=f"因子健康异常: {module_name}",
                        message=alert_msg,
                        status="pending",
                    )
                    db.add(alert)

        db.commit()

        result_data = {
            "trade_date": str(calc_date),
            "n_healthy": n_healthy,
            "n_unhealthy": n_unhealthy,
        }
        _update_task_log(db, task_log, "success", result=result_data)

        logger.info(f"因子健康检查完成: {n_healthy} healthy, {n_unhealthy} unhealthy")
        return {"status": "success", **result_data}

    except Exception as exc:
        logger.error(f"因子健康检查失败: {exc}")
        with contextlib.suppress(Exception):
            _update_task_log(db, task_log, "failed", error=exc)
        raise self.retry(exc=exc, countdown=300) from exc
    finally:
        db.close()
