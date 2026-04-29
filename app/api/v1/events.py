"""事件中心API路由"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.response import success_response
from app.db.base import SessionLocal
from app.services.events_service import EventService

router = APIRouter(prefix="/events", tags=["事件中心"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
async def get_events(
    stock_id: int | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询事件列表"""
    offset = (page - 1) * page_size
    events = EventService.get_events(
        db,
        stock_id=stock_id,
        event_type=event_type,
        start_date=start_date,
        end_date=end_date,
        severity=severity,
        limit=page_size,
        offset=offset,
    )
    return success_response(
        data=[
            {
                "id": e.id,
                "stock_id": e.stock_id,
                "event_type": e.event_type,
                "event_date": str(e.event_date),
                "severity": e.severity,
                "title": e.title,
                "score": float(e.score) if e.score else None,
            }
            for e in events
        ]
    )


@router.get("/{event_id}")
async def get_event(event_id: int, db: Session = Depends(get_db)):
    """获取事件详情"""
    event = EventService.get_event_by_id(db, event_id)
    if not event:
        return success_response(code=40401, message="事件不存在")
    return success_response(
        data={
            "id": event.id,
            "stock_id": event.stock_id,
            "event_type": event.event_type,
            "event_subtype": event.event_subtype,
            "event_date": str(event.event_date),
            "effective_date": str(event.effective_date) if event.effective_date else None,
            "expire_date": str(event.expire_date) if event.expire_date else None,
            "severity": event.severity,
            "score": float(event.score) if event.score else None,
            "title": event.title,
            "content": event.content,
            "source": event.source,
        }
    )


@router.get("/risk-flags")
async def get_risk_flags(
    trade_date: date = Query(...),
    stock_id: int | None = None,
    db: Session = Depends(get_db),
):
    """查询风险标签"""
    flags = EventService.get_risk_flags(db, trade_date, stock_id)
    return success_response(
        data=[
            {
                "trade_date": str(f.trade_date),
                "stock_id": f.stock_id,
                "blacklist_flag": f.blacklist_flag,
                "risk_penalty_score": float(f.risk_penalty_score) if f.risk_penalty_score else 0,
            }
            for f in flags
        ]
    )


@router.get("/risk-flags/blacklist")
async def get_blacklist(db: Session = Depends(get_db)):
    """查询当前黑名单"""
    today = datetime.now(tz=UTC).date()
    blacklist = EventService.get_blacklist(db, today)
    return success_response(data=[{"stock_id": b.stock_id} for b in blacklist])
