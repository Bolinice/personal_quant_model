from sqlalchemy import JSON, Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class ContentBlock(Base):
    """内容块表 - 通用 CMS 模型"""

    __tablename__ = "content_blocks"
    __table_args__ = (
        Index("ix_cb_page_section_lang", "page", "section", "lang"),
        Index("ix_cb_page", "page"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    page: str = Column(String(50), nullable=False, comment="页面标识: home, pricing, about")
    section: str = Column(String(50), nullable=False, comment="区块标识: hero, brand, core_values...")
    lang: str = Column(String(5), nullable=False, default="zh", comment="语言: zh, en")
    sort_order: int = Column(Integer, default=0, comment="排序")
    title: str = Column(String(200), nullable=False, comment="标题")
    subtitle: str = Column(String(500), comment="副标题")
    body: str = Column(Text, comment="正文/描述")
    extra: dict = Column(JSON, comment="扩展数据(卡片列表、标签、价格等)")
    is_active: bool = Column(Boolean, default=True)
    created_at: DateTime = Column(DateTime, server_default=func.now())
    updated_at: DateTime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ContentBlock(id={self.id}, page='{self.page}', section='{self.section}', lang='{self.lang}')>"
