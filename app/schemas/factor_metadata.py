"""因子元数据Schema"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class FactorMetadataBase(BaseModel):
    factor_name: str
    factor_group: str
    description: Optional[str] = None
    formula: Optional[str] = None
    source_table: Optional[str] = None
    pit_required: bool = False
    direction: int = 1
    frequency: str = "daily"
    status: str = "experimental"
    version: str = "1.0"
    coverage_threshold: int = 70


class FactorMetadataCreate(FactorMetadataBase):
    pass


class FactorMetadataResponse(FactorMetadataBase):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
