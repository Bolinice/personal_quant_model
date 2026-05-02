"""
测试 app/core/pure/factor_math.py 中的纯函数
"""

import numpy as np
import pandas as pd
import pytest

from app.core.pure.factor_math import (
    calc_amihud_illiquidity,
    calc_bp,
    calc_cfp_ttm,
    calc_current_ratio,
    calc_ep_ttm,
    calc_gross_profit_margin,
    calc_momentum_skip,
    calc_net_profit_margin,
    calc_reversal_1m,
    calc_roa,
    calc_roe,
    calc_sp_ttm,
    calc_turnover_mean,
    calc_volatility_annualized,
    calc_yoy_growth,
    calc_zero_return_ratio,
    safe_divide,
)


class TestSafeDivide:
    """测试安全除法函数"""

    def test_safe_divide_normal(self):
        numerator = pd.Series([10, 20, 30])
        denominator = pd.Series([2, 4, 5])
        result = safe_divide(numerator, denominator)
        expected = pd.Series([5.0, 5.0, 6.0])
        pd.testing.assert_series_equal(result, expected)

    def test_safe_divide_zero_denominator(self):
        numerator = pd.Series([10, 20, 30])
        denominator = pd.Series([2, 0, 5])
        result = safe_divide(numerator, denominator)
        assert result.iloc[0] == 5.0
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 6.0

    def test_safe_divide_small_denominator(self):
        numerator = pd.Series([10, 20, 30])
        denominator = pd.Series([2, 1e-10, 5])
        result = safe_divide(numerator, denominator, eps=1e-8)
        assert result.iloc[0] == 5.0
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 6.0


class TestMomentumFactors:
    """测试动量因子"""

    def test_calc_momentum_skip(self):
        # 构造单调上涨的价格序列
        close = pd.Series(100 + np.arange(100) * 0.5)
        result = calc_momentum_skip(close, skip_period=20, lookback_period=60)
        # 前60个值应该是NaN
        assert result.iloc[:60].isna().all()
        # 后面的值应该是正数（上涨趋势）
        valid_results = result.iloc[60:].dropna()
        assert (valid_results > 0).all()

    def test_calc_reversal_1m(self):
        # 构造单调上涨的价格序列
        close = pd.Series(100 + np.arange(30) * 2)
        result = calc_reversal_1m(close, period=5)
        # 前5个值应该是NaN
        assert result.iloc[:5].isna().all()
        # 后面的值应该是正数（上涨趋势）
        valid_results = result.iloc[5:].dropna()
        assert (valid_results > 0).all()


class TestVolatilityFactors:
    """测试波动率因子"""

    def test_calc_volatility_annualized(self):
        # 构造有波动的价格序列
        np.random.seed(42)
        close = pd.Series(100 * (1 + np.random.randn(100) * 0.02).cumprod())
        result = calc_volatility_annualized(close, period=20, min_periods=10)
        # 前10个值应该是NaN
        assert result.iloc[:10].isna().all()
        # 后面的值应该是正数
        assert (result.iloc[10:] > 0).all()
        # 年化波动率应该在合理范围内（0-100%）
        assert (result.iloc[10:] < 1.0).all()

    def test_calc_volatility_constant_price(self):
        close = pd.Series([100] * 50)
        result = calc_volatility_annualized(close, period=20, min_periods=10)
        # 常数价格的波动率应该是0
        assert (result.iloc[10:] == 0).all()


class TestLiquidityFactors:
    """测试流动性因子"""

    def test_calc_turnover_mean(self):
        turnover_rate = pd.Series([1.0, 1.5, 2.0, 2.5, 3.0] * 10)
        result = calc_turnover_mean(turnover_rate, period=5, min_periods=3)
        # 前3个值应该有结果
        assert result.iloc[2:].notna().all()
        # 均值应该在合理范围内
        assert (result.iloc[4:] >= 1.0).all()
        assert (result.iloc[4:] <= 3.0).all()

    def test_calc_amihud_illiquidity(self):
        close = pd.Series([100, 102, 104, 103, 105, 107, 106, 108, 110, 109] * 5)
        amount = pd.Series([1e6, 1.5e6, 2e6, 1.8e6, 2.2e6, 2.5e6, 2.3e6, 2.7e6, 3e6, 2.8e6] * 5)
        result = calc_amihud_illiquidity(close, amount, period=5, min_periods=3)
        # 前3个值应该是NaN（pct_change产生1个NaN + rolling min_periods=3）
        assert result.iloc[:3].isna().all()
        # 后面的值应该是正数
        valid_results = result.iloc[3:].dropna()
        assert (valid_results > 0).all()

    def test_calc_zero_return_ratio(self):
        # 构造有零收益的序列
        close = pd.Series([100, 100.05, 100.05, 100.1, 100.1, 100.15, 100.15, 100.2, 100.2, 100.25] * 3)
        result = calc_zero_return_ratio(close, period=5, min_periods=3, threshold=0.001)
        # 前2个值应该是NaN（pct_change产生1个NaN + rolling min_periods=3）
        assert result.iloc[:2].isna().all()
        # 后面的值应该在[0, 1]范围内
        valid_results = result.iloc[2:].dropna()
        assert (valid_results >= 0).all()
        assert (valid_results <= 1).all()


