"""
报告生成异步任务（优化版）
实现ADD 6.1节步骤12: 日终报告生成

优化：消除N+1查询，批量查询所有模型的表现、组合和持仓数据
"""

from __future__ import annotations

import contextlib
from datetime import date, datetime

from app.core.celery_config import celery_app
from app.core.logging import logger
from app.db.base import SessionLocal


def _create_task_log(db, task_type, task_name, run_id, params=None):
    """创建任务日志"""
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
    """更新任务日志"""
    log.status = status
    log.ended_at = datetime.now(tz=datetime.timezone.utc)
    log.duration = (log.ended_at - log.started_at).total_seconds()
    if result:
        log.result_json = result
    if error:
        log.error_message = str(error)[:2000]
    db.commit()


@celery_app.task(bind=True, max_retries=3, name="app.tasks.report_generate_optimized.run_daily_report_generate")
def run_daily_report_generate(self, trade_date: str | None = None, report_types: list | None = None):
    """
    日终报告生成任务（优化版）
    流程: 获取待生成报告 → 汇总数据 → 生成报告内容 → 更新状态

    优化：批量查询所有模型的表现、组合和持仓数据，消除N+1查询
    """
    run_id = self.request.id
    db = SessionLocal()

    try:
        import json

        from sqlalchemy import func

        from app.models.factors import Factor, FactorAnalysis
        from app.models.models import Model, ModelPerformance
        from app.models.portfolios import Portfolio, PortfolioPosition
        from app.models.reports import Report
        from app.models.task_logs import TaskLog

        logger.info(f"Daily report generation started (optimized), run_id={run_id}")

        # 创建任务日志
        task_log = _create_task_log(
            db,
            "report_generate",
            "日终报告生成",
            run_id,
            params={"trade_date": trade_date, "report_types": report_types},
        )

        # 确定计算日期
        if trade_date:
            calc_date = date.fromisoformat(trade_date) if isinstance(trade_date, str) else trade_date
        else:
            calc_date = datetime.now(tz=datetime.timezone.utc).date()

        if report_types is None:
            report_types = ["daily", "factor", "risk"]

        generated_reports = []
        errors = []

        # === 1. 日报: 模型表现汇总（优化版）===
        if "daily" in report_types:
            try:
                active_models = db.query(Model).filter(Model.status == "active").all()

                if not active_models:
                    logger.warning("No active models found")
                    model_summaries = []
                else:
                    model_ids = [m.id for m in active_models]

                    # 批量查询所有模型的最新表现（1次查询）
                    from sqlalchemy import distinct
                    from sqlalchemy.orm import aliased

                    # 子查询：获取每个模型的最新日期
                    subq = (
                        db.query(
                            ModelPerformance.model_id,
                            func.max(ModelPerformance.trade_date).label("max_date")
                        )
                        .filter(
                            ModelPerformance.model_id.in_(model_ids),
                            ModelPerformance.trade_date <= calc_date
                        )
                        .group_by(ModelPerformance.model_id)
                        .subquery()
                    )

                    # 批量查询最新表现
                    perf_list = (
                        db.query(ModelPerformance)
                        .join(
                            subq,
                            (ModelPerformance.model_id == subq.c.model_id) &
                            (ModelPerformance.trade_date == subq.c.max_date)
                        )
                        .all()
                    )
                    perf_map = {p.model_id: p for p in perf_list}

                    # 批量查询所有模型的最新组合（1次查询）
                    subq2 = (
                        db.query(
                            Portfolio.model_id,
                            func.max(Portfolio.trade_date).label("max_date")
                        )
                        .filter(Portfolio.model_id.in_(model_ids))
                        .group_by(Portfolio.model_id)
                        .subquery()
                    )

                    portfolio_list = (
                        db.query(Portfolio)
                        .join(
                            subq2,
                            (Portfolio.model_id == subq2.c.model_id) &
                            (Portfolio.trade_date == subq2.c.max_date)
                        )
                        .all()
                    )
                    portfolio_map = {p.model_id: p for p in portfolio_list}

                    # 批量查询所有组合的持仓数（1次查询）
                    portfolio_ids = [p.id for p in portfolio_list]
                    if portfolio_ids:
                        position_counts = (
                            db.query(
                                PortfolioPosition.portfolio_id,
                                func.count(PortfolioPosition.id).label("count")
                            )
                            .filter(PortfolioPosition.portfolio_id.in_(portfolio_ids))
                            .group_by(PortfolioPosition.portfolio_id)
                            .all()
                        )
                        position_count_map = {pc[0]: pc[1] for pc in position_counts}
                    else:
                        position_count_map = {}

                    # 构建模型汇总（从内存中获取数据，无需查询）
                    model_summaries = []
                    for model in active_models:
                        perf = perf_map.get(model.id)
                        portfolio = portfolio_map.get(model.id)
                        position_count = 0
                        if portfolio:
                            position_count = position_count_map.get(portfolio.id, 0)

                        model_summaries.append(
                            {
                                "model_id": model.id,
                                "model_code": model.model_code,
                                "model_name": model.model_name,
                                "daily_return": float(perf.daily_return) if perf and perf.daily_return else None,
                                "cumulative_return": float(perf.cumulative_return)
                                if perf and perf.cumulative_return
                                else None,
                                "max_drawdown": float(perf.max_drawdown) if perf and perf.max_drawdown else None,
                                "sharpe_ratio": float(perf.sharpe_ratio) if perf and perf.sharpe_ratio else None,
                                "ic": float(perf.ic) if perf and perf.ic else None,
                                "turnover": float(perf.turnover) if perf and perf.turnover else None,
                                "num_selected": perf.num_selected if perf else 0,
                                "position_count": position_count,
                            }
                        )

                # 获取今日任务执行情况
                today_tasks = (
                    db.query(TaskLog)
                    .filter(
                        func.date(TaskLog.created_at) == calc_date,
                    )
                    .all()
                )

                task_summary = {
                    "total": len(today_tasks),
                    "success": sum(1 for t in today_tasks if t.status == "success"),
                    "failed": sum(1 for t in today_tasks if t.status == "failed"),
                    "running": sum(1 for t in today_tasks if t.status == "running"),
                }

                # 生成日报内容
                content = _generate_daily_report_content(calc_date, model_summaries, task_summary)

                # 创建报告记录
                report = Report(
                    title=f"日报 {calc_date}",
                    report_type="daily",
                    report_date=calc_date,
                    content=content,
                    summary=json.dumps(
                        {
                            "models": len(model_summaries),
                            "tasks": task_summary,
                        },
                        ensure_ascii=False,
                    ),
                    status="generated",
                    meta_json={"run_id": run_id},
                )
                db.add(report)
                db.commit()
                db.refresh(report)

                generated_reports.append({"type": "daily", "report_id": report.id})

            except Exception as e:
                errors.append(f"Daily report failed: {e!s}")
                logger.error(f"Daily report generation failed: {e}")

        # === 2. 因子报告: IC/衰减/分组（优化版）===
        if "factor" in report_types:
            try:
                active_factors = db.query(Factor).filter(Factor.is_active).all()

                if not active_factors:
                    logger.warning("No active factors found")
                    factor_summaries = []
                else:
                    factor_ids = [f.id for f in active_factors]

                    # 批量查询所有因子的最新分析结果（1次查询）
                    subq = (
                        db.query(
                            FactorAnalysis.factor_id,
                            func.max(FactorAnalysis.analysis_date).label("max_date")
                        )
                        .filter(
                            FactorAnalysis.factor_id.in_(factor_ids),
                            FactorAnalysis.analysis_date <= calc_date
                        )
                        .group_by(FactorAnalysis.factor_id)
                        .subquery()
                    )

                    analysis_list = (
                        db.query(FactorAnalysis)
                        .join(
                            subq,
                            (FactorAnalysis.factor_id == subq.c.factor_id) &
                            (FactorAnalysis.analysis_date == subq.c.max_date)
                        )
                        .all()
                    )
                    analysis_map = {a.factor_id: a for a in analysis_list}

                    # 构建因子汇总（从内存中获取数据，无需查询）
                    factor_summaries = []
                    for factor in active_factors:
                        analysis = analysis_map.get(factor.id)

                        factor_summaries.append(
                            {
                                "factor_id": factor.id,
                                "factor_code": factor.factor_code,
                                "factor_name": factor.factor_name,
                                "category": factor.category,
                                "ic": float(analysis.ic) if analysis and analysis.ic else None,
                                "rank_ic": float(analysis.rank_ic) if analysis and analysis.rank_ic else None,
                                "ic_ir": float(analysis.ic_ir) if analysis and analysis.ic_ir else None,
                                "coverage": float(analysis.coverage) if analysis and analysis.coverage else None,
                            }
                        )

                content = _generate_factor_report_content(calc_date, factor_summaries)

                report = Report(
                    title=f"因子报告 {calc_date}",
                    report_type="factor",
                    report_date=calc_date,
                    content=content,
                    summary=json.dumps({"factors": len(factor_summaries)}, ensure_ascii=False),
                    status="generated",
                    meta_json={"run_id": run_id},
                )
                db.add(report)
                db.commit()
                db.refresh(report)

                generated_reports.append({"type": "factor", "report_id": report.id})

            except Exception as e:
                errors.append(f"Factor report failed: {e!s}")
                logger.error(f"Factor report generation failed: {e}")

        # === 3. 风控报告: 预警汇总 ===
        if "risk" in report_types:
            try:
                # 获取今日风控任务结果
                risk_tasks = (
                    db.query(TaskLog)
                    .filter(
                        TaskLog.task_type == "risk_check",
                        func.date(TaskLog.created_at) == calc_date,
                        TaskLog.status == "success",
                    )
                    .order_by(TaskLog.created_at.desc())
                    .all()
                )

                risk_summary = {
                    "checks_run": len(risk_tasks),
                    "alerts": [],
                }

                for task in risk_tasks:
                    if task.result_json and isinstance(task.result_json, dict):
                        risk_summary["alerts"].extend(task.result_json.get("alerts", []))

                content = _generate_risk_report_content(calc_date, risk_summary)

                report = Report(
                    title=f"风控报告 {calc_date}",
                    report_type="risk",
                    report_date=calc_date,
                    content=content,
                    summary=json.dumps(
                        {
                            "checks": risk_summary["checks_run"],
                            "total_alerts": len(risk_summary["alerts"]),
                            "critical": len([a for a in risk_summary["alerts"] if a.get("severity") == "critical"]),
                        },
                        ensure_ascii=False,
                    ),
                    status="generated",
                    meta_json={"run_id": run_id},
                )
                db.add(report)
                db.commit()
                db.refresh(report)

                generated_reports.append({"type": "risk", "report_id": report.id})

            except Exception as e:
                errors.append(f"Risk report failed: {e!s}")
                logger.error(f"Risk report generation failed: {e}")

        # 更新任务日志
        result = {
            "trade_date": str(calc_date),
            "reports_generated": len(generated_reports),
            "report_details": generated_reports,
            "errors": errors,
        }
        _update_task_log(db, task_log, "success", result=result)

        logger.info(f"Daily report generation completed: {len(generated_reports)} reports generated")
        return {"status": "success", **result}

    except Exception as exc:
        logger.error(f"Report generation failed: {exc}")
        with contextlib.suppress(Exception):
            _update_task_log(db, task_log, "failed", error=exc)
        raise self.retry(exc=exc, countdown=300) from exc
    finally:
        db.close()


