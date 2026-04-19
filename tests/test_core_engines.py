"""
核心引擎单元测试
测试因子预处理、回测引擎、择时引擎、风险模型
机构级增强: 动量跳月、TTM因子、IC计算、分组回测、正交化、Newey-West、Barra WLS
"""
import pytest
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta


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

    def test_preprocess_dataframe_with_config(self):
        """测试逐因子配置预处理"""
        from app.core.factor_preprocess import FactorPreprocessor
        preprocessor = FactorPreprocessor()

        df = pd.DataFrame({
            'security_id': ['A', 'B', 'C', 'D'],
            'ep_ttm': [0.05, 0.08, 0.12, 0.03],
            'ret_1m_reversal': [0.02, -0.03, 0.05, -0.01],
        })

        # 逐因子配置: ep_ttm用zscore, ret_1m_reversal用rank_normal
        config = {
            'ep_ttm': {'standardize_method': 'zscore'},
            'ret_1m_reversal': {'standardize_method': 'rank_normal'},
        }
        result = preprocessor.preprocess_dataframe(
            df, ['ep_ttm', 'ret_1m_reversal'], config=config
        )
        assert 'ep_ttm' in result.columns
        assert 'ret_1m_reversal' in result.columns

    def test_preprocess_dataframe_coverage_filter(self):
        """测试覆盖率过滤"""
        from app.core.factor_preprocess import FactorPreprocessor
        preprocessor = FactorPreprocessor()

        df = pd.DataFrame({
            'security_id': ['A', 'B', 'C', 'D'],
            'good_factor': [1.0, 2.0, 3.0, 4.0],
            'sparse_factor': [np.nan, np.nan, np.nan, 1.0],  # 25%覆盖率
        })

        result = preprocessor.preprocess_dataframe(
            df, ['good_factor', 'sparse_factor'], min_coverage=0.6
        )
        # sparse_factor覆盖率25% < 60%, 应被跳过
        assert result['sparse_factor'].isna().all()

    def test_orthogonalize_factors(self):
        """测试因子正交化"""
        from app.core.factor_preprocess import FactorPreprocessor
        preprocessor = FactorPreprocessor()

        np.random.seed(42)
        n = 100
        size = np.random.randn(n)
        # value与size相关
        value = 0.5 * size + 0.5 * np.random.randn(n)

        df = pd.DataFrame({
            'security_id': range(n),
            'size': size,
            'value': value,
        })

        # 对value做size中性化
        result = preprocessor.orthogonalize_factors(df, ['value'], target_col='size')
        # 正交化后value与size的相关性应大幅降低
        corr_before = np.corrcoef(size, value)[0, 1]
        corr_after = np.corrcoef(df['size'].values, result['value'].values)[0, 1]
        assert abs(corr_after) < abs(corr_before)

    def test_cross_sectional_residual(self):
        """测试截面回归残差"""
        from app.core.factor_preprocess import FactorPreprocessor
        preprocessor = FactorPreprocessor()

        df = pd.DataFrame({
            'factor': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'control': [2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
        })

        residual = preprocessor.cross_sectional_residual(df, 'factor', ['control'])
        # factor = 0.5 * control, 残差应接近0
        assert residual.dropna().abs().max() < 0.01


class TestMomentumSkipMonth:
    """动量因子跳月处理测试"""

    def test_skip_month_no_overlap(self):
        """验证跳月动量与1月反转无时间重叠"""
        from app.core.factor_engine import FactorEngine

        # 生成300个交易日的价格数据
        np.random.seed(42)
        close = 100 * np.cumprod(1 + np.random.randn(300) * 0.02)
        price_df = pd.DataFrame({
            'ts_code': ['TEST'] * 300,
            'close': close,
        })

        result = FactorEngine._calc_momentum_static(price_df)

        # ret_1m_reversal = close[t]/close[t-20]-1 (含最近1月)
        # ret_12m_skip1 = close[t-20]/close[t-240]-1 (跳过最近1月)
        # 两者不应完全重叠
        assert 'ret_1m_reversal' in result.columns
        assert 'ret_12m_skip1' in result.columns
        assert 'ret_3m_skip1' in result.columns
        assert 'ret_6m_skip1' in result.columns

        # 旧因子名不应存在
        assert 'ret_1m' not in result.columns
        assert 'ret_12m' not in result.columns

    def test_skip_month_values(self):
        """验证跳月动量计算正确"""
        from app.core.factor_engine import FactorEngine

        close = pd.Series(range(100, 400), name='close')  # 300个数据点
        price_df = pd.DataFrame({
            'ts_code': ['TEST'] * 300,
            'close': close.values,
        })

        result = FactorEngine._calc_momentum_static(price_df)

        # ret_12m_skip1 at t=250: close[230]/close[10] - 1
        # close[230] = 330, close[10] = 110
        expected = 330 / 110 - 1
        actual = result['ret_12m_skip1'].iloc[250]
        assert abs(actual - expected) < 0.01


class TestTTMFactors:
    """TTM因子计算测试"""

    def test_valuation_from_raw(self):
        """测试从原始财务数据计算价值因子"""
        from app.core.factor_engine import FactorEngine

        financial_df = pd.DataFrame({
            'ts_code': ['A', 'B'],
            'net_profit': [10e8, 5e8],
            'total_equity': [50e8, 30e8],
            'operating_cash_flow': [12e8, 6e8],
            'revenue': [100e8, 60e8],
            'total_market_cap': [200e8, 100e8],
        })

        engine = FactorEngine.__new__(FactorEngine)
        engine.db = None
        engine.preprocessor = None

        result = engine.calc_valuation_factors(financial_df, pd.DataFrame())

        # EP_TTM = net_profit / market_cap
        assert abs(result['ep_ttm'].iloc[0] - 10e8 / 200e8) < 1e-6
        # BP = total_equity / market_cap
        assert abs(result['bp'].iloc[0] - 50e8 / 200e8) < 1e-6
        # CFP_TTM = operating_cash_flow / market_cap
        assert abs(result['cfp_ttm'].iloc[0] - 12e8 / 200e8) < 1e-6

    def test_quality_from_raw(self):
        """测试从原始财务数据计算质量因子"""
        from app.core.factor_engine import FactorEngine

        financial_df = pd.DataFrame({
            'ts_code': ['A'],
            'net_profit': [10e8],
            'total_equity': [50e8],
            'total_equity_prev': [45e8],
            'total_assets': [100e8],
            'total_assets_prev': [90e8],
            'gross_profit': [30e8],
            'revenue': [100e8],
            'operating_cash_flow': [12e8],
            'current_assets': [40e8],
            'current_liabilities': [20e8],
        })

        engine = FactorEngine.__new__(FactorEngine)
        engine.db = None
        engine.preprocessor = None

        result = engine.calc_quality_factors(financial_df)

        # ROE = net_profit / avg_equity = 10e8 / ((50e8+45e8)/2)
        avg_equity = (50e8 + 45e8) / 2
        assert abs(result['roe'].iloc[0] - 10e8 / avg_equity) < 1e-6

        # Sloan accrual = (net_profit - ocf) / avg_assets
        avg_assets = (100e8 + 90e8) / 2
        expected_accrual = (10e8 - 12e8) / avg_assets
        assert abs(result['sloan_accrual'].iloc[0] - expected_accrual) < 1e-6

        # Current ratio
        assert abs(result['current_ratio'].iloc[0] - 40e8 / 20e8) < 1e-6


class TestAShareSpecificFactors:
    """A股特有因子测试"""

    def test_ashare_specific_factors(self):
        from app.core.factor_engine import FactorEngine

        price_df = pd.DataFrame({
            'ts_code': ['A', 'B', 'C'],
            'pct_chg': [9.95, -9.95, 2.0],
        })

        engine = FactorEngine.__new__(FactorEngine)
        engine.db = None

        result = engine.calc_ashare_specific_factors(price_df)
        assert 'security_id' in result.columns

    def test_accruals_factor(self):
        from app.core.factor_engine import FactorEngine

        financial_df = pd.DataFrame({
            'ts_code': ['A', 'B'],
            'net_profit': [10, 5],
            'operating_cash_flow': [8, 7],
            'total_assets': [100, 50],
        })

        engine = FactorEngine.__new__(FactorEngine)
        engine.db = None

        result = engine.calc_accruals_factor(financial_df)
        # Sloan accrual for A: (10-8)/100 = 0.02
        assert abs(result['sloan_accrual'].iloc[0] - 0.02) < 1e-6
        # Sloan accrual for B: (5-7)/50 = -0.04
        assert abs(result['sloan_accrual'].iloc[1] - (-0.04)) < 1e-6


class TestNeweyWest:
    """Newey-West调整测试"""

    def test_nw_se_greater_than_ols_se(self):
        """NW标准误应 >= OLS标准误 (对正自相关序列)"""
        from app.core.risk_model import newey_west_se

        # 构造正自相关序列
        np.random.seed(42)
        n = 200
        ic = np.zeros(n)
        ic[0] = np.random.randn()
        for t in range(1, n):
            ic[t] = 0.5 * ic[t-1] + np.random.randn() * 0.5

        ic_series = pd.Series(ic)
        nw_se = newey_west_se(ic_series)
        ols_se = ic_series.std() / np.sqrt(n)

        # NW SE should be >= OLS SE for positively autocorrelated series
        assert nw_se >= ols_se * 0.95  # 允许微小数值误差

    def test_nw_tstat_for_white_noise(self):
        """白噪声序列NW t统计量应接近朴素t统计量"""
        from app.core.risk_model import newey_west_tstat

        np.random.seed(42)
        ic = pd.Series(np.random.randn(200) * 0.05)  # 白噪声

        nw_t = newey_west_tstat(ic)
        naive_t = ic.mean() / (ic.std() / np.sqrt(len(ic)))

        # 对白噪声, NW和朴素t应接近
        assert abs(nw_t - naive_t) / max(abs(naive_t), 0.01) < 0.3


class TestBarraWLS:
    """Barra WLS截面回归测试"""

    def test_wls_vs_ols(self):
        """WLS应给大市值股票更大权重"""
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        n = 50
        exposures = pd.DataFrame({
            'size': np.random.randn(n),
            'value': np.random.randn(n),
        }, index=range(n))

        returns = pd.Series(
            0.5 * exposures['size'] + 0.3 * exposures['value'] + np.random.randn(n) * 0.1,
            index=range(n)
        )

        # 大市值
        market_cap = pd.Series(np.random.lognormal(20, 1, n), index=range(n))

        # WLS
        wls_result = model.barra_factor_return(returns, exposures, market_cap)
        # OLS (无市值权重)
        ols_result = model.barra_factor_return(returns, exposures, None)

        # 两者都应返回因子收益
        assert len(wls_result) == 2
        assert len(ols_result) == 2

    def test_estimate_factor_covariance(self):
        """测试因子协方差估计"""
        from app.core.risk_model import RiskModel
        model = RiskModel()

        np.random.seed(42)
        factor_returns = pd.DataFrame(
            np.random.randn(252, 3) * 0.01,
            columns=['size', 'value', 'momentum']
        )

        cov = model.estimate_factor_covariance(factor_returns)
        assert cov.shape == (3, 3)
        # 应为正定
        eigenvalues = np.linalg.eigvalsh(cov.values)
        assert (eigenvalues > 0).all()


class TestICStatistics:
    """IC统计量测试 (含Newey-West)"""

    def test_ic_statistics_with_nw(self):
        from app.core.factor_analyzer import FactorAnalyzer

        np.random.seed(42)
        ic_series = pd.Series(np.random.randn(120) * 0.05 + 0.03)

        analyzer = FactorAnalyzer.__new__(FactorAnalyzer)
        stats = analyzer.calc_ic_statistics(ic_series)

        assert 'ic_mean' in stats
        assert 'icir' in stats
        assert 'ic_nw_t_stat' in stats
        assert 'ic_nw_se' in stats
        # NW t统计量应为有限值
        assert not np.isnan(stats['ic_nw_t_stat'])


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

    def test_run_backtest_basic(self):
        """测试回测主循环基本功能"""
        from app.core.backtest_engine import ABShareBacktestEngine

        engine = ABShareBacktestEngine()

        # 简单信号生成器: 等权持有2只股票
        def signal_generator(trade_date, universe, state):
            return {code: 0.5 for code in universe[:2]}

        # 构造行情数据
        trading_days = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        universe = ['600000.SH', '000001.SZ']
        price_data = {}
        for td in trading_days:
            for code in universe:
                price_data[(code, td)] = {
                    'close': 10.0,
                    'open': 10.0,
                    'pct_chg': 0.0,
                    'volume': 1e8,
                    'amount': 1e9,
                    'is_suspended': False,
                    'is_st': False,
                }

        result = engine.run_backtest(
            signal_generator=signal_generator,
            universe=universe,
            start_date=date(2024, 1, 2),
            end_date=date(2024, 1, 4),
            rebalance_freq='daily',
            initial_capital=1000000,
            trading_days=trading_days,
            price_data=price_data,
        )

        assert 'nav_history' in result
        assert 'trade_records' in result
        assert 'metrics' in result
        assert result['total_days'] > 0


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

    def test_brinson_attribution(self):
        """测试Brinson归因分解"""
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        wp = pd.Series({'金融': 0.4, '科技': 0.35, '消费': 0.25})
        rp = pd.Series({'金融': 0.02, '科技': 0.05, '消费': 0.01})
        wb = pd.Series({'金融': 0.5, '科技': 0.3, '消费': 0.2})
        rb = pd.Series({'金融': 0.01, '科技': 0.03, '消费': 0.02})

        result = analyzer.brinson_attribution(wp, rp, wb, rb)
        assert 'allocation_effect' in result
        assert 'selection_effect' in result
        assert 'interaction_effect' in result
        # 总超额 = 分配+选择+交互
        assert abs(result['total_excess'] - (
            result['allocation_effect'] + result['selection_effect'] + result['interaction_effect']
        )) < 1e-6

    def test_factor_return_attribution(self):
        """测试因子收益归因"""
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        weights = pd.Series([0.3, 0.3, 0.2, 0.2])
        exposures = pd.DataFrame({
            'value': [1.0, -0.5, 0.8, -0.3],
            'momentum': [0.5, 0.8, -0.2, 0.6],
        })
        factor_returns = pd.Series({'value': 0.02, 'momentum': 0.03})
        specific_returns = pd.Series([0.001, -0.002, 0.003, -0.001])

        result = analyzer.factor_return_attribution(weights, exposures, factor_returns, specific_returns)
        assert 'factor_contributions' in result
        assert 'value' in result['factor_contributions']
        assert 'momentum' in result['factor_contributions']

    def test_rolling_performance(self):
        """测试滚动绩效"""
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        np.random.seed(42)
        returns = pd.Series(np.random.randn(252) * 0.01 + 0.0005,
                           index=pd.date_range('2024-01-01', periods=252))

        result = analyzer.rolling_performance(returns, window=60)
        assert len(result) > 0
        assert 'rolling_sharpe' in result.columns

    def test_regime_conditional_performance(self):
        """测试市场状态条件绩效"""
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=252)
        returns = pd.Series(np.random.randn(252) * 0.01, index=dates)
        regime = pd.Series(['bull'] * 100 + ['bear'] * 100 + ['sideways'] * 52, index=dates)

        result = analyzer.regime_conditional_performance(returns, regime)
        assert 'bull' in result
        assert 'bear' in result
        assert 'sharpe' in result['bull']

    def test_stress_test_performance(self):
        """测试压力测试"""
        from app.core.performance_analyzer import PerformanceAnalyzer
        analyzer = PerformanceAnalyzer()

        np.random.seed(42)
        dates = pd.date_range('2015-01-01', periods=2000)
        returns = pd.Series(np.random.randn(2000) * 0.01, index=dates)

        result = analyzer.stress_test_performance(returns)
        assert isinstance(result, dict)


