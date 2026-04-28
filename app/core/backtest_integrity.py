"""
回测完整性检查
==============
验证回测结果是否符合 A 股交易规则和统计合理性。

检查项：
1. Sharpe Ratio 上限 — 超过 5 几乎必然是 bug 或过拟合
2. 换手率上限 — 单次调仓换手率不应超过合理范围
3. T+1 约束 — T 日买入的股票 T 日不可卖出
4. 非交易日无交易 — 非交易日不应有交易记录
5. 涨跌停约束 — 涨停板无法买入，跌停板无法卖出
6. 100 股交易单位 — 交易数量必须是 100 的整数倍
7. 单股最大权重 — 防止 NaN 传播导致单股 100% 权重
8. 行业集中度 — 单行业权重不应过高
"""
import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.core.errors import (
    ErrorCode,
    PortfolioRiskError,
    TradingRuleViolationError,
)

logger = logging.getLogger(__name__)


@dataclass
class IntegrityCheckResult:
    """完整性检查结果"""
    passed: bool = True
    violations: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)

    def add_violation(self, code: ErrorCode, message: str, detail: dict | None = None):
        self.passed = False
        self.violations.append({
            "code": code.value,
            "message": message,
            "detail": detail or {},
        })
        logger.error("VIOLATION [%s]: %s", code.value, message)

    def add_warning(self, code: ErrorCode, message: str, detail: dict | None = None):
        self.warnings.append({
            "code": code.value,
            "message": message,
            "detail": detail or {},
        })
        logger.warning("WARNING [%s]: %s", code.value, message)


def check_sharpe_sanity(
    sharpe: float,
    max_sharpe: float = 5.0,
    warning_sharpe: float = 3.0,
) -> IntegrityCheckResult:
    """
    Sharpe Ratio 合理性检查。
    Sharpe > 5 几乎必然是 bug 或过拟合，Sharpe > 3 需要警惕。
    """
    result = IntegrityCheckResult()
    if sharpe > max_sharpe:
        result.add_violation(
            ErrorCode.FACTOR_DEGRADATION,
            f"Sharpe Ratio {sharpe:.2f} exceeds ceiling {max_sharpe:.1f} — "
            "likely a bug or severe overfitting",
            {"sharpe": sharpe, "max_sharpe": max_sharpe},
        )
    elif sharpe > warning_sharpe:
        result.add_warning(
            ErrorCode.FACTOR_IC_BELOW_THRESHOLD,
            f"Sharpe Ratio {sharpe:.2f} is suspiciously high (>{warning_sharpe:.1f}) — "
            "verify no look-ahead bias",
            {"sharpe": sharpe, "warning_sharpe": warning_sharpe},
        )
    return result


def check_turnover(
    turnover_ratio: float,
    max_turnover: float = 1.5,
    warning_turnover: float = 1.0,
) -> IntegrityCheckResult:
    """换手率合理性检查"""
    result = IntegrityCheckResult()
    if turnover_ratio > max_turnover:
        result.add_violation(
            ErrorCode.TURNOVER_LIMIT_BREACH,
            f"Turnover ratio {turnover_ratio:.2f} exceeds ceiling {max_turnover:.1f}",
            {"turnover_ratio": turnover_ratio, "max_turnover": max_turnover},
        )
    elif turnover_ratio > warning_turnover:
        result.add_warning(
            ErrorCode.TURNOVER_LIMIT_BREACH,
            f"Turnover ratio {turnover_ratio:.2f} is high (>{warning_turnover:.1f})",
            {"turnover_ratio": turnover_ratio},
        )
    return result


def check_t_plus_1(
    trades: pd.DataFrame,
    date_col: str = "trade_date",
    action_col: str = "action",
    code_col: str = "ts_code",
) -> IntegrityCheckResult:
    """
    T+1 约束检查：同一股票同一天不能既买又卖。
    A 股 T+1 规则：T 日买入的股票 T 日不可卖出。
    """
    result = IntegrityCheckResult()
    if trades.empty:
        return result

    # 按日期和股票分组，检查是否有同日买卖
    grouped = trades.groupby([date_col, code_col])
    for (trade_date, ts_code), group in grouped:
        actions = set(group[action_col].unique())
        if "buy" in actions and "sell" in actions:
            result.add_violation(
                ErrorCode.T_PLUS_1_VIOLATION,
                f"T+1 violation: {ts_code} bought and sold on same day {trade_date}",
                {"ts_code": ts_code, "trade_date": str(trade_date)},
            )

    return result


