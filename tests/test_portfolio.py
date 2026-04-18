"""
组合构建器测试
"""
import pytest
import numpy as np
import pandas as pd
from datetime import date


class TestPortfolioBuilder:
    """组合构建测试"""

    def test_select_top_n(self):
        from app.core.portfolio_builder import PortfolioBuilder
        from unittest.mock import MagicMock

        builder = PortfolioBuilder(db=MagicMock())

        scores = pd.Series({
            '000001.SZ': 0.8,
            '000002.SZ': 0.7,
            '000003.SZ': 0.6,
            '000004.SZ': 0.5,
            '000005.SZ': 0.4,
        })

        selected = builder.select_top_n(scores, n=3)
        assert len(selected) == 3
        assert '000001.SZ' in selected

    def test_equal_weight(self):
        from app.core.portfolio_builder import PortfolioBuilder
        from unittest.mock import MagicMock

        builder = PortfolioBuilder(db=MagicMock())

        stocks = ['000001.SZ', '000002.SZ', '000003.SZ']
        weights = builder.equal_weight(stocks)

        assert len(weights) == 3
        assert abs(weights.sum() - 1.0) < 1e-10
        assert abs(weights.iloc[0] - 1.0 / 3) < 1e-10

    def test_score_weight(self):
        from app.core.portfolio_builder import PortfolioBuilder
        from unittest.mock import MagicMock

        builder = PortfolioBuilder(db=MagicMock())

        stocks = ['000001.SZ', '000002.SZ', '000003.SZ']
        scores = pd.Series({
            '000001.SZ': 0.8,
            '000002.SZ': 0.5,
            '000003.SZ': 0.3,
        })

        weights = builder.score_weight(stocks, scores)
        assert len(weights) == 3
        assert abs(weights.sum() - 1.0) < 1e-10
        # Highest score should have highest weight
        assert weights['000001.SZ'] > weights['000002.SZ']

    def test_risk_parity_weight(self):
        from app.core.portfolio_builder import PortfolioBuilder
        from unittest.mock import MagicMock

        builder = PortfolioBuilder(db=MagicMock())

        stocks = ['000001.SZ', '000002.SZ', '000003.SZ']
        volatilities = pd.Series({
            '000001.SZ': 0.3,
            '000002.SZ': 0.2,
            '000003.SZ': 0.1,
        })

        weights = builder.risk_parity_weight(stocks, volatilities)
        assert len(weights) == 3
        assert abs(weights.sum() - 1.0) < 1e-10
        # Low vol should get higher weight
        assert weights['000003.SZ'] > weights['000001.SZ']

    def test_apply_position_limit(self):
        from app.core.portfolio_builder import PortfolioBuilder
        from unittest.mock import MagicMock

        builder = PortfolioBuilder(db=MagicMock())

        weights = pd.Series({
            '000001.SZ': 0.5,
            '000002.SZ': 0.3,
            '000003.SZ': 0.2,
        })

        adjusted = builder.apply_position_limit(weights, max_position=0.4)
        assert adjusted.max() <= 0.4 + 1e-6
        assert abs(adjusted.sum() - 1.0) < 1e-6

    def test_generate_rebalance(self):
        from app.core.portfolio_builder import PortfolioBuilder
        from unittest.mock import MagicMock

        builder = PortfolioBuilder(db=MagicMock())

        current_positions = {'000001.SZ': 0.5, '000002.SZ': 0.5}
        target_portfolio = pd.DataFrame({
            'security_id': ['000001.SZ', '000003.SZ'],
            'weight': [0.4, 0.6],
        })

        result = builder.generate_rebalance(current_positions, target_portfolio, '2024-01-15')
        assert 'sell_list' in result
        assert 'buy_list' in result
        assert 'adjust_list' in result
        assert 'total_turnover' in result
        # Should sell 000002
        sell_codes = [s['ts_code'] for s in result['sell_list']]
        assert '000002.SZ' in sell_codes
        # Should buy 000003
        buy_codes = [b['ts_code'] for b in result['buy_list']]
        assert '000003.SZ' in buy_codes


class TestPortfolioOptimizer:
    """组合优化测试"""

    def test_mean_variance_optimize(self):
        from app.core.portfolio_optimizer import PortfolioOptimizer

        optimizer = PortfolioOptimizer()

        np.random.seed(42)
        n = 5
        expected_returns = pd.Series(np.random.uniform(0.05, 0.2, n),
                                     index=[f'S{i}' for i in range(n)])
        cov = pd.DataFrame(np.cov(np.random.randn(100, n).T),
                           index=[f'S{i}' for i in range(n)],
                           columns=[f'S{i}' for i in range(n)])

        weights = optimizer.mean_variance_optimize(expected_returns, cov)
        assert len(weights) == n
        assert abs(weights.sum() - 1.0) < 1e-4
        assert (weights >= -1e-6).all()

    def test_risk_parity_optimize(self):
        from app.core.portfolio_optimizer import PortfolioOptimizer

        optimizer = PortfolioOptimizer()

        np.random.seed(42)
        n = 4
        cov = pd.DataFrame(np.cov(np.random.randn(100, n).T),
                           index=[f'S{i}' for i in range(n)],
                           columns=[f'S{i}' for i in range(n)])

        weights = optimizer.risk_parity_optimize(cov)
        assert len(weights) == n
        assert abs(weights.sum() - 1.0) < 1e-4

    def test_min_variance_optimize(self):
        from app.core.portfolio_optimizer import PortfolioOptimizer

        optimizer = PortfolioOptimizer()

        np.random.seed(42)
        n = 4
        cov = pd.DataFrame(np.cov(np.random.randn(100, n).T),
                           index=[f'S{i}' for i in range(n)],
                           columns=[f'S{i}' for i in range(n)])

        weights = optimizer.min_variance_optimize(cov)
        assert len(weights) == n
        assert abs(weights.sum() - 1.0) < 1e-4