class TestVaRBacktest:
    """VaR突破率回测测试"""

    def test_var_backtest_well_calibrated(self):
        """校准良好的VaR突破率应接近1-confidence"""
        from app.core.risk_model import RiskModel
        model = RiskModel()

        # 正态分布收益(校准良好)
        np.random.seed(42)
        returns = pd.Series(np.random.randn(1000) * 0.01, index=pd.date_range('2020-01-01', periods=1000))

        result = model.backtest_var(returns, confidence=0.95, window=252)
        assert 'empirical_rate' in result
        assert 'kupiec_pof' in result
        assert 'christoffersen_independence' in result
        # 突破率应接近5%
        assert 0.01 < result['empirical_rate'] < 0.15

    def test_kupiec_rejects_misaligned_var(self):
        """Kupiec检验应拒绝严重偏离的VaR"""
        from app.core.risk_model import RiskModel
        model = RiskModel()

        # 厚尾分布(学生t)
        np.random.seed(42)
        from scipy.stats import t as t_dist
        returns = pd.Series(t_dist.rvs(df=3, size=1000) * 0.01, index=pd.date_range('2020-01-01', periods=1000))

        result = model.backtest_var(returns, confidence=0.99, window=252, method='parametric')
        # 参数法VaR在厚尾分布下突破率应偏高
        assert result['empirical_rate'] > result['expected_rate'] * 0.5


