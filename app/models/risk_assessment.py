"""
风险测评模型
- RiskAssessment: 用户风险测评记录
"""

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class RiskAssessment(Base):
    """风险测评表"""

    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    score = Column(Integer, nullable=False, comment="测评得分(1-100)")
    level = Column(String(10), nullable=False, comment="风险等级: C1保守/C2稳健/C3积极/C4激进")
    answers = Column(JSON, nullable=False, comment="测评答案JSON")
    assessed_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<RiskAssessment(user_id={self.user_id}, level={self.level}, score={self.score})>"
