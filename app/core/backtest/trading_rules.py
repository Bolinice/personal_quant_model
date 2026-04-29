"""A股交易规则 — 从backtest_engine提取"""

from app.core.backtest_engine import (
    GEM_LIMIT,
    GEM_LIMIT_PCT,
    LOT_SIZE,
    MAIN_BOARD_LIMIT,
    MAIN_BOARD_LIMIT_PCT,
    NORTH_LIMIT,
    NORTH_LIMIT_PCT,
    ST_LIMIT,
    ST_LIMIT_PCT,
    STAR_LIMIT,
    STAR_LIMIT_PCT,
)

__all__ = [
    "GEM_LIMIT",
    "GEM_LIMIT_PCT",
    "LOT_SIZE",
    "MAIN_BOARD_LIMIT",
    "MAIN_BOARD_LIMIT_PCT",
    "NORTH_LIMIT",
    "NORTH_LIMIT_PCT",
    "STAR_LIMIT",
    "STAR_LIMIT_PCT",
    "ST_LIMIT",
    "ST_LIMIT_PCT",
]