def _generate_daily_report_content(calc_date, model_summaries, task_summary):
    """生成日报内容(Markdown格式)"""
    lines = [
        f"# 日报 {calc_date}",
        "",
        "## 模型表现",
        "",
        "| 模型 | 日收益 | 累计收益 | 最大回撤 | 夏普 | IC | 换手率 | 持仓数 |",
        "|------|--------|----------|----------|------|-----|--------|--------|",
    ]

    for m in model_summaries:
        dr = f"{m['daily_return']:.2%}" if m["daily_return"] is not None else "-"
        cr = f"{m['cumulative_return']:.2%}" if m["cumulative_return"] is not None else "-"
        dd = f"{m['max_drawdown']:.2%}" if m["max_drawdown"] is not None else "-"
        sr = f"{m['sharpe_ratio']:.2f}" if m["sharpe_ratio"] is not None else "-"
        ic = f"{m['ic']:.4f}" if m["ic"] is not None else "-"
        to = f"{m['turnover']:.2%}" if m["turnover"] is not None else "-"
        lines.append(f"| {m['model_name']} | {dr} | {cr} | {dd} | {sr} | {ic} | {to} | {m['position_count']} |")

    lines.extend(
        [
            "",
            "## 任务执行情况",
            "",
            f"- 总任务数: {task_summary['total']}",
            f"- 成功: {task_summary['success']}",
            f"- 失败: {task_summary['failed']}",
            f"- 运行中: {task_summary['running']}",
        ]
    )

    return "\n".join(lines)


