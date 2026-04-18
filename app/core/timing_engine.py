"""
择时引擎模块
实现ADD 9节: 均线择时、市场宽度择时、波动率择时、回撤控制择时、多信号融合
机构级增强: HMM市场状态识别、DMA动态模型平均、北向资金择时、政策日历择时、贝叶斯共轭更新
"""
from typing import List, Optional, Dict, Tuple
from datetime import date, datetime, timedelta
from enum import Enum
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.core.logging import logger


class TimingSignalType(str, Enum):
    LONG = "long"        # 看多
    SHORT = "short"      # 看空
    NEUTRAL = "neutral"  # 中性


class FusionMethod(str, Enum):
    EQUAL = "equal"              # 等权投票
    MOMENTUM = "momentum"        # 动量加权
    BAYESIAN = "bayesian"        # 贝叶斯融合


class MarketRegime(str, Enum):
    BULL = "bull"       # 牛市
    BEAR = "bear"       # 熊市
    SIDEWAYS = "sideways"  # 震荡


class TimingEngine:
    """择时引擎 - 符合ADD 9节"""

    def __init__(self, db: Session = None):
        self.db = db

    # ==================== 1. 均线择时 (ADD 9.1节) ====================

    def ma_cross_signal(self, close: pd.Series,
                        short_window: int = 20,
                        long_window: int = 60) -> pd.Series:
        """
        均线交叉择时 (ADD 9.1节)
        短均线上穿长均线 → 看多
        短均线下穿长均线 → 看空
        """
        short_ma = close.rolling(short_window).mean()
        long_ma = close.rolling(long_window).mean()

        signal = pd.Series(TimingSignalType.NEUTRAL, index=close.index)

        # 金叉
        golden_cross = (short_ma > long_ma) & (short_ma.shift(1) <= long_ma.shift(1))
        signal[golden_cross] = TimingSignalType.LONG

        # 死叉
        death_cross = (short_ma < long_ma) & (short_ma.shift(1) >= long_ma.shift(1))
        signal[death_cross] = TimingSignalType.SHORT

        # 持续状态
        above = short_ma > long_ma
        below = short_ma < long_ma
        signal[above & ~golden_cross] = TimingSignalType.LONG
        signal[below & ~death_cross] = TimingSignalType.SHORT

        return signal

    def ma_trend_strength(self, close: pd.Series,
                          windows: List[int] = [5, 10, 20, 60, 120]) -> pd.Series:
        """
        多均线趋势强度
        所有均线上方 → 强多头(+1)
        所有均线下方 → 强空头(-1)
        """
        mas = [close.rolling(w).mean() for w in windows]
        above_count = sum(ma < close for ma in mas)
        strength = (above_count / len(windows)) * 2 - 1  # [-1, 1]
        return strength

    # ==================== 2. 市场宽度择时 (ADD 9.2节) ====================

    def breadth_signal(self, advance_count: pd.Series,
                       decline_count: pd.Series,
                       window: int = 20) -> pd.Series:
        """
        市场宽度择时 (ADD 9.2节)
        上涨家数占比 > 阈值 → 看多
        上涨家数占比 < 阈值 → 看空
        """
        total = advance_count + decline_count
        breadth = advance_count / total.replace(0, np.nan)

        # 滚动均值
        breadth_ma = breadth.rolling(window).mean()

        signal = pd.Series(TimingSignalType.NEUTRAL, index=breadth.index)
        signal[breadth_ma > 0.6] = TimingSignalType.LONG
        signal[breadth_ma < 0.4] = TimingSignalType.SHORT

        return signal

    def advance_decline_line(self, advance_count: pd.Series,
                             decline_count: pd.Series) -> pd.Series:
        """腾落指数"""
        net_advance = advance_count - decline_count
        ad_line = net_advance.cumsum()
        return ad_line

    # ==================== 3. 波动率择时 (ADD 9.3节) ====================

    def volatility_signal(self, close: pd.Series,
                          window: int = 20,
                          low_vol_threshold: float = 0.12,
                          high_vol_threshold: float = 0.25) -> pd.Series:
        """
        波动率择时 (ADD 9.3节)
        低波动 → 看多（适合持有）
        高波动 → 看空（适合减仓）
        """
        returns = close.pct_change()
        realized_vol = returns.rolling(window).std() * np.sqrt(252)

        signal = pd.Series(TimingSignalType.NEUTRAL, index=close.index)
        signal[realized_vol < low_vol_threshold] = TimingSignalType.LONG
        signal[realized_vol > high_vol_threshold] = TimingSignalType.SHORT

        return signal

    def vix_signal(self, vix: pd.Series,
                   low_threshold: float = 15,
                   high_threshold: float = 25) -> pd.Series:
        """
        VIX择时（A股可用中国波指iVIX替代）
        """
        signal = pd.Series(TimingSignalType.NEUTRAL, index=vix.index)
        signal[vix < low_threshold] = TimingSignalType.LONG
        signal[vix > high_threshold] = TimingSignalType.SHORT
        return signal

    # ==================== 4. 回撤控制择时 (ADD 9.4节) ====================

    def drawdown_control_signal(self, close: pd.Series,
                                max_drawdown: float = 0.10,
                                recovery_threshold: float = 0.03) -> pd.Series:
        """
        回撤控制择时 (ADD 9.4节)
        回撤超过阈值 → 减仓
        从回撤恢复 → 加仓
        """
        cummax = close.cummax()
        drawdown = (close - cummax) / cummax

        signal = pd.Series(TimingSignalType.LONG, index=close.index)
        signal[drawdown < -max_drawdown] = TimingSignalType.SHORT

        # 恢复信号：回撤后反弹超过阈值
        in_drawdown = drawdown < -max_drawdown
        recovery = in_drawdown.shift(1) & (drawdown > -max_drawdown + recovery_threshold)
        signal[recovery] = TimingSignalType.NEUTRAL

        return signal

    def trailing_stop_signal(self, close: pd.Series,
                             stop_pct: float = 0.05,
                             window: int = 20) -> pd.Series:
        """
        移动止损择时
        """
        high_watermark = close.rolling(window).max()
        trailing_stop = high_watermark * (1 - stop_pct)

        signal = pd.Series(TimingSignalType.LONG, index=close.index)
        signal[close < trailing_stop] = TimingSignalType.SHORT

        return signal

    # ==================== 5. 多信号融合 (ADD 9.5节) ====================

    def fuse_signals(self, signals: Dict[str, pd.Series],
                     method: FusionMethod = FusionMethod.EQUAL,
                     weights: Dict[str, float] = None) -> pd.Series:
        """
        多信号融合 (ADD 9.5节)

        Args:
            signals: 各择时信号 {signal_name: signal_series}
            method: 融合方法
            weights: 信号权重
        """
        if not signals:
            return pd.Series()

        # 将信号转换为数值: long=1, neutral=0, short=-1
        signal_values = {}
        for name, signal in signals.items():
            numeric = signal.map({
                TimingSignalType.LONG: 1,
                TimingSignalType.NEUTRAL: 0,
                TimingSignalType.SHORT: -1,
            }).fillna(0)
            signal_values[name] = numeric

        signal_df = pd.DataFrame(signal_values)

        if method == FusionMethod.EQUAL:
            # 等权投票 (ADD 9.5.1节)
            combined = signal_df.mean(axis=1)
        elif method == FusionMethod.MOMENTUM:
            # 动量加权 (ADD 9.5.2节)
            if weights:
                for col in signal_df.columns:
                    signal_df[col] = signal_df[col] * weights.get(col, 1.0)
                combined = signal_df.sum(axis=1) / sum(weights.values())
            else:
                combined = signal_df.mean(axis=1)
        elif method == FusionMethod.BAYESIAN:
            # 贝叶斯融合 (ADD 9.5.3节) - 简化实现
            combined = signal_df.mean(axis=1)
        else:
            combined = signal_df.mean(axis=1)

        # 转换回信号类型
        result = pd.Series(TimingSignalType.NEUTRAL, index=combined.index)
        result[combined > 0.2] = TimingSignalType.LONG
        result[combined < -0.2] = TimingSignalType.SHORT

        return result

    def calc_target_exposure(self, signal: pd.Series,
                             base_exposure: float = 1.0,
                             max_exposure: float = 1.0,
                             min_exposure: float = 0.0) -> pd.Series:
        """
        根据择时信号计算目标仓位

        Args:
            signal: 择时信号
            base_exposure: 基础仓位
            max_exposure: 最大仓位
            min_exposure: 最小仓位
        """
        exposure = pd.Series(base_exposure, index=signal.index)

        long_mask = signal == TimingSignalType.LONG
        short_mask = signal == TimingSignalType.SHORT
        neutral_mask = signal == TimingSignalType.NEUTRAL

        exposure[long_mask] = max_exposure
        exposure[short_mask] = min_exposure
        exposure[neutral_mask] = base_exposure * 0.5

        return exposure

    # ==================== 6. 市场状态识别 ====================

    def identify_market_regime(self, close: pd.Series,
                               window: int = 60) -> pd.Series:
        """
        市场状态识别
        牛市/熊市/震荡
        """
        returns = close.pct_change()
        ma = close.rolling(window).mean()
        vol = returns.rolling(window).std() * np.sqrt(252)

        regime = pd.Series(MarketRegime.SIDEWAYS, index=close.index)

        # 牛市：价格在均线上方，波动率较低
        bull = (close > ma) & (vol < 0.2)
        regime[bull] = MarketRegime.BULL

        # 熊市：价格在均线下方，波动率较高
        bear = (close < ma) & (vol > 0.25)
        regime[bear] = MarketRegime.BEAR

        return regime

    # ==================== 机构级扩展择时方法 ====================

    def hmm_regime_detection(self, features: pd.DataFrame,
                              n_regimes: int = 3,
                              window: int = 252) -> pd.Series:
        """
        HMM市场状态识别 (Hidden Markov Model)
        使用多特征(收益、波动、宽度等)识别市场状态
        比简单阈值法更准确，能捕捉状态转换概率

        Args:
            features: 市场特征DataFrame, 需包含 returns, volatility, breadth等列
            n_regimes: 状态数(2=牛/熊, 3=牛/熊/震荡)
            window: 训练窗口
        """
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            logger.warning("hmmlearn not available, falling back to simple regime detection")
            if 'close' in features.columns:
                return self.identify_market_regime(features['close'])
            return pd.Series(MarketRegime.SIDEWAYS, index=features.index)

        # 准备特征
        feature_cols = [c for c in features.columns if c != 'close']
        if not feature_cols:
            feature_cols = features.columns.tolist()

        X = features[feature_cols].values
        valid_mask = ~np.isnan(X).any(axis=1)
        X_valid = X[valid_mask]

        if len(X_valid) < 100:
            return pd.Series(MarketRegime.SIDEWAYS, index=features.index)

        # 训练HMM
        model = GaussianHMM(n_components=n_regimes, covariance_type='full',
                            n_iter=100, random_state=42)
        try:
            model.fit(X_valid)
            states = model.predict(X_valid)
        except ValueError:
            return pd.Series(MarketRegime.SIDEWAYS, index=features.index)

        # 将状态映射到市场状态
        # 根据每个状态的均值收益确定牛/熊/震荡
        state_means = model.means_[:, 0]  # 第一列通常是收益率
        sorted_states = np.argsort(state_means)  # 从低到高

        regime_map = {}
        if n_regimes == 2:
            regime_map[sorted_states[0]] = MarketRegime.BEAR
            regime_map[sorted_states[1]] = MarketRegime.BULL
        else:  # n_regimes == 3
            regime_map[sorted_states[0]] = MarketRegime.BEAR
            regime_map[sorted_states[1]] = MarketRegime.SIDEWAYS
            regime_map[sorted_states[2]] = MarketRegime.BULL

        result = pd.Series(MarketRegime.SIDEWAYS, index=features.index)
        valid_indices = features.index[valid_mask]
        for i, state in enumerate(states):
            result.iloc[valid_indices.get_loc(valid_indices[i]) if i < len(valid_indices) else i] = regime_map.get(state, MarketRegime.SIDEWAYS)

        return result

    def northbound_timing_signal(self, north_flow: pd.Series,
                                  window: int = 5,
                                  threshold: float = 0.0) -> pd.Series:
        """
        北向资金择时信号
        北向资金是A股最有效的择时信号之一

        Args:
            north_flow: 北向资金净流入序列
            window: 回看天数
            threshold: 信号阈值
        """
        # 累计N日净流入
        cum_flow = north_flow.rolling(window).sum()
        # 标准化
        flow_zscore = (cum_flow - cum_flow.rolling(60, min_periods=20).mean()) / cum_flow.rolling(60, min_periods=20).std().replace(0, np.nan)

        signal = pd.Series(TimingSignalType.NEUTRAL, index=north_flow.index)
        signal[flow_zscore > threshold + 0.5] = TimingSignalType.LONG
        signal[flow_zscore < -(threshold + 0.5)] = TimingSignalType.SHORT

        return signal

    def policy_calendar_signal(self, trade_dates: pd.Series,
                                policy_events: List[Dict] = None) -> pd.Series:
        """
        政策日历择时
        A股政策事件(两会、政治局会议等)对市场有可预测影响

        Args:
            trade_dates: 交易日期序列
            policy_events: 政策事件列表 [{date, event_name, expected_impact: 1/-1/0, pre_days, post_days}]
        """
        signal = pd.Series(TimingSignalType.NEUTRAL, index=trade_dates.index)

        if policy_events is None:
            # 默认A股重要政策日历
            policy_events = self._default_policy_calendar()

        for event in policy_events:
            event_date = pd.Timestamp(event.get('date', ''))
            pre_days = event.get('pre_days', 5)
            post_days = event.get('post_days', 10)
            impact = event.get('expected_impact', 0)

            # 事件前: 期待效应
            pre_start = event_date - timedelta(days=pre_days)
            pre_mask = (trade_dates >= pre_start) & (trade_dates < event_date)
            if impact > 0:
                signal[pre_mask] = TimingSignalType.LONG
            elif impact < 0:
                signal[pre_mask] = TimingSignalType.NEUTRAL  # 事件前保持谨慎

            # 事件后: 根据政策方向
            post_end = event_date + timedelta(days=post_days)
            post_mask = (trade_dates >= event_date) & (trade_dates <= post_end)
            if impact > 0:
                signal[post_mask] = TimingSignalType.LONG
            elif impact < 0:
                signal[post_mask] = TimingSignalType.SHORT

        return signal

    def _default_policy_calendar(self) -> List[Dict]:
        """A股默认政策日历(年度重要事件)"""
        current_year = datetime.now().year
        return [
            # 两会(3月初): 通常利好
            {'date': f'{current_year}-03-03', 'event_name': '两会开幕', 'expected_impact': 1, 'pre_days': 10, 'post_days': 15},
            # 政治局会议(4月底/7月底/10月底/12月初): 关注经济政策
            {'date': f'{current_year}-04-28', 'event_name': '政治局会议(4月)', 'expected_impact': 1, 'pre_days': 3, 'post_days': 5},
            {'date': f'{current_year}-07-28', 'event_name': '政治局会议(7月)', 'expected_impact': 1, 'pre_days': 3, 'post_days': 5},
            {'date': f'{current_year}-12-05', 'event_name': '中央经济工作会议', 'expected_impact': 1, 'pre_days': 5, 'post_days': 10},
        ]

    def seasonal_signal(self, close: pd.Series,
                         dates: pd.Series = None) -> pd.Series:
        """
        A股季节性择时
        春季躁动、Sell in May、年末效应等

        Args:
            close: 收盘价序列
            dates: 日期序列(可选，默认使用index)
        """
        if dates is None:
            dates = pd.Series(close.index)

        signal = pd.Series(TimingSignalType.NEUTRAL, index=close.index)

        for i, d in enumerate(dates):
            if isinstance(d, (datetime, date, pd.Timestamp)):
                month = d.month
            else:
                continue

            # 春季躁动(1-2月): 偏多
            if month in [1, 2]:
                signal.iloc[i] = TimingSignalType.LONG
            # Sell in May效应(5-9月): 偏空
            elif month in [5, 6, 7, 8, 9]:
                signal.iloc[i] = TimingSignalType.SHORT
            # 年末效应(12月): 基金排名效应，偏多
            elif month == 12:
                signal.iloc[i] = TimingSignalType.LONG

        return signal

    def fuse_signals_dma(self, signals: Dict[str, pd.Series],
                          returns: pd.Series = None,
                          forgetting_factor: float = 0.95,
                          min_evidence: int = 30) -> pd.Series:
        """
        动态模型平均 (Dynamic Model Averaging, DMA)
        根据各信号近期表现动态调整权重，比等权/固定权重更适应市场变化

        Args:
            signals: 各择时信号 {signal_name: signal_series}
            returns: 市场收益率(用于评估信号表现)
            forgetting_factor: 遗忘因子(0-1, 越小越快适应)
            min_evidence: 最小证据数(少于此数的信号不参与)
        """
        if not signals:
            return pd.Series()

        # 将信号转换为数值
        signal_values = {}
        for name, signal in signals.items():
            numeric = signal.map({
                TimingSignalType.LONG: 1,
                TimingSignalType.NEUTRAL: 0,
                TimingSignalType.SHORT: -1,
            }).fillna(0)
            signal_values[name] = numeric

        signal_df = pd.DataFrame(signal_values)

        if returns is None:
            # 无收益率数据，退化为等权
            combined = signal_df.mean(axis=1)
        else:
            # DMA: 根据各信号预测误差更新权重
            n_signals = len(signals)
            log_weights = np.zeros(n_signals)  # 对数权重
            signal_names = list(signals.keys())
            combined = pd.Series(0.0, index=signal_df.index)

            for t in range(len(signal_df)):
                # 当前权重
                weights = np.exp(log_weights - np.max(log_weights))
                weights = weights / weights.sum()

                # 加权组合信号
                combined.iloc[t] = sum(
                    weights[i] * signal_df.iloc[t, i] for i in range(n_signals)
                )

                # 更新权重(基于预测误差)
                if t > 0 and not np.isnan(returns.iloc[t]):
                    actual = 1 if returns.iloc[t] > 0 else -1
                    for i in range(n_signals):
                        prediction = signal_df.iloc[t-1, i]
                        error = (actual - prediction) ** 2
                        log_weights[i] = forgetting_factor * log_weights[i] - 0.5 * error

        # 转换回信号类型
        result = pd.Series(TimingSignalType.NEUTRAL, index=combined.index)
        result[combined > 0.2] = TimingSignalType.LONG
        result[combined < -0.2] = TimingSignalType.SHORT

        return result

    def fuse_signals_bayesian(self, signals: Dict[str, pd.Series],
                               returns: pd.Series = None,
                               prior_alpha: float = 10.0,
                               prior_beta: float = 10.0,
                               lookback: int = 60) -> pd.Series:
        """
        贝叶斯共轭更新信号融合
        对每个信号维护Beta分布的命中率，用后验均值作为权重
        自然降权近期表现差的信号

        Args:
            signals: 各择时信号
            returns: 市场收益率
            prior_alpha: Beta先验alpha(命中次数)
            prior_beta: Beta先验beta(未命中次数)
            lookback: 回看期数
        """
        if not signals:
            return pd.Series()

        signal_values = {}
        for name, signal in signals.items():
            numeric = signal.map({
                TimingSignalType.LONG: 1,
                TimingSignalType.NEUTRAL: 0,
                TimingSignalType.SHORT: -1,
            }).fillna(0)
            signal_values[name] = numeric

        signal_df = pd.DataFrame(signal_values)

        if returns is None:
            return self.fuse_signals(signals, FusionMethod.EQUAL)

        # 计算每个信号的贝叶斯权重
        bayesian_weights = {}
        for col in signal_df.columns:
            # 计算命中率: 信号方向与实际收益方向一致的比例
            signal_dir = np.sign(signal_df[col])
            actual_dir = np.sign(returns)
            valid = (signal_dir != 0) & actual_dir.notna()

            if valid.sum() < 10:
                bayesian_weights[col] = prior_alpha / (prior_alpha + prior_beta)
                continue

            hits = ((signal_dir[valid] == actual_dir[valid])).sum()
            misses = valid.sum() - hits

            # 后验均值 = (alpha + hits) / (alpha + beta + hits + misses)
            posterior_mean = (prior_alpha + hits) / (prior_alpha + prior_beta + hits + misses)
            bayesian_weights[col] = posterior_mean

        # 加权组合
        weight_sum = sum(bayesian_weights.values())
        if weight_sum == 0:
            combined = signal_df.mean(axis=1)
        else:
            combined = pd.Series(0.0, index=signal_df.index)
            for col in signal_df.columns:
                combined += signal_df[col] * bayesian_weights.get(col, 0) / weight_sum

        # 转换回信号类型
        result = pd.Series(TimingSignalType.NEUTRAL, index=combined.index)
        result[combined > 0.2] = TimingSignalType.LONG
        result[combined < -0.2] = TimingSignalType.SHORT

        return result

    # ==================== 7. 择时信号回测验证 ====================

    def backtest_timing_signal(self, close: pd.Series,
                               signal: pd.Series,
                               initial_capital: float = 1000000.0) -> Dict:
        """
        择时信号回测验证 (ADD 9.6节)
        """
        returns = close.pct_change()

        # 根据信号调整收益
        adjusted_returns = returns.copy()
        short_mask = signal == TimingSignalType.SHORT
        adjusted_returns[short_mask] = 0  # 空仓时收益为0

        # 计算净值
        nav = (1 + adjusted_returns).cumprod()
        buy_hold_nav = (1 + returns).cumprod()

        # 计算指标
        total_return = nav.iloc[-1] - 1
        max_dd = ((nav - nav.cummax()) / nav.cummax()).min()

        return {
            'total_return': round(total_return, 4),
            'max_drawdown': round(max_dd, 4),
            'buy_hold_return': round(buy_hold_nav.iloc[-1] - 1, 4),
            'signal_distribution': {
                'long': (signal == TimingSignalType.LONG).sum(),
                'short': (signal == TimingSignalType.SHORT).sum(),
                'neutral': (signal == TimingSignalType.NEUTRAL).sum(),
            },
        }

    def close(self):
        if self.db:
            self.db.close()