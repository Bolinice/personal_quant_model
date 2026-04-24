from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.api.v1 import api_router
from app.middleware.middleware import MetricsMiddleware, LoggingMiddleware, RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Application starting...")

    # 生产环境安全检查
    safety_warnings = settings.check_production_safety()
    if safety_warnings:
        for w in safety_warnings:
            logger.warning(f"Security: {w}")

    # 初始化数据库表
    from app.db.base import Base, engine
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")

    yield

    logger.info("Application shutting down...")


app = FastAPI(
    title="A股多因子增强策略平台",
    description="基于多因子选股模型的量化投资策略平台",
    version="2.1.0",
    lifespan=lifespan,
)


# 添加中间件确保 UTF-8 编码
@app.middleware("http")
async def add_charset_middleware(request: Request, call_next):
    response = await call_next(request)
    if "application/json" in response.headers.get("content-type", ""):
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response


# 添加中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
app.add_middleware(MetricsMiddleware)

# 注册API路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "code": 0,
        "message": "success",
        "data": {
            "name": "A股多因子增强策略平台",
            "version": "2.1.0",
            "api_prefix": "/api/v1",
        },
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        from sqlalchemy import text
        from app.db.base import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        return {"status": "healthy", "message": "All services are running"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


@app.get("/metrics")
async def metrics():
    """监控指标端点"""
    from prometheus_client import generate_latest
    return generate_latest()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
