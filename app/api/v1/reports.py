"""报告管理 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.response import success
from app.db.base import get_db
from app.schemas.reports import (
    ReportCreate,
    ReportScheduleCreate,
    ReportScheduleUpdate,
    ReportTemplateCreate,
    ReportTemplateUpdate,
    ReportUpdate,
)
from app.services.reports_service import (
    create_report,
    create_report_schedule,
    create_report_template,
    delete_report,
    delete_report_schedule,
    delete_report_template,
    generate_report,
    get_report_by_id,
    get_report_schedule_by_id,
    get_report_schedules,
    get_report_template_by_id,
    get_report_templates,
    get_reports,
    schedule_report_generation,
    update_report,
    update_report_schedule,
    update_report_template,
)

router = APIRouter()


@router.get("/")
def read_reports(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取报告列表"""
    reports = get_reports(skip=skip, limit=limit, db=db)
    return success(reports)


@router.get("/{report_id}")
def read_report(report_id: int, db: Session = Depends(get_db)):
    """获取报告详情"""
    report = get_report_by_id(report_id, db=db)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return success(report)


@router.post("/")
def create_report_endpoint(report: ReportCreate, db: Session = Depends(get_db)):
    """创建报告"""
    result = create_report(report, db=db)
    return success(result)


@router.put("/{report_id}")
def update_report_endpoint(report_id: int, report_update: ReportUpdate, db: Session = Depends(get_db)):
    """更新报告"""
    report = update_report(report_id, report_update, db=db)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return success(report)


@router.delete("/{report_id}")
def delete_report_endpoint(report_id: int, db: Session = Depends(get_db)):
    """删除报告"""
    deleted = delete_report(report_id, db=db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")
    return success(message="Report deleted successfully")


# ─── 报告模板 ───


@router.get("/templates/")
def read_report_templates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取报告模板列表"""
    templates = get_report_templates(skip=skip, limit=limit, db=db)
    return success(templates)


@router.get("/templates/{template_id}")
def read_report_template(template_id: int, db: Session = Depends(get_db)):
    """获取报告模板详情"""
    template = get_report_template_by_id(template_id, db=db)
    if template is None:
        raise HTTPException(status_code=404, detail="Report template not found")
    return success(template)


@router.post("/templates/")
def create_report_template_endpoint(template: ReportTemplateCreate, db: Session = Depends(get_db)):
    """创建报告模板"""
    result = create_report_template(template, db=db)
    return success(result)


@router.put("/templates/{template_id}")
def update_report_template_endpoint(
    template_id: int, template_update: ReportTemplateUpdate, db: Session = Depends(get_db)
):
    """更新报告模板"""
    template = update_report_template(template_id, template_update, db=db)
    if template is None:
        raise HTTPException(status_code=404, detail="Report template not found")
    return success(template)


@router.delete("/templates/{template_id}")
def delete_report_template_endpoint(template_id: int, db: Session = Depends(get_db)):
    """删除报告模板"""
    deleted = delete_report_template(template_id, db=db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report template not found")
    return success(message="Report template deleted successfully")


# ─── 报告调度 ───


@router.get("/schedules/")
def read_report_schedules(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取报告调度列表"""
    schedules = get_report_schedules(skip=skip, limit=limit, db=db)
    return success(schedules)


@router.get("/schedules/{schedule_id}")
def read_report_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """获取报告调度详情"""
    schedule = get_report_schedule_by_id(schedule_id, db=db)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return success(schedule)


@router.post("/schedules/")
def create_report_schedule_endpoint(schedule: ReportScheduleCreate, db: Session = Depends(get_db)):
    """创建报告调度"""
    result = create_report_schedule(schedule, db=db)
    return success(result)


@router.put("/schedules/{schedule_id}")
def update_report_schedule_endpoint(
    schedule_id: int, schedule_update: ReportScheduleUpdate, db: Session = Depends(get_db)
):
    """更新报告调度"""
    schedule = update_report_schedule(schedule_id, schedule_update, db=db)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return success(schedule)


@router.delete("/schedules/{schedule_id}")
def delete_report_schedule_endpoint(schedule_id: int, db: Session = Depends(get_db)):
    """删除报告调度"""
    deleted = delete_report_schedule(schedule_id, db=db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return success(message="Report schedule deleted successfully")


# ─── 报告操作 ───


@router.post("/generate/{report_id}")
def generate_report_endpoint(report_id: int, db: Session = Depends(get_db)):
    """生成报告"""
    report = generate_report(report_id, db=db)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return success(data={"report_id": report_id}, message="Report generation started")


@router.post("/schedules/{schedule_id}/run")
def run_report_schedule_endpoint(schedule_id: int, db: Session = Depends(get_db)):
    """执行报告调度"""
    schedule = schedule_report_generation(schedule_id, db=db)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return success(data={"schedule_id": schedule_id}, message="Report schedule execution started")
