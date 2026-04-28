"""数据快照Schema"""

from datetime import date, datetime

from pydantic import BaseModel


class DataSnapshotBase(BaseModel):
    snapshot_id: str
    snapshot_date: date
    description: str | None = None
    source_version_json: str | None = None
    code_version: str | None = None


class DataSnapshotCreate(BaseModel):
    snapshot_type: str = "daily"
    description: str | None = None


class DataSnapshotResponse(DataSnapshotBase):
    created_at: datetime | None = None

    class Config:
        from_attributes = True
