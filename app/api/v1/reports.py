from fastapi import APIRouter, Depends, HTTPException, status

from typing import List
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.reports_service import (
    get_reports, get_report_by_id, create_report, update_report, delete_report,
    get_report_templates, get_report_template_by_id, create_report_template, update_report_template, delete_report_template,
    get_report_schedules, get_report_schedule_by_id, create_report_schedule, update_report_schedule, delete_report_schedule,
    generate_report, schedule_report_generation
)
from app.models.reports import Report, ReportTemplate, ReportSchedule
from app.schemas.reports import (
    ReportCreate, ReportUpdate, ReportOut,
    ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateOut,
    ReportScheduleCreate, ReportScheduleUpdate, ReportScheduleOut
)

router = APIRouter()

@router.get("/", response_model=List[ReportOut])
def read_reports(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    reports = get_reports(skip=skip, limit=limit, db=db)
    return reports

@router.get("/{report_id}", response_model=ReportOut)
def read_report(report_id: int, db: Session = Depends(get_db)):
    report = get_report_by_id(report_id, db=db)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.post("/", response_model=ReportOut)
def create_report_endpoint(report: ReportCreate, db: Session = Depends(get_db)):
    return create_report(report, db=db)

@router.put("/{report_id}", response_model=ReportOut)
def update_report_endpoint(report_id: int, report_update: ReportUpdate, db: Session = Depends(get_db)):
    report = update_report(report_id, report_update, db=db)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.delete("/{report_id}")
def delete_report_endpoint(report_id: int, db: Session = Depends(get_db)):
    success = delete_report(report_id, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report deleted successfully"}

# Report Templates
@router.get("/templates/", response_model=List[ReportTemplateOut])
def read_report_templates(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    templates = get_report_templates(skip=skip, limit=limit, db=db)
    return templates

@router.get("/templates/{template_id}", response_model=ReportTemplateOut)
def read_report_template(template_id: int, db: Session = Depends(get_db)):
    template = get_report_template_by_id(template_id, db=db)
    if template is None:
        raise HTTPException(status_code=404, detail="Report template not found")
    return template

@router.post("/templates/", response_model=ReportTemplateOut)
def create_report_template_endpoint(template: ReportTemplateCreate, db: Session = Depends(get_db)):
    return create_report_template(template, db=db)

@router.put("/templates/{template_id}", response_model=ReportTemplateOut)
def update_report_template_endpoint(template_id: int, template_update: ReportTemplateUpdate, db: Session = Depends(get_db)):
    template = update_report_template(template_id, template_update, db=db)
    if template is None:
        raise HTTPException(status_code=404, detail="Report template not found")
    return template

@router.delete("/templates/{template_id}")
def delete_report_template_endpoint(template_id: int, db: Session = Depends(get_db)):
    success = delete_report_template(template_id, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Report template not found")
    return {"message": "Report template deleted successfully"}

# Report Schedules
@router.get("/schedules/", response_model=List[ReportScheduleOut])
def read_report_schedules(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    schedules = get_report_schedules(skip=skip, limit=limit, db=db)
    return schedules

@router.get("/schedules/{schedule_id}", response_model=ReportScheduleOut)
def read_report_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = get_report_schedule_by_id(schedule_id, db=db)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return schedule

@router.post("/schedules/", response_model=ReportScheduleOut)
def create_report_schedule_endpoint(schedule: ReportScheduleCreate, db: Session = Depends(get_db)):
    return create_report_schedule(schedule, db=db)

@router.put("/schedules/{schedule_id}", response_model=ReportScheduleOut)
def update_report_schedule_endpoint(schedule_id: int, schedule_update: ReportScheduleUpdate, db: Session = Depends(get_db)):
    schedule = update_report_schedule(schedule_id, schedule_update, db=db)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return schedule

@router.delete("/schedules/{schedule_id}")
def delete_report_schedule_endpoint(schedule_id: int, db: Session = Depends(get_db)):
    success = delete_report_schedule(schedule_id, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return {"message": "Report schedule deleted successfully"}

# Report Actions
@router.post("/generate/{report_id}")
def generate_report_endpoint(report_id: int, db: Session = Depends(get_db)):
    report = generate_report(report_id, db=db)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report generation started", "report_id": report_id}

@router.post("/schedules/{schedule_id}/run")
def run_report_schedule_endpoint(schedule_id: int, db: Session = Depends(get_db)):
    schedule = schedule_report_generation(schedule_id, db=db)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return {"message": "Report schedule execution started", "schedule_id": schedule_id}