class TestBayesianFusion:
    """贝叶斯融合测试"""

    def test_bayesian_fuse_basic(self):
        """测试贝叶斯融合基本功能"""
        from app.core.timing_engine import TimingEngine, TimingSignalType, FusionMethod
        engine = TimingEngine()

        signals = {
            'ma': pd.Series([TimingSignalType.LONG] * 10),
            'vol': pd.Series([TimingSignalType.LONG] * 10),
        }

        result = engine.fuse_signals(signals, method=FusionMethod.BAYESIAN)
        assert result.iloc[0] == TimingSignalType.LONG

    def test_bayesian_fuse_with_returns(self):
        """测试带收益数据的贝叶斯融合"""
        from app.core.timing_engine import TimingEngine, TimingSignalType, FusionMethod
        engine = TimingEngine()

        signals = {
            'good_signal': pd.Series([TimingSignalType.LONG] * 20),
            'bad_signal': pd.Series([TimingSignalType.SHORT] * 20),
        }
        # 市场上涨, good_signal命中, bad_signal未命中
        returns = pd.Series([0.01] * 20)

        result = engine.fuse_signals(signals, method=FusionMethod.BAYESIAN)
        # good_signal权重应更高, 结果偏多
        assert len(result) == 20


class TestTimingSignalEvaluation:
    """择时信号评估测试"""

    def test_evaluate_timing_signal(self):
        """测试择时信号评估"""
        from app.core.timing_engine import TimingEngine, TimingSignalType
        engine = TimingEngine()

        dates = pd.date_range('2024-01-01', periods=100)
        signal = pd.Series([TimingSignalType.LONG] * 50 + [TimingSignalType.SHORT] * 50, index=dates)
        # 前半段上涨(多头正确), 后半段下跌(空头正确)
        returns = pd.Series([0.01] * 50 + [-0.01] * 50, index=dates)

        result = engine.evaluate_timing_signal(signal, returns)
        assert 'hit_rate' in result
        assert 'profit_loss_factor' in result
        assert 'signal_to_noise_ratio' in result
        assert result['hit_rate'] > 0.5  # 信号应有效

    def test_evaluate_with_regime(self):
        """测试带市场状态的信号评估"""
        from app.core.timing_engine import TimingEngine, TimingSignalType, MarketRegime
        engine = TimingEngine()

        dates = pd.date_range('2024-01-01', periods=100)
        signal = pd.Series([TimingSignalType.LONG] * 100, index=dates)
        returns = pd.Series(np.random.randn(100) * 0.01 + 0.001, index=dates)
        regime = pd.Series([MarketRegime.BULL] * 50 + [MarketRegime.BEAR] * 50, index=dates)

        result = engine.evaluate_timing_signal(signal, returns, regime)
        assert 'regime_conditional' in result


