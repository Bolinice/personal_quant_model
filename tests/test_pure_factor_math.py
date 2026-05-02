"""
测试 app/core/pure/factor_math.py 中的纯函数
"""

import numpy as np
import pandas as pd
import pytest

from app.core.pure.factor_math import (
    calc_amihud_illiquidity,
    calc_bollinger_position,
    calc_bp,
    calc_cash_flow_manipulation,
    calc_cfo_to_net_profit,
    calc_cfp_ttm,
    calc_current_ratio,
    calc_earnings_stability,
    calc_earnings_surprise,
    calc_ep_ttm,
    calc_eps_revision,
    calc_goodwill_ratio,
    calc_gross_profit_margin,
    calc_intraday_return,
    calc_ipo_age,
    calc_large_order_ratio,
    calc_limit_up_down_ratio,
    calc_macd_signal,
    calc_margin_signal,
    calc_momentum_skip,
    calc_net_profit_margin,
    calc_north_holding_change,
    calc_north_net_buy_ratio,
    calc_obv_ratio,
    calc_overnight_return,
    calc_rating_upgrade_ratio,
    calc_reversal_1m,
    calc_roa,
    calc_roe,
    calc_rsi,
    calc_size_momentum_interaction,
    calc_sloan_accrual,
    calc_smart_money_ratio,
    calc_sp_ttm,
    calc_turnover_mean,
    calc_value_quality_interaction,
    calc_volatility_annualized,
    calc_vpin,
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


class TestAccrualFactors:
    """测试应计项因子"""

    def test_calc_sloan_accrual_with_prev(self):
        net_profit = pd.Series([1e8, 2e8, 3e8])
        operating_cash_flow = pd.Series([0.8e8, 1.5e8, 2.5e8])
        total_assets = pd.Series([10e8, 20e8, 30e8])
        total_assets_prev = pd.Series([9e8, 18e8, 27e8])
        result = calc_sloan_accrual(net_profit, operating_cash_flow, total_assets, total_assets_prev)
        # 应计 = (净利润 - 经营现金流) / 平均总资产
        expected = pd.Series([0.2e8 / 9.5e8, 0.5e8 / 19e8, 0.5e8 / 28.5e8])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_sloan_accrual_without_prev(self):
        net_profit = pd.Series([1e8, 2e8, 3e8])
        operating_cash_flow = pd.Series([0.8e8, 1.5e8, 2.5e8])
        total_assets = pd.Series([10e8, 20e8, 30e8])
        result = calc_sloan_accrual(net_profit, operating_cash_flow, total_assets)
        # 应计 = (净利润 - 经营现金流) / 总资产
        expected = pd.Series([0.2e8 / 10e8, 0.5e8 / 20e8, 0.5e8 / 30e8])
        pd.testing.assert_series_equal(result, expected)


class TestEarningsQualityFactors:
    """测试盈余质量因子"""

    def test_calc_cash_flow_manipulation(self):
        net_profit = pd.Series([1e8, 2e8, 3e8])
        operating_cash_flow = pd.Series([0.8e8, 2.5e8, 2.7e8])
        result = calc_cash_flow_manipulation(net_profit, operating_cash_flow)
        # |CFO - 净利润| / |净利润|
        expected = pd.Series([0.2e8 / 1e8, 0.5e8 / 2e8, 0.3e8 / 3e8])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_cfo_to_net_profit(self):
        operating_cash_flow = pd.Series([0.8e8, 2e8, 3e8])
        net_profit = pd.Series([1e8, 2e8, 3e8])
        result = calc_cfo_to_net_profit(operating_cash_flow, net_profit)
        expected = pd.Series([0.8, 1.0, 1.0])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_cfo_to_net_profit_clipping(self):
        operating_cash_flow = pd.Series([10e8, -10e8, 2e8])
        net_profit = pd.Series([1e8, 1e8, 2e8])
        result = calc_cfo_to_net_profit(operating_cash_flow, net_profit, clip_range=(-5, 5))
        # 10/1=10 应该被截断为5, -10/1=-10 应该被截断为-5
        expected = pd.Series([5.0, -5.0, 1.0])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_earnings_stability(self):
        net_profit_std = pd.Series([0.1e8, 0.2e8, 0.5e8])
        net_profit_mean = pd.Series([1e8, 2e8, 5e8])
        result = calc_earnings_stability(net_profit_std, net_profit_mean)
        # CV = std / |mean|, stability = 1/(1+CV)
        cv1 = 0.1e8 / 1e8  # 0.1
        cv2 = 0.2e8 / 2e8  # 0.1
        cv3 = 0.5e8 / 5e8  # 0.1
        expected = pd.Series([1 / (1 + cv1), 1 / (1 + cv2), 1 / (1 + cv3)])
        pd.testing.assert_series_equal(result, expected)


class TestRiskPenaltyFactors:
    """测试风险惩罚因子"""

    def test_calc_goodwill_ratio(self):
        goodwill = pd.Series([1e8, 2e8, 3e8])
        total_equity = pd.Series([10e8, 20e8, 30e8])
        result = calc_goodwill_ratio(goodwill, total_equity)
        expected = pd.Series([0.1, 0.1, 0.1])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_goodwill_ratio_zero_equity(self):
        goodwill = pd.Series([1e8, 2e8, 3e8])
        total_equity = pd.Series([10e8, 0, 30e8])
        result = calc_goodwill_ratio(goodwill, total_equity)
        assert result.iloc[0] == 0.1
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 0.1


class TestInteractionFactors:
    """测试因子交互项"""

    def test_calc_value_quality_interaction(self):
        ep_ttm = pd.Series([0.1, 0.15, 0.2])
        roe = pd.Series([0.15, 0.2, 0.25])
        result = calc_value_quality_interaction(ep_ttm, roe)
        expected = pd.Series([0.015, 0.03, 0.05])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_size_momentum_interaction(self):
        market_cap = pd.Series([1e9, 10e9, 100e9])
        momentum = pd.Series([0.1, 0.2, 0.3])
        result = calc_size_momentum_interaction(market_cap, momentum)
        # log(1e9) * 0.1, log(10e9) * 0.2, log(100e9) * 0.3
        expected = pd.Series([np.log(1e9) * 0.1, np.log(10e9) * 0.2, np.log(100e9) * 0.3])
        pd.testing.assert_series_equal(result, expected)


class TestNorthboundFactors:
    """测试北向资金因子"""

    def test_calc_north_net_buy_ratio(self):
        north_net_buy = pd.Series([1e6, 2e6, 3e6])
        daily_volume = pd.Series([10e6, 20e6, 30e6])
        result = calc_north_net_buy_ratio(north_net_buy, daily_volume)
        expected = pd.Series([0.1, 0.1, 0.1])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_north_holding_change(self):
        north_holding = pd.Series([100, 105, 110, 115, 120, 125])
        result = calc_north_holding_change(north_holding, period=5)
        # 前5个值应该是NaN
        assert result.iloc[:5].isna().all()
        # 第6个值: 125/100 - 1 = 0.25
        assert abs(result.iloc[5] - 0.25) < 1e-10


class TestMicrostructureFactors:
    """测试微观结构因子"""

    def test_calc_large_order_ratio(self):
        large_order_volume = pd.Series([1e6, 2e6, 3e6])
        super_large_order_volume = pd.Series([0.5e6, 1e6, 1.5e6])
        total_volume = pd.Series([10e6, 20e6, 30e6])
        result = calc_large_order_ratio(large_order_volume, super_large_order_volume, total_volume)
        expected = pd.Series([0.15, 0.15, 0.15])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_overnight_return(self):
        open_price = pd.Series([102, 105, 103])
        prev_close = pd.Series([100, 104, 105])
        result = calc_overnight_return(open_price, prev_close)
        expected = pd.Series([0.02, 105/104 - 1, 103/105 - 1])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_intraday_return(self):
        close = pd.Series([105, 103, 107])
        open_price = pd.Series([100, 105, 105])
        result = calc_intraday_return(close, open_price)
        expected = pd.Series([0.05, 103/105 - 1, 107/105 - 1])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_vpin(self):
        abs_return = pd.Series([0.02, 0.03, 0.01])
        volume_ratio = pd.Series([1.5, 2.0, 1.2])
        result = calc_vpin(abs_return, volume_ratio)
        expected = pd.Series([0.03, 0.06, 0.012])
        pd.testing.assert_series_equal(result, expected)


class TestTechnicalFactors:
    """测试技术指标因子"""

    def test_calc_rsi(self):
        # 构造上涨趋势的价格序列，需要足够长
        close = pd.Series(100 + np.arange(50) * 2)
        result = calc_rsi(close, period=14)
        # RSI需要至少period+1个数据点才能开始计算
        # EMA需要一些数据才能稳定，检查后半部分
        valid_results = result.iloc[20:].dropna()
        # 上涨趋势RSI应该>50
        assert len(valid_results) > 0
        assert (valid_results > 50).all()

    def test_calc_bollinger_position(self):
        # 构造价格序列
        close = pd.Series([100, 102, 104, 103, 105, 107, 106, 108, 110, 109] * 3)
        result = calc_bollinger_position(close, period=10, num_std=2.0)
        # rolling(10)需要10个数据点，所以前9个是NaN
        assert result.iloc[:9].isna().all()
        # 位置应该在[-1, 1]范围内
        valid_results = result.iloc[9:].dropna()
        assert (valid_results >= -1).all()
        assert (valid_results <= 1).all()

    def test_calc_macd_signal(self):
        # 构造价格序列
        close = pd.Series(100 + np.arange(50) * 0.5)
        result = calc_macd_signal(close, fast=12, slow=26, signal=9)
        # MACD从第一个数据点就开始计算（EMA不需要等待）
        # 但前面的值可能不稳定，我们只检查后面的值
        valid_results = result.iloc[35:].dropna()
        # 上涨趋势MACD信号应该>0
        assert len(valid_results) > 0
        assert (valid_results > 0).all()

    def test_calc_obv_ratio(self):
        # 构造价格和成交量序列
        close = pd.Series([100, 102, 104, 103, 105, 107, 106, 108, 110, 109] * 3)
        volume = pd.Series([1e6, 1.5e6, 2e6, 1.8e6, 2.2e6, 2.5e6, 2.3e6, 2.7e6, 3e6, 2.8e6] * 3)
        result = calc_obv_ratio(close, volume, period=10, min_periods=5)
        # rolling(10, min_periods=5)需要至少5个数据点
        # pct_change产生1个NaN，所以前4个是NaN
        assert result.iloc[:4].isna().all()
        # 比率应该在[-3, 3]范围内
        valid_results = result.iloc[4:].dropna()
        assert (valid_results >= -3).all()
        assert (valid_results <= 3).all()


class TestAnalystFactors:
    """测试分析师因子"""

    def test_calc_eps_revision(self):
        current_eps = pd.Series([1.2, 1.5, 1.8])
        prev_eps = pd.Series([1.0, 1.2, 1.5])
        result = calc_eps_revision(current_eps, prev_eps)
        expected = pd.Series([0.2, 0.25, 0.2])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_rating_upgrade_ratio(self):
        current_rating = pd.Series([2.0, 2.5, 3.0])
        prev_rating = pd.Series([2.5, 3.0, 3.5])
        result = calc_rating_upgrade_ratio(current_rating, prev_rating)
        # (2.5-2.0)/2.5=0.2, (3.0-2.5)/3.0=0.167, (3.5-3.0)/3.5=0.143
        expected = pd.Series([0.2, (3.0 - 2.5) / 3.0, (3.5 - 3.0) / 3.5])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_earnings_surprise(self):
        actual_eps = pd.Series([1.2, 0.8, 1.5])
        expected_eps = pd.Series([1.0, 1.0, 1.5])
        result = calc_earnings_surprise(actual_eps, expected_eps)
        expected = pd.Series([0.2, -0.2, 0.0])
        pd.testing.assert_series_equal(result, expected)


class TestAShareSpecificFactors:
    """测试A股特色因子"""

    def test_calc_limit_up_down_ratio(self):
        pct_chg = pd.Series([10.0, -10.0, 5.0, -5.0, 0.0])
        is_limit_up, is_limit_down = calc_limit_up_down_ratio(pct_chg, limit_pct=10.0, tolerance=0.01)
        # 10.0 >= 10-0.01 = True
        assert is_limit_up.iloc[0] == 1.0
        # -10.0 <= -(10-0.01) = True
        assert is_limit_down.iloc[1] == 1.0
        # 5.0不是涨停
        assert is_limit_up.iloc[2] == 0.0

    def test_calc_ipo_age(self):
        list_date = pd.Series(['2020-01-01', '2021-06-01', '2022-01-01'])
        trade_date = pd.Series(['2023-01-01', '2023-01-01', '2023-01-01'])
        result = calc_ipo_age(list_date, trade_date)
        # 约3年、1.5年、1年
        assert result.iloc[0] > 2.9
        assert result.iloc[0] < 3.1
        assert result.iloc[1] > 1.4
        assert result.iloc[1] < 1.7


class TestSmartMoneyFactors:
    """测试聪明钱因子"""

    def test_calc_smart_money_ratio(self):
        large_order_volume = pd.Series([1e6, 2e6, 3e6])
        super_large_order_volume = pd.Series([0.5e6, 1e6, 1.5e6])
        total_volume = pd.Series([10e6, 20e6, 30e6])
        result = calc_smart_money_ratio(large_order_volume, super_large_order_volume, total_volume)
        expected = pd.Series([0.15, 0.15, 0.15])
        pd.testing.assert_series_equal(result, expected)

    def test_calc_margin_signal(self):
        margin_balance = pd.Series([100, 105, 110, 115, 120, 125])
        result = calc_margin_signal(margin_balance, period=5)
        # 前5个值应该是NaN
        assert result.iloc[:5].isna().all()
        # 第6个值: 125/100 - 1 = 0.25
        assert abs(result.iloc[5] - 0.25) < 1e-10
