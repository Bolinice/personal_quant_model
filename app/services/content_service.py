from sqlalchemy.orm import Session
from app.db.base import with_db
from app.models.content import ContentBlock
from app.schemas.content import ContentBlockCreate, ContentBlockUpdate, PageContentOut, ContentSectionOut


@with_db
def get_page_content(page: str, lang: str = "zh", db: Session = None) -> PageContentOut:
    """获取指定页面的所有内容块，按 section 分组"""
    blocks = db.query(ContentBlock).filter(
        ContentBlock.page == page,
        ContentBlock.lang == lang,
        ContentBlock.is_active == True,
    ).order_by(ContentBlock.sort_order).all()

    sections = {}
    for block in blocks:
        sections[block.section] = ContentSectionOut(
            title=block.title,
            subtitle=block.subtitle,
            body=block.body,
            extra=block.extra,
        )

    return PageContentOut(page=page, sections=sections)


@with_db
def get_section_content(page: str, section: str, lang: str = "zh", db: Session = None) -> ContentSectionOut | None:
    """获取指定页面指定区块的内容"""
    block = db.query(ContentBlock).filter(
        ContentBlock.page == page,
        ContentBlock.section == section,
        ContentBlock.lang == lang,
        ContentBlock.is_active == True,
    ).first()

    if not block:
        return None

    return ContentSectionOut(
        title=block.title,
        subtitle=block.subtitle,
        body=block.body,
        extra=block.extra,
    )


@with_db
def get_available_pages(lang: str = "zh", db: Session = None) -> list[str]:
    """获取所有可用页面列表"""
    pages = db.query(ContentBlock.page).filter(
        ContentBlock.lang == lang,
        ContentBlock.is_active == True,
    ).distinct().all()
    return [p[0] for p in pages]


@with_db
def create_content_block(block: ContentBlockCreate, db: Session = None) -> ContentBlock:
    """创建内容块"""
    db_block = ContentBlock(**block.model_dump())
    db.add(db_block)
    db.commit()
    db.refresh(db_block)
    return db_block


@with_db
def update_content_block(block_id: int, block_update: ContentBlockUpdate, db: Session = None) -> ContentBlock | None:
    """更新内容块"""
    db_block = db.query(ContentBlock).filter(ContentBlock.id == block_id).first()
    if not db_block:
        return None
    update_data = block_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_block, key, value)
    db.commit()
    db.refresh(db_block)
    return db_block
