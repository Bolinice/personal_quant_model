"""
信号融合层测试 - 适配V2 EnsembleEngine API
"""

import numpy as np
import pandas as pd


class TestEnsembleSteps:
    """融合引擎5步流程测试"""

    def test_step1_base_weights(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()

        weights = engine.step1_base_weights()
        assert len(weights) == 4
        assert abs(sum(weights.values()) - 1.0) < 1e-6
        assert weights["quality_growth"] == 0.35

    def test_step2_dynamic_ic_weights(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()

        base_weights = engine.step1_base_weights()
        ic_dict = {
            "quality_growth": 0.08,
            "expectation": 0.06,
            "residual_momentum": 0.05,
            "flow_confirm": 0.04,
        }

        dynamic_weights = engine.step2_dynamic_ic_weights(base_weights, ic_dict)
        assert len(dynamic_weights) == 4
        # Positive IC should increase weight
        assert dynamic_weights["quality_growth"] > base_weights["quality_growth"]

    def test_step2_no_ic(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()

        base_weights = engine.step1_base_weights()
        result = engine.step2_dynamic_ic_weights(base_weights, None)
        assert result == base_weights

    def test_step3_regime_adjustment(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()

        weights = {"quality_growth": 0.35, "expectation": 0.30, "residual_momentum": 0.25, "flow_confirm": 0.10}

        # Defensive regime: quality up, momentum down
        adjusted = engine.step3_regime_adjustment(weights, "defensive")
        assert adjusted["quality_growth"] > weights["quality_growth"]
        assert adjusted["residual_momentum"] < weights["residual_momentum"]

    def test_step4_correlation_shrinkage(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()

        weights = {"quality_growth": 0.35, "expectation": 0.30, "residual_momentum": 0.25, "flow_confirm": 0.10}

        shrunk = engine.step4_correlation_shrinkage(weights, None)
        assert len(shrunk) == 4

    def test_step5_normalize(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()

        weights = {"quality_growth": 0.35, "expectation": 0.30, "residual_momentum": 0.25, "flow_confirm": 0.10}

        normalized = engine.step5_normalize(weights)
        assert abs(sum(normalized.values()) - 1.0) < 1e-6
        # Each weight should be within bounds (allow floating-point tolerance)
        for w in normalized.values():
            assert w >= engine.min_weight - 1e-9
            assert w <= engine.max_weight + 1e-9


class TestEnsembleFullFuse:
    """完整融合流程测试"""

    def test_fuse_basic(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()

        np.random.seed(42)
        n = 50
        df = pd.DataFrame(
            {
                "roe_ttm": np.random.randn(n),
                "roe_delta": np.random.randn(n),
                "gross_margin": np.random.uniform(0.1, 0.5, n),
                "revenue_growth_yoy": np.random.randn(n),
                "profit_growth_yoy": np.random.randn(n),
                "operating_cashflow_ratio": np.random.uniform(0.5, 1.5, n),
                "accrual_ratio": np.random.randn(n),
                "eps_revision_fy0": np.random.randn(n),
                "eps_revision_fy1": np.random.randn(n),
                "analyst_coverage": np.random.randint(1, 30, n),
                "rating_upgrade_ratio": np.random.uniform(0, 1, n),
                "earnings_surprise": np.random.randn(n),
                "guidance_up_ratio": np.random.uniform(0, 1, n),
                "residual_return_20d": np.random.randn(n),
                "residual_return_60d": np.random.randn(n),
                "residual_return_120d": np.random.randn(n),
                "residual_sharpe": np.random.randn(n),
                "turnover_ratio_20d": np.random.uniform(0.01, 0.1, n),
                "max_drawdown_20d": -np.random.uniform(0.01, 0.1, n),
                "north_net_inflow_5d": np.random.randn(n),
                "north_net_inflow_20d": np.random.randn(n),
                "main_force_net_inflow": np.random.randn(n),
                "large_order_net_ratio": np.random.randn(n),
                "margin_balance_change": np.random.randn(n),
                "institutional_holding_change": np.random.randn(n),
                "volatility_20d": np.random.uniform(0.1, 0.5, n),
                "idiosyncratic_vol": np.random.uniform(0.05, 0.3, n),
                "max_drawdown_60d": -np.random.uniform(0.05, 0.3, n),
                "illiquidity": np.random.uniform(0, 1, n),
                "concentration_top10": np.random.uniform(0.1, 0.8, n),
                "pledge_ratio": np.random.uniform(0, 0.5, n),
                "goodwill_ratio": np.random.uniform(0, 0.3, n),
            },
            index=[f"S{i}" for i in range(n)],
        )

        final_scores, meta = engine.fuse(df, regime="trending")
        assert len(final_scores) == n
        assert "step5_final_weights" in meta
        assert "final_score_stats" in meta

    def test_fuse_with_risk_penalty(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()

        np.random.seed(42)
        n = 30
        df = pd.DataFrame(
            {
                "roe_ttm": np.random.randn(n),
                "roe_delta": np.random.randn(n),
                "gross_margin": np.random.uniform(0.1, 0.5, n),
                "revenue_growth_yoy": np.random.randn(n),
                "profit_growth_yoy": np.random.randn(n),
                "operating_cashflow_ratio": np.random.uniform(0.5, 1.5, n),
                "accrual_ratio": np.random.randn(n),
                "eps_revision_fy0": np.random.randn(n),
                "eps_revision_fy1": np.random.randn(n),
                "analyst_coverage": np.random.randint(1, 30, n),
                "rating_upgrade_ratio": np.random.uniform(0, 1, n),
                "earnings_surprise": np.random.randn(n),
                "guidance_up_ratio": np.random.uniform(0, 1, n),
                "residual_return_20d": np.random.randn(n),
                "residual_return_60d": np.random.randn(n),
                "residual_return_120d": np.random.randn(n),
                "residual_sharpe": np.random.randn(n),
                "turnover_ratio_20d": np.random.uniform(0.01, 0.1, n),
                "max_drawdown_20d": -np.random.uniform(0.01, 0.1, n),
                "north_net_inflow_5d": np.random.randn(n),
                "north_net_inflow_20d": np.random.randn(n),
                "main_force_net_inflow": np.random.randn(n),
                "large_order_net_ratio": np.random.randn(n),
                "margin_balance_change": np.random.randn(n),
                "institutional_holding_change": np.random.randn(n),
                "volatility_20d": np.random.uniform(0.1, 0.5, n),
                "idiosyncratic_vol": np.random.uniform(0.05, 0.3, n),
                "max_drawdown_60d": -np.random.uniform(0.05, 0.3, n),
                "illiquidity": np.random.uniform(0, 1, n),
                "concentration_top10": np.random.uniform(0.1, 0.8, n),
                "pledge_ratio": np.random.uniform(0, 0.5, n),
                "goodwill_ratio": np.random.uniform(0, 0.3, n),
            },
            index=[f"S{i}" for i in range(n)],
        )

        scores_with_penalty, _meta = engine.fuse(df, apply_risk_penalty=True)
        scores_no_penalty, _ = engine.fuse(df, apply_risk_penalty=False)
        # With risk penalty, scores should be lower
        assert scores_with_penalty.mean() < scores_no_penalty.mean()


class TestEnsembleConvenienceFunctions:
    """便捷函数测试"""

    def test_get_default_weights(self):
        from app.core.ensemble import get_default_weights

        weights = get_default_weights()
        assert len(weights) == 4
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_get_regime_adjustments(self):
        from app.core.ensemble import get_regime_adjustments

        adjustments = get_regime_adjustments()
        assert len(adjustments) == 4  # 4 regime types

    def test_create_ensemble_engine(self):
        from app.core.ensemble import create_ensemble_engine

        engine = create_ensemble_engine()
        assert engine is not None
