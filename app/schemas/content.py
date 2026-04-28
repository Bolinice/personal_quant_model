from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ContentBlockBase(BaseModel):
    page: str
    section: str
    lang: str = "zh"
    sort_order: int = 0
    title: str
    subtitle: str | None = None
    body: str | None = None
    extra: dict | None = None
    is_active: bool = True


class ContentBlockCreate(ContentBlockBase):
    pass


class ContentBlockUpdate(BaseModel):
    sort_order: int | None = None
    title: str | None = None
    subtitle: str | None = None
    body: str | None = None
    extra: dict | None = None
    is_active: bool | None = None


class ContentBlockOut(ContentBlockBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContentSectionOut(BaseModel):
    """单个区块的输出格式"""

    title: str
    subtitle: str | None = None
    body: str | None = None
    extra: dict | None = None


class PageContentOut(BaseModel):
    """页面内容输出格式 - 按 section 分组"""

    page: str
    sections: dict[str, ContentSectionOut]