def _generate_factor_report_content(calc_date, factor_summaries):
    """生成因子报告内容(Markdown格式)"""
    lines = [
        f"# 因子报告 {calc_date}",
        "",
        "## 因子IC汇总",
        "",
        "| 因子 | 分类 | IC | Rank IC | ICIR | 覆盖率 |",
        "|------|------|-----|---------|------|--------|",
    ]

    for f in factor_summaries:
        ic = f"{f['ic']:.4f}" if f["ic"] is not None else "-"
        ric = f"{f['rank_ic']:.4f}" if f["rank_ic"] is not None else "-"
        icir = f"{f['ic_ir']:.4f}" if f["ic_ir"] is not None else "-"
        cov = f"{f['coverage']:.2%}" if f["coverage"] is not None else "-"
        lines.append(f"| {f['factor_name']} | {f['category']} | {ic} | {ric} | {icir} | {cov} |")

    # IC分布统计
    valid_ics = [f["ic"] for f in factor_summaries if f["ic"] is not None]
    if valid_ics:
        import numpy as np

        lines.extend(
            [
                "",
                "## IC分布统计",
                "",
                f"- 因子数: {len(valid_ics)}",
                f"- IC均值: {np.mean(valid_ics):.4f}",
                f"- IC标准差: {np.std(valid_ics):.4f}",
                f"- IC>0占比: {sum(1 for ic in valid_ics if ic > 0) / len(valid_ics):.2%}",
                f"- |IC|>0.03占比: {sum(1 for ic in valid_ics if abs(ic) > 0.03) / len(valid_ics):.2%}",
            ]
        )

    return "\n".join(lines)


