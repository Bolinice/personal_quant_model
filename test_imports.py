#!/usr/bin/env python3
"""
测试所有导入是否能正常工作
"""

def test_imports():
    """测试所有模块导入"""
    print("开始测试导入...")

    try:
        # 测试核心配置
        from app.core.config import settings
        print("✅ app.core.config")

        # 测试数据库连接
        from app.db.connection import engine, SessionLocal
        print("✅ app.db.connection")

        # 测试缓存
        from app.core.cache import cache_service
        print("✅ app.core.cache")

        # 测试日志
        from app.core.logging import logger
        print("✅ app.core.logging")

        # 测试Celery
        from app.core.celery_config import celery_app
        print("✅ app.core.celery_config")

        # 测试中间件
        from app.middleware.middleware import MetricsMiddleware, LoggingMiddleware, RateLimitMiddleware
        print("✅ app.middleware.middleware")

        # 测试监控
        from app.monitoring.metrics import record_request
        print("✅ app.monitoring.metrics")

        # 测试模型
        from app.models import User, Security, Backtest, SimulatedPortfolio
        print("✅ app.models")

        # 测试schemas
        from app.schemas import UserCreate, SecurityCreate, BacktestCreate
        print("✅ app.schemas")

        # 测试服务
        from app.services import get_securities, create_backtest
        print("✅ app.services")

        # 测试API
        from app.api.v1 import auth, users, securities, market, backtests
        print("✅ app.api.v1")

        print("\n🎉 所有导入测试通过！")

    except Exception as e:
        print(f"\n❌ 导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    test_imports()