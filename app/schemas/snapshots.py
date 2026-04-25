"""数据快照Schema"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class DataSnapshotBase(BaseModel):
    snapshot_id: str
    snapshot_date: date
    description: Optional[str] = None
    source_version_json: Optional[str] = None
    code_version: Optional[str] = None


class DataSnapshotCreate(BaseModel):
    snapshot_type: str = "daily"
    description: Optional[str] = None


class DataSnapshotResponse(DataSnapshotBase):
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
