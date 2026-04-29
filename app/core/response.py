"""
统一响应格式
符合ADD 11节: 统一返回格式、分页格式
所有响应包含 timestamp 字段，便于客户端判断数据新鲜度。
"""

from datetime import UTC, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


def _now_iso() -> str:
    """当前UTC时间的ISO格式"""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Response(BaseModel):
    """统一响应格式 (ADD 11.1节)"""

    code: int = 0
    message: str = "success"
    data: Any = None
    timestamp: str = Field(default_factory=_now_iso)
    request_id: str | None = None


class PageData(BaseModel):
    """分页数据格式 (ADD 11.2节)"""

    items: list[Any] = Field(default_factory=list)
    page: int = 1
    page_size: int = 20
    total: int = 0


class PageResponse(BaseModel):
    """分页响应"""

    code: int = 0
    message: str = "success"
    data: PageData = Field(default_factory=PageData)
    timestamp: str = Field(default_factory=_now_iso)
    request_id: str | None = None


def success(data: Any = None, message: str = "success") -> dict:
    """成功响应"""
    return {"code": 0, "message": message, "data": data, "timestamp": _now_iso()}


# 别名: 兼容API路由中的success_response引用
success_response = success


def error(code: int = -1, message: str = "error", data: Any = None) -> dict:
    """错误响应"""
    return {"code": code, "message": message, "data": data, "timestamp": _now_iso()}


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
        "timestamp": _now_iso(),
    }
