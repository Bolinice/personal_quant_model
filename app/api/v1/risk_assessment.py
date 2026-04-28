"""风险测评 API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.response import success
from app.db.base import get_db
from app.models.user import User
from app.schemas.risk_assessment import (
    RiskAssessmentSubmit,
)
from app.services import risk_assessment_service

router = APIRouter()


@router.get("/questions")
def get_questions():
    """获取风险测评题目"""
    questions = risk_assessment_service.get_questions()
    return success([q.model_dump() for q in questions])


@router.post("/submit")
def submit_assessment(
    submit: RiskAssessmentSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交风险测评"""
    result = risk_assessment_service.submit_assessment(db, current_user.id, submit)
    return success(result.model_dump())


@router.get("/latest")
def get_latest_assessment(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户最新测评结果"""
    result = risk_assessment_service.get_latest_assessment(db, current_user.id)
    if result is None:
        return success(None)
    return success(result.model_dump())