def _generate_risk_report_content(calc_date, risk_summary):
    """生成风控报告内容(Markdown格式)"""
    alerts = risk_summary.get("alerts", [])
    critical = [a for a in alerts if a.get("severity") == "critical"]
    high = [a for a in alerts if a.get("severity") == "high"]
    medium = [a for a in alerts if a.get("severity") == "medium"]

    lines = [
        f"# 风控报告 {calc_date}",
        "",
        "## 预警汇总",
        "",
        f"- 检查次数: {risk_summary['checks_run']}",
        f"- 总预警数: {len(alerts)}",
        f"- 严重(Critical): {len(critical)}",
        f"- 高(High): {len(high)}",
        f"- 中(Medium): {len(medium)}",
    ]

    if critical:
        lines.extend(["", "## 严重预警", ""])
        lines.extend(f"- **[{a.get('model_code', '')}]** {a.get('message', '')}" for a in critical)

    if high:
        lines.extend(["", "## 高级预警", ""])
        lines.extend(f"- **[{a.get('model_code', '')}]** {a.get('message', '')}" for a in high)

    if medium:
        lines.extend(["", "## 中级预警", ""])
        lines.extend(f"- [{a.get('model_code', '')}] {a.get('message', '')}" for a in medium)

    return "\n".join(lines)
