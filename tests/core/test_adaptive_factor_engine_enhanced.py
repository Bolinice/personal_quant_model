"""
测试自适应因子引擎的IC衰减监控功能
"""

import numpy as np
import pandas as pd
import pytest
from datetime import date, timedelta

from app.core.adaptive_factor_engine import (
    AdaptiveFactorEngine,
    FactorState,
    FactorProfile,
)


class TestICDecayMonitoring:
    """测试IC衰减监控"""

    def test_monitor_ic_decay_stable_factor(self):
        """测试稳定因子（无衰减）"""
        # 创建稳定的IC序列
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")
        ic_data = pd.DataFrame(
            {
                "trade_date": dates,
                "factor_code": ["factor1"] * 60,
                "ic": np.random.randn(60) * 0.01 + 0.05,  # 均值0.05，稳定
            }
        )

        engine = AdaptiveFactorEngine()
        report = engine.monitor_ic_decay(ic_data, lookback_short=20, lookback_long=60)

        # 验证报告结构
        assert "factors" in report
        assert "alerts" in report
        assert "summary" in report

        # 稳定因子应该没有预警
        assert len(report["alerts"]) == 0

        # 验证因子指标
        factor_report = report["factors"]["factor1"]
        assert abs(factor_report["decay_rate"]) < 0.2  # 衰减率应该很小
        assert factor_report["is_decaying"] is False

    def test_monitor_ic_decay_decaying_factor(self):
        """测试衰减因子"""
        # 创建衰减的IC序列
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")

        # 指数衰减：从0.08降到0.02
        t = np.arange(60)
        ic_values = 0.08 * np.exp(-0.03 * t) + np.random.randn(60) * 0.005

        ic_data = pd.DataFrame(
            {
                "trade_date": dates,
                "factor_code": ["factor1"] * 60,
                "ic": ic_values,
            }
        )

        engine = AdaptiveFactorEngine()
        report = engine.monitor_ic_decay(ic_data, lookback_short=20, lookback_long=60)

        # 衰减因子应该有预警
        assert len(report["alerts"]) > 0

        # 验证衰减指标
        factor_report = report["factors"]["factor1"]
        assert factor_report["decay_rate"] > 0.3  # 显著衰减
        assert factor_report["is_decaying"] is True
        assert factor_report["trend"] == "下降"

    def test_monitor_ic_decay_reversal(self):
        """测试IC方向反转"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")

        # 前40天正IC，后20天负IC
        ic_values = np.concatenate([
            np.random.randn(40) * 0.01 + 0.05,  # 正IC
            np.random.randn(20) * 0.01 - 0.03,  # 负IC
        ])

        ic_data = pd.DataFrame(
            {
                "trade_date": dates,
                "factor_code": ["factor1"] * 60,
                "ic": ic_values,
            }
        )

        engine = AdaptiveFactorEngine()
        report = engine.monitor_ic_decay(ic_data, lookback_short=20, lookback_long=60)

        # 应该有IC反转预警
        reversal_alerts = [a for a in report["alerts"] if a["type"] == "ic_reversal"]
        assert len(reversal_alerts) > 0
        assert reversal_alerts[0]["level"] == "critical"


class TestFactorHealthReport:
    """测试因子健康度报告"""

    def test_generate_health_report_excellent_factor(self):
        """测试优秀因子的健康度评分"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")

        # 优秀因子：高IC，高ICIR，高胜率
        ic_values = np.random.randn(60) * 0.01 + 0.06  # IC均值0.06

        ic_data = pd.DataFrame(
            {
                "trade_date": dates,
                "factor_code": ["excellent_factor"] * 60,
                "ic": ic_values,
            }
        )

        engine = AdaptiveFactorEngine()
        report = engine.generate_factor_health_report(ic_data, lookback=60)

        # 验证健康度评分
        factor_health = report["factors"]["excellent_factor"]
        assert factor_health["health_score"] >= 70
        assert factor_health["health_level"] in ["优秀", "良好"]
        assert factor_health["ic_positive_rate"] > 0.8

    def test_generate_health_report_poor_factor(self):
        """测试较差因子的健康度评分"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")

        # 较差因子：低IC，低ICIR，低胜率
        ic_values = np.random.randn(60) * 0.03 + 0.01  # IC均值0.01，波动大

        ic_data = pd.DataFrame(
            {
                "trade_date": dates,
                "factor_code": ["poor_factor"] * 60,
                "ic": ic_values,
            }
        )

        engine = AdaptiveFactorEngine()
        report = engine.generate_factor_health_report(ic_data, lookback=60)

        # 验证健康度评分
        factor_health = report["factors"]["poor_factor"]
        assert factor_health["health_score"] < 50
        assert factor_health["health_level"] in ["较差", "一般", "失效"]

    def test_generate_health_report_multiple_factors(self):
        """测试多因子健康度报告"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")

        # 3个因子：优秀、一般、较差
        ic_data = pd.DataFrame({
            "trade_date": np.tile(dates, 3),
            "factor_code": ["good"] * 60 + ["medium"] * 60 + ["poor"] * 60,
            "ic": np.concatenate([
                np.random.randn(60) * 0.01 + 0.06,  # 优秀
                np.random.randn(60) * 0.02 + 0.03,  # 一般
                np.random.randn(60) * 0.03 + 0.01,  # 较差
            ]),
        })

        engine = AdaptiveFactorEngine()
        report = engine.generate_factor_health_report(ic_data, lookback=60)

        # 验证报告结构
        assert len(report["factors"]) == 3
        assert "overall_health" in report
        assert "top_factors" in report
        assert "bottom_factors" in report

        # 验证排序
        assert report["top_factors"][0][0] == "good"
        assert report["bottom_factors"][0][0] == "poor"


