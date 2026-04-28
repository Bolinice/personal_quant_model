"""事件中心Schema"""

from datetime import date, datetime

from pydantic import BaseModel


class EventBase(BaseModel):
    stock_id: int
    event_type: str
    event_subtype: str | None = None
    event_date: date
    effective_date: date | None = None
    expire_date: date | None = None
    severity: str | None = None
    score: float | None = None
    title: str | None = None
    content: str | None = None
    source: str | None = None


class EventCreate(EventBase):
    pass


class EventResponse(EventBase):
    id: int
    snapshot_id: str | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class RiskFlagResponse(BaseModel):
    trade_date: date
    stock_id: int
    blacklist_flag: bool = False
    audit_issue_flag: bool = False
    violation_flag: bool = False
    pledge_high_flag: bool = False
    goodwill_high_flag: bool = False
    earnings_warning_flag: bool = False
    reduction_flag: bool = False
    cashflow_risk_flag: bool = False
    risk_penalty_score: float = 0.0

    class Config:
        from_attributes = True
