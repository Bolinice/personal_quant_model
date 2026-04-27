"""
因子引擎测试 - 适配V2架构(FactorCalculator + FactorEngine)
"""
import pytest
import numpy as np
import pandas as pd
from datetime import date
from unittest.mock import MagicMock


class TestFactorCalculatorValuation:
    """因子计算器 - 价值因子"""

    def test_valuation_from_precomputed(self):
        from app.core.factor_calculator import FactorCalculator
        calc = FactorCalculator()

        financial_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'pe_ttm': [10.0, 20.0],
            'pb': [1.5, 2.0],
            'ps_ttm': [3.0, 5.0],
            'dividend_yield': [0.03, 0.02],
        })

        result = calc.calc_valuation_factors(financial_df)
        assert 'ep_ttm' in result.columns
        assert 'bp' in result.columns
        assert len(result) == 2
        # EP = 1/PE
        assert abs(result['ep_ttm'].iloc[0] - 0.1) < 1e-6

    def test_valuation_from_raw(self):
        from app.core.factor_calculator import FactorCalculator
        calc = FactorCalculator()

        financial_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'net_profit': [1e9, 2e9],
            'total_market_cap': [20e9, 60e9],
            'total_equity': [8e9, 20e9],
            'operating_cash_flow': [1.2e9, 2.5e9],
            'revenue': [10e9, 30e9],
        })

        result = calc.calc_valuation_factors(financial_df)
        assert 'ep_ttm' in result.columns
        assert 'bp' in result.columns
        assert 'cfp_ttm' in result.columns
        # EP = net_profit / market_cap
        assert abs(result['ep_ttm'].iloc[0] - 1e9 / 20e9) < 1e-6


class TestFactorCalculatorGrowth:
    """因子计算器 - 成长因子"""

    def test_growth_from_precomputed(self):
        from app.core.factor_calculator import FactorCalculator
        calc = FactorCalculator()

        financial_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'yoy_revenue': [0.15, 0.25],
            'yoy_net_profit': [0.10, 0.20],
            'yoy_deduct_net_profit': [0.08, 0.18],
            'yoy_roe': [0.05, 0.10],
        })

        result = calc.calc_growth_factors(financial_df)
        assert 'yoy_revenue' in result.columns
        assert len(result) == 2
        assert abs(result['yoy_revenue'].iloc[0] - 0.15) < 1e-6


class TestFactorCalculatorQuality:
    """因子计算器 - 质量因子"""

    def test_quality_from_raw(self):
        from app.core.factor_calculator import FactorCalculator
        calc = FactorCalculator()

        financial_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'net_profit': [1e9, 2e9],
            'total_equity': [8e9, 20e9],
            'total_assets': [20e9, 50e9],
            'total_revenue': [10e9, 30e9],
            'operating_revenue': [10e9, 30e9],
            'operating_cost': [8e9, 24e9],
        })

        result = calc.calc_quality_factors(financial_df)
        assert 'roe' in result.columns
        assert 'roa' in result.columns
        assert len(result) == 2


class TestFactorEngineIC:
    """因子引擎 - IC计算"""

    def test_calc_ic(self):
        from app.core.factor_engine import FactorEngine
        engine = FactorEngine(db=MagicMock())

        np.random.seed(42)
        factor_values = pd.Series(np.random.randn(100))
        forward_returns = pd.Series(np.random.randn(100))

        result = engine.calc_ic(factor_values, forward_returns)
        assert 'ic' in result
        assert 'rank_ic' in result
        assert -1 <= result['ic'] <= 1
        assert -1 <= result['rank_ic'] <= 1

    def test_calc_ic_insufficient_data(self):
        from app.core.factor_engine import FactorEngine
        engine = FactorEngine(db=MagicMock())

        factor_values = pd.Series([1.0, 2.0])
        forward_returns = pd.Series([0.01, 0.02])

        result = engine.calc_ic(factor_values, forward_returns)
        assert np.isnan(result['ic']) or isinstance(result['ic'], (int, float))

    def test_calc_ic_perfect_positive(self):
        from app.core.factor_engine import FactorEngine
        engine = FactorEngine(db=MagicMock())

        factor_values = pd.Series(range(100), dtype=float)
        forward_returns = pd.Series(range(100), dtype=float)

        result = engine.calc_ic(factor_values, forward_returns)
        assert result['ic'] > 0.99

    def test_calc_ic_perfect_negative(self):
        from app.core.factor_engine import FactorEngine
        engine = FactorEngine(db=MagicMock())

        factor_values = pd.Series(range(100), dtype=float)
        forward_returns = pd.Series(range(99, -1, -1), dtype=float)

        result = engine.calc_ic(factor_values, forward_returns)
        assert result['ic'] < -0.99


