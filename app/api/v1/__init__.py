from fastapi import APIRouter

from app.api.v1 import (
    auth, users, securities, market, stock_pools, factors,
    models, timing, portfolios, backtests, simulated_portfolios,
    products, subscriptions, reports, task_logs, alert_logs, performance,
    strategies, notifications,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(securities.router, prefix="/securities", tags=["证券管理"])
api_router.include_router(market.router, prefix="/market", tags=["市场数据"])
api_router.include_router(stock_pools.router, prefix="/stock-pools", tags=["股票池管理"])
api_router.include_router(factors.router, prefix="/factors", tags=["因子管理"])
api_router.include_router(models.router, prefix="/models", tags=["模型管理"])
api_router.include_router(timing.router, prefix="/timing", tags=["择时管理"])
api_router.include_router(portfolios.router, prefix="/portfolios", tags=["组合管理"])
api_router.include_router(backtests.router, prefix="/backtests", tags=["回测管理"])
api_router.include_router(simulated_portfolios.router, prefix="/simulated-portfolios", tags=["模拟组合"])
api_router.include_router(products.router, prefix="/products", tags=["产品管理"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["订阅管理"])
api_router.include_router(reports.router, prefix="/reports", tags=["报告管理"])
api_router.include_router(task_logs.router, prefix="/task-logs", tags=["任务日志"])
api_router.include_router(alert_logs.router, prefix="/alert-logs", tags=["告警日志"])
api_router.include_router(performance.router, prefix="/performance", tags=["绩效分析"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["策略管理"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知管理"])
