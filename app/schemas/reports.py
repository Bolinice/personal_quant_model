from datetime import datetime
from pydantic import BaseModel, ConfigDict
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

    model_config = ConfigDict(from_attributes=True)

class ReportOut(ReportBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Report(ReportOut):
    pass

class ReportTemplateBase(BaseModel):
    template_name: str
    template_type: str
    template_content: str
    description: Optional[str] = None

class ReportTemplateCreate(ReportTemplateBase):
    pass

class ReportTemplateUpdate(BaseModel):
    template_name: Optional[str] = None
    template_type: Optional[str] = None
    template_content: Optional[str] = None
    description: Optional[str] = None

class ReportTemplateInDB(ReportTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReportTemplateOut(ReportTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReportTemplate(ReportTemplateOut):
    pass

class ReportScheduleBase(BaseModel):
    schedule_name: str
    report_template_id: int
    cron_expression: str
    is_active: bool = True

class ReportScheduleCreate(ReportScheduleBase):
    pass

class ReportScheduleUpdate(BaseModel):
    schedule_name: Optional[str] = None
    report_template_id: Optional[int] = None
    cron_expression: Optional[str] = None
    is_active: Optional[bool] = None

class ReportScheduleInDB(ReportScheduleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReportScheduleOut(ReportScheduleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReportSchedule(ReportScheduleOut):
    pass