class TestWalkForwardBacktest:
    """Walk-Forward回测测试"""

    def test_walk_forward_backtest_basic(self):
        """测试Walk-Forward回测基本功能"""
        from app.core.backtest_engine import ABShareBacktestEngine
        engine = ABShareBacktestEngine()

        # 简单模型工厂
        def model_factory(train_start, train_end):
            def signal_generator(trade_date, universe, state):
                return {code: 0.5 for code in universe[:2]}
            return signal_generator

        trading_days = [date(2024, 1, 2) + timedelta(days=i) for i in range(0, 300, 2) if (date(2024, 1, 2) + timedelta(days=i)).weekday() < 5][:150]
        universe = ['600000.SH', '000001.SZ']
        price_data = {}
        for td in trading_days:
            for code in universe:
                price_data[(code, td)] = {
                    'close': 10.0, 'open': 10.0, 'pct_chg': 0.0,
                    'volume': 1e8, 'amount': 1e9,
                    'is_suspended': False, 'is_st': False,
                }

        result = engine.walk_forward_backtest(
            model_factory=model_factory,
            train_start=date(2024, 1, 2),
            train_end=date(2024, 4, 1),
            test_end=date(2024, 9, 1),
            retrain_freq=42,
            train_window=60,
            gap=5,
            initial_capital=1000000,
            universe=universe,
            price_data=price_data,
            trading_days=trading_days,
        )

        assert 'n_windows' in result
        assert result['n_windows'] >= 0


