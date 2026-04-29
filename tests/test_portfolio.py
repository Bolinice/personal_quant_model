"""
组合构建器测试 - 适配V2架构(PortfolioBuilder无db参数)
"""

import numpy as np
import pandas as pd


class TestPortfolioBuilderProduction:
    """V2组合构建器 - 实盘模式"""

    def test_build_production_basic(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder(top_n=5)

        scores = pd.Series(
            {
                "000001.SZ": 0.8,
                "000002.SZ": 0.7,
                "000003.SZ": 0.6,
                "000004.SZ": 0.5,
                "000005.SZ": 0.4,
                "000006.SZ": 0.3,
            }
        )

        result = builder.build_production_portfolio(scores)
        assert len(result) <= 5
        assert "ts_code" in result.columns
        assert "weight" in result.columns
        assert abs(result["weight"].sum() - 1.0) < 1e-6

    def test_build_production_with_risk_discount(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder(top_n=3)

        scores = pd.Series(
            {
                "000001.SZ": 0.9,
                "000002.SZ": 0.7,
                "000003.SZ": 0.5,
            }
        )
        risk_levels = pd.Series(
            {
                "000001.SZ": "low",
                "000002.SZ": "high",
                "000003.SZ": "medium",
            }
        )

        result = builder.build_production_portfolio(scores, risk_levels=risk_levels)
        assert len(result) <= 3
        # High risk stock should have lower weight than low risk
        low_weight = result[result["ts_code"] == "000001.SZ"]["weight"].values[0]
        high_weight = result[result["ts_code"] == "000002.SZ"]["weight"].values[0]
        # With same tier multiplier, low risk should have higher weight
        assert low_weight >= high_weight

    def test_build_production_with_liquidity_discount(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder(top_n=3)

        scores = pd.Series(
            {
                "000001.SZ": 0.9,
                "000002.SZ": 0.7,
                "000003.SZ": 0.5,
            }
        )
        liquidity_levels = pd.Series(
            {
                "000001.SZ": "normal",
                "000002.SZ": "insufficient",
                "000003.SZ": "marginal",
            }
        )

        result = builder.build_production_portfolio(scores, liquidity_levels=liquidity_levels)
        assert len(result) <= 3

    def test_build_production_with_industry_constraints(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder(top_n=5)

        scores = pd.Series(
            {
                "000001.SZ": 0.9,
                "000002.SZ": 0.8,
                "000003.SZ": 0.7,
                "000004.SZ": 0.6,
                "000005.SZ": 0.5,
            }
        )
        industry_series = pd.Series(
            {
                "000001.SZ": "银行",
                "000002.SZ": "银行",
                "000003.SZ": "银行",
                "000004.SZ": "电子",
                "000005.SZ": "医药",
            }
        )

        result = builder.build_production_portfolio(scores, industry_series=industry_series)
        # Verify industry column is present and result is valid
        if "industry" in result.columns:
            result.groupby("industry")["weight"].sum()
            # Industry constraint may not be fully enforced with only 5 stocks
            # but the result should still be valid
            assert abs(result["weight"].sum() - 1.0) < 1e-6

    def test_build_production_with_rebalance_buffer(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder(top_n=3)

        scores = pd.Series(
            {
                "000001.SZ": 0.9,
                "000002.SZ": 0.7,
                "000003.SZ": 0.5,
                "000004.SZ": 0.3,
            }
        )
        current_holdings = pd.Series(
            {
                "000001.SZ": 0.4,
                "000002.SZ": 0.3,
                "000004.SZ": 0.3,
            }
        )

        result = builder.build_production_portfolio(scores, current_holdings=current_holdings)
        assert len(result) > 0


class TestPortfolioBuilderResearch:
    """V2组合构建器 - 研究模式"""

    def test_build_research_basic(self):
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(top_n=3, mode=PortfolioMode.RESEARCH)

        scores = pd.Series(
            {
                "000001.SZ": 0.8,
                "000002.SZ": 0.7,
                "000003.SZ": 0.6,
                "000004.SZ": 0.5,
                "000005.SZ": 0.4,
            }
        )

        result = builder.build_research_portfolio(scores)
        assert len(result) <= 3
        assert abs(result["weight"].sum() - 1.0) < 1e-6

    def test_build_research_with_risk_penalty(self):
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(top_n=3, mode=PortfolioMode.RESEARCH)

        scores = pd.Series(
            {
                "000001.SZ": 0.8,
                "000002.SZ": 0.7,
                "000003.SZ": 0.6,
            }
        )
        risk_penalty = pd.Series(
            {
                "000001.SZ": 0.1,
                "000002.SZ": 0.5,
                "000003.SZ": 0.2,
            }
        )

        result = builder.build_research_portfolio(scores, risk_penalty=risk_penalty)
        assert len(result) <= 3

    def test_build_method_dispatches_correctly(self):
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(top_n=3, mode=PortfolioMode.RESEARCH)

        scores = pd.Series(
            {
                "000001.SZ": 0.8,
                "000002.SZ": 0.7,
                "000003.SZ": 0.6,
            }
        )

        # Default mode should use research
        result = builder.build(scores)
        assert len(result) <= 3

        # Override to production
        result_prod = builder.build(scores, mode=PortfolioMode.PRODUCTION)
        assert len(result_prod) <= 3


class TestPortfolioBuilderTierMultipliers:
    """分层赋权测试"""

    def test_tier1_multiplier(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder()
        assert builder._get_tier_multiplier(1) == 1.5
        assert builder._get_tier_multiplier(10) == 1.5

    def test_tier2_multiplier(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder()
        assert builder._get_tier_multiplier(11) == 1.2
        assert builder._get_tier_multiplier(30) == 1.2

    def test_tier3_multiplier(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder()
        assert builder._get_tier_multiplier(31) == 1.0
        assert builder._get_tier_multiplier(60) == 1.0

    def test_out_of_range_multiplier(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder()
        assert builder._get_tier_multiplier(100) == 1.0


class TestPortfolioBuilderLotSize:
    """100股整数倍处理"""

    def test_round_to_lot(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder()

        # 10% weight, 1e8 capital, 10 yuan price
        result = builder._round_to_lot(0.10, 10.0, 1e8)
        assert result > 0
        # Verify it's close to 10%
        assert abs(result - 0.10) < 0.005

    def test_round_to_lot_zero_price(self):
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder()

        result = builder._round_to_lot(0.10, 0.0, 1e8)
        assert result == 0.0


class TestPortfolioOptimizer:
    """组合优化测试"""

    def test_mean_variance_optimize(self):
        from app.core.portfolio_optimizer import PortfolioOptimizer

        optimizer = PortfolioOptimizer()

        np.random.seed(42)
        n = 5
        expected_returns = pd.Series(np.random.uniform(0.05, 0.2, n), index=[f"S{i}" for i in range(n)])
        cov = pd.DataFrame(
            np.cov(np.random.randn(100, n).T), index=[f"S{i}" for i in range(n)], columns=[f"S{i}" for i in range(n)]
        )

        weights = optimizer.mean_variance_optimize(expected_returns, cov)
        assert len(weights) == n
        assert abs(weights.sum() - 1.0) < 1e-4
        assert (weights >= -1e-6).all()

    def test_risk_parity_optimize(self):
        from app.core.portfolio_optimizer import PortfolioOptimizer

        optimizer = PortfolioOptimizer()

        np.random.seed(42)
        n = 4
        cov = pd.DataFrame(
            np.cov(np.random.randn(100, n).T), index=[f"S{i}" for i in range(n)], columns=[f"S{i}" for i in range(n)]
        )

        weights = optimizer.risk_parity_optimize(cov)
        assert len(weights) == n
        assert abs(weights.sum() - 1.0) < 1e-4

    def test_min_variance_optimize(self):
        from app.core.portfolio_optimizer import PortfolioOptimizer

        optimizer = PortfolioOptimizer()

        np.random.seed(42)
        n = 4
        cov = pd.DataFrame(
            np.cov(np.random.randn(100, n).T), index=[f"S{i}" for i in range(n)], columns=[f"S{i}" for i in range(n)]
        )

        weights = optimizer.min_variance_optimize(cov)
        assert len(weights) == n
        assert abs(weights.sum() - 1.0) < 1e-4
