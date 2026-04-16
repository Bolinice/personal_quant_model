"""
择时信号计算模块
实现均线择时、市场宽度择时、波动率择时、多信号融合
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, with_db
from app.models.timing import TimingSignal, TimingConfig
from app.models.market import IndexDaily, StockDaily
from app.core.logging import logger


class TimingSignalCalculator:
    """择时信号计算器"""

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    def get_index_data(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数数据"""
        data = self.db.query(IndexDaily).filter(
            IndexDaily.ts_code == index_code,
            IndexDaily.trade_date >= start_date,
            IndexDaily.trade_date <= end_date
        ).order_by(IndexDaily.trade_date).all()

        if not data:
            return pd.DataFrame()

        return pd.DataFrame([{
            'trade_date': d.trade_date,
            'close': float(d.close) if d.close else None,
            'high': float(d.high) if d.high else None,
            'low': float(d.low) if d.low else None,
            'volume': float(d.vol) if d.vol else None,
            'pct_chg': float(d.pct_chg) if d.pct_chg else None,
        } for d in data])

    # ==================== 均线择时 ====================

    def ma_signal(self, prices: pd.Series, short_period: int = 5,
                  long_period: int = 20) -> pd.Series:
        """
        均线择时信号
        短期均线上穿长期均线 -> 买入信号(1)
        短期均线下穿长期均线 -> 卖出信号(-1)

        Args:
            prices: 价格序列
            short_period: 短期均线周期
            long_period: 长期均线周期

        Returns:
            信号序列 (1: 多头, -1: 空头, 0: 中性)
        """
        short_ma = prices.rolling(short_period).mean()
        long_ma = prices.rolling(long_period).mean()

        # 计算均线差
        diff = short_ma - long_ma

        # 生成信号
        signal = pd.Series(0, index=prices.index)
        signal[diff > 0] = 1
        signal[diff < 0] = -1

        return signal

    def ma_signal_with_confirmation(self, prices: pd.Series,
                                    short_period: int = 5,
                                    long_period: int = 20,
                                    confirm_days: int = 2) -> pd.Series:
        """
        带确认的均线择时信号
        需要连续N天确认才发出信号

        Args:
            prices: 价格序列
            short_period: 短期均线周期
            long_period: 长期均线周期
            confirm_days: 确认天数

        Returns:
            信号序列
        """
        raw_signal = self.ma_signal(prices, short_period, long_period)

        confirmed_signal = pd.Series(0, index=prices.index)

        for i in range(confirm_days, len(prices)):
            recent_signals = raw_signal.iloc[i - confirm_days + 1:i + 1]

            if (recent_signals == 1).all():
                confirmed_signal.iloc[i] = 1
            elif (recent_signals == -1).all():
                confirmed_signal.iloc[i] = -1
            else:
                confirmed_signal.iloc[i] = confirmed_signal.iloc[i - 1]

        return confirmed_signal

    # ==================== 市场宽度择时 ====================

    def calc_market_breadth(self, trade_date: str,
                           threshold: float = 0.0) -> float:
        """
        计算市场宽度
        市场宽度 = 上涨股票数 / 总股票数

        Args:
            trade_date: 交易日期
            threshold: 涨跌幅阈值

        Returns:
            市场宽度值 [0, 1]
        """
        data = self.db.query(StockDaily).filter(
            StockDaily.trade_date == trade_date
        ).all()

        if not data:
            return 0.5

        up_count = sum(1 for d in data if d.pct_chg and float(d.pct_chg) > threshold)
        total = len(data)

        return up_count / total if total > 0 else 0.5

    def breadth_signal(self, breadth_series: pd.Series,
                       overbought: float = 0.8,
                       oversold: float = 0.2) -> pd.Series:
        """
        市场宽度择时信号
        市场宽度 > overbought -> 超买, 减仓
        市场宽度 < oversold -> 超卖, 加仓

        Args:
            breadth_series: 市场宽度序列
            overbought: 超买阈值
            oversold: 超卖阈值

        Returns:
            信号序列 (1: 多头, -1: 空头, 0: 中性)
        """
        signal = pd.Series(0, index=breadth_series.index)

        signal[breadth_series < oversold] = 1   # 超卖，加仓
        signal[breadth_series > overbought] = -1  # 超买，减仓

        return signal

    # ==================== 波动率择时 ====================

    def calc_volatility(self, returns: pd.Series, period: int = 20) -> pd.Series:
        """
        计算滚动波动率

        Args:
            returns: 收益率序列
            period: 计算周期

        Returns:
            波动率序列
        """
        return returns.rolling(period).std() * np.sqrt(252)

    def volatility_signal(self, vol_series: pd.Series,
                          high_vol_threshold: float = 0.3,
                          low_vol_threshold: float = 0.15) -> pd.Series:
        """
        波动率择时信号
        高波动 -> 降仓
        低波动 -> 加仓

        Args:
            vol_series: 波动率序列
            high_vol_threshold: 高波动阈值
            low_vol_threshold: 低波动阈值

        Returns:
            信号序列
        """
        signal = pd.Series(0, index=vol_series.index)

        signal[vol_series < low_vol_threshold] = 1   # 低波动，加仓
        signal[vol_series > high_vol_threshold] = -1  # 高波动，降仓

        return signal

    # ==================== 回撤触发择时 ====================

    def drawdown_signal(self, prices: pd.Series,
                        drawdown_threshold: float = -0.15) -> pd.Series:
        """
        回撤触发择时
        当回撤超过阈值时，降低仓位

        Args:
            prices: 价格序列
            drawdown_threshold: 回撤阈值（负数）

        Returns:
            信号序列
        """
        # 计算累计最高点
        cummax = prices.cummax()

        # 计算回撤
        drawdown = (prices - cummax) / cummax

        # 生成信号
        signal = pd.Series(1, index=prices.index)  # 默认满仓
        signal[drawdown < drawdown_threshold] = 0.5  # 回撤超阈值，半仓

        return signal

    # ==================== 多信号融合 ====================

    def combine_signals(self, signals: Dict[str, pd.Series],
                       weights: Dict[str, float] = None) -> pd.Series:
        """
        多信号融合

        Args:
            signals: 信号字典 {信号名: 信号序列}
            weights: 权重字典 {信号名: 权重}

        Returns:
            融合后的信号序列
        """
        if weights is None:
            # 等权融合
            weights = {name: 1.0 / len(signals) for name in signals}

        combined = pd.Series(0.0, index=list(signals.values())[0].index)

        for name, signal in signals.items():
            weight = weights.get(name, 0)
            combined += signal * weight

        return combined

    def vote_signals(self, signals: Dict[str, pd.Series],
                    threshold: float = 0.5) -> pd.Series:
        """
        信号投票

        Args:
            signals: 信号字典
            threshold: 投票阈值

        Returns:
            投票结果
        """
        signal_df = pd.DataFrame(signals)

        # 计算看多信号比例
        bullish_ratio = (signal_df > 0).sum(axis=1) / len(signals)

        # 生成信号
        result = pd.Series(0, index=signal_df.index)
        result[bullish_ratio >= threshold] = 1
        result[bullish_ratio <= 1 - threshold] = -1

        return result

    # ==================== 仓位计算 ====================

    def signal_to_position(self, signal: pd.Series,
                          max_position: float = 1.0,
                          min_position: float = 0.0) -> pd.Series:
        """
        将信号转换为仓位

        Args:
            signal: 信号序列 (-1 to 1)
            max_position: 最大仓位
            min_position: 最小仓位

        Returns:
            仓位序列
        """
        # 将信号映射到仓位范围
        position = (signal + 1) / 2  # 映射到 [0, 1]
        position = position * (max_position - min_position) + min_position

        return position

    # ==================== 完整择时计算 ====================

    def calculate_timing_signal(self, model_id: int, trade_date: str,
                               index_code: str = '000300.SH') -> Dict:
        """
        计算完整的择时信号

        Args:
            model_id: 模型ID
            trade_date: 交易日期
            index_code: 指数代码

        Returns:
            择时信号结果
        """
        # 获取历史数据
        end_date = datetime.strptime(trade_date, "%Y-%m-%d")
        start_date = (end_date - timedelta(days=250)).strftime("%Y-%m-%d")

        index_df = self.get_index_data(index_code, start_date, trade_date)

        if index_df.empty:
            return {'signal': 0, 'position': 1.0, 'reason': 'No data'}

        prices = index_df.set_index('trade_date')['close']
        returns = index_df.set_index('trade_date')['pct_chg'] / 100

        # 计算各类信号
        signals = {}

        # 1. 均线信号
        ma_sig = self.ma_signal(prices, 5, 20)
        signals['ma'] = ma_sig.iloc[-1]

        # 2. 波动率信号
        vol = self.calc_volatility(returns, 20)
        vol_sig = self.volatility_signal(vol)
        signals['volatility'] = vol_sig.iloc[-1]

        # 3. 回撤信号
        dd_sig = self.drawdown_signal(prices, -0.15)
        signals['drawdown'] = dd_sig.iloc[-1]

        # 4. 市场宽度信号
        breadth = self.calc_market_breadth(trade_date)
        if breadth < 0.2:
            signals['breadth'] = 1
        elif breadth > 0.8:
            signals['breadth'] = -1
        else:
            signals['breadth'] = 0

        # 融合信号
        combined = self.combine_signals(signals, {
            'ma': 0.3,
            'volatility': 0.2,
            'drawdown': 0.3,
            'breadth': 0.2
        })

        # 转换为仓位
        position = self.signal_to_position(pd.Series([combined.iloc[-1]]), 1.0, 0.0).iloc[0]

        return {
            'signal': combined.iloc[-1],
            'position': position,
            'signals': signals,
            'reason': 'Combined timing signals'
        }

    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()


@with_db
def run_timing_calculation(model_id: int, trade_date: str, db: Session = None) -> Optional[TimingSignal]:
    """
    运行择时计算并保存结果

    Args:
        model_id: 模型ID
        trade_date: 交易日期
        db: 数据库会话

    Returns:
        择时信号
    """
    calculator = TimingSignalCalculator(db)

    try:
        result = calculator.calculate_timing_signal(model_id, trade_date)

        # 保存信号
        signal = TimingSignal(
            model_id=model_id,
            trade_date=trade_date,
            signal_type='long' if result['position'] > 0.5 else 'short' if result['position'] < 0.5 else 'neutral',
            exposure=result['position']
        )

        db.add(signal)
        db.commit()

        logger.info(f"Timing signal for model {model_id} on {trade_date}: position={result['position']:.2f}")

        return signal

    except Exception as e:
        logger.error(f"Error calculating timing signal: {e}")
        db.rollback()
        return None
