"""
统一响应格式
符合ADD 11节: 统一返回格式、分页格式
"""
from typing import Any, Optional, List, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')


class Response(BaseModel):
    """统一响应格式 (ADD 11.1节)"""
    code: int = 0
    message: str = "success"
    data: Any = None
    request_id: Optional[str] = None


class PageData(BaseModel):
    """分页数据格式 (ADD 11.2节)"""
    items: List[Any] = Field(default_factory=list)
    page: int = 1
    page_size: int = 20
    total: int = 0


class PageResponse(BaseModel):
    """分页响应"""
    code: int = 0
    message: str = "success"
    data: PageData = Field(default_factory=PageData)
    request_id: Optional[str] = None


def success(data: Any = None, message: str = "success") -> dict:
    """成功响应"""
    return {"code": 0, "message": message, "data": data}

# 别名: 兼容API路由中的success_response引用
success_response = success


def error(code: int = -1, message: str = "error", data: Any = None) -> dict:
    """错误响应"""
    return {"code": code, "message": message, "data": data}


def page_result(items: list, page: int, page_size: int, total: int) -> dict:
    """分页响应"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    }
