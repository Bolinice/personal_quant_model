"""因子元数据API路由"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.core.response import success_response
from app.services.factor_metadata_service import FactorMetadataService
from app.schemas.factor_metadata import FactorResearchRequest

router = APIRouter(tags=["因子元数据"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/factor-metadata")
async def get_factor_metadata(
    factor_group: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """查询因子元数据列表"""
    factors = FactorMetadataService.get_all_factors(db, factor_group=factor_group, status=status)
    return success_response(data=[{
        "factor_name": f.factor_name, "factor_group": f.factor_group,
        "description": f.description, "direction": f.direction,
        "status": f.status, "version": f.version,
        "pit_required": f.pit_required, "coverage_threshold": f.coverage_threshold,
    } for f in factors])


@router.get("/factor-metadata/{factor_name}")
async def get_factor_detail(factor_name: str, db: Session = Depends(get_db)):
    """获取因子详情"""
    factor = FactorMetadataService.get_factor_by_name(db, factor_name)
    if not factor:
        return success_response(code=40401, message="因子不存在")
    return success_response(data={
        "factor_name": factor.factor_name, "factor_group": factor.factor_group,
        "description": factor.description, "formula": factor.formula,
        "source_table": factor.source_table, "pit_required": factor.pit_required,
        "direction": factor.direction, "frequency": factor.frequency,
        "status": factor.status, "version": factor.version,
        "coverage_threshold": factor.coverage_threshold,
    })


@router.post("/factor-research")
async def submit_factor_research(request: FactorResearchRequest):
    """提交因子研究任务"""
    task_id = f"fr_{request.factor_name}_{id(request)}"
    return success_response(data={"task_id": task_id, "status": "pending"})


@router.get("/factor-research/{task_id}")
async def get_factor_research_result(task_id: str):
    """查询因子研究结果"""
    return success_response(data={"task_id": task_id, "status": "pending", "result": None})
