from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.api.v1 import auth, users, securities, market, stock_pools, factors, models, timing, portfolios, backtests, simulated_portfolios, products, subscriptions, reports, task_logs, alert_logs, performance
from app.middleware.middleware import MetricsMiddleware, LoggingMiddleware, RateLimitMiddleware

app = FastAPI(
    title="A股多因子增强策略平台",
    description="基于多因子选股模型的量化投资策略平台",
    version="1.0.0"
)

# 初始化日志系统
logger.info("Application starting...")

# 添加中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
app.add_middleware(MetricsMiddleware)

# 包含API路由 - 使用特定路径前缀避免冲突
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(users.router, prefix="/api/v1/users", tags=["用户管理"])
app.include_router(securities.router, prefix="/api/v1/securities", tags=["证券管理"])
app.include_router(market.router, prefix="/api/v1/market", tags=["市场数据"])
app.include_router(stock_pools.router, prefix="/api/v1/stock-pools", tags=["股票池管理"])
app.include_router(factors.router, prefix="/api/v1/factors", tags=["因子管理"])
app.include_router(models.router, prefix="/api/v1/models", tags=["模型管理"])
app.include_router(timing.router, prefix="/api/v1/timing", tags=["择时管理"])
app.include_router(portfolios.router, prefix="/api/v1/portfolios", tags=["组合管理"])
app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["回测管理"])
app.include_router(simulated_portfolios.router, prefix="/api/v1/simulated-portfolios", tags=["模拟组合"])
app.include_router(products.router, prefix="/api/v1/products", tags=["产品管理"])
app.include_router(subscriptions.router, prefix="/api/v1/subscriptions", tags=["订阅管理"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["报告管理"])
app.include_router(task_logs.router, prefix="/api/v1/task-logs", tags=["任务日志"])
app.include_router(alert_logs.router, prefix="/api/v1/alert-logs", tags=["告警日志"])
app.include_router(performance.router, prefix="/api/v1/performance", tags=["绩效分析"])

@app.get("/")
async def root():
    return {"message": "A股多因子增强策略平台 API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """健康检查端点"""
    try:
        # 检查数据库连接
        from app.db.connection import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")

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
