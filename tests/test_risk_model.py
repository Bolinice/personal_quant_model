"""
风险模型测试
"""
import pytest
import numpy as np
import pandas as pd


class TestRiskModelCovariance:
    """协方差估计测试"""

    def test_sample_covariance(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.DataFrame(np.random.randn(100, 3), columns=['A', 'B', 'C'])
        cov = model.sample_covariance(returns)

        assert cov.shape == (3, 3)
        assert (cov.values == cov.values.T).all()  # symmetric

    def test_ledoit_wolf_shrinkage(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.DataFrame(np.random.randn(100, 5), columns=list('ABCDE'))
        cov = model.ledoit_wolf_shrinkage(returns)

        assert cov.shape == (5, 5)
        # Should be positive definite
        eigenvalues = np.linalg.eigvalsh(cov.values)
        assert (eigenvalues > 0).all()

    def test_ewma_covariance(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.DataFrame(np.random.randn(100, 3), columns=['A', 'B', 'C'])
        cov = model.ewma_covariance(returns, halflife=20)

        assert cov.shape == (3, 3)


class TestRiskModelVaR:
    """VaR/CVaR测试"""

    def test_historical_var(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.02)
        var = model.historical_var(returns, confidence=0.95)
        assert var > 0

    def test_parametric_var(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.02)
        var = model.parametric_var(returns, confidence=0.95)
        assert var > 0

    def test_conditional_var(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.02)
        cvar = model.conditional_var(returns, confidence=0.95)
        assert cvar > 0
        # CVaR should be >= VaR
        var = model.historical_var(returns, confidence=0.95)
        assert cvar >= var

    def test_student_t_var(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.02)
        var = model.student_t_var(returns, confidence=0.95)
        assert var > 0


class TestRiskDecomposition:
    """风险分解测试"""

    def test_risk_contribution(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        weights = np.array([0.25, 0.25, 0.25, 0.25])
        cov = np.eye(4) * 0.04

        rc = model.risk_contribution_pct(weights, cov)
        assert abs(rc.sum() - 1.0) < 1e-10

    def test_marginal_risk_contribution(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        weights = np.array([0.5, 0.5])
        cov = np.array([[0.04, 0.01], [0.01, 0.09]])

        mrc = model.marginal_risk_contribution(weights, cov)
        assert len(mrc) == 2

    def test_liquidity_adjusted_var(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.02)
        result = model.liquidity_adjusted_var(
            returns, position_size=1e6, daily_volume=1e8
        )
        assert result['lvar'] > result['var']  # LVaR should be > VaR
        assert result['impact_cost'] > 0
