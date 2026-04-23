"""Celery 异步任务包。"""

from app.tasks.backtests import run_backtest

__all__ = ["run_backtest"]