class TestFactorRecommendations:
    """测试因子使用建议"""

    def test_get_recommendations_mixed_factors(self):
        """测试混合质量因子的建议"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")

        # 创建不同质量的因子
        ic_data = pd.DataFrame({
            "trade_date": np.tile(dates, 4),
            "factor_code": ["keep"] * 60 + ["monitor"] * 60 + ["reduce"] * 60 + ["remove"] * 60,
            "ic": np.concatenate([
                np.random.randn(60) * 0.01 + 0.06,  # 优秀，保持
                np.random.randn(60) * 0.015 + 0.04,  # 良好，监控
                np.random.randn(60) * 0.02 + 0.02,  # 一般，降权
                np.random.randn(60) * 0.03 + 0.005,  # 较差，移除
            ]),
        })

        engine = AdaptiveFactorEngine()
        recommendations = engine.get_factor_recommendations(ic_data, lookback=60)

        # 验证建议结构
        assert "keep" in recommendations
        assert "monitor" in recommendations
        assert "reduce" in recommendations
        assert "remove" in recommendations

        # 验证建议合理性
        assert "keep" in recommendations["keep"]
        assert "remove" in recommendations["remove"]

    def test_get_recommendations_all_good(self):
        """测试全部优秀因子的建议"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")

        ic_data = pd.DataFrame({
            "trade_date": np.tile(dates, 3),
            "factor_code": ["factor1"] * 60 + ["factor2"] * 60 + ["factor3"] * 60,
            "ic": np.concatenate([
                np.random.randn(60) * 0.01 + 0.06,
                np.random.randn(60) * 0.01 + 0.05,
                np.random.randn(60) * 0.01 + 0.055,
            ]),
        })

        engine = AdaptiveFactorEngine()
        recommendations = engine.get_factor_recommendations(ic_data, lookback=60)

        # 所有因子都应该保持或监控
        assert len(recommendations["keep"]) + len(recommendations["monitor"]) == 3
        assert len(recommendations["remove"]) == 0


