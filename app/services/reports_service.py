from datetime import datetime
from sqlalchemy.orm import Session
from app.db.base import with_db
from app.core.logging import logger
from app.models.reports import Report, ReportTemplate, ReportSchedule
from app.schemas.reports import ReportCreate, ReportUpdate, ReportOut, ReportTemplateCreate, ReportTemplateOut, ReportScheduleCreate, ReportScheduleUpdate, ReportScheduleOut

@with_db
def get_reports(skip: int = 0, limit: int = 100, db: Session = None):
    return db.query(Report).offset(skip).limit(limit).all()

@with_db
def get_report_by_id(report_id: int, db: Session = None):
    return db.query(Report).filter(Report.id == report_id).first()

@with_db
def create_report(report: ReportCreate, db: Session = None):
    db_report = Report(**report.model_dump())
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

@with_db
def update_report(report_id: int, report_update: ReportUpdate, db: Session = None):
    db_report = get_report_by_id(report_id, db)
    if db_report is None:
        return None
    for var, value in report_update.model_dump(exclude_unset=True).items():
        setattr(db_report, var, value)
    db.commit()
    db.refresh(db_report)
    return db_report

@with_db
def delete_report(report_id: int, db: Session = None):
    db_report = get_report_by_id(report_id, db)
    if db_report is None:
        return False
    db.delete(db_report)
    db.commit()
    return True

@with_db
def get_report_templates(skip: int = 0, limit: int = 100, db: Session = None):
    return db.query(ReportTemplate).offset(skip).limit(limit).all()

@with_db
def get_report_template_by_id(template_id: int, db: Session = None):
    return db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()

@with_db
def create_report_template(template: ReportTemplateCreate, db: Session = None):
    db_template = ReportTemplate(**template.model_dump())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

@with_db
def update_report_template(template_id: int, template_update: ReportTemplateUpdate, db: Session = None):
    db_template = get_report_template_by_id(template_id, db)
    if db_template is None:
        return None
    for var, value in template_update.model_dump(exclude_unset=True).items():
        setattr(db_template, var, value)
    db.commit()
    db.refresh(db_template)
    return db_template

@with_db
def delete_report_template(template_id: int, db: Session = None):
    db_template = get_report_template_by_id(template_id, db)
    if db_template is None:
        return False
    db.delete(db_template)
    db.commit()
    return True

@with_db
def get_report_schedules(skip: int = 0, limit: int = 100, db: Session = None):
    return db.query(ReportSchedule).offset(skip).limit(limit).all()

@with_db
def get_report_schedule_by_id(schedule_id: int, db: Session = None):
    return db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()

@with_db
def create_report_schedule(schedule: ReportScheduleCreate, db: Session = None):
    db_schedule = ReportSchedule(**schedule.model_dump())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

@with_db
def update_report_schedule(schedule_id: int, schedule_update: ReportScheduleUpdate, db: Session = None):
    db_schedule = get_report_schedule_by_id(schedule_id, db)
    if db_schedule is None:
        return None
    for var, value in schedule_update.model_dump(exclude_unset=True).items():
        setattr(db_schedule, var, value)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

@with_db
def delete_report_schedule(schedule_id: int, db: Session = None):
    db_schedule = get_report_schedule_by_id(schedule_id, db)
    if db_schedule is None:
        return False
    db.delete(db_schedule)
    db.commit()
    return True

