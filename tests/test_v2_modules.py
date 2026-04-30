"""
核心V2模块单元测试
覆盖: alpha_modules, ensemble, universe, labels, regime, factor_monitor, daily_pipeline, compliance
"""

from datetime import date

import numpy as np
import pandas as pd

# ==================== Universe测试 ====================


class TestUniverseBuilder:
    """股票池构建测试"""

    def test_build_basic(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()

        stock_basic_df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
                "list_date": ["2020-01-01", "2021-06-01", "2023-01-01"],
                "list_status": ["L", "L", "L"],
            }
        )
        price_df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
                "trade_date": [date(2024, 1, 15)] * 3,
                "close": [10.0, 20.0, 5.0],
                "amount": [1e8, 2e8, 5e7],
            }
        )

        result = builder.build(
            date(2024, 1, 15), stock_basic_df, price_df, min_list_days=0, min_daily_amount=0, min_price=0
        )
        assert len(result) >= 1
        assert all(isinstance(c, str) for c in result)

    def test_exclude_delisted(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()

        stock_basic_df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "list_date": ["2020-01-01", "2020-01-01"],
                "list_status": ["L", "D"],
            }
        )
        price_df = pd.DataFrame()

        result = builder.build(
            date(2024, 1, 15),
            stock_basic_df,
            price_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            exclude_delist=True,
        )
        assert "000001.SZ" in result
        assert "000002.SZ" not in result

    def test_st_filter(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()

        stock_basic_df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "list_date": ["2020-01-01", "2020-01-01"],
                "list_status": ["L", "L"],
            }
        )
        price_df = pd.DataFrame()
        stock_status_df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "trade_date": [date(2024, 1, 15)] * 2,
                "is_st": [False, True],
            }
        )

        result = builder.build(
            date(2024, 1, 15),
            stock_basic_df,
            price_df,
            stock_status_df=stock_status_df,
            min_list_days=0,
            min_daily_amount=0,
            min_price=0,
            exclude_st=True,
        )
        assert "000001.SZ" in result
        assert "000002.SZ" not in result

    def test_price_filter(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()

        stock_basic_df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "list_date": ["2020-01-01", "2020-01-01"],
                "list_status": ["L", "L"],
            }
        )
        price_df = pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ"],
                "trade_date": [date(2024, 1, 15)] * 2,
                "close": [10.0, 1.5],
                "amount": [1e8, 1e8],
            }
        )

        result = builder.build(
            date(2024, 1, 15), stock_basic_df, price_df, min_list_days=0, min_daily_amount=0, min_price=3.0
        )
        assert "000001.SZ" in result
        assert "000002.SZ" not in result

    def test_filter_risk_events(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()

        candidates = {"000001.SZ", "000002.SZ", "000003.SZ"}
        risk_events_df = pd.DataFrame(
            {
                "ts_code": ["000002.SZ"],
                "event_date": [date(2024, 1, 10)],
                "event_type": ["investigation"],
                "severity": ["critical"],
            }
        )

        filtered, _reasons = builder.filter_risk_events(candidates, risk_events_df, date(2024, 1, 15))
        assert "000002.SZ" not in filtered
        assert "000001.SZ" in filtered

    def test_filter_blacklist(self):
        from app.core.universe import UniverseBuilder

        builder = UniverseBuilder()

        candidates = {"000001.SZ", "000002.SZ"}
        blacklist_df = pd.DataFrame(
            {
                "ts_code": ["000002.SZ"],
                "reason": ["重大立案"],
            }
        )

        filtered, _reasons = builder.filter_blacklist(candidates, blacklist_df, date(2024, 1, 15))
        assert "000002.SZ" not in filtered
        assert "000001.SZ" in filtered


# ==================== Labels测试 ====================


class TestLabelBuilder:
    """超额收益标签测试"""

    def test_excess_return_no_benchmark(self):
        from app.core.labels import LabelBuilder

        builder = LabelBuilder()

        price_df = pd.DataFrame(
            {
                "ts_code": ["A"] * 30,
                "trade_date": pd.date_range("2024-01-01", periods=30),
                "close": np.cumprod(1 + np.random.randn(30) * 0.01 + 0.001),
            }
        )

        result = builder.excess_return(price_df, horizon=5)
        assert not result.empty
        assert "excess_return" in result.columns

    def test_excess_return_with_benchmark(self):
        from app.core.labels import LabelBuilder

        builder = LabelBuilder()

        price_df = pd.DataFrame(
            {
                "ts_code": ["A"] * 30,
                "trade_date": pd.date_range("2024-01-01", periods=30),
                "close": np.cumprod(1 + np.random.randn(30) * 0.01 + 0.001),
            }
        )
        benchmark_df = pd.DataFrame(
            {
                "trade_date": pd.date_range("2024-01-01", periods=30),
                "close": np.cumprod(1 + np.random.randn(30) * 0.005 + 0.0005),
            }
        )

        result = builder.excess_return(price_df, benchmark_df, horizon=5)
        assert not result.empty
        assert "excess_return" in result.columns

    def test_industry_neutral_return(self):
        from app.core.labels import LabelBuilder

        builder = LabelBuilder()

        price_df = pd.DataFrame(
            {
                "ts_code": ["A"] * 20 + ["B"] * 20,
                "trade_date": list(pd.date_range("2024-01-01", periods=20)) * 2,
                "close": np.cumprod(1 + np.random.randn(40) * 0.01 + 0.001),
            }
        )
        industry_df = pd.DataFrame(
            {
                "ts_code": ["A", "B"],
                "industry": ["银行", "电子"],
            }
        )

        result = builder.industry_neutral_return(price_df, industry_df, horizon=5)
        assert not result.empty
        assert "industry_neutral_return" in result.columns

    def test_multi_horizon_labels(self):
        from app.core.labels import LabelBuilder

        builder = LabelBuilder()

        price_df = pd.DataFrame(
            {
                "ts_code": ["A"] * 60,
                "trade_date": pd.date_range("2024-01-01", periods=60),
                "close": np.cumprod(1 + np.random.randn(60) * 0.01 + 0.001),
            }
        )

        result = builder.multi_horizon_labels(price_df, horizons=[5, 10, 20])
        assert not result.empty


# ==================== Regime测试 ====================


class TestRegimeDetector:
    """市场状态检测测试"""

    def test_detect_trending(self):
        from app.core.regime import RegimeDetector

        detector = RegimeDetector()

        # 构造上升趋势数据
        dates = pd.date_range("2024-01-01", periods=120)
        close = pd.Series(range(100, 220), index=dates)
        market_data = pd.DataFrame(
            {
                "trade_date": dates,
                "close": close.values,
            }
        )

        regime, _confidence = detector.detect(market_data)
        assert regime in ["trending", "mean_reverting", "defensive", "risk_on"]

    def test_detect_with_empty_data(self):
        from app.core.regime import RegimeDetector

        detector = RegimeDetector()

        regime, _confidence = detector.detect(pd.DataFrame())
        assert regime == "mean_reverting"  # 默认震荡市

    def test_market_features(self):
        from app.core.regime import RegimeDetector

        detector = RegimeDetector()

        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=120)
        close = pd.Series(100 * np.cumprod(1 + np.random.randn(120) * 0.01), index=dates)
        market_data = pd.DataFrame(
            {
                "trade_date": dates,
                "close": close.values,
            }
        )

        features = detector.market_features(market_data)
        assert "market_vol_20d" in features
        assert features["market_vol_20d"] > 0

    def test_weight_adjustments(self):
        from app.core.regime import RegimeDetector

        detector = RegimeDetector()

        base_weights = {"quality_growth": 0.35, "expectation": 0.30, "residual_momentum": 0.25, "flow_confirm": 0.10}

        # 防御模式应增加质量权重
        adjusted = detector.get_weight_adjustments("defensive", base_weights)
        assert adjusted["quality_growth"] > base_weights["quality_growth"]
        assert adjusted["residual_momentum"] < base_weights["residual_momentum"]

    def test_detect_with_confidence(self):
        from app.core.regime import RegimeDetector

        detector = RegimeDetector()

        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=120)
        close = pd.Series(100 * np.cumprod(1 + np.random.randn(120) * 0.01), index=dates)
        market_data = pd.DataFrame(
            {
                "trade_date": dates,
                "close": close.values,
            }
        )

        result = detector.detect_with_confidence(market_data)
        assert "regime" in result
        assert "confidence" in result
        assert 0 <= result["confidence"] <= 1