class TestFactorDecayAnalysis:
    """测试因子衰减分析"""

    def test_analyze_factor_decay_exponential(self):
        """测试指数衰减拟合"""
        np.random.seed(42)

        # 创建指数衰减序列
        t = np.arange(60)
        ic_values = 0.08 * np.exp(-0.02 * t) + np.random.randn(60) * 0.005
        ic_series = pd.Series(ic_values)

        engine = AdaptiveFactorEngine()
        result = engine.analyze_factor_decay(ic_series, half_life_init=60)

        # 验证衰减检测
        assert result["is_decaying"] is True
        assert result["half_life"] < 60
        assert result["decay_rate"] > 0

    def test_analyze_factor_decay_stable(self):
        """测试稳定因子（无衰减）"""
        np.random.seed(42)

        # 创建稳定序列
        ic_values = np.random.randn(60) * 0.01 + 0.05
        ic_series = pd.Series(ic_values)

        engine = AdaptiveFactorEngine()
        result = engine.analyze_factor_decay(ic_series, half_life_init=60)

        # 验证无衰减
        assert result["is_decaying"] is False


class TestIntegration:
    """集成测试"""

    def test_full_monitoring_workflow(self):
        """测试完整的监控工作流"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")

        # 创建多个因子的IC数据
        ic_data = pd.DataFrame({
            "trade_date": np.tile(dates, 3),
            "factor_code": ["stable"] * 60 + ["decaying"] * 60 + ["volatile"] * 60,
            "ic": np.concatenate([
                np.random.randn(60) * 0.01 + 0.05,  # 稳定
                0.08 * np.exp(-0.03 * np.arange(60)) + np.random.randn(60) * 0.005,  # 衰减
                np.random.randn(60) * 0.03 + 0.02,  # 波动大
            ]),
        })

        engine = AdaptiveFactorEngine()

        # 1. 批量更新因子画像
        profiles = engine.batch_update_profiles(ic_data, trade_date=date.today())
        assert len(profiles) == 3

        # 2. IC衰减监控
        decay_report = engine.monitor_ic_decay(ic_data)
        assert len(decay_report["factors"]) == 3
        assert len(decay_report["alerts"]) > 0  # 应该有衰减预警

        # 3. 健康度报告
        health_report = engine.generate_factor_health_report(ic_data)
        assert len(health_report["factors"]) == 3
        assert "overall_health" in health_report

        # 4. 使用建议
        recommendations = engine.get_factor_recommendations(ic_data)
        assert sum(len(v) for v in recommendations.values()) == 3

        # 验证衰减因子被识别
        assert "decaying" in recommendations["reduce"] or "decaying" in recommendations["remove"]


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_ic_history(self):
        """测试空IC历史"""
        ic_data = pd.DataFrame()

        engine = AdaptiveFactorEngine()
        report = engine.monitor_ic_decay(ic_data)

        assert report["factors"] == {}
        assert report["alerts"] == []

    def test_insufficient_data(self):
        """测试数据不足"""
        dates = pd.date_range("2023-01-01", periods=5, freq="D")
        ic_data = pd.DataFrame({
            "trade_date": dates,
            "factor_code": ["factor1"] * 5,
            "ic": [0.05, 0.04, 0.06, 0.05, 0.04],
        })

        engine = AdaptiveFactorEngine()
        report = engine.monitor_ic_decay(ic_data, lookback_short=20, lookback_long=60)

        # 数据不足时应该跳过
        assert len(report["factors"]) == 0

    def test_single_factor(self):
        """测试单个因子"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=60, freq="D")
        ic_data = pd.DataFrame({
            "trade_date": dates,
            "factor_code": ["factor1"] * 60,
            "ic": np.random.randn(60) * 0.01 + 0.05,
        })

        engine = AdaptiveFactorEngine()

        # 所有功能都应该正常工作
        decay_report = engine.monitor_ic_decay(ic_data)
        health_report = engine.generate_factor_health_report(ic_data)
        recommendations = engine.get_factor_recommendations(ic_data)

        assert len(decay_report["factors"]) == 1
        assert len(health_report["factors"]) == 1
        assert sum(len(v) for v in recommendations.values()) == 1
