from sqlalchemy.orm import Session
from app.db.base import SessionLocal
from app.models.reports import Report, ReportTemplate, ReportSchedule
from app.schemas.reports import ReportCreate, ReportUpdate, ReportOut, ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateOut, ReportScheduleCreate, ReportScheduleUpdate, ReportScheduleOut

def get_reports(skip: int = 0, limit: int = 100, db: Session = None):
    if db is None:
        db = SessionLocal()
    return db.query(Report).offset(skip).limit(limit).all()

def get_report_by_id(report_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
    return db.query(Report).filter(Report.id == report_id).first()

def create_report(report: ReportCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_report = Report(**report.dict())
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def update_report(report_id: int, report_update: ReportUpdate, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_report = get_report_by_id(report_id, db)
    if db_report is None:
        return None
    for var, value in report_update.dict(exclude_unset=True).items():
        setattr(db_report, var, value)
    db.commit()
    db.refresh(db_report)
    return db_report

def delete_report(report_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_report = get_report_by_id(report_id, db)
    if db_report is None:
        return False
    db.delete(db_report)
    db.commit()
    return True

def get_report_templates(skip: int = 0, limit: int = 100, db: Session = None):
    if db is None:
        db = SessionLocal()
    return db.query(ReportTemplate).offset(skip).limit(limit).all()

def get_report_template_by_id(template_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
    return db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()

def create_report_template(template: ReportTemplateCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_template = ReportTemplate(**template.dict())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

def update_report_template(template_id: int, template_update: ReportTemplateUpdate, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_template = get_report_template_by_id(template_id, db)
    if db_template is None:
        return None
    for var, value in template_update.dict(exclude_unset=True).items():
        setattr(db_template, var, value)
    db.commit()
    db.refresh(db_template)
    return db_template

def delete_report_template(template_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_template = get_report_template_by_id(template_id, db)
    if db_template is None:
        return False
    db.delete(db_template)
    db.commit()
    return True

def get_report_schedules(skip: int = 0, limit: int = 100, db: Session = None):
    if db is None:
        db = SessionLocal()
    return db.query(ReportSchedule).offset(skip).limit(limit).all()

def get_report_schedule_by_id(schedule_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
    return db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()

def create_report_schedule(schedule: ReportScheduleCreate, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_schedule = ReportSchedule(**schedule.dict())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

def update_report_schedule(schedule_id: int, schedule_update: ReportScheduleUpdate, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_schedule = get_report_schedule_by_id(schedule_id, db)
    if db_schedule is None:
        return None
    for var, value in schedule_update.dict(exclude_unset=True).items():
        setattr(db_schedule, var, value)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

def delete_report_schedule(schedule_id: int, db: Session = None):
    if db is None:
        db = SessionLocal()
    db_schedule = get_report_schedule_by_id(schedule_id, db)
    if db_schedule is None:
        return False
    db.delete(db_schedule)
    db.commit()
    return True

def generate_report(report_id: int, db: Session = None):
    """生成报告的函数（实际实现需要根据具体需求）"""
    if db is None:
        db = SessionLocal()
    report = get_report_by_id(report_id, db)
    if report is None:
        return None

    # 这里应该是实际的报告生成逻辑
    # 例如：从数据库获取数据，使用模板生成报告，保存到文件等
    report.report_data = {"status": "generated", "generated_at": "2026-04-15T00:00:00"}
    db.commit()
    db.refresh(report)
    return report

def schedule_report_generation(schedule_id: int, db: Session = None):
    """调度报告生成的函数"""
    if db is None:
        db = SessionLocal()
    schedule = get_report_schedule_by_id(schedule_id, db)
    if schedule is None:
        return None

    # 这里应该是实际的调度逻辑
    # 例如：设置定时任务，调用生成报告函数等
    schedule.next_run_time = "2026-04-16T00:00:00"
    db.commit()
    db.refresh(schedule)
    return schedule