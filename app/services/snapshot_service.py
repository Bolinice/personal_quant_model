"""数据快照服务"""

from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session
import uuid

from app.models.data_snapshot_registry import DataSnapshotRegistry
from app.schemas.snapshots import DataSnapshotCreate


class SnapshotService:
    """数据快照服务"""

    @staticmethod
    def get_all_snapshots(
        db: Session,
        snapshot_date: Optional[date] = None,
        limit: int = 30,
    ) -> List[DataSnapshotRegistry]:
        """获取快照列表"""
        query = db.query(DataSnapshotRegistry)
        if snapshot_date:
            query = query.filter(DataSnapshotRegistry.snapshot_date == snapshot_date)
        return query.order_by(DataSnapshotRegistry.snapshot_date.desc()).limit(limit).all()

    @staticmethod
    def get_snapshot_by_id(db: Session, snapshot_id: str) -> Optional[DataSnapshotRegistry]:
        """获取快照详情"""
        return db.query(DataSnapshotRegistry).filter(
            DataSnapshotRegistry.snapshot_id == snapshot_id
        ).first()

    @staticmethod
    def create_snapshot(db: Session, data: DataSnapshotCreate) -> DataSnapshotRegistry:
        """创建数据快照"""
        snapshot_id = f"snap_{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
        snapshot = DataSnapshotRegistry(
            snapshot_id=snapshot_id,
            snapshot_date=date.today(),
            description=data.description,
            code_version=data.snapshot_type,
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot
