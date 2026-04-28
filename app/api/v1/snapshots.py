"""数据快照API路由"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.response import success_response
from app.db.base import SessionLocal
from app.schemas.snapshots import DataSnapshotCreate
from app.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/snapshots", tags=["数据快照"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
async def get_snapshots(
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询快照列表"""
    snapshots = SnapshotService.get_all_snapshots(db, limit=page_size)
    return success_response(
        data=[
            {
                "snapshot_id": s.snapshot_id,
                "snapshot_date": str(s.snapshot_date),
                "description": s.description,
            }
            for s in snapshots
        ]
    )


@router.get("/{snapshot_id}")
async def get_snapshot_detail(snapshot_id: str, db: Session = Depends(get_db)):
    """获取快照详情"""
    snapshot = SnapshotService.get_snapshot_by_id(db, snapshot_id)
    if not snapshot:
        return success_response(code=40401, message="快照不存在")
    return success_response(
        data={
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_date": str(snapshot.snapshot_date),
            "description": snapshot.description,
            "source_version_json": snapshot.source_version_json,
            "code_version": snapshot.code_version,
        }
    )


@router.post("")
async def create_snapshot(data: DataSnapshotCreate, db: Session = Depends(get_db)):
    """手动触发快照生成"""
    snapshot = SnapshotService.create_snapshot(db, data)
    return success_response(
        data={
            "snapshot_id": snapshot.snapshot_id,
            "status": "pending",
        }
    )
