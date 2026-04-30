"""Alpha模块化架构 单元测试 — 因子计算与模块注册"""

import numpy as np
import pandas as pd

from app.core.alpha_modules import (
    MODULE_REGISTRY,
    ExpectationModule,
    FlowConfirmModule,
    QualityGrowthModule,
    ResidualMomentumModule,
    RiskPenaltyModule,
    get_all_modules,
    get_alpha_modules,
    get_module,
    get_risk_penalty_module,
)


def _make_factor_df(n_stocks: int = 30) -> pd.DataFrame:
    """生成模拟因子数据"""
    np.random.seed(42)
    ts_codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]
    return pd.DataFrame(
        {
            "ts_code": ts_codes,
            # 质量成长因子
            "roe_ttm": np.random.uniform(0.05, 0.25, n_stocks),
            "roe_delta": np.random.uniform(-0.05, 0.1, n_stocks),
            "gross_margin": np.random.uniform(0.1, 0.6, n_stocks),
            "revenue_growth_yoy": np.random.uniform(-0.2, 0.5, n_stocks),
            "profit_growth_yoy": np.random.uniform(-0.3, 0.6, n_stocks),
            "operating_cashflow_ratio": np.random.uniform(0.3, 1.5, n_stocks),
            "accrual_ratio": np.random.uniform(-0.1, 0.3, n_stocks),
            # 预期修正因子
            "eps_revision_fy0": np.random.uniform(-0.1, 0.2, n_stocks),
            "eps_revision_fy1": np.random.uniform(-0.1, 0.2, n_stocks),
            "analyst_coverage": np.random.uniform(1, 30, n_stocks),
            "rating_upgrade_ratio": np.random.uniform(0, 1, n_stocks),
            "earnings_surprise": np.random.uniform(-0.2, 0.3, n_stocks),
            "guidance_up_ratio": np.random.uniform(0, 1, n_stocks),
            # 残差动量因子
            "residual_return_20d": np.random.uniform(-0.1, 0.1, n_stocks),
            "residual_return_60d": np.random.uniform(-0.15, 0.15, n_stocks),
            "residual_return_120d": np.random.uniform(-0.2, 0.2, n_stocks),
            "residual_sharpe": np.random.uniform(-1, 3, n_stocks),
            "turnover_ratio_20d": np.random.uniform(0.01, 0.3, n_stocks),
            "max_drawdown_20d": np.random.uniform(-0.2, -0.01, n_stocks),
            # 资金流因子
            "north_net_inflow_5d": np.random.uniform(-1e8, 1e8, n_stocks),
            "north_net_inflow_20d": np.random.uniform(-3e8, 3e8, n_stocks),
            "main_force_net_inflow": np.random.uniform(-1e8, 1e8, n_stocks),
            "large_order_net_ratio": np.random.uniform(-0.1, 0.1, n_stocks),
            "margin_balance_change": np.random.uniform(-0.1, 0.1, n_stocks),
            "institutional_holding_change": np.random.uniform(-0.05, 0.05, n_stocks),
            # 风险因子
            "volatility_20d": np.random.uniform(0.01, 0.05, n_stocks),
            "idiosyncratic_vol": np.random.uniform(0.005, 0.03, n_stocks),
            "max_drawdown_60d": np.random.uniform(-0.4, -0.05, n_stocks),
            "illiquidity": np.random.uniform(1e-9, 1e-6, n_stocks),
            "concentration_top10": np.random.uniform(0.2, 0.8, n_stocks),
            "pledge_ratio": np.random.uniform(0, 0.5, n_stocks),
            "goodwill_ratio": np.random.uniform(0, 0.3, n_stocks),
        }
    )


class TestModuleRegistry:
    def test_registry_has_all_modules(self):
        assert set(MODULE_REGISTRY.keys()) == {
            "quality_growth",
            "expectation",
            "residual_momentum",
            "flow_confirm",
            "risk_penalty",
        }

    def test_get_module(self):
        m = get_module("quality_growth")
        assert isinstance(m, QualityGrowthModule)
        assert get_module("nonexistent") is None

    def test_get_alpha_modules_excludes_risk(self):
        modules = get_alpha_modules()
        assert "risk_penalty" not in modules
        assert len(modules) == 4

    def test_get_risk_penalty_module(self):
        m = get_risk_penalty_module()
        assert isinstance(m, RiskPenaltyModule)

    def test_get_all_modules(self):
        modules = get_all_modules()
        assert len(modules) == 5


class TestQualityGrowthModule:
    def setup_method(self):
        self.module = QualityGrowthModule()

    def test_get_factor_names(self):
        names = self.module.get_factor_names()
        assert "roe_ttm" in names
        assert len(names) == 7

    def test_compute_scores_returns_series(self):
        df = _make_factor_df()
        scores = self.module.compute_scores(df)
        assert isinstance(scores, pd.Series)
        assert len(scores) == len(df)


class TestExpectationModule:
    def setup_method(self):
        self.module = ExpectationModule()

    def test_get_factor_names(self):
        names = self.module.get_factor_names()
        assert "eps_revision_fy0" in names
        assert len(names) == 6

    def test_compute_scores_returns_series(self):
        df = _make_factor_df()
        scores = self.module.compute_scores(df)
        assert isinstance(scores, pd.Series)
        assert len(scores) == len(df)


class TestResidualMomentumModule:
    def setup_method(self):
        self.module = ResidualMomentumModule()

    def test_get_factor_names(self):
        names = self.module.get_factor_names()
        assert "residual_return_60d" in names
        assert len(names) == 6

    def test_compute_scores_returns_series(self):
        df = _make_factor_df()
        scores = self.module.compute_scores(df)
        assert isinstance(scores, pd.Series)


class TestFlowConfirmModule:
    def setup_method(self):
        self.module = FlowConfirmModule()

    def test_get_factor_names(self):
        names = self.module.get_factor_names()
        assert "north_net_inflow_5d" in names

    def test_compute_scores_returns_series(self):
        df = _make_factor_df()
        scores = self.module.compute_scores(df)
        assert isinstance(scores, pd.Series)


class TestRiskPenaltyModule:
    def setup_method(self):
        self.module = RiskPenaltyModule()

    def test_get_factor_names(self):
        names = self.module.get_factor_names()
        assert "volatility_20d" in names
        assert len(names) == 7

    def test_compute_scores_returns_bounded(self):
        df = _make_factor_df()
        scores = self.module.compute_scores(df)
        assert isinstance(scores, pd.Series)
        # RiskPenalty uses sigmoid-0.5, so scores should be in [-0.5, 0.5]
        assert scores.min() >= -0.5
        assert scores.max() <= 0.5

    def test_lambda_value(self):
        assert self.module.LAMBDA == 0.35


class TestPreprocessFactor:
    def test_preprocess_factor(self):
        module = QualityGrowthModule()
        series = pd.Series(np.random.normal(0, 1, 100))
        result = module.preprocess_factor(series)
        assert isinstance(result, pd.Series)
        # Z-score should have mean ~0 and std ~1
        assert abs(result.mean()) < 0.5
        assert abs(result.std() - 1.0) < 0.5
