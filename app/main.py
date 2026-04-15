from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import auth, users, securities, market, stock_pools, factors, models, timing, portfolios, backtests, simulated_portfolios, products, subscriptions, reports, task_logs, alert_logs

app = FastAPI(
    title="A股多因子增强策略平台",
    description="基于多因子选股模型的量化投资策略平台",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含API路由
app.include_router(auth.router, prefix="/api/v1", tags=["认证"])
app.include_router(users.router, prefix="/api/v1", tags=["用户管理"])
app.include_router(securities.router, prefix="/api/v1", tags=["证券管理"])
app.include_router(market.router, prefix="/api/v1", tags=["市场数据"])
app.include_router(stock_pools.router, prefix="/api/v1", tags=["股票池管理"])
app.include_router(factors.router, prefix="/api/v1", tags=["因子管理"])
app.include_router(models.router, prefix="/api/v1", tags=["模型管理"])
app.include_router(timing.router, prefix="/api/v1", tags=["择时管理"])
app.include_router(portfolios.router, prefix="/api/v1", tags=["组合管理"])
app.include_router(backtests.router, prefix="/api/v1", tags=["回测管理"])
app.include_router(simulated_portfolios.router, prefix="/api/v1", tags=["模拟组合"])
app.include_router(products.router, prefix="/api/v1", tags=["产品管理"])
app.include_router(subscriptions.router, prefix="/api/v1", tags=["订阅管理"])
app.include_router(reports.router, prefix="/api/v1", tags=["报告管理"])
app.include_router(task_logs.router, prefix="/api/v1", tags=["任务日志"])
app.include_router(alert_logs.router, prefix="/api/v1", tags=["告警日志"])
app.include_router(performance.router, prefix="/api/v1", tags=["绩效分析"])

@app.get("/")
async def root():
    return {"message": "A股多因子增强策略平台 API", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