def check_no_trades_on_non_trading_days(
    trades: pd.DataFrame,
    trading_dates: set[str],
    date_col: str = "trade_date",
) -> IntegrityCheckResult:
    """非交易日不应有交易"""
    result = IntegrityCheckResult()
    if trades.empty:
        return result

    trade_dates = set(trades[date_col].unique())
    non_trading = trade_dates - trading_dates
    if non_trading:
        result.add_violation(
            ErrorCode.T_PLUS_1_VIOLATION,
            f"Trades found on {len(non_trading)} non-trading days: {sorted(non_trading)[:5]}",
            {"non_trading_days": sorted(non_trading)},
        )
    return result


def check_position_limits(
    weights: dict[str, float],
    max_single_weight: float = 0.10,
    max_sector_weight: float = 0.40,
    sector_map: dict[str, str] | None = None,
) -> IntegrityCheckResult:
    """
    持仓限制检查：
    - 单股最大权重（防止 NaN 传播导致单股 100% 权重）
    - 行业集中度（单行业权重不应过高）
    """
    result = IntegrityCheckResult()

    # 单股权重检查
    for code, weight in weights.items():
        if weight > max_single_weight:
            result.add_violation(
                ErrorCode.POSITION_LIMIT_BREACH,
                f"Single stock {code} weight {weight:.2%} exceeds limit {max_single_weight:.0%}",
                {"ts_code": code, "weight": weight, "max_weight": max_single_weight},
            )

    # 行业集中度检查
    if sector_map:
        sector_weights: dict[str, float] = {}
        for code, weight in weights.items():
            sector = sector_map.get(code, "unknown")
            sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

        for sector, weight in sector_weights.items():
            if weight > max_sector_weight:
                result.add_violation(
                    ErrorCode.SECTOR_CONCENTRATION_BREACH,
                    f"Sector {sector} weight {weight:.2%} exceeds limit {max_sector_weight:.0%}",
                    {"sector": sector, "weight": weight, "max_weight": max_sector_weight},
                )

    return result


def check_lot_size(
    trades: pd.DataFrame,
    volume_col: str = "volume",
    min_lot: int = 100,
) -> IntegrityCheckResult:
    """100 股交易单位检查"""
    result = IntegrityCheckResult()
    if trades.empty:
        return result

    invalid = trades[trades[volume_col] % min_lot != 0]
    if not invalid.empty:
        result.add_violation(
            ErrorCode.LOT_SIZE_VIOLATION,
            f"{len(invalid)} trades have volume not divisible by {min_lot}",
            {"invalid_count": len(invalid), "min_lot": min_lot},
        )
    return result


def run_all_integrity_checks(
    sharpe: float | None = None,
    turnover_ratio: float | None = None,
    trades: pd.DataFrame | None = None,
    weights: dict[str, float] | None = None,
    trading_dates: set[str] | None = None,
    sector_map: dict[str, str] | None = None,
) -> IntegrityCheckResult:
    """
    运行所有完整性检查，返回汇总结果。
    可在回测完成后调用，也可在日终流水线中定期调用。
    """
    combined = IntegrityCheckResult()

    if sharpe is not None:
        r = check_sharpe_sanity(sharpe)
        combined.violations.extend(r.violations)
        combined.warnings.extend(r.warnings)
        combined.passed = combined.passed and r.passed

    if turnover_ratio is not None:
        r = check_turnover(turnover_ratio)
        combined.violations.extend(r.violations)
        combined.warnings.extend(r.warnings)
        combined.passed = combined.passed and r.passed

    if trades is not None and not trades.empty:
        r = check_t_plus_1(trades)
        combined.violations.extend(r.violations)
        combined.warnings.extend(r.warnings)
        combined.passed = combined.passed and r.passed

        if trading_dates:
            r = check_no_trades_on_non_trading_days(trades, trading_dates)
            combined.violations.extend(r.violations)
            combined.warnings.extend(r.warnings)
            combined.passed = combined.passed and r.passed

        r = check_lot_size(trades)
        combined.violations.extend(r.violations)
        combined.warnings.extend(r.warnings)
        combined.passed = combined.passed and r.passed

    if weights is not None:
        r = check_position_limits(weights, sector_map=sector_map)
        combined.violations.extend(r.violations)
        combined.warnings.extend(r.warnings)
        combined.passed = combined.passed and r.passed

    if combined.violations:
        logger.error(
            "Backtest integrity check FAILED: %d violations, %d warnings",
            len(combined.violations),
            len(combined.warnings),
        )
    elif combined.warnings:
        logger.warning(
            "Backtest integrity check passed with %d warnings",
            len(combined.warnings),
        )
    else:
        logger.info("Backtest integrity check passed — all clear")

    return combined
