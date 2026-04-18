"""
绩效分析器测试
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime


class TestPerformanceAnalyzer:
    """绩效分析测试"""

    def test_total_return(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        nav = pd.Series([1.0, 1.1, 1.2, 1.3])
        ret = analyzer.calc_total_return(nav)
        assert abs(ret - 0.3) < 1e-10

    def test_annual_return(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        nav = pd.Series([1.0] + list(np.cumprod(1 + np.random.randn(252) * 0.005 + 0.001)))
        ret = analyzer.calc_annual_return(nav)
        assert isinstance(ret, float)

    def test_max_drawdown(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        nav = pd.Series([1.0, 1.1, 1.05, 1.2, 1.15, 1.3])
        max_dd, start, end = analyzer.calc_max_drawdown(nav)
        assert max_dd < 0  # Should be negative

    def test_sharpe_ratio(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.01 + 0.0005)
        sharpe = analyzer.calc_sharpe_ratio(returns)
        assert isinstance(sharpe, float)

    def test_sortino_ratio(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.01 + 0.0005)
        sortino = analyzer.calc_sortino_ratio(returns)
        assert isinstance(sortino, float)

    def test_win_rate(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        returns = pd.Series([0.01, -0.02, 0.03, 0.01, -0.01])
        win_rate = analyzer.calc_win_rate(returns)
        assert 0 <= win_rate <= 1
        assert abs(win_rate - 0.6) < 1e-10  # 3 out of 5

    def test_profit_loss_ratio(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        returns = pd.Series([0.02, -0.01, 0.03, 0.01, -0.02])
        pl_ratio = analyzer.calc_profit_loss_ratio(returns)
        assert pl_ratio > 0

    def test_beta_calculation(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        np.random.seed(42)
        strategy = pd.Series(np.random.randn(252) * 0.02)
        benchmark = pd.Series(np.random.randn(252) * 0.015)
        beta = analyzer.calc_beta(strategy, benchmark)
        assert isinstance(beta, float)

    def test_information_ratio(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        np.random.seed(42)
        strategy = pd.Series(np.random.randn(252) * 0.02 + 0.001)
        benchmark = pd.Series(np.random.randn(252) * 0.015)
        ir = analyzer.calc_information_ratio(strategy, benchmark)
        assert isinstance(ir, float)

    def test_full_performance_analysis(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        np.random.seed(42)
        nav = pd.Series([1.0] + list(np.cumprod(1 + np.random.randn(252) * 0.005 + 0.001)))
        result = analyzer.analyze_performance(nav)

        assert 'total_return' in result
        assert 'annual_return' in result
        assert 'max_drawdown' in result
        assert 'sharpe_ratio' in result
        assert 'sortino_ratio' in result
        assert 'win_rate' in result