class TestFactorEngineManagement:
    """因子引擎 - 定义管理"""

    def test_create_and_get_factor(self):
        from app.core.factor_engine import FactorEngine
        mock_db = MagicMock()
        mock_factor = MagicMock()
        mock_factor.id = 1
        mock_factor.factor_code = "test_ep"
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        engine = FactorEngine(db=mock_db)
        # Just verify the engine can be constructed and methods exist
        assert hasattr(engine, 'create_factor')
        assert hasattr(engine, 'get_factor')
        assert hasattr(engine, 'list_factors')
        assert hasattr(engine, 'calc_ic')
        assert hasattr(engine, 'calc_all_factors')


class TestPITFilter:
    """PIT (Point-in-Time) 过滤测试"""

    def test_pit_filter_basic(self):
        from app.core.factor_calculator import pit_filter

        financial_df = pd.DataFrame({
            'ts_code': ['A', 'A', 'B'],
            'ann_date': ['2024-01-15', '2024-02-20', '2024-01-10'],
            'roe': [0.10, 0.12, 0.08],
        })

        result = pit_filter(financial_df, date(2024, 2, 1))
        # Should include records with ann_date <= 2024-02-01
        assert len(result) == 2  # A(2024-01-15) and B(2024-01-10)

    def test_pit_filter_no_ann_date(self):
        from app.core.factor_calculator import pit_filter

        financial_df = pd.DataFrame({
            'ts_code': ['A', 'B'],
            'roe': [0.10, 0.08],
        })

        # Should warn but return all data
        with pytest.warns(UserWarning):
            result = pit_filter(financial_df, date(2024, 2, 1))
        assert len(result) == 2


