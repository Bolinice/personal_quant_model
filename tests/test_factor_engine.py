"""
因子引擎测试
"""
import pytest
import numpy as np
import pandas as pd
from datetime import date


class TestFactorEngineCalculation:
    """因子计算测试"""

    def test_valuation_factors(self):
        from app.core.factor_engine import FactorEngine
        from unittest.mock import MagicMock

        engine = FactorEngine(db=MagicMock())

        financial_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'pe_ttm': [10.0, 20.0],
            'pb': [1.5, 2.0],
            'ps_ttm': [3.0, 5.0],
            'dividend_yield': [0.03, 0.02],
        })
        price_df = pd.DataFrame({'close': [10.0, 20.0]})

        result = engine.calc_valuation_factors(financial_df, price_df)
        assert 'ep_ttm' in result.columns
        assert 'bp' in result.columns
        assert len(result) == 2
        # EP = 1/PE
        assert abs(result['ep_ttm'].iloc[0] - 0.1) < 1e-6

    def test_growth_factors(self):
        from app.core.factor_engine import FactorEngine
        from unittest.mock import MagicMock

        engine = FactorEngine(db=MagicMock())

        financial_df = pd.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'yoy_revenue': [0.15, 0.25],
            'yoy_net_profit': [0.10, 0.20],
            'yoy_deduct_net_profit': [0.08, 0.18],
            'yoy_roe': [0.05, 0.10],
        })

        result = engine.calc_growth_factors(financial_df)
        assert 'yoy_revenue' in result.columns
        assert len(result) == 2

    def test_momentum_factors(self):
        from app.core.factor_engine import FactorEngine
        from unittest.mock import MagicMock

        engine = FactorEngine(db=MagicMock())

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 250,
            'close': list(range(100, 350)),
        })

        result = engine.calc_momentum_factors(price_df)
        assert 'ret_1m' in result.columns
        assert 'ret_1m_reversal' in result.columns

    def test_volatility_factors(self):
        from app.core.factor_engine import FactorEngine
        from unittest.mock import MagicMock

        engine = FactorEngine(db=MagicMock())

        np.random.seed(42)
        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 100,
            'close': 100 * np.cumprod(1 + np.random.randn(100) * 0.02),
        })

        result = engine.calc_volatility_factors(price_df)
        assert 'vol_20d' in result.columns
        assert 'vol_60d' in result.columns

    def test_liquidity_factors(self):
        from app.core.factor_engine import FactorEngine
        from unittest.mock import MagicMock

        engine = FactorEngine(db=MagicMock())

        price_df = pd.DataFrame({
            'ts_code': ['000001.SZ'] * 100,
            'close': 100 + np.random.randn(100),
            'turnover_rate': np.random.uniform(0.01, 0.1, 100),
            'amount': np.random.uniform(1e8, 1e9, 100),
        })

        result = engine.calc_liquidity_factors(price_df)
        assert 'turnover_20d' in result.columns
        assert 'amihud_20d' in result.columns


class TestFactorIC:
    """因子IC计算测试"""

    def test_calc_ic(self):
        from app.core.factor_engine import FactorEngine
        from unittest.mock import MagicMock

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
        from unittest.mock import MagicMock

        engine = FactorEngine(db=MagicMock())

        factor_values = pd.Series([1.0, 2.0])
        forward_returns = pd.Series([0.01, 0.02])

        result = engine.calc_ic(factor_values, forward_returns)
        assert np.isnan(result['ic']) or isinstance(result['ic'], (int, float))
