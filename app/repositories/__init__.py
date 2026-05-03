"""
Repository层 - 数据访问抽象
================================

职责:
- 封装所有数据库查询逻辑
- 提供统一的数据访问接口
- 处理ORM映射和缓存
- 与Core层解耦

设计原则:
- Repository只返回DataFrame或基础数据类型
- 不包含业务逻辑
- 支持批量操作
- 统一异常处理
"""

from app.repositories.market_data_repo import MarketDataRepository
from app.repositories.factor_repo import FactorRepository
from app.repositories.backtest_repo import BacktestRepository
from app.repositories.model_repo import ModelRepository

__all__ = [
    "MarketDataRepository",
    "FactorRepository",
    "BacktestRepository",
    "ModelRepository",
]
