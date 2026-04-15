from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any

# Report 模型
class ReportBase(BaseModel):
    report_type: str
    report_date: datetime
    report_data: Optional[Dict[str, Any]] = None
    report_path: Optional[str] = None
    is_public: bool = False

class ReportCreate(ReportBase):
    pass

class ReportUpdate(BaseModel):
    report_type: Optional[str] = None
    report_date: Optional[datetime] = None
    report_data: Optional[Dict[str, Any]] = None
    report_path: Optional[str] = None
    is_public: Optional[bool] = None

class ReportOut(ReportBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

# ReportTemplate 模型
class ReportTemplateBase(BaseModel):
    template_name: str
    template_content: Dict[str, Any]
    is_active: bool = True

class ReportTemplateCreate(ReportTemplateBase):
    pass

class ReportTemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    template_content: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class ReportTemplateOut(ReportTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# ReportSchedule 模型
class ReportScheduleBase(BaseModel):
    report_type: str
    frequency: str
    recipients: List[str]
    is_active: bool = True

class ReportScheduleCreate(ReportScheduleBase):
    pass

class ReportScheduleUpdate(BaseModel):
    report_type: Optional[str] = None
    frequency: Optional[str] = None
    recipients: Optional[List[str]] = None
    is_active: Optional[bool] = None

class ReportScheduleOut(ReportScheduleBase):
    id: int
    next_run_time: datetime
    created_at: datetime

    class Config:
        orm_mode = True

# 综合响应模型
class ReportWithTemplate(ReportOut):
    template: Optional[ReportTemplateOut] = None

class ReportScheduleWithDetails(ReportScheduleOut):
    pass