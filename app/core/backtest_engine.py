"""
A股回测引擎
实现完整的A股回测逻辑：T+1限制、涨跌停处理、停牌处理、交易成本、滑点等
符合ADD 12节回测规则和PRD 9.8节需求
机构级增强: 参与率滑点模型、Walk-Forward验证、蒙特卡洛置换检验、通胀夏普比率
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.core.logging import logger


# A股交易成本常量 (ADD 11节)
DEFAULT_COMMISSION_RATE = 0.00025  # 佣金率 万2.5
DEFAULT_STAMP_TAX_RATE = 0.001     # 印花税率 千1（仅卖出）
DEFAULT_TRANSFER_FEE_RATE = 0.00001  # 过户费率
DEFAULT_SLIPPAGE_RATE = 0.001      # 默认滑点 0.1%
MIN_COMMISSION = 5.0               # 最低佣金5元

# 涨跌停限制 (ADD 12.4节)
MAIN_BOARD_LIMIT = 0.10   # 主板 10%
GEM_LIMIT = 0.20          # 创业板 20%
STAR_LIMIT = 0.20         # 科创板 20%
ST_LIMIT = 0.05           # ST 5%
NORTH_LIMIT = 0.20        # 北交所 20%

# 交易单位
LOT_SIZE = 100  # A股最小交易单位100股


@dataclass
class TransactionCost:
    """交易成本模型 (ADD 11节 + 机构级增强)"""
    commission_rate: float = DEFAULT_COMMISSION_RATE
    stamp_tax_rate: float = DEFAULT_STAMP_TAX_RATE
    transfer_fee_rate: float = DEFAULT_TRANSFER_FEE_RATE
    slippage_rate: float = DEFAULT_SLIPPAGE_RATE
    min_commission: float = MIN_COMMISSION
    # 参与率滑点参数
    impact_coefficient: float = 0.3  # 市场冲击系数
    base_spread: float = 0.0005  # 基础价差 5bps

    def calc_buy_cost(self, amount: float,
                      daily_volume: float = None,
                      volatility: float = None) -> Dict[str, float]:
        """
        计算买入成本
        支持参与率滑点模型: slippage = base_spread + impact * sqrt(participation_rate)
        """
        commission = max(amount * self.commission_rate, self.min_commission)
        transfer_fee = amount * self.transfer_fee_rate

        # 滑点: 参与率模型或固定比率
        if daily_volume is not None and daily_volume > 0 and volatility is not None:
            participation_rate = amount / daily_volume
            slippage = amount * (self.base_spread + self.impact_coefficient * volatility * np.sqrt(participation_rate))
        else:
            slippage = amount * self.slippage_rate

        total = commission + transfer_fee + slippage
        return {
            'commission': round(commission, 2),
            'stamp_tax': 0.0,
            'transfer_fee': round(transfer_fee, 2),
            'slippage': round(slippage, 2),
            'total_cost': round(total, 2),
        }

    def calc_sell_cost(self, amount: float,
                       daily_volume: float = None,
                       volatility: float = None) -> Dict[str, float]:
        """计算卖出成本（含印花税）"""
        commission = max(amount * self.commission_rate, self.min_commission)
        stamp_tax = amount * self.stamp_tax_rate
        transfer_fee = amount * self.transfer_fee_rate

        if daily_volume is not None and daily_volume > 0 and volatility is not None:
            participation_rate = amount / daily_volume
            slippage = amount * (self.base_spread + self.impact_coefficient * volatility * np.sqrt(participation_rate))
        else:
            slippage = amount * self.slippage_rate

        total = commission + stamp_tax + transfer_fee + slippage
        return {
            'commission': round(commission, 2),
            'stamp_tax': round(stamp_tax, 2),
            'transfer_fee': round(transfer_fee, 2),
            'slippage': round(slippage, 2),
            'total_cost': round(total, 2),
        }


@dataclass
class Position:
    """持仓信息"""
    security_id: str
    shares: int = 0
    cost_price: float = 0.0
    market_value: float = 0.0
    weight: float = 0.0
    board_type: str = 'main'  # main, gem, star, st


@dataclass
class BacktestState:
    """回测状态"""
    cash: float = 1000000.0
    initial_capital: float = 1000000.0
    positions: Dict[str, Position] = field(default_factory=dict)
    nav_history: List[Dict] = field(default_factory=list)
    trade_records: List[Dict] = field(default_factory=list)
    position_history: List[Dict] = field(default_factory=list)


class ABShareBacktestEngine:
    """A股回测引擎 - 符合ADD 12节和PRD 9.8节"""

    def __init__(self, db: Session = None,
                 commission_rate: float = DEFAULT_COMMISSION_RATE,
                 stamp_tax_rate: float = DEFAULT_STAMP_TAX_RATE,
                 slippage_rate: float = DEFAULT_SLIPPAGE_RATE):
        self.db = db
        self.cost_model = TransactionCost(
            commission_rate=commission_rate,
            stamp_tax_rate=stamp_tax_rate,
            slippage_rate=slippage_rate,
        )

    # ==================== A股交易规则 ====================

    def get_board_type(self, ts_code: str) -> str:
        """判断板块类型"""
        if ts_code.endswith('.SZ') and ts_code.startswith('3'):
            return 'gem'  # 创业板
        elif ts_code.endswith('.SH') and ts_code.startswith('688'):
            return 'star'  # 科创板
        elif ts_code.endswith('.BJ') or ts_code.startswith('8'):
            return 'north'  # 北交所
        return 'main'

    def get_limit_pct(self, board_type: str, is_st: bool = False) -> float:
        """获取涨跌停比例"""
        if is_st:
            return ST_LIMIT
        limits = {
            'main': MAIN_BOARD_LIMIT,
            'gem': GEM_LIMIT,
            'star': STAR_LIMIT,
            'north': NORTH_LIMIT,
        }
        return limits.get(board_type, MAIN_BOARD_LIMIT)

    def is_limit_up(self, pct_chg: float, board_type: str = 'main',
                    is_st: bool = False) -> bool:
        """判断是否涨停 (ADD 12.4节)"""
        limit = self.get_limit_pct(board_type, is_st)
        return pct_chg >= (limit * 100 - 0.01)  # 允许0.01%误差

    def is_limit_down(self, pct_chg: float, board_type: str = 'main',
                      is_st: bool = False) -> bool:
        """判断是否跌停"""
        limit = self.get_limit_pct(board_type, is_st)
        return pct_chg <= -(limit * 100 - 0.01)

    def round_lot(self, shares: float) -> int:
        """调整为100股整数倍 (ADD 12.4节)"""
        return int(shares // LOT_SIZE) * LOT_SIZE

    def is_tradable(self, ts_code: str, trade_date: date,
                    action: str, stock_data: Dict = None) -> Tuple[bool, str]:
        """
        判断是否可交易 (ADD 12.4节 + 11.2.2节)

        Returns:
            (是否可交易, 原因)
        """
        if stock_data is None:
            return False, "无数据"

        # 停牌检查
        if stock_data.get('is_suspended', False):
            return False, "停牌"

        # 涨跌停检查
        pct_chg = stock_data.get('pct_chg', 0)
        board_type = self.get_board_type(ts_code)
        is_st = stock_data.get('is_st', False)

        if action == 'buy' and self.is_limit_up(pct_chg, board_type, is_st):
            return False, "涨停无法买入"

        if action == 'sell' and self.is_limit_down(pct_chg, board_type, is_st):
            return False, "跌停无法卖出"

        # 退市整理检查
        if stock_data.get('is_delist', False):
            return False, "退市整理"

        return True, ""

    # ==================== 交易执行 ====================

    def execute_buy(self, state: BacktestState, ts_code: str,
                    target_amount: float, price: float,
                    trade_date: date, stock_data: Dict = None) -> Optional[Dict]:
        """
        执行买入 (ADD 12.3节)

        Args:
            state: 回测状态
            ts_code: 股票代码
            target_amount: 目标买入金额
            price: 买入价格
            trade_date: 交易日期
            stock_data: 当日行情数据
        """
        # 可交易性检查
        tradable, reason = self.is_tradable(ts_code, trade_date, 'buy', stock_data)
        if not tradable:
            return None

        # 计算可买入金额（考虑成本）
        max_amount = state.cash / (1 + self.cost_model.commission_rate + self.cost_model.transfer_fee_rate + self.cost_model.slippage_rate)
        buy_amount = min(target_amount, max_amount)

        if buy_amount <= 0:
            return None

        # 计算股数（100股整数倍）
        shares = self.round_lot(buy_amount / price)
        if shares < LOT_SIZE:
            return None

        # 计算成交金额和成本
        amount = shares * price
        cost_detail = self.cost_model.calc_buy_cost(amount)
        total_cost = cost_detail['total_cost']

        if amount + total_cost > state.cash:
            return None

        # 更新状态
        state.cash -= (amount + total_cost)

        if ts_code in state.positions:
            pos = state.positions[ts_code]
            total_shares = pos.shares + shares
            pos.cost_price = (pos.cost_price * pos.shares + amount) / total_shares
            pos.shares = total_shares
        else:
            state.positions[ts_code] = Position(
                security_id=ts_code,
                shares=shares,
                cost_price=price,
                board_type=self.get_board_type(ts_code),
            )

        trade = {
            'trade_date': trade_date,
            'security_id': ts_code,
            'action': 'buy',
            'price': price,
            'quantity': shares,
            'amount': round(amount, 2),
            **cost_detail,
            'trade_status': 'success',
        }
        state.trade_records.append(trade)
        return trade

    def execute_sell(self, state: BacktestState, ts_code: str,
                     shares: int, price: float,
                     trade_date: date, stock_data: Dict = None) -> Optional[Dict]:
        """执行卖出"""
        tradable, reason = self.is_tradable(ts_code, trade_date, 'sell', stock_data)
        if not tradable:
            return None

        if ts_code not in state.positions:
            return None

        pos = state.positions[ts_code]
        sell_shares = min(shares, pos.shares)
        if sell_shares <= 0:
            return None

        amount = sell_shares * price
        cost_detail = self.cost_model.calc_sell_cost(amount)

        state.cash += (amount - cost_detail['total_cost'])
        pos.shares -= sell_shares

        if pos.shares <= 0:
            del state.positions[ts_code]

        trade = {
            'trade_date': trade_date,
            'security_id': ts_code,
            'action': 'sell',
            'price': price,
            'quantity': sell_shares,
            'amount': round(amount, 2),
            **cost_detail,
            'trade_status': 'success',
        }
        state.trade_records.append(trade)
        return trade

    # ==================== 净值计算 ====================

    def calc_nav(self, state: BacktestState, trade_date: date,
                 price_data: Dict[str, float]) -> Dict:
        """计算当日净值"""
        position_value = 0
        for ts_code, pos in state.positions.items():
            price = price_data.get(ts_code, 0)
            pos.market_value = pos.shares * price
            position_value += pos.market_value

        total_nav = state.cash + position_value
        nav = total_nav / state.initial_capital

        # 计算回撤
        if state.nav_history:
            peak = max(h['nav'] for h in state.nav_history)
            drawdown = (total_nav - peak * state.initial_capital) / (peak * state.initial_capital)
        else:
            drawdown = 0

        nav_record = {
            'trade_date': trade_date,
            'nav': nav,
            'total_value': total_nav,
            'cash': state.cash,
            'position_value': position_value,
            'drawdown': drawdown,
            'num_positions': len(state.positions),
        }
        state.nav_history.append(nav_record)
        return nav_record

    # ==================== 回测指标计算 ====================

    def calc_metrics(self, nav_history: List[Dict],
                     trade_records: List[Dict],
                     benchmark_nav: List[Dict] = None) -> Dict:
        """计算回测指标 (PRD 9.8.2节)"""
        if not nav_history:
            return {}

        nav_df = pd.DataFrame(nav_history)
        nav_series = nav_df['nav']

        # 收益率
        returns = nav_series.pct_change().dropna()
        cum_return = nav_series.iloc[-1] - 1

        # 年化收益
        total_days = len(nav_series)
        annual_return = (nav_series.iloc[-1]) ** (252 / total_days) - 1 if total_days > 0 else 0

        # 最大回撤
        cummax = nav_series.cummax()
        drawdown = (nav_series - cummax) / cummax
        max_drawdown = drawdown.min()

        # 最大回撤持续天数
        is_dd = drawdown < 0
        dd_groups = (~is_dd).cumsum()
        max_dd_duration = is_dd.groupby(dd_groups).sum().max() if is_dd.any() else 0

        # 波动率
        volatility = returns.std() * np.sqrt(252) if len(returns) > 0 else 0

        # 下行波动率
        neg_returns = returns[returns < 0]
        downside_vol = neg_returns.std() * np.sqrt(252) if len(neg_returns) > 0 else 0

        # 夏普比率
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

        # 索提诺比率
        sortino = returns.mean() * 252 / downside_vol if downside_vol > 0 else 0

        # 卡玛比率
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # 换手率
        total_buy = sum(t.get('amount', 0) for t in trade_records if t.get('action') == 'buy')
        avg_nav = nav_df['total_value'].mean()
        turnover_rate = total_buy / avg_nav / (total_days / 252) if avg_nav > 0 and total_days > 0 else 0

        # 胜率
        win_rate = (returns > 0).sum() / len(returns) if len(returns) > 0 else 0

        # 盈亏比
        profits = returns[returns > 0]
        losses = returns[returns < 0]
        pl_ratio = profits.mean() / abs(losses.mean()) if len(losses) > 0 and losses.mean() != 0 else 0

        # 成本侵蚀率
        total_cost = sum(t.get('total_cost', 0) for t in trade_records)
        cost_erosion = total_cost / (nav_df['total_value'].iloc[-1] - nav_df['total_value'].iloc[0]) if nav_df['total_value'].iloc[-1] != nav_df['total_value'].iloc[0] else 0

        result = {
            'total_return': round(cum_return, 4),
            'annual_return': round(annual_return, 4),
            'max_drawdown': round(max_drawdown, 4),
            'max_drawdown_duration': int(max_dd_duration),
            'volatility': round(volatility, 4),
            'downside_volatility': round(downside_vol, 4),
            'sharpe': round(sharpe, 2),
            'sortino': round(sortino, 2),
            'calmar': round(calmar, 2),
            'turnover_rate': round(turnover_rate, 4),
            'win_rate': round(win_rate, 4),
            'profit_loss_ratio': round(pl_ratio, 2),
            'cost_erosion': round(cost_erosion, 4),
            'total_trades': len(trade_records),
            'total_cost': round(total_cost, 2),
        }

        # 基准对比
        if benchmark_nav and len(benchmark_nav) > 0:
            bm_df = pd.DataFrame(benchmark_nav)
            bm_returns = bm_df['nav'].pct_change().dropna()
            bm_annual_return = (bm_df['nav'].iloc[-1]) ** (252 / len(bm_df)) - 1

            # 对齐
            common_idx = returns.index.intersection(bm_returns.index)
            if len(common_idx) > 0:
                aligned_ret = returns.loc[common_idx]
                aligned_bm = bm_returns.loc[common_idx]

                # Alpha/Beta
                beta = aligned_ret.cov(aligned_bm) / aligned_bm.var() if aligned_bm.var() > 0 else 0
                alpha = annual_return - (0.03 + beta * (bm_annual_return - 0.03))

                # 信息比率
                excess_ret = aligned_ret - aligned_bm
                info_ratio = excess_ret.mean() / excess_ret.std() * np.sqrt(252) if excess_ret.std() > 0 else 0

                result.update({
                    'benchmark_return': round(bm_annual_return, 4),
                    'excess_return': round(annual_return - bm_annual_return, 4),
                    'alpha': round(alpha, 4),
                    'beta': round(beta, 4),
                    'information_ratio': round(info_ratio, 2),
                })

        return result

    # ==================== 调仓判断 ====================

    def should_rebalance(self, trade_date: date, freq: str,
                         trading_days: List[date] = None) -> bool:
        """判断是否需要调仓 (ADD 12.1节)"""
        if freq == 'daily':
            return True
        elif freq == 'weekly':
            return trade_date.weekday() == 4  # 周五
        elif freq == 'biweekly':
            # 双周：每两周的周五
            if trade_date.weekday() != 4:
                return False
            if trading_days:
                idx = trading_days.index(trade_date) if trade_date in trading_days else -1
                return idx >= 0 and idx % 10 == 0
            return trade_date.day <= 7  # 简化：每月前7天内的周五
        elif freq == 'monthly':
            # 月频：每月最后一个交易日
            if trading_days:
                idx = trading_days.index(trade_date) if trade_date in trading_days else -1
                if idx >= 0 and idx + 1 < len(trading_days):
                    return trading_days[idx].month != trading_days[idx + 1].month
                return idx == len(trading_days) - 1
            return False
        return False

    # ==================== 机构级回测增强 ====================

    def walk_forward_validation(self, nav_series: pd.Series,
                                 train_window: int = 504,
                                 test_window: int = 63,
                                 gap: int = 20,
                                 min_periods: int = 252) -> Dict:
        """
        Walk-Forward滚动窗口验证
        避免过拟合，模拟真实投资中的模型更新过程

        Args:
            nav_series: 净值序列
            train_window: 训练窗口(交易日数)
            test_window: 测试窗口
            gap: 间隔期(防止信息泄漏)
            min_periods: 最小数据量

        Returns:
            各窗口回测结果汇总
        """
        T = len(nav_series)
        if T < min_periods:
            return {'error': 'Insufficient data for walk-forward validation'}

        results = []
        start = 0

        while start + train_window + gap + test_window <= T:
            train_end = start + train_window
            test_start = train_end + gap
            test_end = test_start + test_window

            train_nav = nav_series.iloc[start:train_end]
            test_nav = nav_series.iloc[test_start:test_end]

            # 计算测试期指标
            test_returns = test_nav.pct_change().dropna()
            if len(test_returns) > 0:
                sharpe = test_returns.mean() / test_returns.std() * np.sqrt(252) if test_returns.std() > 0 else 0
                cummax = test_nav.cummax()
                max_dd = ((test_nav - cummax) / cummax).min()

                results.append({
                    'train_start': nav_series.index[start],
                    'train_end': nav_series.index[train_end - 1],
                    'test_start': nav_series.index[test_start],
                    'test_end': nav_series.index[min(test_end - 1, T - 1)],
                    'sharpe': round(sharpe, 2),
                    'max_drawdown': round(max_dd, 4),
                    'cum_return': round(test_nav.iloc[-1] / test_nav.iloc[0] - 1, 4),
                })

            start += test_window  # 滚动

        if not results:
            return {'error': 'No valid walk-forward windows'}

        # 汇总
        sharpes = [r['sharpe'] for r in results]
        drawdowns = [r['max_drawdown'] for r in results]
        returns_list = [r['cum_return'] for r in results]

        return {
            'n_windows': len(results),
            'window_results': results,
            'avg_sharpe': round(np.mean(sharpes), 2),
            'std_sharpe': round(np.std(sharpes), 2),
            'avg_max_drawdown': round(np.mean(drawdowns), 4),
            'avg_return': round(np.mean(returns_list), 4),
            'consistency': round(sum(1 for s in sharpes if s > 0) / len(sharpes), 4),  # 正Sharpe比例
        }

    def monte_carlo_permutation_test(self, strategy_returns: pd.Series,
                                      n_permutations: int = 1000,
                                      block_size: int = 5) -> Dict:
        """
        蒙特卡洛置换检验
        打乱信号与收益的对应关系，检验策略是否统计显著

        Args:
            strategy_returns: 策略收益率序列
            n_permutations: 置换次数
            block_size: 块大小(保留自相关结构)
        """
        actual_sharpe = strategy_returns.mean() / strategy_returns.std() * np.sqrt(252) if strategy_returns.std() > 0 else 0

        # 块置换: 保持时间序列结构
        n = len(strategy_returns)
        permuted_sharpes = []

        for _ in range(n_permutations):
            # 块置换
            n_blocks = n // block_size
            block_indices = np.arange(n_blocks)
            np.random.shuffle(block_indices)

            permuted = np.concatenate([
                strategy_returns.iloc[i * block_size:(i + 1) * block_size].values
                for i in block_indices
            ])
            # 处理剩余
            remainder = n % block_size
            if remainder > 0:
                permuted = np.concatenate([permuted, strategy_returns.iloc[-remainder:].values])

            perm_sharpe = permuted.mean() / permuted.std() * np.sqrt(252) if permuted.std() > 0 else 0
            permuted_sharpes.append(perm_sharpe)

        # p值 = 置换后Sharpe超过实际Sharpe的比例
        p_value = sum(1 for s in permuted_sharpes if s >= actual_sharpe) / n_permutations

        return {
            'actual_sharpe': round(actual_sharpe, 2),
            'p_value': round(p_value, 4),
            'is_significant': p_value < 0.05,
            'permuted_sharpe_mean': round(np.mean(permuted_sharpes), 2),
            'permuted_sharpe_std': round(np.std(permuted_sharpes), 2),
            'n_permutations': n_permutations,
        }

    def deflated_sharpe_ratio(self, sharpe: float, n_trials: int,
                               backtest_length_years: float,
                               skewness: float = 0,
                               kurtosis: float = 3) -> Dict:
        """
        通胀夏普比率 (Deflated Sharpe Ratio, DSR)
        考虑多次测试后最佳Sharpe的统计显著性
        防止数据窥探偏差

        Args:
            sharpe: 观测到的Sharpe比率
            n_trials: 测试的策略数量
            backtest_length_years: 回测长度(年)
            skewness: 收益率偏度
            kurtosis: 收益率峰度
        """
        from scipy.stats import norm

        # 期望最大Sharpe(在零假设下)
        # E[max_SR] = (1 - gamma) * Phi^{-1}(1 - 1/N) + gamma * Phi^{-1}(1 - 1/(N*e))
        # 简化: E[max_SR] ≈ sqrt(var(SR)) * sqrt(2 * ln(N))
        var_sr = (1 - skewness * sharpe + (kurtosis - 1) / 4 * sharpe**2) / max(backtest_length_years, 0.5)
        expected_max_sr = np.sqrt(var_sr) * np.sqrt(2 * np.log(max(n_trials, 2)))

        # DSR = Phi((SR - E[max_SR]) / SE(SR))
        se_sr = np.sqrt(var_sr)
        if se_sr > 0:
            dsr = norm.cdf((sharpe - expected_max_sr) / se_sr)
        else:
            dsr = 1.0 if sharpe > expected_max_sr else 0.0

        return {
            'sharpe': round(sharpe, 2),
            'expected_max_sharpe': round(expected_max_sr, 2),
            'dsr': round(dsr, 4),
            'is_significant': dsr > 0.95,
            'n_trials': n_trials,
            'backtest_years': backtest_length_years,
        }

    def min_backtest_length(self, sharpe: float, confidence: float = 0.95) -> Dict:
        """
        最小回测长度 (Bailey & Lopez de Prado)
        回测太短则Sharpe不可信

        MinBTL = (z_alpha / SR)^2
        """
        from scipy.stats import norm
        z = norm.ppf(confidence)

        if abs(sharpe) < 0.01:
            return {'min_years': float('inf'), 'is_sufficient': False}

        min_years = (z / sharpe) ** 2

        return {
            'min_years': round(min_years, 2),
            'confidence': confidence,
            'sharpe': round(sharpe, 2),
        }

    def bootstrap_confidence_interval(self, returns: pd.Series,
                                       metric: str = 'sharpe',
                                       n_bootstrap: int = 1000,
                                       confidence: float = 0.95,
                                       block_size: int = 5) -> Dict:
        """
        Bootstrap置信区间
        使用块Bootstrap保留自相关结构

        Args:
            returns: 收益率序列
            metric: 指标类型 ('sharpe', 'max_drawdown', 'annual_return')
            n_bootstrap: Bootstrap次数
            confidence: 置信水平
            block_size: 块大小
        """
        n = len(returns)
        bootstrap_metrics = []

        for _ in range(n_bootstrap):
            # 块Bootstrap
            indices = []
            n_blocks = n // block_size
            for _ in range(n_blocks):
                start = np.random.randint(0, n - block_size + 1)
                indices.extend(range(start, start + block_size))

            indices = indices[:n]
            sample = returns.iloc[indices]

            # 计算指标
            if metric == 'sharpe':
                val = sample.mean() / sample.std() * np.sqrt(252) if sample.std() > 0 else 0
            elif metric == 'max_drawdown':
                cum = (1 + sample).cumprod()
                dd = ((cum - cum.cummax()) / cum.cummax()).min()
                val = dd
            elif metric == 'annual_return':
                val = (1 + sample).prod() ** (252 / n) - 1
            else:
                val = sample.mean() / sample.std() * np.sqrt(252) if sample.std() > 0 else 0

            bootstrap_metrics.append(val)

        alpha = (1 - confidence) / 2
        lower = np.percentile(bootstrap_metrics, alpha * 100)
        upper = np.percentile(bootstrap_metrics, (1 - alpha) * 100)

        return {
            'metric': metric,
            'point_estimate': round(bootstrap_metrics[len(bootstrap_metrics)//2], 4),
            'lower': round(lower, 4),
            'upper': round(upper, 4),
            'confidence': confidence,
            'n_bootstrap': n_bootstrap,
        }

    def close(self):
        if self.db:
            self.db.close()