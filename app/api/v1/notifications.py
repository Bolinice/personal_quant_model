"""
通知API
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.alert_logs import Notification
from app.core.response import success, page_result


router = APIRouter()


@router.get("/")
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = None,
    user_id: int = None,
    db: Session = Depends(get_db),
):
    """获取通知列表"""
    query = db.query(Notification)
    if user_id:
        query = query.filter(Notification.user_id == user_id)
    if status:
        query = query.filter(Notification.status == status)

    total = query.count()
    items = query.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return page_result(
        items=[{
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "notification_type": n.notification_type,
            "status": n.status,
            "link": n.link,
            "created_at": str(n.created_at),
        } for n in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/unread-count")
def get_unread_count(user_id: int, db: Session = Depends(get_db)):
    """获取未读通知数量"""
    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.status == "unread",
    ).count()
    return success({"count": count})


@router.put("/{notification_id}/read")
def mark_as_read(notification_id: int, user_id: int, db: Session = Depends(get_db)):
    """标记通知为已读"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    notification.status = "read"
    from datetime import datetime
    notification.read_at = datetime.now()
    db.commit()

    return success(message="已标记为已读")


@router.put("/read-all")
def mark_all_as_read(user_id: int, db: Session = Depends(get_db)):
    """全部标记为已读"""
    notifications = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.status == "unread",
    ).all()

    from datetime import datetime
    for n in notifications:
        n.status = "read"
        n.read_at = datetime.now()

    db.commit()
    return success({"count": len(notifications)}, message="全部标记为已读")
