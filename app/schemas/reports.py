from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReportBase(BaseModel):
    report_name: str
    report_type: str
    description: str | None = None


class ReportCreate(ReportBase):
    pass


class ReportUpdate(BaseModel):
    report_name: str | None = None
    report_type: str | None = None
    description: str | None = None


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
    description: str | None = None


class ReportTemplateCreate(ReportTemplateBase):
    pass


class ReportTemplateUpdate(BaseModel):
    template_name: str | None = None
    template_type: str | None = None
    template_content: str | None = None
    description: str | None = None


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
    schedule_name: str | None = None
    report_template_id: int | None = None
    cron_expression: str | None = None
    is_active: bool | None = None


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
