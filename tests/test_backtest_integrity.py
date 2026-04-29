"""
回测完整性检查测试
"""

import pandas as pd

from app.core.backtest_integrity import (
    check_lot_size,
    check_no_trades_on_non_trading_days,
    check_position_limits,
    check_sharpe_sanity,
    check_t_plus_1,
    check_turnover,
    run_all_integrity_checks,
)
from app.core.errors import ErrorCode


class TestSharpeSanity:
    def test_normal_sharpe_passes(self):
        result = check_sharpe_sanity(1.5)
        assert result.passed
        assert not result.violations

    def test_suspicious_sharpe_warns(self):
        result = check_sharpe_sanity(3.5)
        assert result.passed  # warning, not violation
        assert len(result.warnings) == 1

    def test_extreme_sharpe_fails(self):
        result = check_sharpe_sanity(6.0)
        assert not result.passed
        assert len(result.violations) == 1
        assert result.violations[0]["code"] == ErrorCode.FACTOR_DEGRADATION.value

    def test_negative_sharpe_passes(self):
        result = check_sharpe_sanity(-1.0)
        assert result.passed


class TestTurnoverCheck:
    def test_normal_turnover_passes(self):
        result = check_turnover(0.3)
        assert result.passed

    def test_high_turnover_warns(self):
        result = check_turnover(1.2)
        assert result.passed
        assert len(result.warnings) == 1

    def test_extreme_turnover_fails(self):
        result = check_turnover(2.0)
        assert not result.passed
        assert result.violations[0]["code"] == ErrorCode.TURNOVER_LIMIT_BREACH.value


class TestTPlusOne:
    def test_no_same_day_buy_sell(self):
        trades = pd.DataFrame(
            {
                "trade_date": ["20250110", "20250110", "20250111"],
                "ts_code": ["000001.SZ", "000002.SZ", "000001.SZ"],
                "action": ["buy", "buy", "sell"],
            }
        )
        result = check_t_plus_1(trades)
        assert result.passed

    def test_same_day_buy_sell_violation(self):
        trades = pd.DataFrame(
            {
                "trade_date": ["20250110", "20250110"],
                "ts_code": ["000001.SZ", "000001.SZ"],
                "action": ["buy", "sell"],
            }
        )
        result = check_t_plus_1(trades)
        assert not result.passed
        assert result.violations[0]["code"] == ErrorCode.T_PLUS_1_VIOLATION.value

    def test_empty_trades(self):
        result = check_t_plus_1(pd.DataFrame())
        assert result.passed


class TestNonTradingDays:
    def test_all_trading_days(self):
        trades = pd.DataFrame(
            {
                "trade_date": ["20250110", "20250113"],
                "ts_code": ["000001.SZ", "000002.SZ"],
                "action": ["buy", "sell"],
            }
        )
        trading_dates = {"20250110", "20250113"}
        result = check_no_trades_on_non_trading_days(trades, trading_dates)
        assert result.passed

    def test_non_trading_day_violation(self):
        trades = pd.DataFrame(
            {
                "trade_date": ["20250111"],  # 周六
                "ts_code": ["000001.SZ"],
                "action": ["buy"],
            }
        )
        trading_dates = {"20250110", "20250113"}
        result = check_no_trades_on_non_trading_days(trades, trading_dates)
        assert not result.passed


class TestPositionLimits:
    def test_normal_weights_pass(self):
        weights = {"000001.SZ": 0.05, "000002.SZ": 0.08, "000003.SZ": 0.03}
        result = check_position_limits(weights)
        assert result.passed

    def test_single_stock_overweight(self):
        weights = {"000001.SZ": 0.15, "000002.SZ": 0.05}
        result = check_position_limits(weights)
        assert not result.passed
        assert result.violations[0]["code"] == ErrorCode.POSITION_LIMIT_BREACH.value

    def test_sector_concentration(self):
        weights = {"000001.SZ": 0.09, "000002.SZ": 0.09, "000003.SZ": 0.09, "000004.SZ": 0.09, "000005.SZ": 0.09}
        sector_map = dict.fromkeys(weights, "银行")
        result = check_position_limits(weights, sector_map=sector_map)
        assert not result.passed
        assert any(v["code"] == ErrorCode.SECTOR_CONCENTRATION_BREACH.value for v in result.violations)


class TestLotSize:
    def test_valid_lot_sizes(self):
        trades = pd.DataFrame({"volume": [100, 200, 500]})
        result = check_lot_size(trades)
        assert result.passed

    def test_invalid_lot_sizes(self):
        trades = pd.DataFrame({"volume": [100, 150, 200]})
        result = check_lot_size(trades)
        assert not result.passed
        assert result.violations[0]["code"] == ErrorCode.LOT_SIZE_VIOLATION.value


class TestRunAllChecks:
    def test_all_pass(self):
        result = run_all_integrity_checks(
            sharpe=1.5,
            turnover_ratio=0.3,
            trades=pd.DataFrame(
                {
                    "trade_date": ["20250110"],
                    "ts_code": ["000001.SZ"],
                    "action": ["buy"],
                    "volume": [100],
                }
            ),
            weights={"000001.SZ": 0.05},
            trading_dates={"20250110"},
        )
        assert result.passed

    def test_multiple_violations(self):
        result = run_all_integrity_checks(
            sharpe=6.0,
            turnover_ratio=2.0,
        )
        assert not result.passed
        assert len(result.violations) >= 2