class TestValuationFactors:
    """测试估值因子"""

    def test_calc_ep_ttm(self):
        net_profit = pd.Series([1e8, 2e8, 3e8, 4e8, 5e8])
        total_market_cap = pd.Series([10e8, 20e8, 30e8, 40e8, 50e8])
        result = calc_ep_ttm(net_profit, total_market_cap)
        expected = pd.Series([0.1, 0.1, 0.1, 0.1, 0.1])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_bp(self):
        total_equity = pd.Series([5e8, 10e8, 15e8, 20e8, 25e8])
        total_market_cap = pd.Series([10e8, 20e8, 30e8, 40e8, 50e8])
        result = calc_bp(total_equity, total_market_cap)
        expected = pd.Series([0.5, 0.5, 0.5, 0.5, 0.5])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_sp_ttm(self):
        revenue = pd.Series([20e8, 40e8, 60e8, 80e8, 100e8])
        total_market_cap = pd.Series([10e8, 20e8, 30e8, 40e8, 50e8])
        result = calc_sp_ttm(revenue, total_market_cap)
        expected = pd.Series([2.0, 2.0, 2.0, 2.0, 2.0])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_cfp_ttm(self):
        operating_cash_flow = pd.Series([1.5e8, 3e8, 4.5e8, 6e8, 7.5e8])
        total_market_cap = pd.Series([10e8, 20e8, 30e8, 40e8, 50e8])
        result = calc_cfp_ttm(operating_cash_flow, total_market_cap)
        expected = pd.Series([0.15, 0.15, 0.15, 0.15, 0.15])
        pd.testing.assert_series_equal(result, expected)

    def test_valuation_factors_zero_market_cap(self):
        net_profit = pd.Series([1e8, 2e8, 3e8])
        total_market_cap = pd.Series([10e8, 0, 30e8])
        result = calc_ep_ttm(net_profit, total_market_cap)
        assert result.iloc[0] == 0.1
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 0.1


class TestGrowthFactors:
    """测试成长因子"""

    def test_calc_yoy_growth(self):
        current = pd.Series([110, 120, 130, 140, 150])
        yoy_4q = pd.Series([100, 100, 100, 100, 100])
        result = calc_yoy_growth(current, yoy_4q)
        expected = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_yoy_growth_negative_base(self):
        current = pd.Series([10, 20, 30])
        yoy_4q = pd.Series([-100, -100, -100])
        result = calc_yoy_growth(current, yoy_4q)
        # 负基数取绝对值
        expected = pd.Series([1.1, 1.2, 1.3])
        pd.testing.assert_series_equal(result, expected)


class TestQualityFactors:
    """测试质量因子"""

    def test_calc_roe_with_prev(self):
        net_profit = pd.Series([1e8, 2e8, 3e8])
        total_equity = pd.Series([10e8, 20e8, 30e8])
        total_equity_prev = pd.Series([9e8, 18e8, 27e8])
        result = calc_roe(net_profit, total_equity, total_equity_prev)
        # ROE = 净利润 / 平均净资产
        expected = pd.Series([1e8 / 9.5e8, 2e8 / 19e8, 3e8 / 28.5e8])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_roe_without_prev(self):
        net_profit = pd.Series([1e8, 2e8, 3e8])
        total_equity = pd.Series([10e8, 20e8, 30e8])
        result = calc_roe(net_profit, total_equity)
        # ROE = 净利润 / ((期末 + 期末*0.9) / 2)
        expected = pd.Series([1e8 / 9.5e8, 2e8 / 19e8, 3e8 / 28.5e8])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_roa(self):
        net_profit = pd.Series([1e8, 2e8, 3e8])
        total_assets = pd.Series([50e8, 100e8, 150e8])
        result = calc_roa(net_profit, total_assets)
        expected = pd.Series([0.02, 0.02, 0.02])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_gross_profit_margin(self):
        gross_profit = pd.Series([3e8, 6e8, 9e8])
        revenue = pd.Series([10e8, 20e8, 30e8])
        result = calc_gross_profit_margin(gross_profit, revenue)
        expected = pd.Series([0.3, 0.3, 0.3])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_net_profit_margin(self):
        net_profit = pd.Series([1e8, 2e8, 3e8])
        revenue = pd.Series([10e8, 20e8, 30e8])
        result = calc_net_profit_margin(net_profit, revenue)
        expected = pd.Series([0.1, 0.1, 0.1])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_current_ratio(self):
        current_assets = pd.Series([20e8, 40e8, 60e8])
        current_liabilities = pd.Series([10e8, 20e8, 30e8])
        result = calc_current_ratio(current_assets, current_liabilities)
        expected = pd.Series([2.0, 2.0, 2.0])
        pd.testing.assert_series_equal(result, expected)


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_series(self):
        empty = pd.Series([], dtype=float)
        result = calc_momentum_skip(empty, skip_period=20, lookback_period=60)
        assert result.empty

    def test_all_nan_series(self):
        nan_series = pd.Series([np.nan, np.nan, np.nan])
        result = calc_volatility_annualized(nan_series, period=2, min_periods=1)
        assert result.isna().all()

    def test_single_value_series(self):
        single = pd.Series([100.0])
        result = calc_reversal_1m(single, period=1)
        assert len(result) == 1

    def test_insufficient_data(self):
        short = pd.Series([100, 101, 102])
        result = calc_volatility_annualized(short, period=20, min_periods=10)
        # 数据不足，全部为NaN
        assert result.isna().all()