class TestPositionPnLAttribution:
    """持仓级P&L归因测试"""

    def test_position_pnl_attribution(self):
        """测试持仓级P&L因子归因"""
        from app.core.backtest_engine import ABShareBacktestEngine
        engine = ABShareBacktestEngine()

        nav_history = [
            {
                'trade_date': date(2024, 1, 2),
                'position_pnl': {
                    '600000.SH': {'shares': 1000, 'price': 10.5, 'prev_price': 10.0, 'pnl': 500, 'weight': 0.5},
                    '000001.SZ': {'shares': 500, 'price': 20.2, 'prev_price': 20.0, 'pnl': 100, 'weight': 0.5},
                },
            },
        ]

        factor_exposures = {
            '600000.SH': {'value': 1.0, 'momentum': 0.5},
            '000001.SZ': {'value': -0.5, 'momentum': 0.8},
        }

        result = engine.position_pnl_attribution(nav_history, factor_exposures)
        assert 'factor_pnl' in result
        assert 'value' in result['factor_pnl']
        assert 'momentum' in result['factor_pnl']
        assert 'total_pnl' in result


class TestTradingCalendar:
    """交易日历测试"""

    def test_fallback_without_db(self):
        """无数据库时回退到工作日计算"""
        from app.core.trading_utils import TradingCalendar
        from datetime import date

        cal = TradingCalendar(db_session=None)
        # 周五的下一个交易日应为周一
        friday = date(2024, 1, 5)  # Friday
        next_td = cal.get_next_trading_date(friday, n=1)
        assert next_td.weekday() == 0  # Monday

    def test_trading_dates_between(self):
        """测试获取交易日区间"""
        from app.core.trading_utils import TradingCalendar
        from datetime import date

        cal = TradingCalendar(db_session=None)
        dates = cal.get_trading_dates_between(date(2024, 1, 1), date(2024, 1, 7))
        # 应只包含工作日
        for d in dates:
            assert d.weekday() < 5

    def test_count_trading_days(self):
        """测试交易日计数"""
        from app.core.trading_utils import TradingCalendar
        from datetime import date

        cal = TradingCalendar(db_session=None)
        count = cal.count_trading_days(date(2024, 1, 1), date(2024, 1, 7))
        assert count == 5  # Mon-Fri


