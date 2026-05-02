"""
全局异常处理器
确保所有异常都返回统一的响应格式
"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import error


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """处理HTTP异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content=error(
            code=exc.status_code,
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        ),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """处理请求验证异常"""
    errors = []
    for error_detail in exc.errors():
        field = ".".join(str(loc) for loc in error_detail["loc"])
        message = error_detail["msg"]
        errors.append(f"{field}: {message}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error(
            code=422,
            message="请求参数验证失败",
            data={"errors": errors},
        ),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未捕获的异常"""
    import traceback

    # 记录异常堆栈
    traceback.print_exc()

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error(
            code=500,
            message="服务器内部错误",
            data={"error": str(exc)} if request.app.debug else None,
        ),
    )