# ==================== FactorMonitor测试 ====================


class TestFactorMonitor:
    """因子监控测试"""

    def test_rolling_ic(self):
        from app.core.factor_monitor import FactorMonitor

        monitor = FactorMonitor()

        np.random.seed(42)
        factor_values = pd.Series(np.random.randn(200))
        forward_returns = pd.Series(np.random.randn(200))

        result = monitor.rolling_ic(factor_values, forward_returns, window=60)
        assert len(result) > 0

    def test_ic_drift(self):
        from app.core.factor_monitor import FactorMonitor

        monitor = FactorMonitor()

        # 稳定IC序列
        ic_series = pd.Series(np.random.randn(200) * 0.05 + 0.03)
        result = monitor.ic_drift(ic_series)
        assert "ic_recent" in result
        assert "ic_long" in result
        assert "is_decaying" in result

    def test_psi_no_change(self):
        from app.core.factor_monitor import FactorMonitor

        monitor = FactorMonitor()

        np.random.seed(42)
        dist = pd.Series(np.random.randn(1000))
        psi = monitor.psi(dist, dist)
        assert psi < 0.01  # 相同分布PSI应接近0

    def test_psi_significant_change(self):
        from app.core.factor_monitor import FactorMonitor

        monitor = FactorMonitor()

        np.random.seed(42)
        ref = pd.Series(np.random.randn(1000))
        current = pd.Series(np.random.randn(1000) + 2)  # 均值偏移
        psi = monitor.psi(current, ref)
        assert psi > 0.10  # 显著变化

    def test_ks_test(self):
        from app.core.factor_monitor import FactorMonitor

        monitor = FactorMonitor()

        np.random.seed(42)
        ref = pd.Series(np.random.randn(1000))
        current = pd.Series(np.random.randn(1000) + 1)
        result = monitor.rolling_ks(current, ref)
        assert "ks_statistic" in result
        assert "is_significant" in result
        assert result["is_significant"]  # 均值偏移1σ应显著

    def test_module_correlation_matrix(self):
        from app.core.factor_monitor import FactorMonitor

        monitor = FactorMonitor()

        np.random.seed(42)
        module_scores = pd.DataFrame(np.random.randn(100, 4), columns=["quality", "expectation", "momentum", "flow"])
        corr = monitor.module_correlation_matrix(module_scores)
        assert corr.shape == (4, 4)
        assert (corr.values == corr.values.T).all()  # symmetric

    def test_check_health(self):
        from app.core.factor_monitor import FactorMonitor

        monitor = FactorMonitor()

        ic_series = pd.Series(np.random.randn(200) * 0.05 + 0.03)
        result = monitor.check_health(ic_series=ic_series, module_name="test")
        assert "is_healthy" in result
        assert "alerts" in result


# ==================== DailyPipeline测试 ====================


class TestDailyPipeline:
    """日终流水线测试"""

    def test_pipeline_init(self):
        from app.core.daily_pipeline import DailyPipeline

        pipeline = DailyPipeline(session=None)
        assert pipeline.universe_builder is not None
        assert pipeline.ensemble_engine is not None
        assert pipeline.regime_detector is not None
        assert pipeline.portfolio_builder is not None

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


# ==================== Compliance测试 ====================


class TestCompliance:
    """合规模块测试"""

    def test_compliance_module_exists(self):
        from app.core.compliance import add_disclaimer, check_high_risk_text

        assert callable(check_high_risk_text)
        assert callable(add_disclaimer)

    def test_check_text_no_violations(self):
        from app.core.compliance import check_high_risk_text

        safe_text = "本策略基于历史回测分析，不代表未来收益"
        violations = check_high_risk_text(safe_text)
        assert len(violations) == 0

    def test_check_text_with_violations(self):
        from app.core.compliance import check_high_risk_text

        risky_text = "本策略荐股，保证收益，建议跟单操作"
        violations = check_high_risk_text(risky_text)
        assert len(violations) > 0
