"""因子元数据Schema"""

from datetime import datetime

from pydantic import BaseModel


class FactorMetadataBase(BaseModel):
    factor_name: str
    factor_group: str
    description: str | None = None
    formula: str | None = None
    source_table: str | None = None
    pit_required: bool = False
    direction: int = 1
    frequency: str = "daily"
    status: str = "experimental"
    version: str = "1.0"
    coverage_threshold: int = 70


class FactorMetadataCreate(FactorMetadataBase):
    pass


class FactorMetadataResponse(FactorMetadataBase):
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class FactorResearchRequest(BaseModel):
    factor_name: str
    factor_expression: str
    factor_group: str
    universe: str = "CSI800"
    start_date: str
    end_date: str


class FactorResearchResponse(BaseModel):
    task_id: str
    status: str = "pending"
