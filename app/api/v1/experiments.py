"""实验API路由"""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.core.response import success_response
from app.models.experiment_registry import ExperimentRegistry

router = APIRouter(prefix="/experiments", tags=["实验管理"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
async def get_experiments(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """查询实验列表"""
    query = db.query(ExperimentRegistry)
    if status:
        query = query.filter(ExperimentRegistry.status == status)
    offset = (page - 1) * page_size
    experiments = query.order_by(ExperimentRegistry.created_at.desc()).offset(offset).limit(page_size).all()
    return success_response(data=[{
        "experiment_id": e.experiment_id, "experiment_name": e.experiment_name,
        "status": e.status, "config_version": e.config_version,
        "code_version": e.code_version,
    } for e in experiments])


@router.get("/{experiment_id}")
async def get_experiment_detail(experiment_id: str, db: Session = Depends(get_db)):
    """获取实验详情"""
    exp = db.query(ExperimentRegistry).filter(
        ExperimentRegistry.experiment_id == experiment_id
    ).first()
    if not exp:
        return success_response(code=40401, message="实验不存在")
    return success_response(data={
        "experiment_id": exp.experiment_id, "experiment_name": exp.experiment_name,
        "snapshot_id": exp.snapshot_id, "config_version": exp.config_version,
        "code_version": exp.code_version, "result_summary": exp.result_summary,
        "status": exp.status,
    })
