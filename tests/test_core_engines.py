"""
核心引擎单元测试
测试因子预处理、回测引擎、择时引擎、风险模型
"""
import pytest
import numpy as np
import pandas as pd
from datetime import date, datetime


class TestFactorPreprocessor:
    """因子预处理测试"""

    def test_winsorize_mad(self):
        from app.core.factor_preprocess import FactorPreprocessor
        preprocessor = FactorPreprocessor()

        # 正常数据
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = preprocessor.winsorize_mad(data, n_mad=3.0)
        assert len(result) == len(data)

        # 含极端值
        data_with_outlier = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        result = preprocessor.winsorize_mad(data_with_outlier, n_mad=3.0)
        assert result.max() < 100  # 极端值应被截断

    def test_standardize_zscore(self):
        from app.core.factor_preprocess import FactorPreprocessor
        preprocessor = FactorPreprocessor()

        data = pd.Series([1, 2, 3, 4, 5])
        result = preprocessor.standardize_zscore(data)
        assert abs(result.mean()) < 1e-10  # 均值应接近0
        assert abs(result.std() - 1.0) < 1e-10  # 标准差应接近1

    def test_align_direction(self):
        from app.core.factor_preprocess import FactorPreprocessor
        preprocessor = FactorPreprocessor()

        data = pd.Series([1, 2, 3, 4, 5])

        # 正向
        result = preprocessor.align_direction(data, direction=1)
        assert (result == data).all()

        # 反向
        result = preprocessor.align_direction(data, direction=-1)
        assert (result == -data).all()

    def test_full_preprocess(self):
        from app.core.factor_preprocess import FactorPreprocessor
        preprocessor = FactorPreprocessor()

        # 含缺失值和极端值
        data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 100, np.nan])
        result = preprocessor.preprocess(data)
        assert not result.isna().any()  # 缺失值应被填充
        assert abs(result.mean()) < 1  # 标准化后均值应接近0


class TestBacktestEngine:
    """回测引擎测试"""

    def test_transaction_cost(self):
        from app.core.backtest_engine import TransactionCost
        cost_model = TransactionCost()

        # 买入成本
        buy_cost = cost_model.calc_buy_cost(100000)
        assert buy_cost['stamp_tax'] == 0  # 买入无印花税
        assert buy_cost['commission'] >= 5  # 最低佣金5元
        assert buy_cost['total_cost'] > 0

        # 卖出成本
        sell_cost = cost_model.calc_sell_cost(100000)
        assert sell_cost['stamp_tax'] > 0  # 卖出有印花税
        assert sell_cost['total_cost'] > buy_cost['total_cost']  # 卖出成本更高

    def test_round_lot(self):
        from app.core.backtest_engine import ABShareBacktestEngine
        engine = ABShareBacktestEngine()

        assert engine.round_lot(150) == 100
        assert engine.round_lot(250) == 200
        assert engine.round_lot(99) == 0
        assert engine.round_lot(100) == 100

    def test_limit_check(self):
        from app.core.backtest_engine import ABShareBacktestEngine
        engine = ABShareBacktestEngine()

        # 主板涨停
        assert engine.is_limit_up(9.99, 'main') == True
        assert engine.is_limit_up(5.0, 'main') == False

        # 创业板涨停
        assert engine.is_limit_up(19.99, 'gem') == True
        assert engine.is_limit_up(10.0, 'gem') == False

    def test_board_type(self):
        from app.core.backtest_engine import ABShareBacktestEngine
        engine = ABShareBacktestEngine()

        assert engine.get_board_type('600000.SH') == 'main'
        assert engine.get_board_type('300001.SZ') == 'gem'
        assert engine.get_board_type('688001.SH') == 'star'


class TestTimingEngine:
    """择时引擎测试"""

    def test_ma_cross_signal(self):
        from app.core.timing_engine import TimingEngine, TimingSignalType
        engine = TimingEngine()

        # 上升趋势
        close = pd.Series(range(100, 200))
        signal = engine.ma_cross_signal(close, short_window=5, long_window=20)
        assert signal.iloc[-1] == TimingSignalType.LONG

        # 下降趋势
        close = pd.Series(range(200, 100, -1))
        signal = engine.ma_cross_signal(close, short_window=5, long_window=20)
        assert signal.iloc[-1] == TimingSignalType.SHORT

    def test_drawdown_control(self):
        from app.core.timing_engine import TimingEngine, TimingSignalType
        engine = TimingEngine()

        # 模拟回撤
        close = pd.Series([100, 105, 110, 100, 90, 80, 85, 90])
        signal = engine.drawdown_control_signal(close, max_drawdown=0.10)
        assert TimingSignalType.SHORT in signal.values  # 回撤超阈值应触发减仓

    def test_fuse_signals(self):
        from app.core.timing_engine import TimingEngine, TimingSignalType, FusionMethod
        engine = TimingEngine()

        signals = {
            'ma': pd.Series([TimingSignalType.LONG] * 5),
            'vol': pd.Series([TimingSignalType.LONG] * 5),
            'breadth': pd.Series([TimingSignalType.NEUTRAL] * 5),
        }

        result = engine.fuse_signals(signals, method=FusionMethod.EQUAL)
        assert result.iloc[0] == TimingSignalType.LONG  # 多数看多


class TestRiskModel:
    """风险模型测试"""

    def test_sample_covariance(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.DataFrame(np.random.randn(100, 3), columns=['A', 'B', 'C'])
        cov = model.sample_covariance(returns)

        assert cov.shape == (3, 3)
        assert (cov.values == cov.values.T).all()  # 对称

    def test_historical_var(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.02)
        var = model.historical_var(returns, confidence=0.95)
        assert var > 0  # VaR应为正

    def test_conditional_var(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.02)
        cvar = model.conditional_var(returns, confidence=0.95)
        assert cvar > 0  # CVaR应为正

    def test_risk_contribution(self):
        from app.core.risk_model import RiskModel
        model = RiskModel()

        # 等权组合
        weights = np.array([0.25, 0.25, 0.25, 0.25])
        cov = np.eye(4) * 0.04  # 单位协方差

        rc = model.risk_contribution_pct(weights, cov)
        assert abs(rc.sum() - 1.0) < 1e-10  # 风险贡献之和应为1


class TestPerformanceAnalyzer:
    """绩效分析测试"""

    def test_sharpe_ratio(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.01 + 0.0005)
        sharpe = analyzer.calc_sharpe_ratio(returns)
        assert isinstance(sharpe, float)

    def test_max_drawdown(self):
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        nav = pd.Series([1.0, 1.1, 1.05, 1.2, 1.15, 1.3])
        max_dd, start, end = analyzer.calc_max_drawdown(nav)
        assert max_dd < 0  # 最大回撤应为负


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
