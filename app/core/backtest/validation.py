"""统计验证 — 从backtest_engine提取

Walk-Forward / 蒙特卡洛 / DSR / Bootstrap
"""

# 验证方法集成在 ABShareBacktestEngine 中
# 可通过以下方式访问:
#   from app.core.backtest import ABShareBacktestEngine
#   engine.walk_forward_analysis(...)
#   engine.monte_carlo_simulation(...)
#   engine.bootstrap_analysis(...)

from app.core.backtest_engine import ABShareBacktestEngine

__all__ = ["ABShareBacktestEngine"]