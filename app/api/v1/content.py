"""内容管理 API。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.compliance import SAFE_REPLACEMENTS, check_high_risk_text
from app.core.response import success
from app.db.base import get_db
from app.schemas.content import (
    ContentBlockCreate,
    ContentBlockUpdate,
)
from app.services.content_service import (
    create_content_block,
    get_available_pages,
    get_page_content,
    get_section_content,
    update_content_block,
)

router = APIRouter()


class CheckTextRequest(BaseModel):
    text: str


class CheckTextResponse(BaseModel):
    has_risk: bool
    found_terms: list[str]
    replacements: dict


@router.get("/pages")
def list_pages(lang: str = "zh", db: Session = Depends(get_db)):
    """获取所有可用页面列表"""
    pages = get_available_pages(lang=lang, db=db)
    return success(pages)


@router.get("/pages/{page}")
def get_page(page: str, lang: str = "zh", db: Session = Depends(get_db)):
    """获取指定页面的所有内容块"""
    content = get_page_content(page, lang=lang, db=db)
    return success(content)


@router.get("/pages/{page}/sections/{section}")
def get_section(page: str, section: str, lang: str = "zh", db: Session = Depends(get_db)):
    """获取指定页面指定区块的内容"""
    content = get_section_content(page, section, lang=lang, db=db)
    if content is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return success(content)


@router.post("/blocks")
def create_block(block: ContentBlockCreate, db: Session = Depends(get_db)):
    """创建内容块"""
    result = create_content_block(block, db=db)
    return success(result)


@router.put("/blocks/{block_id}")
def update_block(block_id: int, block_update: ContentBlockUpdate, db: Session = Depends(get_db)):
    """更新内容块"""
    block = update_content_block(block_id, block_update, db=db)
    if block is None:
        raise HTTPException(status_code=404, detail="Block not found")
    return success(block)


@router.post("/check-text")
def check_text(req: CheckTextRequest):
    """检测文本中的高风险词汇（合规审核）

    返回检测到的高风险词汇及安全替换建议。
    """
    found_terms = check_high_risk_text(req.text)
    replacements = {term: SAFE_REPLACEMENTS[term] for term in found_terms if term in SAFE_REPLACEMENTS}
    return success(
        {
            "has_risk": len(found_terms) > 0,
            "found_terms": found_terms,
            "replacements": replacements,
        }
    )
