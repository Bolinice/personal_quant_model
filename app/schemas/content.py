from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any


class ContentBlockBase(BaseModel):
    page: str
    section: str
    lang: str = "zh"
    sort_order: int = 0
    title: str
    subtitle: Optional[str] = None
    body: Optional[str] = None
    extra: Optional[dict] = None
    is_active: bool = True


class ContentBlockCreate(ContentBlockBase):
    pass


class ContentBlockUpdate(BaseModel):
    sort_order: Optional[int] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    body: Optional[str] = None
    extra: Optional[dict] = None
    is_active: Optional[bool] = None


class ContentBlockOut(ContentBlockBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContentSectionOut(BaseModel):
    """单个区块的输出格式"""
    title: str
    subtitle: Optional[str] = None
    body: Optional[str] = None
    extra: Optional[dict] = None


class PageContentOut(BaseModel):
    """页面内容输出格式 - 按 section 分组"""
    page: str
    sections: dict[str, ContentSectionOut]