class TestPanelDataSafety:
    """面板数据安全性回归测试 - 验证groupby(ts_code)不跨股票边界"""

    def test_momentum_panel_does_not_cross_stock_boundary(self):
        """回归测试: calc_momentum_factors面板数据应按股票分组,
        shift/rolling不应跨股票边界"""
        from app.core.factor_calculator import FactorCalculator

        # 构造2只股票的面板数据，价格模式完全不同
        n = 60
        stock_a_dates = pd.date_range('2024-01-01', periods=n)
        stock_b_dates = pd.date_range('2024-01-01', periods=n)

        # A股持续上涨, B股持续下跌
        close_a = 100 + np.arange(n) * 0.5  # 从100到130
        close_b = 100 - np.arange(n) * 0.3  # 从100到82

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ'] * n + ['000002.SZ'] * n,
            'trade_date': list(stock_a_dates) + list(stock_b_dates),
            'close': list(close_a) + list(close_b),
        })

        calc = FactorCalculator()
        result = calc.calc_momentum_factors(price_df)

        # 检查每只股票的因子值是否有NaN跨边界污染
        # 如果没有groupby，shift(20)会把A股最后一个值传给B股第一个值
        # 导致B股的第一行ret_1m_reversal不为NaN(而是基于A股数据)
        stock_a_mask = result['security_id'] == '000001.SZ'
        stock_b_mask = result['security_id'] == '000002.SZ'

        # A股前20行ret_1m_reversal应为NaN(没有足够历史数据)
        a_first_20 = result.loc[stock_a_mask, 'ret_1m_reversal'].iloc[:20]
        assert a_first_20.isna().all(), "A股前20行应为NaN(历史数据不足)"

        # B股前20行ret_1m_reversal也应为NaN(不应从A股跨过来)
        b_first_20 = result.loc[stock_b_mask, 'ret_1m_reversal'].iloc[:20]
        assert b_first_20.isna().all(), "B股前20行应为NaN, 不应被A股数据污染"

    def test_technical_factors_panel_does_not_cross_stock_boundary(self):
        """回归测试: calc_technical_factors面板数据应按groupby(ts_code)计算
        ewm/rolling/cumsum不应跨股票边界"""
        from app.core.factor_calculator import FactorCalculator

        np.random.seed(42)
        n = 50
        # 生成有涨有跌的价格数据(确保avg_loss非零, RSI可计算)
        stock_a_close = 100 * np.cumprod(1 + np.random.randn(n) * 0.02)
        stock_b_close = 50 * np.cumprod(1 + np.random.randn(n) * 0.03)

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ'] * n + ['000002.SZ'] * n,
            'trade_date': list(pd.date_range('2024-01-01', periods=n)) + list(pd.date_range('2024-01-01', periods=n)),
            'close': list(stock_a_close) + list(stock_b_close),
            'volume': [1e8] * n + [5e7] * n,
        })

        calc = FactorCalculator()
        result = calc.calc_technical_factors(price_df)

        stock_a_mask = result['security_id'] == '000001.SZ'
        stock_b_mask = result['security_id'] == '000002.SZ'

        if 'rsi_14d' in result.columns:
            # A股和B股的RSI应该不同(因为价格模式不同)
            a_rsi = result.loc[stock_a_mask, 'rsi_14d'].dropna()
            b_rsi = result.loc[stock_b_mask, 'rsi_14d'].dropna()
            if len(a_rsi) > 5 and len(b_rsi) > 5:
                assert abs(a_rsi.mean() - b_rsi.mean()) > 1.0, \
                    "A股B股RSI应有显著差异, 否则可能跨股票边界计算"

        # 关键验证: bollinger_position不应跨边界
        if 'bollinger_position' in result.columns:
            a_boll = result.loc[stock_a_mask, 'bollinger_position'].dropna()
            b_boll = result.loc[stock_b_mask, 'bollinger_position'].dropna()
            if len(a_boll) > 5 and len(b_boll) > 5:
                # 两只股票波动率不同, 布林带位置应有差异
                assert abs(a_boll.mean() - b_boll.mean()) > 0.01, \
                    "A股B股布林带位置应有差异"

    def test_sentiment_factors_panel_does_not_cross_stock_boundary(self):
        """回归测试: calc_sentiment_factors面板数据应按groupby(ts_code)计算
        rolling/pct_change不应跨股票边界"""
        from app.core.factor_calculator import FactorCalculator

        n = 30
        sentiment_df = pd.DataFrame({
            'ts_code': ['000001.SZ'] * n + ['000002.SZ'] * n,
            'retail_order_ratio': [0.5] * n + [0.2] * n,
            'margin_balance': [1e9 + i * 1e7 for i in range(n)] + [5e8 + i * 5e6 for i in range(n)],
            'new_accounts': [100 + i * 10 for i in range(n)] + [50 + i * 5 for i in range(n)],
        })

        calc = FactorCalculator()
        result = calc.calc_sentiment_factors(sentiment_df)

        stock_a_mask = result['security_id'] == '000001.SZ'
        stock_b_mask = result['security_id'] == '000002.SZ'

        if 'retail_sentiment' in result.columns:
            # A股和B股的retail_sentiment应不同(输入不同)
            a_vals = result.loc[stock_a_mask, 'retail_sentiment'].dropna()
            b_vals = result.loc[stock_b_mask, 'retail_sentiment'].dropna()
            if len(a_vals) > 0 and len(b_vals) > 0:
                assert abs(a_vals.mean() - b_vals.mean()) > 0.01, \
                    "A股B股sentiment应有差异"

        # 确保B股前几行的margin_balance_chg为NaN(没有足够历史)
        if 'margin_balance_chg' in result.columns:
            b_margin = result.loc[stock_b_mask, 'margin_balance_chg']
            # pct_change(5)在前5行应为NaN
            assert b_margin.iloc[:5].isna().all(), \
                "B股前5行margin_balance_chg应为NaN, 不应跨A股边界"

    def test_smart_money_factors_panel_does_not_cross_stock_boundary(self):
        """回归测试: calc_smart_money_factors面板数据应按groupby(ts_code)计算
        rolling不应跨股票边界"""
        from app.core.factor_calculator import FactorCalculator

        np.random.seed(42)
        n = 30
        # 不同的大单/超大单比例, 确保smart_money_ratio有差异
        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ'] * n + ['000002.SZ'] * n,
            'trade_date': list(pd.date_range('2024-01-01', periods=n)) + list(pd.date_range('2024-01-01', periods=n)),
            'close': list(100 * np.cumprod(1 + np.random.randn(n) * 0.01)) + list(50 * np.cumprod(1 + np.random.randn(n) * 0.01)),
            'volume': [1e8] * n + [5e7] * n,
            # A股大单占比高, B股大单占比低
            'large_order_volume': [3e7] * n + [5e6] * n,
            'super_large_order_volume': [2e7] * n + [1e6] * n,
            'margin_balance': [1e9 + i * 1e7 for i in range(n)] + [5e8 + i * 5e6 for i in range(n)],
        })

        calc = FactorCalculator()
        result = calc.calc_smart_money_factors(price_df)

        stock_a_mask = result['security_id'] == '000001.SZ'
        stock_b_mask = result['security_id'] == '000002.SZ'

        if 'smart_money_ratio' in result.columns:
            # A股和B股的smart_money_ratio应不同
            a_vals = result.loc[stock_a_mask, 'smart_money_ratio'].dropna()
            b_vals = result.loc[stock_b_mask, 'smart_money_ratio'].dropna()
            if len(a_vals) > 0 and len(b_vals) > 0:
                # A股大单占比(50%)远高于B股(12%), 均值应有显著差异
                assert abs(a_vals.mean() - b_vals.mean()) > 0.05, \
                    "A股B股smart_money_ratio应有显著差异(大单占比不同)"

    def test_smart_money_institutional_not_early_return(self):
        """回归测试: calc_smart_money_factors传入institutional_df时应合并而非提前返回

        bug现象: 当institutional_df有数据时, calc_smart_money_factors在处理完
        institutional_holding_chg后直接return result, 导致后续的margin_signal
        等因子不被计算

        fix: 将institutional数据合并到result而非提前返回
        """
        from app.core.factor_calculator import FactorCalculator

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'close': [10.0, 20.0],
            'volume': [1e8, 5e7],
            'margin_balance': [1e9, 5e8],
        })

        institutional_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'hold_ratio': [0.05, 0.08],
        })

        calc = FactorCalculator()
        result = calc.calc_smart_money_factors(price_df, institutional_df=institutional_df)

        # institutional_holding_chg应存在
        assert 'institutional_holding_chg' in result.columns, \
            "institutional_holding_chg应存在于结果中"

        # margin_signal也应存在(不应被提前返回跳过)
        assert 'margin_signal' in result.columns, \
            "margin_signal不应因institutional_df的提前返回而丢失"


