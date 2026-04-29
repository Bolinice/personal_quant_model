"""
Alpha模块化架构测试
测试五大Alpha模块 + 风险惩罚模块的得分计算
"""

import numpy as np
import pandas as pd


class TestAlphaModuleBase:
    """Alpha模块基类测试"""

    def test_quality_growth_module(self):
        from app.core.alpha_modules import QualityGrowthModule

        module = QualityGrowthModule()

        assert module.name == "quality_growth"
        assert len(module.get_factor_names()) == 7
        assert "roe_ttm" in module.get_factor_names()
        assert "accrual_ratio" in module.get_factor_names()

    def test_expectation_module(self):
        from app.core.alpha_modules import ExpectationModule

        module = ExpectationModule()

        assert module.name == "expectation"
        assert len(module.get_factor_names()) == 6
        assert "eps_revision_fy0" in module.get_factor_names()

    def test_residual_momentum_module(self):
        from app.core.alpha_modules import ResidualMomentumModule

        module = ResidualMomentumModule()

        assert module.name == "residual_momentum"
        assert len(module.get_factor_names()) == 6
        assert "residual_return_60d" in module.get_factor_names()

    def test_flow_confirm_module(self):
        from app.core.alpha_modules import FlowConfirmModule

        module = FlowConfirmModule()

        assert module.name == "flow_confirm"
        assert len(module.get_factor_names()) == 6
        assert "north_net_inflow_5d" in module.get_factor_names()

    def test_risk_penalty_module(self):
        from app.core.alpha_modules import RiskPenaltyModule

        module = RiskPenaltyModule()

        assert module.name == "risk_penalty"
        assert len(module.get_factor_names()) == 7
        assert module.LAMBDA == 0.35


class TestAlphaModuleScoring:
    """Alpha模块得分计算测试"""

    def _make_sample_df(self, n=100, seed=42):
        """生成包含所有因子列的测试DataFrame"""
        np.random.seed(seed)
        return pd.DataFrame(
            {
                "ts_code": [f"{i:06d}.SZ" for i in range(n)],
                # 质量成长因子
                "roe_ttm": np.random.randn(n) * 0.1,
                "roe_delta": np.random.randn(n) * 0.05,
                "gross_margin": np.random.uniform(0.1, 0.5, n),
                "revenue_growth_yoy": np.random.randn(n) * 0.2,
                "profit_growth_yoy": np.random.randn(n) * 0.2,
                "operating_cashflow_ratio": np.random.uniform(0.5, 1.5, n),
                "accrual_ratio": np.random.randn(n) * 0.1,
                # 预期修正因子
                "eps_revision_fy0": np.random.randn(n) * 0.1,
                "eps_revision_fy1": np.random.randn(n) * 0.1,
                "analyst_coverage": np.random.randint(1, 30, n),
                "rating_upgrade_ratio": np.random.uniform(0, 1, n),
                "earnings_surprise": np.random.randn(n) * 0.05,
                "guidance_up_ratio": np.random.uniform(0, 1, n),
                # 残差动量因子
                "residual_return_20d": np.random.randn(n) * 0.05,
                "residual_return_60d": np.random.randn(n) * 0.1,
                "residual_return_120d": np.random.randn(n) * 0.15,
                "residual_sharpe": np.random.randn(n),
                "turnover_ratio_20d": np.random.uniform(0.01, 0.1, n),
                "max_drawdown_20d": -np.random.uniform(0.01, 0.1, n),
                # 资金流确认因子
                "north_net_inflow_5d": np.random.randn(n) * 1e8,
                "north_net_inflow_20d": np.random.randn(n) * 2e8,
                "main_force_net_inflow": np.random.randn(n) * 1e7,
                "large_order_net_ratio": np.random.randn(n) * 0.1,
                "margin_balance_change": np.random.randn(n) * 0.05,
                "institutional_holding_change": np.random.randn(n) * 0.02,
                # 风险惩罚因子
                "volatility_20d": np.random.uniform(0.1, 0.5, n),
                "idiosyncratic_vol": np.random.uniform(0.05, 0.3, n),
                "max_drawdown_60d": -np.random.uniform(0.05, 0.3, n),
                "illiquidity": np.random.uniform(0, 1, n),
                "concentration_top10": np.random.uniform(0.1, 0.8, n),
                "pledge_ratio": np.random.uniform(0, 0.5, n),
                "goodwill_ratio": np.random.uniform(0, 0.3, n),
            }
        ).set_index("ts_code")

    def test_quality_growth_scoring(self):
        from app.core.alpha_modules import QualityGrowthModule

        module = QualityGrowthModule()
        df = self._make_sample_df()

        scores = module.compute_scores(df)
        assert len(scores) == len(df)
        assert not scores.isna().any()

    def test_expectation_scoring(self):
        from app.core.alpha_modules import ExpectationModule

        module = ExpectationModule()
        df = self._make_sample_df()

        scores = module.compute_scores(df)
        assert len(scores) == len(df)

    def test_residual_momentum_scoring(self):
        from app.core.alpha_modules import ResidualMomentumModule

        module = ResidualMomentumModule()
        df = self._make_sample_df()

        scores = module.compute_scores(df)
        assert len(scores) == len(df)

    def test_flow_confirm_scoring(self):
        from app.core.alpha_modules import FlowConfirmModule

        module = FlowConfirmModule()
        df = self._make_sample_df()

        scores = module.compute_scores(df)
        assert len(scores) == len(df)

    def test_risk_penalty_scoring(self):
        from app.core.alpha_modules import RiskPenaltyModule

        module = RiskPenaltyModule()
        df = self._make_sample_df()

        penalty = module.compute_scores(df)
        assert len(penalty) == len(df)
        # Penalty should be in [0, 1] (sigmoid output)
        assert penalty.min() >= 0
        assert penalty.max() <= 1

    def test_missing_factor_columns(self):
        """缺失因子列时应跳过而非报错"""
        from app.core.alpha_modules import QualityGrowthModule

        module = QualityGrowthModule()

        df = pd.DataFrame(
            {
                "ts_code": ["A", "B"],
                "roe_ttm": [0.1, 0.2],
            }
        ).set_index("ts_code")

        scores = module.compute_scores(df)
        assert len(scores) == 2


class TestModuleRegistry:
    """模块注册表测试"""

    def test_get_module(self):
        from app.core.alpha_modules import get_module

        module = get_module("quality_growth")
        assert module is not None
        assert module.name == "quality_growth"

    def test_get_nonexistent_module(self):
        from app.core.alpha_modules import get_module

        module = get_module("nonexistent")
        assert module is None

    def test_get_alpha_modules(self):
        from app.core.alpha_modules import get_alpha_modules

        modules = get_alpha_modules()
        assert len(modules) == 4  # 4 alpha modules (excl risk_penalty)
        assert "risk_penalty" not in modules

    def test_get_risk_penalty_module(self):
        from app.core.alpha_modules import get_risk_penalty_module

        module = get_risk_penalty_module()
        assert module.name == "risk_penalty"
