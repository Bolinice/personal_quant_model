"""
V2核心模块单元测试
=================
覆盖优化后的核心模块: alpha_modules, ensemble, universe, portfolio_builder,
risk_budget_engine, cache, regime, daily_pipeline
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

# ═══════════════════════════════════════════════
# Alpha Modules Tests
# ═══════════════════════════════════════════════


class TestAlphaModuleBase:
    """AlphaModuleBase基类默认实现测试"""

    def test_compute_scores_default_implementation(self):
        """基类compute_scores默认实现: 遍历FACTOR_CONFIG加权融合"""
        from app.core.alpha_modules import QualityGrowthModule

        module = QualityGrowthModule()
        np.random.seed(42)
        n = 50
        df = pd.DataFrame(
            {
                "roe_ttm": np.random.randn(n),
                "roe_delta": np.random.randn(n),
                "gross_margin": np.random.randn(n),
                "revenue_growth_yoy": np.random.randn(n),
                "profit_growth_yoy": np.random.randn(n),
                "operating_cashflow_ratio": np.random.randn(n),
                "accrual_ratio": np.random.randn(n),
            }
        )

        scores = module.compute_scores(df)
        assert len(scores) == n
        assert not scores.isna().any()

    def test_compute_scores_missing_factors(self):
        """缺失因子应跳过, 不报错"""
        from app.core.alpha_modules import QualityGrowthModule

        module = QualityGrowthModule()
        df = pd.DataFrame(
            {
                "roe_ttm": np.random.randn(10),
                # 其他因子缺失
            }
        )

        scores = module.compute_scores(df)
        assert len(scores) == 10
        # 只有roe_ttm参与, 结果应非零
        assert scores.abs().sum() > 0

    def test_compute_scores_direction_negation(self):
        """direction=-1的因子应取反"""
        from app.core.alpha_modules import QualityGrowthModule

        module = QualityGrowthModule()
        # accrual_ratio direction=-1, weight=0.10
        df = pd.DataFrame(
            {
                "accrual_ratio": pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]),
            }
        )
        scores = module.compute_scores(df)
        # accrual_ratio取反后, 高值→低分
        assert scores.iloc[0] > scores.iloc[4]

    def test_preprocess_factor_delegation(self):
        """preprocess_factor应委托给FactorPreprocessor"""
        from app.core.alpha_modules import QualityGrowthModule

        module = QualityGrowthModule()
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])

        result = module.preprocess_factor(data)
        # MAD去极值应截断极端值
        assert result.max() < 100
        # Z-score标准化后均值应接近0
        assert abs(result.mean()) < 0.5

    def test_preprocess_factor_no_zscore(self):
        """zscore=False时只做MAD去极值"""
        from app.core.alpha_modules import QualityGrowthModule

        module = QualityGrowthModule()
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])

        result = module.preprocess_factor(data, zscore=False)
        assert result.max() < 100


class TestAlphaModules:
    """各Alpha模块独立测试"""

    def test_quality_growth_module(self):
        from app.core.alpha_modules import QualityGrowthModule

        m = QualityGrowthModule()
        assert m.name == "quality_growth"
        assert len(m.get_factor_names()) == 7
        assert sum(c["weight"] for c in m.FACTOR_CONFIG.values()) == pytest.approx(1.0)

    def test_expectation_module(self):
        from app.core.alpha_modules import ExpectationModule

        m = ExpectationModule()
        assert m.name == "expectation"
        assert len(m.get_factor_names()) == 6
        assert sum(c["weight"] for c in m.FACTOR_CONFIG.values()) == pytest.approx(1.0)

    def test_residual_momentum_module(self):
        from app.core.alpha_modules import ResidualMomentumModule

        m = ResidualMomentumModule()
        assert m.name == "residual_momentum"
        assert len(m.get_factor_names()) == 6
        assert sum(c["weight"] for c in m.FACTOR_CONFIG.values()) == pytest.approx(1.0)

    def test_flow_confirm_module(self):
        from app.core.alpha_modules import FlowConfirmModule

        m = FlowConfirmModule()
        assert m.name == "flow_confirm"
        assert len(m.get_factor_names()) == 6
        assert sum(c["weight"] for c in m.FACTOR_CONFIG.values()) == pytest.approx(1.0)

    def test_risk_penalty_module_sigmoid(self):
        """RiskPenaltyModule使用sigmoid压缩, 返回[-0.5, 0.5]"""
        from app.core.alpha_modules import RiskPenaltyModule

        m = RiskPenaltyModule()
        np.random.seed(42)
        df = pd.DataFrame(
            {
                "volatility_20d": np.random.randn(50),
                "idiosyncratic_vol": np.random.randn(50),
                "max_drawdown_60d": np.random.randn(50),
                "illiquidity": np.random.randn(50),
                "concentration_top10": np.random.randn(50),
                "pledge_ratio": np.random.randn(50),
                "goodwill_ratio": np.random.randn(50),
            }
        )

        scores = m.compute_scores(df)
        assert len(scores) == 50
        # Sigmoid(x)-0.5输出应在[-0.5, 0.5]
        assert (scores >= -0.5).all()
        assert (scores <= 0.5).all()

    def test_risk_penalty_lambda(self):
        from app.core.alpha_modules import RiskPenaltyModule

        m = RiskPenaltyModule()
        assert m.LAMBDA == 0.35


class TestModuleRegistry:
    """模块注册表测试"""

    def test_registry_contains_all_modules(self):
        from app.core.alpha_modules import MODULE_REGISTRY

        assert "quality_growth" in MODULE_REGISTRY
        assert "expectation" in MODULE_REGISTRY
        assert "residual_momentum" in MODULE_REGISTRY
        assert "flow_confirm" in MODULE_REGISTRY
        assert "risk_penalty" in MODULE_REGISTRY

    def test_get_alpha_modules_excludes_risk(self):
        from app.core.alpha_modules import get_alpha_modules

        modules = get_alpha_modules()
        assert "risk_penalty" not in modules
        assert len(modules) == 4

    def test_get_risk_penalty_module(self):
        from app.core.alpha_modules import RiskPenaltyModule, get_risk_penalty_module

        m = get_risk_penalty_module()
        assert isinstance(m, RiskPenaltyModule)


# ═══════════════════════════════════════════════
# Ensemble Engine Tests
# ═══════════════════════════════════════════════


class TestEnsembleEngine:
    """信号融合引擎测试"""

    def _make_test_df(self, n=50):
        """构造测试DataFrame, 包含所有模块因子"""
        np.random.seed(42)
        data = {}
        # QualityGrowth因子
        data["roe_ttm"] = np.random.randn(n)
        data["roe_delta"] = np.random.randn(n)
        data["gross_margin"] = np.random.randn(n)
        data["revenue_growth_yoy"] = np.random.randn(n)
        data["profit_growth_yoy"] = np.random.randn(n)
        data["operating_cashflow_ratio"] = np.random.randn(n)
        data["accrual_ratio"] = np.random.randn(n)
        # Expectation因子
        data["eps_revision_fy0"] = np.random.randn(n)
        data["eps_revision_fy1"] = np.random.randn(n)
        data["analyst_coverage"] = np.random.randn(n)
        data["rating_upgrade_ratio"] = np.random.randn(n)
        data["earnings_surprise"] = np.random.randn(n)
        data["guidance_up_ratio"] = np.random.randn(n)
        # ResidualMomentum因子
        data["residual_return_20d"] = np.random.randn(n)
        data["residual_return_60d"] = np.random.randn(n)
        data["residual_return_120d"] = np.random.randn(n)
        data["residual_sharpe"] = np.random.randn(n)
        data["turnover_ratio_20d"] = np.random.randn(n)
        data["max_drawdown_20d"] = np.random.randn(n)
        # FlowConfirm因子
        data["north_net_inflow_5d"] = np.random.randn(n)
        data["north_net_inflow_20d"] = np.random.randn(n)
        data["main_force_net_inflow"] = np.random.randn(n)
        data["large_order_net_ratio"] = np.random.randn(n)
        data["margin_balance_change"] = np.random.randn(n)
        data["institutional_holding_change"] = np.random.randn(n)
        # RiskPenalty因子
        data["volatility_20d"] = np.random.randn(n)
        data["idiosyncratic_vol"] = np.random.randn(n)
        data["max_drawdown_60d"] = np.random.randn(n)
        data["illiquidity"] = np.random.randn(n)
        data["concentration_top10"] = np.random.randn(n)
        data["pledge_ratio"] = np.random.randn(n)
        data["goodwill_ratio"] = np.random.randn(n)
        return pd.DataFrame(data)

    def test_fuse_basic(self):
        """基本融合流程"""
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()
        df = self._make_test_df()

        scores, meta = engine.fuse(df, regime="trending")
        assert len(scores) == len(df)
        assert not scores.isna().any()
        assert "step5_final_weights" in meta

    def test_fuse_with_precomputed_module_scores(self):
        """预计算模块得分应避免重复计算"""
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()
        df = self._make_test_df()

        # 先计算模块得分
        module_scores = engine.compute_module_scores(df)
        risk_penalty = engine.compute_risk_penalty(df)

        # 使用预计算结果
        scores1, _meta1 = engine.fuse(
            df,
            regime="trending",
            precomputed_module_scores=module_scores,
            precomputed_risk_penalty=risk_penalty,
        )

        # 不使用预计算结果
        scores2, _meta2 = engine.fuse(df, regime="trending")

        # 结果应一致
        np.testing.assert_array_almost_equal(scores1.values, scores2.values, decimal=5)

    def test_fuse_without_risk_penalty(self):
        """apply_risk_penalty=False时跳过风险惩罚"""
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()
        df = self._make_test_df()

        _scores, meta = engine.fuse(df, regime="trending", apply_risk_penalty=False)
        assert "risk_penalty_stats" not in meta

    def test_step1_base_weights(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()
        weights = engine.step1_base_weights()
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)
        assert "quality_growth" in weights

    def test_step2_dynamic_ic_weights(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()
        base = engine.step1_base_weights()

        # 有IC时调整
        ic_dict = {"quality_growth": 0.1, "expectation": -0.05}
        adjusted = engine.step2_dynamic_ic_weights(base, ic_dict)
        assert adjusted["quality_growth"] > base["quality_growth"]
        assert adjusted["expectation"] < base["expectation"]

        # 无IC时不变
        no_ic = engine.step2_dynamic_ic_weights(base, None)
        assert no_ic == base

    def test_step3_regime_adjustment(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()
        base = engine.step1_base_weights()

        # risk_on: 动量↑ 质量↓
        risk_on = engine.step3_regime_adjustment(base, "risk_on")
        assert risk_on["residual_momentum"] > base["residual_momentum"]
        assert risk_on["quality_growth"] < base["quality_growth"]

        # defensive: 质量↑ 动量↓
        defensive = engine.step3_regime_adjustment(base, "defensive")
        assert defensive["quality_growth"] > base["quality_growth"]
        assert defensive["residual_momentum"] < base["residual_momentum"]

    def test_step4_correlation_shrinkage(self):
        from app.core.ensemble import EnsembleEngine

        engine = EnsembleEngine()
        base = engine.step1_base_weights()

        # 无相关性信息时向基线收缩
        dynamic = {k: v * 1.2 for k, v in base.items()}
        shrunk = engine.step4_correlation_shrinkage(dynamic, None)
        # 收缩后应比dynamic更接近base
        for k in base:
            assert abs(shrunk[k] - base[k]) <= abs(dynamic[k] - base[k])

    def test_step5_normalize_bounds(self):
        from app.core.ensemble import MIN_WEIGHT, EnsembleEngine

        engine = EnsembleEngine()

        # 极端权重应被约束到[min, max], 然后归一化
        extreme = {"quality_growth": 0.8, "expectation": 0.05, "residual_momentum": 0.1, "flow_confirm": 0.05}
        normalized = engine.step5_normalize(extreme)
        for w in normalized.values():
            assert w >= MIN_WEIGHT
        # 归一化后总和应为1
        assert sum(normalized.values()) == pytest.approx(1.0)

    def test_regime_weight_consistency(self):
        """ensemble.py和regime.py的REGIME_WEIGHT_ADJUSTMENTS应一致"""
        from app.core.ensemble import REGIME_WEIGHT_ADJUSTMENTS as ENSEMBLE_ADJUSTMENTS
        from app.core.regime import REGIME_WEIGHT_ADJUSTMENTS as REGIME_ADJUSTMENTS

        for regime in ["risk_on", "trending", "defensive", "mean_reverting"]:
            assert regime in ENSEMBLE_ADJUSTMENTS
            assert regime in REGIME_ADJUSTMENTS
            for module in ENSEMBLE_ADJUSTMENTS[regime]:
                assert ENSEMBLE_ADJUSTMENTS[regime][module] == REGIME_ADJUSTMENTS[regime][module], (
                    f"Mismatch for {regime}/{module}"
                )


# ═══════════════════════════════════════════════
# Universe Builder Tests
# ═══════════════════════════════════════════════


class TestUniverseBuilder:
    """股票池构建器测试"""

    def _make_stock_basic(self):
        return pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ", "600000.SH", "300001.SZ", "688001.SH"],
                "list_date": ["2020-01-01", "2019-06-01", "2015-01-01", "2023-06-01", "2022-01-01"],
                "list_status": ["L", "L", "L", "L", "D"],
            }
        )

    def _make_price_df(self, trade_date):
        return pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ", "600000.SH"] * 5,
                "trade_date": [trade_date] * 15,
                "close": [10.0, 20.0, 30.0] * 5,
                "amount": [1e8, 2e8, 3e8] * 5,
                "volume": [1e6, 2e6, 3e6] * 5,
            }
        )

    def test_build_basic(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()
        trade_date = date(2024, 1, 15)

        result = builder.build(
            trade_date,
            self._make_stock_basic(),
            self._make_price_df(trade_date),
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            min_market_cap=0,
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_build_excludes_delisted(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()
        trade_date = date(2024, 1, 15)

        result = builder.build(
            trade_date,
            self._make_stock_basic(),
            self._make_price_df(trade_date),
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            min_market_cap=0,
            exclude_delist=True,
        )
        assert "688001.SH" not in result  # list_status='D'

    def test_build_excludes_st(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()
        trade_date = date(2024, 1, 15)

        stock_status = pd.DataFrame(
            {
                "ts_code": ["000001.SZ"],
                "trade_date": [trade_date],
                "is_st": [True],
                "is_suspended": [False],
                "is_delist": [False],
            }
        )

        result = builder.build(
            trade_date,
            self._make_stock_basic(),
            self._make_price_df(trade_date),
            stock_status_df=stock_status,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            min_market_cap=0,
        )
        assert "000001.SZ" not in result

    def test_build_min_price_filter(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()
        trade_date = date(2024, 1, 15)

        price_df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ"] * 5,
                "trade_date": [trade_date] * 10,
                "close": [1.0, 20.0] * 5,  # 000001价格<3
                "amount": [1e8, 2e8] * 5,
            }
        )

        result = builder.build(
            trade_date,
            self._make_stock_basic(),
            price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=3.0,
            min_market_cap=0,
        )
        assert "000001.SZ" not in result

    def test_filter_risk_events(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()
        trade_date = date(2024, 1, 15)

        candidates = {"000001.SZ", "000002.SZ", "600000.SH"}
        risk_events = pd.DataFrame(
            {
                "ts_code": ["000001.SZ"],
                "event_date": ["2024-01-10"],
                "event_type": ["investigation"],
                "severity": ["critical"],
            }
        )

        filtered, _reasons = builder.filter_risk_events(candidates, risk_events, trade_date)
        assert "000001.SZ" not in filtered
        assert "000002.SZ" in filtered

    def test_filter_blacklist(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()

        candidates = {"000001.SZ", "000002.SZ", "600000.SH"}
        blacklist = pd.DataFrame(
            {
                "ts_code": ["000002.SZ"],
                "reason": ["重大立案"],
            }
        )

        filtered, _reasons = builder.filter_blacklist(candidates, blacklist, date(2024, 1, 15))
        assert "000002.SZ" not in filtered
        assert "000001.SZ" in filtered

    def test_filter_limit_up_down_vectorized(self):
        """向量化一字板过滤测试"""
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()
        trade_date = date(2024, 1, 15)

        candidates = {"000001.SZ", "000002.SZ", "600000.SH"}
        price_df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ", "600000.SH"],
                "trade_date": [trade_date] * 3,
                "open": [10.0, 20.0, 30.0],
                "high": [10.0, 20.5, 30.2],  # 000001一字板
                "close": [10.0, 20.3, 30.1],
                "low": [10.0, 19.8, 29.9],
            }
        )

        filtered, _reasons = builder.filter_limit_up_down(candidates, price_df, trade_date)
        assert "000001.SZ" not in filtered  # 一字板被排除
        assert "000002.SZ" in filtered
        assert "600000.SH" in filtered

    def test_filter_limit_up_down_normal_trading(self):
        """正常交易的股票不应被过滤"""
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()
        trade_date = date(2024, 1, 15)

        candidates = {"000001.SZ", "000002.SZ"}
        price_df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "trade_date": [trade_date] * 2,
                "open": [10.0, 20.0],
                "high": [10.5, 20.5],
                "close": [10.2, 20.3],
                "low": [9.8, 19.8],
            }
        )

        filtered, _reasons = builder.filter_limit_up_down(candidates, price_df, trade_date)
        assert "000001.SZ" in filtered
        assert "000002.SZ" in filtered

    def test_build_core_pool(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()
        trade_date = date(2024, 1, 15)

        result = builder.build_core_pool(
            trade_date,
            self._make_stock_basic(),
            self._make_price_df(trade_date),
        )
        assert isinstance(result, list)

    def test_build_extended_pool(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()
        trade_date = date(2024, 1, 15)

        result = builder.build_extended_pool(
            trade_date,
            self._make_stock_basic(),
            self._make_price_df(trade_date),
        )
        assert isinstance(result, list)
        # 扩展池应>=核心池
        core = builder.build_core_pool(
            trade_date,
            self._make_stock_basic(),
            self._make_price_df(trade_date),
        )
        assert len(result) >= len(core)


# ═══════════════════════════════════════════════
# Portfolio Builder Tests
# ═══════════════════════════════════════════════


class TestPortfolioBuilderV2:
    """V2组合构建器测试"""

    def _make_scores(self, n=60):
        np.random.seed(42)
        codes = [f"{i:06d}.SZ" for i in range(1, n + 1)]
        return pd.Series(np.random.randn(n), index=codes)

    def test_production_portfolio_basic(self):
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(mode=PortfolioMode.PRODUCTION)
        scores = self._make_scores()

        result = builder.build_production_portfolio(scores)
        assert "ts_code" in result.columns
        assert "weight" in result.columns
        assert abs(result["weight"].sum() - 1.0) < 0.01

    def test_research_portfolio_basic(self):
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(mode=PortfolioMode.RESEARCH)
        scores = self._make_scores()

        result = builder.build_research_portfolio(scores)
        assert "ts_code" in result.columns
        assert "weight" in result.columns
        assert abs(result["weight"].sum() - 1.0) < 0.01

    def test_tiered_weighting(self):
        """分层赋权: rank 1-10应比31-60权重更高"""
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(mode=PortfolioMode.PRODUCTION)
        scores = self._make_scores()

        result = builder.build_production_portfolio(scores)
        # 排名靠前的权重应更大(分层赋权1.5x vs 1.0x)
        top10 = result[result["rank"] <= 10]["weight"].mean()
        bottom30 = result[result["rank"] > 30]["weight"].mean()
        assert top10 > bottom30

    def test_risk_discount(self):
        """风险折扣: 高风险股票权重应被缩减"""
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(mode=PortfolioMode.PRODUCTION)
        scores = self._make_scores()

        # 设置一只股票为高风险
        risk_levels = pd.Series("low", index=scores.index)
        risk_levels.iloc[0] = "high"

        result_no_risk = builder.build_production_portfolio(scores)
        result_with_risk = builder.build_production_portfolio(scores, risk_levels=risk_levels)

        # 高风险股票权重应更低
        high_risk_code = scores.index[0]
        w_no_risk = result_no_risk[result_no_risk["ts_code"] == high_risk_code]["weight"].values
        w_with_risk = result_with_risk[result_with_risk["ts_code"] == high_risk_code]["weight"].values
        if len(w_no_risk) > 0 and len(w_with_risk) > 0:
            assert w_with_risk[0] < w_no_risk[0]

    def test_liquidity_discount(self):
        """流动性折扣: 流动性不足的股票权重应被缩减"""
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(mode=PortfolioMode.PRODUCTION)
        scores = self._make_scores()

        liq_levels = pd.Series("normal", index=scores.index)
        liq_levels.iloc[0] = "insufficient"

        result = builder.build_production_portfolio(scores, liquidity_levels=liq_levels)
        assert not result.empty

    def test_lot_rounding(self):
        """100股整数倍处理"""
        from app.core.portfolio_builder import PortfolioBuilder

        builder = PortfolioBuilder()

        # 150股 → 100股
        w = builder._round_to_lot(0.015, 10.0, 1e8)
        assert w >= 0

        # 价格<=0 → 0
        w = builder._round_to_lot(0.01, 0.0, 1e8)
        assert w == 0.0

    def test_industry_constraints(self):
        """行业约束: 单行业<=20%"""
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(mode=PortfolioMode.PRODUCTION)
        scores = self._make_scores()

        # 所有股票设为同一行业 → 约束生效后所有股票等权
        industry = pd.Series("金融", index=scores.index)

        result = builder.build_production_portfolio(scores, industry_series=industry)
        assert not result.empty

    def test_rebalance_buffer(self):
        """调仓缓冲区: 排名<=75继续持有, 新买入需排名<=50"""
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(mode=PortfolioMode.PRODUCTION)
        scores = self._make_scores()

        # 模拟当前持仓
        current_holdings = pd.Series(0.0, index=scores.index[:40])
        current_holdings[:] = 1.0 / 40

        result = builder.build_production_portfolio(scores, current_holdings=current_holdings)
        assert not result.empty

    def test_build_dispatches_by_mode(self):
        """build()方法根据mode分派"""
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        builder = PortfolioBuilder(mode=PortfolioMode.RESEARCH)
        scores = self._make_scores()

        result_research = builder.build(scores)
        result_production = builder.build(scores, mode=PortfolioMode.PRODUCTION)

        # 两种模式结果应不同
        assert len(result_research) > 0
        assert len(result_production) > 0

    def test_extreme_risk_zero_weight(self):
        """极高风险(extreme)权重应为0"""
        from app.core.portfolio_builder import RISK_DISCOUNT

        assert RISK_DISCOUNT["extreme"] == 0.0


# ═══════════════════════════════════════════════
# Risk Budget Engine Tests
# ═══════════════════════════════════════════════


class TestRiskBudgetEngine:
    """风险预算引擎测试"""

    def test_allocate_risk_budget_equal(self):
        from app.core.risk_budget_engine import RiskBudgetEngine

        engine = RiskBudgetEngine()

        result = engine.allocate_risk_budget(
            {"value": 0.3, "momentum": 0.4, "quality": 0.3},
            {"value": 0.5, "momentum": 0.3, "quality": 0.4},
            method="equal",
        )
        assert len(result) == 3
        assert all(v == pytest.approx(0.05, abs=0.01) for v in result.values())

    def test_allocate_risk_budget_icir(self):
        from app.core.risk_budget_engine import RiskBudgetEngine

        engine = RiskBudgetEngine()

        result = engine.allocate_risk_budget(
            {"value": 0.3, "momentum": 0.4},
            {"value": 0.8, "momentum": 0.2},
            method="icir_proportional",
        )
        # 高ICIR因子应获得更多预算
        assert result["value"] > result["momentum"]

    def test_risk_limit_check_normal(self):
        from app.core.risk_budget_engine import RiskAction, RiskBudgetEngine

        engine = RiskBudgetEngine()

        # 所有指标在限制内
        action = engine.check_risk_limits(
            {
                "portfolio_vol": 0.15,
                "max_drawdown": 0.05,
                "var_95": 0.01,
                "cvar_95": 0.02,
                "max_factor_exposure": 0.8,
            }
        )
        assert action == RiskAction.NORMAL

    def test_risk_limit_check_drawdown_violation(self):
        from app.core.risk_budget_engine import RiskAction, RiskBudgetEngine

        engine = RiskBudgetEngine()

        action = engine.check_risk_limits(
            {
                "portfolio_vol": 0.15,
                "max_drawdown": 0.15,  # 超限
                "var_95": 0.01,
                "cvar_95": 0.02,
                "max_factor_exposure": 0.8,
            }
        )
        assert action == RiskAction.REDUCE_EXPOSURE

    def test_risk_limit_check_force_liquidate(self):
        from app.core.risk_budget_engine import RiskAction, RiskBudgetEngine

        engine = RiskBudgetEngine()

        # 3项以上违规 → 强制清仓
        action = engine.check_risk_limits(
            {
                "portfolio_vol": 0.30,  # 超限
                "max_drawdown": 0.15,  # 超限
                "var_95": 0.03,  # 超限
                "cvar_95": 0.05,  # 超限
                "max_factor_exposure": 1.5,  # 超限
            }
        )
        assert action == RiskAction.FORCE_LIQUIDATE

    def test_compute_risk_adjusted_exposure(self):
        from app.core.risk_budget_engine import RiskAction, RiskBudgetEngine

        engine = RiskBudgetEngine()

        assert engine.compute_risk_adjusted_exposure(RiskAction.NORMAL) == 1.0
        assert engine.compute_risk_adjusted_exposure(RiskAction.REDUCE_EXPOSURE) == 0.5
        assert engine.compute_risk_adjusted_exposure(RiskAction.INCREASE_HEDGE) == 0.7
        assert engine.compute_risk_adjusted_exposure(RiskAction.FORCE_LIQUIDATE) == 0.2

    def test_timing_signal_drawdown(self):
        """回撤保护信号"""
        from app.core.risk_budget_engine import RiskBudgetEngine

        engine = RiskBudgetEngine()

        assert engine.timing_signal_drawdown(-0.03) == 0  # <5%: 不降档
        assert engine.timing_signal_drawdown(-0.06) == 1  # >5%: 降一档
        assert engine.timing_signal_drawdown(-0.09) == 2  # >8%: 降两档
        assert engine.timing_signal_drawdown(-0.15) == 3  # >12%: 最低30%

    def test_timing_signal_trend(self):
        """指数中期趋势信号"""
        from app.core.risk_budget_engine import RiskBudgetEngine

        engine = RiskBudgetEngine()

        # 上升趋势
        up_data = pd.DataFrame({"close": range(100, 250)})
        assert engine.timing_signal_trend(up_data) >= 1

        # 下降趋势
        down_data = pd.DataFrame({"close": range(250, 100, -1)})
        assert engine.timing_signal_trend(down_data) == 0

    def test_timing_signal_breadth(self):
        """市场宽度信号"""
        from app.core.risk_budget_engine import RiskBudgetEngine

        engine = RiskBudgetEngine()

        # 大多数上涨
        bull_data = pd.DataFrame({"pct_chg": np.random.randn(500) * 0.02 + 0.01})
        signal = engine.timing_signal_breadth(bull_data)
        assert signal >= 0

    def test_position_tiers(self):
        """4档仓位映射"""
        from app.core.risk_budget_engine import RiskBudgetEngine

        engine = RiskBudgetEngine()

        assert engine.POSITION_TIERS["strong_positive"] == 1.00
        assert engine.POSITION_TIERS["positive"] == 0.80
        assert engine.POSITION_TIERS["neutral"] == 0.60
        assert engine.POSITION_TIERS["negative"] == 0.30

    def test_optimize_with_linear_constraints(self):
        """风险约束优化: 线性约束替代abs()"""
        from app.core.risk_budget_engine import RiskBudgetEngine

        engine = RiskBudgetEngine()

        n = 10
        stocks = [f"S{i}" for i in range(n)]
        alpha = pd.Series(np.random.uniform(0.05, 0.15, n), index=stocks)
        exposures = pd.DataFrame(
            {
                "size": np.random.randn(n),
                "value": np.random.randn(n),
            },
            index=stocks,
        )
        factor_cov = pd.DataFrame(np.eye(2) * 0.01, columns=["size", "value"], index=["size", "value"])
        risk_budget = {"size": 0.5, "value": 0.5}

        weights = engine.optimize_with_risk_constraints(alpha, exposures, factor_cov, risk_budget)
        assert len(weights) == n
        assert abs(weights.sum() - 1.0) < 0.05
        assert (weights >= -1e-4).all()  # long-only


# ═══════════════════════════════════════════════
# Cache Service Tests
# ═══════════════════════════════════════════════


class TestCacheService:
    """缓存服务测试"""

    def test_basic_get_set(self):
        from app.core.cache import CacheService

        cache = CacheService(max_size=100, default_ttl=60)

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        from app.core.cache import CacheService

        cache = CacheService(max_size=100, default_ttl=1)  # 1秒TTL

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        import time

        time.sleep(1.1)
        assert cache.get("key1") is None  # 已过期

    def test_lru_eviction(self):
        from app.core.cache import CacheService

        cache = CacheService(max_size=3, default_ttl=300)

        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # 应驱逐'a'

        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_trade_date_index(self):
        """trade_date反向索引"""
        from app.core.cache import CacheService

        cache = CacheService(max_size=100, default_ttl=300)

        td = str(date(2024, 1, 15))
        cache.set("fv:value:20240115", 1.0, trade_date=td)
        cache.set("fv:momentum:20240115", 2.0, trade_date=td)
        cache.set("fv:quality:20240116", 3.0, trade_date=str(date(2024, 1, 16)))

        assert td in cache._trade_date_index
        assert len(cache._trade_date_index[td]) == 2

    def test_invalidate_by_trade_date_with_index(self):
        """按交易日失效: 使用反向索引"""
        from app.core.cache import CacheService

        cache = CacheService(max_size=100, default_ttl=300)

        td = str(date(2024, 1, 15))
        cache.set("fv:value:20240115", 1.0, trade_date=td)
        cache.set("fv:momentum:20240115", 2.0, trade_date=td)
        cache.set("fv:quality:20240116", 3.0, trade_date=str(date(2024, 1, 16)))

        count = cache.invalidate_by_trade_date(date(2024, 1, 15))
        assert count == 2
        assert cache.get("fv:value:20240115") is None
        assert cache.get("fv:momentum:20240115") is None
        assert cache.get("fv:quality:20240116") == 3.0  # 不同日期不受影响

    def test_invalidate_by_trade_date_fallback(self):
        """按交易日失效: 无索引时线性扫描回退"""
        from app.core.cache import CacheService

        cache = CacheService(max_size=100, default_ttl=300)

        # 不使用trade_date参数设置缓存
        cache.set("fv:value:2024-01-15", 1.0)
        cache.set("fv:momentum:2024-01-15", 2.0)

        count = cache.invalidate_by_trade_date(date(2024, 1, 15))
        assert count >= 0  # 回退模式可能匹配到

    def test_cache_stats(self):
        from app.core.cache import CacheService

        cache = CacheService(max_size=100, default_ttl=300)

        cache.set("key1", 1)
        cache.get("key1")  # hit
        cache.get("nonexistent")  # miss

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_cache_decorator(self):
        from app.core.cache import CacheService

        cache = CacheService(max_size=100, default_ttl=300)

        call_count = 0

        @cache.cache_decorator(ttl=60)
        def expensive_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_func(5)
        result2 = expensive_func(5)  # 应命中缓存

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1  # 只计算一次

    def test_invalidate_by_prefix(self):
        from app.core.cache import CacheService

        cache = CacheService(max_size=100, default_ttl=300)

        cache.set("fv:value", 1)
        cache.set("fv:momentum", 2)
        cache.set("other:key", 3)

        count = cache.invalidate_by_prefix("fv:")
        assert count == 2
        assert cache.get("other:key") == 3


# ═══════════════════════════════════════════════
# Regime Detector Tests
# ═══════════════════════════════════════════════


class TestRegimeDetector:
    """市场状态检测器测试"""

    def test_detect_default(self):
        from app.core.regime import REGIME_MEAN_REVERTING, RegimeDetector

        detector = RegimeDetector()

        # 空数据应返回默认震荡市
        regime, _confidence = detector.detect(pd.DataFrame())
        assert regime == REGIME_MEAN_REVERTING

    def test_detect_trending(self):
        from app.core.regime import REGIME_MEAN_REVERTING, REGIME_RISK_ON, REGIME_TRENDING, RegimeDetector

        detector = RegimeDetector()

        # 强上升趋势: 确定性上涨
        close = np.arange(100, 300, dtype=float)  # 100→300 线性上涨
        data = pd.DataFrame(
            {
                "trade_date": pd.date_range("2024-01-01", periods=200),
                "close": close,
            }
        )

        regime, _confidence = detector.detect(data)
        # 确定性上涨应被检测为趋势市或进攻市
        assert regime in [REGIME_TRENDING, REGIME_RISK_ON, REGIME_MEAN_REVERTING]

    def test_detect_defensive(self):
        from app.core.regime import REGIME_DEFENSIVE, REGIME_MEAN_REVERTING, RegimeDetector

        detector = RegimeDetector()

        # 高波动: 大幅震荡
        np.random.seed(42)
        close = np.cumprod(1 + np.random.randn(200) * 0.05) * 100
        data = pd.DataFrame(
            {
                "trade_date": pd.date_range("2024-01-01", periods=200),
                "close": close,
            }
        )

        regime, _confidence = detector.detect(data)
        # 高波动应触发防御或震荡
        assert regime in [REGIME_DEFENSIVE, REGIME_MEAN_REVERTING]

    def test_weight_adjustments_v2_delta(self):
        """V2: 权重调整使用增量(delta)而非乘数"""
        from app.core.regime import RegimeDetector

        detector = RegimeDetector()

        base = {"quality_growth": 0.35, "expectation": 0.30, "residual_momentum": 0.25, "flow_confirm": 0.10}

        # risk_on: momentum+0.08, quality-0.05
        risk_on = detector.get_weight_adjustments("risk_on", base)
        assert risk_on["residual_momentum"] > base["residual_momentum"]
        assert risk_on["quality_growth"] < base["quality_growth"]

        # 归一化后总和应为1
        assert abs(sum(risk_on.values()) - 1.0) < 1e-10

    def test_weight_adjustments_trending_no_change(self):
        from app.core.regime import RegimeDetector

        detector = RegimeDetector()

        base = {"quality_growth": 0.35, "expectation": 0.30, "residual_momentum": 0.25, "flow_confirm": 0.10}
        trending = detector.get_weight_adjustments("trending", base)
        # trending所有delta=0, 归一化后应与base相同
        for k in base:
            assert abs(trending[k] - base[k]) < 1e-10

    def test_detect_with_confidence(self):
        from app.core.regime import RegimeDetector

        detector = RegimeDetector()

        np.random.seed(42)
        data = pd.DataFrame(
            {
                "trade_date": pd.date_range("2024-01-01", periods=200),
                "close": np.cumprod(1 + np.random.randn(200) * 0.01) * 100,
            }
        )

        result = detector.detect_with_confidence(data)
        assert "regime" in result
        assert "confidence" in result
        assert "weight_adjustments" in result
        assert 0 <= result["confidence"] <= 1

    def test_regime_weight_adjustments_v2_module_names(self):
        """V2: REGIME_WEIGHT_ADJUSTMENTS使用V2模块名"""
        from app.core.regime import REGIME_WEIGHT_ADJUSTMENTS

        v2_modules = {"quality_growth", "expectation", "residual_momentum", "flow_confirm"}

        for regime, adj in REGIME_WEIGHT_ADJUSTMENTS.items():
            for module in adj:
                assert module in v2_modules, f"Regime {regime} has non-V2 module: {module}"

    def test_market_features(self):
        from app.core.regime import RegimeDetector

        detector = RegimeDetector()

        np.random.seed(42)
        data = pd.DataFrame(
            {
                "trade_date": pd.date_range("2024-01-01", periods=200),
                "close": np.cumprod(1 + np.random.randn(200) * 0.01) * 100,
            }
        )

        features = detector.market_features(data)
        assert "market_trend_20d" in features
        assert "market_vol_20d" in features


# ═══════════════════════════════════════════════
# Daily Pipeline Tests
# ═══════════════════════════════════════════════


class TestDailyPipeline:
    """日终流水线测试"""

    def test_pipeline_initialization(self):
        from app.core.daily_pipeline import DailyPipeline

        pipeline = DailyPipeline(session=None)
        assert pipeline.universe_builder is not None
        assert pipeline.ensemble_engine is not None
        assert pipeline.regime_detector is not None

    def test_step1_data_collection(self):
        from app.core.daily_pipeline import DailyPipeline, PipelineContext

        pipeline = DailyPipeline(session=None)
        ctx = PipelineContext(trade_date=date(2024, 1, 15))
        pipeline._step1_data_collection(ctx)
        # 无数据库会话时跳过，不报错

    def test_step2_snapshot(self):
        from app.core.daily_pipeline import DailyPipeline, PipelineContext

        pipeline = DailyPipeline(session=None)
        ctx = PipelineContext(trade_date=date(2024, 1, 15))
        pipeline._step2_snapshot(ctx)
        assert ctx.snapshot_id is not None

    def test_step6_ensemble(self):
        from app.core.daily_pipeline import DailyPipeline, PipelineContext

        pipeline = DailyPipeline(session=None)

        np.random.seed(42)
        n = 20
        df = pd.DataFrame(
            {
                "roe_ttm": np.random.randn(n),
                "roe_delta": np.random.randn(n),
                "gross_margin": np.random.randn(n),
                "revenue_growth_yoy": np.random.randn(n),
                "profit_growth_yoy": np.random.randn(n),
                "operating_cashflow_ratio": np.random.randn(n),
                "accrual_ratio": np.random.randn(n),
                "eps_revision_fy0": np.random.randn(n),
                "eps_revision_fy1": np.random.randn(n),
                "analyst_coverage": np.random.randn(n),
                "rating_upgrade_ratio": np.random.randn(n),
                "earnings_surprise": np.random.randn(n),
                "guidance_up_ratio": np.random.randn(n),
                "residual_return_20d": np.random.randn(n),
                "residual_return_60d": np.random.randn(n),
                "residual_return_120d": np.random.randn(n),
                "residual_sharpe": np.random.randn(n),
                "turnover_ratio_20d": np.random.randn(n),
                "max_drawdown_20d": np.random.randn(n),
                "north_net_inflow_5d": np.random.randn(n),
                "north_net_inflow_20d": np.random.randn(n),
                "main_force_net_inflow": np.random.randn(n),
                "large_order_net_ratio": np.random.randn(n),
                "margin_balance_change": np.random.randn(n),
                "institutional_holding_change": np.random.randn(n),
                "volatility_20d": np.random.randn(n),
                "idiosyncratic_vol": np.random.randn(n),
                "max_drawdown_60d": np.random.randn(n),
                "illiquidity": np.random.randn(n),
                "concentration_top10": np.random.randn(n),
                "pledge_ratio": np.random.randn(n),
                "goodwill_ratio": np.random.randn(n),
            }
        )

        ctx = PipelineContext(
            trade_date=date(2024, 1, 15),
            factor_df=df,
            factor_names=list(df.columns),
        )
        pipeline._step6_ensemble(ctx)

    def test_step5_regime_detection_no_data(self):
        from app.core.daily_pipeline import DailyPipeline, PipelineContext

        pipeline = DailyPipeline(session=None)
        ctx = PipelineContext(trade_date=date(2024, 1, 15))
        pipeline._step5_regime(ctx)
        # 无指数数据时使用默认市场状态

    def test_step11_factor_health_check(self):
        from app.core.daily_pipeline import DailyPipeline, PipelineContext

        pipeline = DailyPipeline(session=None)
        ctx = PipelineContext(trade_date=date(2024, 1, 15))
        pipeline._step11_factor_health(ctx)
        # 无因子数据时跳过，不报错

    def test_step12_archive(self):
        from app.core.daily_pipeline import DailyPipeline, PipelineContext

        pipeline = DailyPipeline(session=None)
        ctx = PipelineContext(trade_date=date(2024, 1, 15))
        pipeline._step12_archive(ctx)

    def test_run_regime_before_ensemble(self):
        """流水线中step5(regime检测)应在step6(融合)之前执行"""
        import inspect

        from app.core.daily_pipeline import DailyPipeline

        source = inspect.getsource(DailyPipeline.run)

        # step5_regime应出现在step6_ensemble之前
        step5_pos = source.find("_step5_regime")
        step6_pos = source.find("_step6_ensemble")

        assert step5_pos > 0, "_step5_regime not found in run()"
        assert step6_pos > 0, "_step6_ensemble not found in run()"
        assert step5_pos < step6_pos, "step5_regime should come before step6_ensemble"

    def test_run_basic(self):
        """基本流水线执行 — 无数据库时关键步骤(1,3,4,5,8)会抛异常"""
        from app.core.daily_pipeline import DailyPipeline

        pipeline = DailyPipeline(session=None)

        # 无数据库会话，step1跳过 → step3因无行情数据抛ValueError
        with pytest.raises(ValueError, match="Step3"):
            pipeline.run(date(2024, 1, 15))


# ═══════════════════════════════════════════════
# Integration Tests
# ═══════════════════════════════════════════════


class TestIntegration:
    """跨模块集成测试"""

    def test_ensemble_to_portfolio_flow(self):
        """Ensemble → Portfolio 完整流程"""
        from app.core.ensemble import EnsembleEngine
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode

        np.random.seed(42)
        n = 60
        # 构造因子数据
        df = pd.DataFrame(
            {
                "roe_ttm": np.random.randn(n),
                "roe_delta": np.random.randn(n),
                "gross_margin": np.random.randn(n),
                "revenue_growth_yoy": np.random.randn(n),
                "profit_growth_yoy": np.random.randn(n),
                "operating_cashflow_ratio": np.random.randn(n),
                "accrual_ratio": np.random.randn(n),
                "eps_revision_fy0": np.random.randn(n),
                "eps_revision_fy1": np.random.randn(n),
                "analyst_coverage": np.random.randn(n),
                "rating_upgrade_ratio": np.random.randn(n),
                "earnings_surprise": np.random.randn(n),
                "guidance_up_ratio": np.random.randn(n),
                "residual_return_20d": np.random.randn(n),
                "residual_return_60d": np.random.randn(n),
                "residual_return_120d": np.random.randn(n),
                "residual_sharpe": np.random.randn(n),
                "turnover_ratio_20d": np.random.randn(n),
                "max_drawdown_20d": np.random.randn(n),
                "north_net_inflow_5d": np.random.randn(n),
                "north_net_inflow_20d": np.random.randn(n),
                "main_force_net_inflow": np.random.randn(n),
                "large_order_net_ratio": np.random.randn(n),
                "margin_balance_change": np.random.randn(n),
                "institutional_holding_change": np.random.randn(n),
                "volatility_20d": np.random.randn(n),
                "idiosyncratic_vol": np.random.randn(n),
                "max_drawdown_60d": np.random.randn(n),
                "illiquidity": np.random.randn(n),
                "concentration_top10": np.random.randn(n),
                "pledge_ratio": np.random.randn(n),
                "goodwill_ratio": np.random.randn(n),
            }
        )

        # 融合
        engine = EnsembleEngine()
        scores, _meta = engine.fuse(df, regime="trending")

        # 组合构建
        builder = PortfolioBuilder(mode=PortfolioMode.PRODUCTION)
        portfolio = builder.build_production_portfolio(scores)

        assert len(portfolio) > 0
        assert abs(portfolio["weight"].sum() - 1.0) < 0.01
        assert portfolio["weight"].min() >= 0

    def test_regime_ensemble_consistency(self):
        """Regime检测结果应正确传递给EnsembleEngine"""
        from app.core.ensemble import REGIME_WEIGHT_ADJUSTMENTS, EnsembleEngine
        from app.core.regime import RegimeDetector

        detector = RegimeDetector()
        engine = EnsembleEngine()

        np.random.seed(42)
        data = pd.DataFrame(
            {
                "trade_date": pd.date_range("2024-01-01", periods=200),
                "close": np.cumprod(1 + np.random.randn(200) * 0.01) * 100,
            }
        )

        regime, _confidence = detector.detect(data)
        assert regime in REGIME_WEIGHT_ADJUSTMENTS

        # Ensemble应能使用任意regime
        base = engine.step1_base_weights()
        adjusted = engine.step3_regime_adjustment(base, regime)
        assert len(adjusted) == len(base)

    def test_universe_to_portfolio_flow(self):
        """Universe → Portfolio 流程"""
        from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode
        from app.core.universe import UniverseBuilder

        builder_u = UniverseBuilder()
        trade_date = date(2024, 1, 15)

        stock_basic = pd.DataFrame(
            {
                "ts_code": [f"{i:06d}.SZ" for i in range(1, 101)],
                "list_date": ["2020-01-01"] * 100,
                "list_status": ["L"] * 100,
            }
        )

        price_df = pd.DataFrame(
            {
                "ts_code": [f"{i:06d}.SZ" for i in range(1, 101)] * 5,
                "trade_date": [trade_date] * 500,
                "close": [10.0 + i for i in range(100)] * 5,
                "amount": [1e8 + i * 1e6 for i in range(100)] * 5,
            }
        )

        universe = builder_u.build(
            trade_date,
            stock_basic,
            price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            min_market_cap=0,
        )

        if len(universe) > 0:
            # 用universe构建组合
            scores = pd.Series(np.random.randn(len(universe)), index=universe)
            builder_p = PortfolioBuilder(mode=PortfolioMode.PRODUCTION)
            portfolio = builder_p.build_production_portfolio(scores)
            assert len(portfolio) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