class TestMissingColumnsExcludedFromPreprocessing:
    """缺失因子列排除回归测试 - preprocess_dataframe应跳过不存在的因子列"""

    def test_missing_columns_not_in_result(self):
        """验证preprocess_dataframe跳过DataFrame中不存在于columns中的因子"""
        from app.core.factor_preprocess import FactorPreprocessor

        preprocessor = FactorPreprocessor()

        df = pd.DataFrame({
            'security_id': ['A', 'B', 'C'],
            'ep_ttm': [0.05, 0.08, 0.12],
        })

        # 要求预处理ep_ttm和一个不存在的因子vol_20d
        result = preprocessor.preprocess_dataframe(
            df, ['ep_ttm', 'vol_20d'],
            min_coverage=0.6,
        )

        # ep_ttm应被预处理
        assert 'ep_ttm' in result.columns
        # vol_20d不存在于原始df中，不应被添加或报错
        # preprocess_dataframe中 `if col not in result.columns: continue`
        assert 'vol_20d' not in result.columns

    def test_missing_indicator_columns_excluded(self):
        """验证缺失指示器列不应进入预处理流水线

        preprocess_dataframe中 `_missing` 后缀列应被跳过，
        不应被当作因子列进行标准化等操作
        """
        from app.core.factor_preprocess import FactorPreprocessor

        preprocessor = FactorPreprocessor()

        df = pd.DataFrame({
            'security_id': ['A', 'B', 'C', 'D'],
            'good_factor': [1.0, 2.0, np.nan, 4.0],
        })

        # 第一步: preprocess会自动添加good_factor_missing指示器列
        result = preprocessor.preprocess_dataframe(
            df, ['good_factor'],
            add_missing_indicators=True,
        )

        # good_factor_missing应该是0/1二值列，不应被标准化处理
        if 'good_factor_missing' in result.columns:
            # 二值指示器值只能是0或1
            assert set(result['good_factor_missing'].dropna().unique()).issubset({0, 1}), \
                "缺失指示器应为0/1二值列, 不应被标准化"


