"""
风险测评服务
- 测评题目定义
- 评分计算
- 等级判定
"""

from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.risk_assessment import RiskAssessment
from app.models.user import User
from app.schemas.risk_assessment import (
    RiskAnswer, RiskAssessmentSubmit, RiskAssessmentResult,
    RiskQuestion, RiskAssessmentOut,
)

# ============================================================
# 测评题目（5道题，每题5个选项，分值0-4）
# ============================================================

RISK_QUESTIONS: List[RiskQuestion] = [
    RiskQuestion(
        id=1,
        question="您的投资经验年限？",
        options=["无投资经验", "1年以内", "1-3年", "3-5年", "5年以上"],
        scores=[0, 1, 2, 3, 4],
    ),
    RiskQuestion(
        id=2,
        question="您能接受的最大亏损幅度？",
        options=["不能接受亏损", "5%以内", "5%-15%", "15%-30%", "30%以上"],
        scores=[0, 1, 2, 3, 4],
    ),
    RiskQuestion(
        id=3,
        question="您的投资资金占可支配资产比例？",
        options=["10%以下", "10%-30%", "30%-50%", "50%-70%", "70%以上"],
        scores=[4, 3, 2, 1, 0],  # 占比越高越需保守
    ),
    RiskQuestion(
        id=4,
        question="您的预期投资期限？",
        options=["3个月以内", "3-12个月", "1-3年", "3-5年", "5年以上"],
        scores=[0, 1, 2, 3, 4],
    ),
    RiskQuestion(
        id=5,
        question="当您的投资组合下跌20%时，您会？",
        options=["全部卖出止损", "卖出部分降低风险", "持有不动等待回升", "逢低加仓", "大幅加仓"],
        scores=[0, 1, 2, 3, 4],
    ),
]

# 等级定义
RISK_LEVELS = {
    "C1": {"name": "保守型", "min_score": 0, "max_score": 6,
            "description": "您属于保守型投资者，适合低风险产品，追求资产保值。"},
    "C2": {"name": "稳健型", "min_score": 7, "max_score": 12,
            "description": "您属于稳健型投资者，适合中低风险产品，追求稳健收益。"},
    "C3": {"name": "积极型", "min_score": 13, "max_score": 17,
            "description": "您属于积极型投资者，适合中高风险产品，追求较高收益。"},
    "C4": {"name": "激进型", "min_score": 18, "max_score": 20,
            "description": "您属于激进型投资者，适合高风险产品，追求最大化收益。"},
}


def get_questions() -> List[RiskQuestion]:
    """获取测评题目"""
    return RISK_QUESTIONS


def calculate_score(answers: List[RiskAnswer]) -> int:
    """计算测评得分"""
    score_map = {q.id: q.scores for q in RISK_QUESTIONS}
    total = 0
    for ans in answers:
        scores = score_map.get(ans.question_id, [])
        if 0 <= ans.answer < len(scores):
            total += scores[ans.answer]
    return total


def score_to_level(score: int) -> str:
    """得分 → 风险等级"""
    for level_code, info in RISK_LEVELS.items():
        if info["min_score"] <= score <= info["max_score"]:
            return level_code
    return "C1"  # 默认保守


def submit_assessment(db: Session, user_id: int, submit: RiskAssessmentSubmit) -> RiskAssessmentResult:
    """提交测评并保存"""
    score = calculate_score(submit.answers)
    level = score_to_level(score)
    level_info = RISK_LEVELS[level]

    # 保存测评记录
    assessment = RiskAssessment(
        user_id=user_id,
        score=score,
        level=level,
        answers=[a.model_dump() for a in submit.answers],
    )
    db.add(assessment)

    # 更新用户风险等级
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.risk_level = level

    db.commit()
    db.refresh(assessment)

    return RiskAssessmentResult(
        score=score,
        level=level,
        level_name=level_info["name"],
        description=level_info["description"],
    )


def get_latest_assessment(db: Session, user_id: int) -> Optional[RiskAssessmentOut]:
    """获取用户最新测评结果"""
    assessment = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.user_id == user_id)
        .order_by(RiskAssessment.assessed_at.desc())
        .first()
    )
    if not assessment:
        return None

    level_info = RISK_LEVELS.get(assessment.level, RISK_LEVELS["C1"])
    return RiskAssessmentOut(
        id=assessment.id,
        user_id=assessment.user_id,
        score=assessment.score,
        level=assessment.level,
        level_name=level_info["name"],
        assessed_at=assessment.assessed_at.isoformat() if assessment.assessed_at else "",
    )