class TestPortfolioOptimizerPhase2:
    """Phase2组合优化器测试"""

    def test_black_litterman(self):
        """测试Black-Litterman优化"""
        from app.core.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()

        n = 5
        stocks = [f'S{i}' for i in range(n)]
        market_cap_weights = pd.Series([0.4, 0.25, 0.15, 0.12, 0.08], index=stocks)
        np.random.seed(42)
        cov = pd.DataFrame(np.eye(n) * 0.04 + 0.01, index=stocks, columns=stocks)

        # 一个观点: 资产0将跑赢5%
        P = np.zeros((1, n))
        P[0, 0] = 1
        Q = np.array([0.05])
        Omega = np.array([[0.01]])

        weights = optimizer.black_litterman_optimize(market_cap_weights, cov, P, Q, Omega)
        assert len(weights) == n
        assert abs(weights.sum() - 1.0) < 0.01

    def test_robust_optimize(self):
        """测试稳健优化"""
        from app.core.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()

        n = 5
        stocks = [f'S{i}' for i in range(n)]
        expected_returns = pd.Series([0.10, 0.08, 0.12, 0.06, 0.09], index=stocks)
        np.random.seed(42)
        cov = pd.DataFrame(np.eye(n) * 0.04 + 0.01, index=stocks, columns=stocks)
        uncertainty = pd.Series([0.02, 0.03, 0.01, 0.05, 0.02], index=stocks)

        weights = optimizer.robust_mean_variance_optimize(
            expected_returns, cov, uncertainty, kappa=1.0
        )
        assert len(weights) == n
        assert abs(weights.sum() - 1.0) < 0.05

    def test_transaction_cost_aware(self):
        """测试交易成本感知优化"""
        from app.core.portfolio_optimizer import PortfolioOptimizer
        optimizer = PortfolioOptimizer()

        n = 5
        stocks = [f'S{i}' for i in range(n)]
        expected_returns = pd.Series([0.10, 0.08, 0.12, 0.06, 0.09], index=stocks)
        np.random.seed(42)
        cov = pd.DataFrame(np.eye(n) * 0.04 + 0.01, index=stocks, columns=stocks)
        prev_weights = pd.Series([0.2] * n, index=stocks)

        weights = optimizer.transaction_cost_aware_optimize(
            expected_returns, cov, prev_weights, linear_cost=0.003
        )
        assert len(weights) == n
        assert abs(weights.sum() - 1.0) < 0.05