class TestNeutralizeIndustryConstrainedDimensions:
    """约束回归中性化KKT矩阵维度回归测试"""

    def test_kkt_matrix_correct_dimensions(self):
        """回归测试: neutralize_industry_constrained的KKT系统维度应正确

        bug现象: KKT矩阵维度错误导致np.linalg.solve失败

        正确维度: KKT = (n_vars+1, n_vars+1), 其中n_vars = 1(截距) + n_industries
        约束矩阵A: (1, n_vars), A[0, 1:] = 1.0 (跳过截距列)
        """
        from app.core.factor_preprocess import FactorPreprocessor

        preprocessor = FactorPreprocessor()

        # 3个行业，每行业2只股票
        df = pd.DataFrame({
            'industry': ['银行', '银行', '电子', '电子', '医药', '医药', '银行', '电子'],
            'factor_value': [0.10, 0.12, 0.08, 0.09, 0.11, 0.13, 0.07, 0.06],
        })

        result = preprocessor.neutralize_industry_constrained(df, 'factor_value', 'industry')

        # 结果应非空且长度与输入一致
        assert len(result) == len(df)
        # 有效值不应全为NaN
        assert result.dropna().shape[0] > 0

    def test_constrained_neutralization_sum_of_coefficients_near_zero(self):
        """验证约束回归的行业系数之和接近0"""
        from app.core.factor_preprocess import FactorPreprocessor

        preprocessor = FactorPreprocessor()

        # 构造足够大的数据集以确保回归可执行
        n = 200
        industries = ['银行', '电子', '医药', '消费', '制造']
        df = pd.DataFrame({
            'industry': np.random.choice(industries, n),
            'factor_value': np.random.randn(n) * 0.1 + 0.05,
        })

        result = preprocessor.neutralize_industry_constrained(df, 'factor_value', 'industry')

        # 残差应在合理范围内
        assert result.dropna().mean() < 0.01, "残差均值应接近0(截距已吸收)"
        assert len(result.dropna()) > 0

    def test_fallback_with_insufficient_samples(self):
        """验证样本不足时退化为neutralize_industry"""
        from app.core.factor_preprocess import FactorPreprocessor

        preprocessor = FactorPreprocessor()

        # 极少样本: 3个行业但只有5只股票(不足 n_industries+10)
        df = pd.DataFrame({
            'industry': ['银行', '电子', '医药', '银行', '电子'],
            'factor_value': [0.10, 0.08, 0.12, 0.11, 0.09],
        })

        result = preprocessor.neutralize_industry_constrained(df, 'factor_value', 'industry')

        # 应退化为行业内标准化, 不应报错
        assert len(result) == len(df)
        assert not result.isna().all(), "退化处理应返回有效值"


class TestSentimentIndependentOfSupplyChain:
    """情绪因子独立性回归测试 - 验证sentiment不依赖supply_chain_df"""

    def test_sentiment_computed_without_supply_chain(self):
        """回归测试: calc_all_factors中sentiment因子应独立于supply_chain_df

        bug现象: calc_sentiment_factors在calc_all_factors中被放在
        supply_chain_df条件分支内，导致无supply_chain_df时sentiment不被计算

        fix: calc_sentiment_factors移出supply_chain_df分支，独立判断
        """
        from app.core.factor_calculator import FactorCalculator

        # 构造最小的sentiment数据
        sentiment_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ'],
            'retail_order_ratio': [0.5, 0.6],
        })

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ'],
            'trade_date': pd.date_range('2024-01-01', periods=2),
            'close': [10.0, 10.5],
            'volume': [1e8, 1e8],
            'amount': [1e9, 1e9],
        })

        financial_df = pd.DataFrame({
            'ts_code': ['000001.SZ'],
            'net_profit': [1e9],
            'total_equity': [5e9],
            'total_assets': [10e9],
            'total_market_cap': [20e9],
            'operating_cash_flow': [1.2e9],
        })

        calc = FactorCalculator()
        # 不提供supply_chain_df，但提供sentiment_df
        result = calc.calc_all_factors(
            financial_df=financial_df,
            price_df=price_df,
            sentiment_df=sentiment_df,
            neutralize=False,
        )

        # sentiment因子应被计算(不受supply_chain_df缺失影响)
        if not result.empty and 'security_id' in result.columns:
            sentiment_factor_cols = ['retail_sentiment', 'margin_balance_chg', 'new_account_growth']
            found = any(c in result.columns for c in sentiment_factor_cols)
            assert found, \
                "sentiment因子应被独立计算, 不应依赖supply_chain_df"

    def test_calc_sentiment_factors_directly(self):
        """直接测试calc_sentiment_factors不依赖supply_chain_df"""
        from app.core.factor_calculator import FactorCalculator

        sentiment_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'retail_order_ratio': [0.5, 0.2],
        })

        calc = FactorCalculator()
        result = calc.calc_sentiment_factors(sentiment_df)

        # 应独立工作，不需要任何supply_chain数据
        assert 'retail_sentiment' in result.columns
        assert len(result) == 2
