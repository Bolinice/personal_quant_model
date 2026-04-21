from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.services.content_service import (
    get_page_content, get_section_content, get_available_pages,
    create_content_block, update_content_block,
)
from app.schemas.content import (
    ContentBlockCreate, ContentBlockUpdate, ContentBlockOut,
    PageContentOut, ContentSectionOut,
)

router = APIRouter()


@router.get("/pages", response_model=List[str])
def list_pages(lang: str = "zh", db: Session = Depends(get_db)):
    """获取所有可用页面列表"""
    return get_available_pages(lang=lang, db=db)


@router.get("/pages/{page}", response_model=PageContentOut)
def get_page(page: str, lang: str = "zh", db: Session = Depends(get_db)):
    """获取指定页面的所有内容块"""
    content = get_page_content(page, lang=lang, db=db)
    return content


@router.get("/pages/{page}/sections/{section}", response_model=ContentSectionOut)
def get_section(page: str, section: str, lang: str = "zh", db: Session = Depends(get_db)):
    """获取指定页面指定区块的内容"""
    content = get_section_content(page, section, lang=lang, db=db)
    if content is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return content


@router.post("/blocks", response_model=ContentBlockOut)
def create_block(block: ContentBlockCreate, db: Session = Depends(get_db)):
    """创建内容块"""
    return create_content_block(block, db=db)


@router.put("/blocks/{block_id}", response_model=ContentBlockOut)
def update_block(block_id: int, block_update: ContentBlockUpdate, db: Session = Depends(get_db)):
    """更新内容块"""
    block = update_content_block(block_id, block_update, db=db)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    return block