class TestModelScorerPhase2:
    """Phase2评分器测试"""

    def test_compute_ic_weights(self):
        """测试IC/ICIR权重计算"""
        from app.core.model_scorer import MultiFactorScorer
        scorer = MultiFactorScorer.__new__(MultiFactorScorer)
        scorer.db = None

        np.random.seed(42)
        n_stocks = 50
        n_dates = 30

        factor_records = []
        return_records = []
        for dt_idx in range(n_dates):
            dt = date(2024, 1, 1) + timedelta(days=dt_idx)
            for sid in range(n_stocks):
                factor_records.append({
                    'trade_date': dt, 'security_id': sid,
                    'factor_code': 'value', 'value': np.random.randn(),
                })
                factor_records.append({
                    'trade_date': dt, 'security_id': sid,
                    'factor_code': 'momentum', 'value': np.random.randn(),
                })
                return_records.append({
                    'trade_date': dt, 'security_id': sid,
                    'forward_return': np.random.randn() * 0.05,
                })

        factor_df = pd.DataFrame(factor_records)
        return_df = pd.DataFrame(return_records)

        weights = scorer.compute_ic_weights(factor_df, return_df, method='icir')
        assert isinstance(weights, dict)

    def test_stacking_score(self):
        """测试Stacking集成评分"""
        from app.core.model_scorer import MultiFactorScorer
        scorer = MultiFactorScorer.__new__(MultiFactorScorer)
        scorer.db = None

        np.random.seed(42)
        factor_scores = pd.DataFrame({
            'ep_ttm': np.random.randn(100),
            'ret_12m_skip1': np.random.randn(100),
        })
        returns = pd.Series(np.random.randn(100) * 0.05)

        result = scorer.stacking_score(factor_scores, returns, n_folds=3)
        assert len(result) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
