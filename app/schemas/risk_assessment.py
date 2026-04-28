"""
风险测评 Pydantic schemas
"""

from pydantic import BaseModel, Field


class RiskAnswer(BaseModel):
    """单个题目答案"""

    question_id: int
    answer: int = Field(..., ge=0, le=4, description="选项索引 0-4")


class RiskAssessmentSubmit(BaseModel):
    """提交测评请求"""

    answers: list[RiskAnswer] = Field(..., min_length=1)


class RiskAssessmentResult(BaseModel):
    """测评结果"""

    score: int = Field(..., ge=1, le=100)
    level: str = Field(..., description="C1保守/C2稳健/C3积极/C4激进")
    level_name: str
    description: str


class RiskQuestion(BaseModel):
    """测评题目"""

    id: int
    question: str
    options: list[str]
    scores: list[int] = Field(..., description="各选项对应分值")


class RiskAssessmentOut(BaseModel):
    """测评记录输出"""

    id: int
    user_id: int
    score: int
    level: str
    level_name: str
    assessed_at: str