@with_db
def generate_report(report_id: int, db: Session = None):
    """生成报告 — 调用真实绩效分析和回测引擎"""
    report = get_report_by_id(report_id, db)
    if report is None:
        return None

    from datetime import date as date_type
    import json

    try:
        content_parts = []
        calc9_date = report.report_date or date_type.today()

        if report.report_type == 'daily':
            # 日报：汇总所有活跃模型表现
            from app.models.models import Model, ModelPerformance
            from app.models.portfolios import Portfolio, PortfolioPosition

            active_models = db.query(Model).filter(Model.status == 'active').all()
            content_parts.append(f"# 日报 {calc9_date}\n")

            for model in active_models:
                perf = db.query(ModelPerformance).filter(
                    ModelPerformance.model_id == model.id,
                ).order_by(ModelPerformance.trade_date.desc()).first()

                portfolio = db.query(Portfolio).filter(
                    Portfolio.model_id == model.id,
                ).order_by(Portfolio.trade_date.desc()).first()

                pos_count = 0
                if portfolio:
                    pos_count = db.query(PortfolioPosition).filter(
                        PortfolioPosition.portfolio_id == portfolio.id
                    ).count()

                dr = f"{perf.daily_return:.2%}" if perf and perf.daily_return else "N/A"
                cr = f"{perf.cumulative_return:.2%}" if perf and perf.cumulative_return else "N/A"
                dd = f"{perf.max_drawdown:.2%}" if perf and perf.max_drawdown else "N/A"
                sr = f"{perf.sharpe_ratio:.2f}" if perf and perf.sharpe_ratio else "N/A"

                content_parts.append(
                    f"## {model.model_name}\n"
                    f"- 日收益: {dr} | 累计收益: {cr}\n"
                    f"- 最大回撤: {dd} | 夏普: {sr}\n"
                    f"- 持仓数: {pos_count}\n"
                )

        elif report.report_type == 'factor':
            # 因子报告：IC/衰减/分组
            from app.models.factors import Factor, FactorAnalysis

            active_factors = db.query(Factor).filter(Factor.is_active == True).all()
            content_parts.append(f"# 因子报告 {calc9_date}\n")
            content_parts.append("| 因子 | 分类 | IC | Rank IC | ICIR | 覆盖率 |")
            content_parts.append("|------|------|-----|---------|------|--------|")

            for factor in active_factors:
                analysis = db.query(FactorAnalysis).filter(
                    FactorAnalysis.factor_id == factor.id,
                ).order_by(FactorAnalysis.analysis_date.desc()).first()

                ic = f"{analysis.ic:.4f}" if analysis and analysis.ic else "-"
                ric = f"{analysis.rank_ic:.4f}" if analysis and analysis.rank_ic else "-"
                icir = f"{analysis.ic_ir:.4f}" if analysis and analysis.ic_ir else "-"
                cov = f"{analysis.coverage:.2%}" if analysis and analysis.coverage else "-"
                content_parts.append(f"| {factor.factor_name} | {factor.category} | {ic} | {ric} | {icir} | {cov} |")

        elif report.report_type == 'risk':
            # 风控报告
            from app.models.task_logs import TaskLog
            from sqlalchemy import func

            risk_tasks = db.query(TaskLog).filter(
                TaskLog.task_type == "risk_check",
                func.date(TaskLog.created_at) == calc9_date,
            ).all()

            content_parts.append(f"# 风控报告 {calc9_date}\n")
            content_parts.append(f"- 风控检查次数: {len(risk_tasks)}")
            alerts = []
            for task in risk_tasks:
                if task.result_json and isinstance(task.result_json, dict):
                    alerts.extend(task.result_json.get("alerts", []))
            content_parts.append(f"- 总预警数: {len(alerts)}")
            critical = [a for a in alerts if a.get("severity") == "critical"]
            if critical:
                content_parts.append("\n## 严重预警")
                for a in critical:
                    content_parts.append(f"- **{a.get('message', '')}**")

        else:
            content_parts.append(f"# {report.title}\n\n报告类型: {report.report_type}")

        report.content = "\n".join(content_parts)
        report.status = "generated"
        report.meta_json = {"generated_at": datetime.now().isoformat()}
        db.commit()
        db.refresh(report)
        return report

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        report.status = "error"
        report.meta_json = {"error": str(e)}
        db.commit()
        return report

@with_db
def schedule_report_generation(schedule_id: int, db: Session = None):
    """调度报告生成 — 触发 Celery 异步任务"""
    schedule = get_report_schedule_by_id(schedule_id, db)
    if schedule is None:
        return None

    from datetime import datetime
    from app.tasks.report_generate import run_daily_report_generate

    # 触发异步报告生成任务
    try:
        task = run_daily_report_generate.delay()
        schedule.next_run_time = datetime.now().isoformat()
        schedule.meta_json = schedule.meta_json or {}
        schedule.meta_json['last_task_id'] = task.id
        db.commit()
        db.refresh(schedule)
    except Exception as e:
        logger.error(f"Failed to schedule report generation: {e}")

    return schedule