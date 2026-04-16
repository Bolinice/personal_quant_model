from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ReportBase(BaseModel):
    report_name: str
    report_type: str
    description: Optional[str] = None

class ReportCreate(ReportBase):
    pass

class ReportUpdate(BaseModel):
    report_name: Optional[str] = None
    report_type: Optional[str] = None
    description: Optional[str] = None

class ReportInDB(ReportBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ReportOut(ReportBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Report(ReportOut):
    pass

class ReportTemplateBase(BaseModel):
    template_name: str
    template_type: str
    template_content: str
    description: Optional[str] = None

class ReportTemplateCreate(ReportTemplateBase):
    pass

class ReportTemplateInDB(ReportTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ReportTemplateOut(ReportTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ReportTemplate(ReportTemplateOut):
    pass