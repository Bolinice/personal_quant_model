"""回测指标计算 — 从backtest_engine提取"""

# 指标计算集成在 ABShareBacktestEngine._calc_metrics() 中
# 可通过以下方式访问:
#   from app.core.backtest import ABShareBacktestEngine
#   result = engine.run(...)
#   result.metrics  # 包含所有回测指标

from app.core.backtest_engine import ABShareBacktestEngine

__all__ = ["ABShareBacktestEngine"]