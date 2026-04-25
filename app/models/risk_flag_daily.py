"""风险标签日表模型"""

from sqlalchemy import Column, BigInteger, String, Date, Boolean, Numeric
from app.db.base import Base


class RiskFlagDaily(Base):
    """风险标签日表 - 每日每只股票的风险标签"""
    __tablename__ = "risk_flag_daily"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, index=True, comment="交易日")
    stock_id = Column(BigInteger, nullable=False, index=True, comment="股票ID")
    blacklist_flag = Column(Boolean, default=False, comment="黑名单标记")
    audit_issue_flag = Column(Boolean, default=False, comment="审计异常")
    violation_flag = Column(Boolean, default=False, comment="违规标记")
    pledge_high_flag = Column(Boolean, default=False, comment="高质押(>50%)")
    goodwill_high_flag = Column(Boolean, default=False, comment="高商誉(商誉/净资产>50%)")
    earnings_warning_flag = Column(Boolean, default=False, comment="业绩预警")
    reduction_flag = Column(Boolean, default=False, comment="减持标记")
    cashflow_risk_flag = Column(Boolean, default=False, comment="现金流风险")
    risk_penalty_score = Column(Numeric(10, 6), default=0, comment="风险惩罚分(0~1)")

    __table_args__ = (
        {"comment": "风险标签日表"},
    )