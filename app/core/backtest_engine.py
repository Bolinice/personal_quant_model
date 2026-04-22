"""
A股回测引擎
实现完整的A股回测逻辑：T+1限制、涨跌停处理、停牌处理、交易成本、滑点等
符合ADD 12节回测规则和PRD 9.8节需求
机构级增强: 参与率滑点模型、Walk-Forward验证、蒙特卡洛置换检验、通胀夏普比率
事件驱动架构: BacktestEvent/Order/OrderBook + EventDrivenBacktestEngine + 自适应调仓
"""
from typing import Any, Callable, Dict, List, Optional, Tuple, Protocol
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from enum import Enum
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


# ==================== 事件驱动架构 ====================

class BacktestEventType(str, Enum):
    """回测事件类型"""
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"
    REBALANCE = "rebalance"
    FILL = "fill"
    RISK_CHECK = "risk_check"


@dataclass
class BacktestEvent:
    """回测事件"""
    event_type: BacktestEventType
    trade_date: date
    data: Dict[str, Any] = field(default_factory=dict)


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL_FILLED = "partial_filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """订单 (目标权重→订单→成交的完整链路)"""
    order_id: str
    ts_code: str
    direction: str  # 'buy' or 'sell'
    target_amount: float
    price: float
    trade_date: date
    status: OrderStatus = OrderStatus.PENDING
    filled_amount: float = 0.0
    filled_price: float = 0.0
    reject_reason: str = ""

    @property
    def filled_shares(self) -> int:
        return int(self.filled_amount / self.price) if self.price > 0 else 0


@dataclass
class OrderBook:
    """订单簿 - 管理当日所有订单"""
    orders: List[Order] = field(default_factory=list)
    rejected_orders: List[Order] = field(default_factory=list)

    def add_order(self, order: Order) -> None:
        self.orders.append(order)

    def add_rejected(self, order: Order) -> None:
        order.status = OrderStatus.REJECTED
        self.rejected_orders.append(order)

    def filled_orders(self) -> List[Order]:
        return [o for o in self.orders if o.status == OrderStatus.FILLED]

    def total_buy_amount(self) -> float:
        return sum(o.filled_amount for o in self.orders if o.direction == 'buy' and o.status == OrderStatus.FILLED)

    def total_sell_amount(self) -> float:
        return sum(o.filled_amount for o in self.orders if o.direction == 'sell' and o.status == OrderStatus.FILLED)

    def clear(self) -> None:
        self.orders.clear()
        self.rejected_orders.clear()


class SignalGenerator(Protocol):
    """信号生成器协议 (替代Callable，类型安全)"""
    def __call__(self, trade_date: date, universe: List[str], state: Any) -> Dict[str, float]: ...


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
                      daily_volume: Optional[float] = None,
                      volatility: Optional[float] = None) -> Dict[str, float]:
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
                       daily_volume: Optional[float] = None,
                       volatility: Optional[float] = None) -> Dict[str, float]:
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
    entry_date: Optional[date] = None  # 首次买入日期，用于T+1检查


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

    def __init__(self, db: Optional[Session] = None,
                 commission_rate: float = DEFAULT_COMMISSION_RATE,
                 stamp_tax_rate: float = DEFAULT_STAMP_TAX_RATE,
                 slippage_rate: float = DEFAULT_SLIPPAGE_RATE) -> None:
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
                    action: str, stock_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
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
                    trade_date: date, stock_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
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
            # T+1: 更新entry_date为当日(新买入部分当日不可卖)
            pos.entry_date = trade_date
        else:
            state.positions[ts_code] = Position(
                security_id=ts_code,
                shares=shares,
                cost_price=price,
                board_type=self.get_board_type(ts_code),
                entry_date=trade_date,  # T+1: 记录买入日期
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
                     trade_date: date, stock_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """执行卖出 (含T+1限制: 当日买入的股票不可卖出)"""
        tradable, reason = self.is_tradable(ts_code, trade_date, 'sell', stock_data)
        if not tradable:
            return None

        if ts_code not in state.positions:
            return None

        pos = state.positions[ts_code]

        # T+1检查: 当日买入的股票不可卖出 (A股规则)
        if pos.entry_date is not None and pos.entry_date == trade_date:
            logger.debug(
                "T+1 restriction: cannot sell stock bought today",
                extra={"ts_code": ts_code, "trade_date": str(trade_date)},
            )
            return None

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
                 price_data: Dict[str, float],
                 prev_price_data: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        计算当日净值 (含持仓级P&L归因)

        Args:
            state: 回测状态
            trade_date: 交易日期
            price_data: 当日价格 {ts_code: price}
            prev_price_data: 前日价格 (用于P&L归因)
        """
        position_value = 0
        position_pnl = {}  # 持仓级P&L

        for ts_code, pos in state.positions.items():
            price = price_data.get(ts_code, 0)
            prev_price = prev_price_data.get(ts_code, price) if prev_price_data else price
            pos.market_value = pos.shares * price
            position_value += pos.market_value

            # 持仓级P&L: pnl_i = shares_i * (price_t - price_{t-1})
            if prev_price > 0:
                pnl = pos.shares * (price - prev_price)
                position_pnl[ts_code] = {
                    'shares': pos.shares,
                    'price': price,
                    'prev_price': prev_price,
                    'pnl': round(pnl, 2),
                    'weight': 0,  # 后面计算
                }

        total_nav = state.cash + position_value
        nav = total_nav / state.initial_capital

        # 填充权重
        for ts_code in position_pnl:
            if total_nav > 0:
                position_pnl[ts_code]['weight'] = round(
                    state.positions[ts_code].market_value / total_nav, 6
                )

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
            'position_pnl': position_pnl,
        }
        state.nav_history.append(nav_record)
        logger.debug(
            "NAV calculated",
            extra={
                "trade_date": str(trade_date),
                "nav": round(nav, 6),
                "total_value": round(total_nav, 2),
                "drawdown": round(drawdown, 4),
                "num_positions": len(state.positions),
            },
        )
        return nav_record

    def position_pnl_attribution(self, nav_history: List[Dict[str, Any]],
                                  factor_exposures: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, Any]:
        """
        持仓级P&L因子归因
        将P&L按因子暴露聚合: pnl_from_factor_k = Σ_i pnl_i * exposure_i_k

        Args:
            nav_history: 净值历史(含position_pnl)
            factor_exposures: 因子暴露 {ts_code: {factor_name: exposure_value}}

        Returns:
            因子P&L归因结果
        """
        if not nav_history or factor_exposures is None:
            return {}

        # 汇总各持仓的总P&L
        total_pnl_by_stock = {}
        for record in nav_history:
            position_pnl = record.get('position_pnl', {})
            for ts_code, pnl_info in position_pnl.items():
                if ts_code not in total_pnl_by_stock:
                    total_pnl_by_stock[ts_code] = 0
                total_pnl_by_stock[ts_code] += pnl_info.get('pnl', 0)

        # 按因子暴露聚合
        factor_pnl = {}
        unattributed_pnl = 0

        for ts_code, stock_pnl in total_pnl_by_stock.items():
            exposures = factor_exposures.get(ts_code, {})
            if not exposures:
                unattributed_pnl += stock_pnl
                continue

            # 按因子暴露加权分配P&L
            total_exposure = sum(abs(v) for v in exposures.values())
            if total_exposure == 0:
                unattributed_pnl += stock_pnl
                continue

            for factor_name, exposure in exposures.items():
                if factor_name not in factor_pnl:
                    factor_pnl[factor_name] = 0
                # P&L按暴露占比分配
                factor_pnl[factor_name] += stock_pnl * (exposure / total_exposure)

        total_pnl = sum(total_pnl_by_stock.values())

        result = {
            'factor_pnl': {k: round(v, 2) for k, v in factor_pnl.items()},
            'unattributed_pnl': round(unattributed_pnl, 2),
            'total_pnl': round(total_pnl, 2),
            'factor_pnl_pct': {k: round(v / total_pnl, 4) for k, v in factor_pnl.items()} if total_pnl != 0 else {},
        }
        logger.info(
            "P&L attribution computed",
            extra={
                "total_pnl": round(total_pnl, 2),
                "unattributed_pnl": round(unattributed_pnl, 2),
                "n_factors": len(factor_pnl),
                "n_stocks": len(total_pnl_by_stock),
            },
        )
        return result

    # ==================== 回测指标计算 ====================

    def calc_metrics(self, nav_history: List[Dict[str, Any]],
                     trade_records: List[Dict[str, Any]],
                     benchmark_nav: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
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
                         trading_days: Optional[List[date]] = None) -> bool:
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
                                 min_periods: int = 252) -> Dict[str, Any]:
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
                                      block_size: int = 5) -> Dict[str, Any]:
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
                               kurtosis: float = 3) -> Dict[str, Any]:
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

    def min_backtest_length(self, sharpe: float, confidence: float = 0.95) -> Dict[str, Any]:
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
                                       block_size: int = 5) -> Dict[str, Any]:
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

    def close(self) -> None:
        if self.db:
            self.db.close()

    # ==================== Walk-Forward模型重训练回测 ====================

    def walk_forward_backtest(self, model_factory: Callable[[date, date], Any],
                               train_start: date,
                               train_end: date,
                               test_end: date,
                               retrain_freq: int = 63,
                               train_window: int = 504,
                               gap: int = 60,
                               initial_capital: float = 1000000.0,
                               universe: Optional[List[str]] = None,
                               price_data: Optional[Dict[Tuple[str, date], Dict[str, Any]]] = None,
                               trading_days: Optional[List[date]] = None) -> Dict[str, Any]:
        """
        Walk-Forward模型重训练回测
        每个窗口: 训练模型 → 测试期交易 → 下一窗口重新训练
        避免过拟合，模拟真实投资中的模型定期更新

        Args:
            model_factory: 可调用对象, model_factory(train_start, train_end) -> signal_generator
            train_start: 初始训练期开始
            train_end: 初始训练期结束
            test_end: 测试结束日期
            retrain_freq: 重训练频率(交易日数, 63≈1季度)
            train_window: 训练窗口长度
            gap: 训练/测试间隔(防止信息泄漏, 默认60覆盖最大因子回看期)
            initial_capital: 初始资金
            universe: 股票池
            price_data: 行情数据
            trading_days: 交易日列表

        Returns:
            各窗口回测结果汇总
        """
        if trading_days is None:
            return {'error': 'trading_days required for walk_forward_backtest'}

        # 按时间排序交易日
        trading_days = sorted(trading_days)
        results = []
        all_nav = []
        all_trades = []

        # 划分窗口
        current_test_start = train_end
        window_id = 0

        while current_test_start < test_end:
            # 计算当前窗口的训练期
            current_train_end_idx = None
            for i, td in enumerate(trading_days):
                if td >= current_test_start:
                    current_train_end_idx = i - gap
                    break

            if current_train_end_idx is None or current_train_end_idx < 0:
                break

            current_train_start_idx = max(0, current_train_end_idx - train_window)
            current_train_start = trading_days[current_train_start_idx]
            current_train_end = trading_days[current_train_end_idx]

            # 测试期
            current_test_end_idx = min(
                current_train_end_idx + gap + retrain_freq,
                len(trading_days) - 1
            )
            current_test_end = trading_days[current_test_end_idx]
            actual_test_start = trading_days[current_train_end_idx + gap]

            # 训练模型
            try:
                signal_generator = model_factory(current_train_start, current_train_end)
            except Exception as e:
                logger.warning(f"Walk-forward window {window_id}: model training failed: {e}")
                current_test_start = trading_days[min(current_test_end_idx + 1, len(trading_days) - 1)]
                window_id += 1
                continue

            # 测试期回测
            window_trading_days = [td for td in trading_days if actual_test_start <= td <= current_test_end]
            if len(window_trading_days) < 5:
                break

            try:
                window_result = self.run_backtest(
                    signal_generator=signal_generator,
                    universe=universe or [],
                    start_date=actual_test_start,
                    end_date=current_test_end,
                    rebalance_freq='weekly',
                    initial_capital=initial_capital,
                    trading_days=window_trading_days,
                    price_data=price_data or {},
                )

                results.append({
                    'window_id': window_id,
                    'train_start': current_train_start,
                    'train_end': current_train_end,
                    'test_start': actual_test_start,
                    'test_end': current_test_end,
                    'metrics': window_result.get('metrics', {}),
                    'total_days': window_result.get('total_days', 0),
                })

                if 'nav_history' in window_result:
                    all_nav.extend(window_result['nav_history'])
                if 'trade_records' in window_result:
                    all_trades.extend(window_result['trade_records'])

            except Exception as e:
                logger.warning(f"Walk-forward window {window_id}: backtest failed: {e}")

            current_test_start = trading_days[min(current_test_end_idx + 1, len(trading_days) - 1)]
            window_id += 1

        if not results:
            return {'error': 'No valid walk-forward windows completed'}

        # 汇总
        window_sharpes = [r['metrics'].get('sharpe_ratio', 0) for r in results if r.get('metrics')]
        window_returns = [r['metrics'].get('total_return', 0) for r in results if r.get('metrics')]

        avg_sharpe = round(np.mean(window_sharpes), 2) if window_sharpes else 0
        avg_return = round(np.mean(window_returns), 4) if window_returns else 0

        logger.info(
            "Walk-forward backtest completed",
            extra={
                "n_windows": len(results),
                "avg_sharpe": avg_sharpe,
                "avg_return": avg_return,
                "std_sharpe": round(np.std(window_sharpes), 2) if window_sharpes else 0,
                "consistency": round(sum(1 for s in window_sharpes if s > 0) / len(window_sharpes), 4) if window_sharpes else 0,
            },
        )

        return {
            'n_windows': len(results),
            'window_results': results,
            'avg_sharpe': avg_sharpe,
            'std_sharpe': round(np.std(window_sharpes), 2) if window_sharpes else 0,
            'avg_return': avg_return,
            'consistency': round(sum(1 for s in window_sharpes if s > 0) / len(window_sharpes), 4) if window_sharpes else 0,
            'nav_history': all_nav,
            'trade_records': all_trades,
        }

    # ==================== 回测主循环 ====================

    def run_backtest(self, signal_generator: Callable[[date, List[str], BacktestState], Dict[str, float]],
                     universe: List[str],
                     start_date: date, end_date: date,
                     rebalance_freq: str = 'monthly',
                     initial_capital: float = 1000000.0,
                     trading_days: Optional[List[date]] = None,
                     price_data: Optional[Dict[Tuple[str, date], Dict[str, Any]]] = None,
                     max_turnover: float = 1.0,
                     benchmark_nav: Optional[List[Dict[str, Any]]] = None,
                     use_next_day_open: bool = True) -> Dict[str, Any]:
        """
        回测主循环 (机构级: 完整信号→权重→交易→NAV流程)

        Args:
            signal_generator: 可调用对象, 签名 (trade_date, universe, state) -> Dict[str, float]
                             返回 {ts_code: target_weight}
            universe: 股票池
            start_date: 开始日期
            end_date: 结束日期
            rebalance_freq: 调仓频率 ('daily', 'weekly', 'biweekly', 'monthly')
            initial_capital: 初始资金
            trading_days: 交易日列表
            price_data: 行情数据 {(ts_code, trade_date): {close, open, pct_chg, volume, amount, is_suspended, is_st, ...}}
            max_turnover: 单次最大换手率 (0-1, 1=无限制)
            benchmark_nav: 基准净值 [{trade_date, nav}]
            use_next_day_open: 是否使用次日开盘价成交 (True=实盘真实, False=当日收盘价)

        Returns:
            回测结果 {nav_history, trade_records, metrics, ...}
        """
        state = BacktestState(cash=initial_capital, initial_capital=initial_capital)
        prev_weights = pd.Series(dtype=float)  # 上期权重

        if trading_days is None:
            # 简化: 生成工作日
            trading_days = pd.bdate_range(start_date, end_date).date.tolist()

        # 构建交易日索引映射，用于查找下一交易日
        trading_day_to_idx = {td: i for i, td in enumerate(trading_days)}

        for trade_date in trading_days:
            if trade_date < start_date or trade_date > end_date:
                continue

            # 判断是否调仓日
            is_rebalance = self.should_rebalance(trade_date, rebalance_freq, trading_days)

            if is_rebalance:
                # 获取目标权重 (信号在T日收盘后生成)
                try:
                    target_weights = signal_generator(trade_date, universe, state)
                except Exception as e:
                    logger.warning(f"Signal generator failed on {trade_date}: {e}")
                    target_weights = {}

                if target_weights:
                    target_w = pd.Series(target_weights)

                    # 换手率控制
                    if not prev_weights.empty and max_turnover < 1.0:
                        turnover = (target_w.subtract(prev_weights, fill_value=0).abs().sum()) / 2
                        if turnover > max_turnover:
                            alpha = max_turnover / turnover
                            target_w = prev_weights.reindex(target_w.index, fill_value=0) + alpha * (
                                target_w - prev_weights.reindex(target_w.index, fill_value=0)
                            )
                            # 归一化
                            if target_w.sum() > 0:
                                target_w = target_w / target_w.sum()

                    # 确定成交日期和价格:
                    # 机构实盘: 信号T日收盘生成 → T+1日开盘价成交
                    # 简化回测: 信号T日收盘生成 → T日收盘价成交 (use_next_day_open=False)
                    if use_next_day_open:
                        # 查找下一交易日
                        current_idx = trading_day_to_idx.get(trade_date, -1)
                        if current_idx >= 0 and current_idx + 1 < len(trading_days):
                            exec_date = trading_days[current_idx + 1]
                        else:
                            exec_date = trade_date  # 回退到当日
                    else:
                        exec_date = trade_date

                    # 执行交易: 先卖后买
                    # 计算当前持仓市值
                    current_total = state.cash + sum(
                        pos.market_value for pos in state.positions.values()
                    )

                    # 卖出: 不在目标组合中的持仓
                    for ts_code in list(state.positions.keys()):
                        if ts_code not in target_w or target_w[ts_code] < 1e-6:
                            pos = state.positions[ts_code]
                            stock_key = (ts_code, exec_date)
                            stock_info = price_data.get(stock_key, {}) if price_data else {}
                            # 使用次日开盘价成交(实盘真实)，回退到收盘价
                            if use_next_day_open:
                                sell_price = stock_info.get('open', stock_info.get('close', pos.cost_price))
                            else:
                                sell_price = stock_info.get('close', pos.cost_price)
                            self.execute_sell(state, ts_code, pos.shares, sell_price,
                                            exec_date, stock_info)

                    # 买入: 目标组合中的持仓
                    for ts_code, weight in target_w.items():
                        if weight < 1e-6:
                            continue

                        target_amount = weight * current_total
                        stock_key = (ts_code, exec_date)
                        stock_info = price_data.get(stock_key, {}) if price_data else {}
                        # 使用次日开盘价成交(实盘真实)，回退到收盘价
                        if use_next_day_open:
                            buy_price = stock_info.get('open', stock_info.get('close', 0))
                        else:
                            buy_price = stock_info.get('close', 0)

                        if buy_price <= 0:
                            continue

                        # 计算已有持仓金额
                        current_amount = 0
                        if ts_code in state.positions:
                            current_amount = state.positions[ts_code].shares * buy_price

                        # 只在需要增仓时买入
                        if target_amount > current_amount * 1.05:  # 5%缓冲避免微小交易
                            self.execute_buy(state, ts_code, target_amount - current_amount,
                                           buy_price, exec_date, stock_info)

                    # 更新上期权重
                    total_value = state.cash + sum(
                        pos.shares * (price_data.get((ts_code, trade_date), {}).get('close', pos.cost_price) if price_data else pos.cost_price)
                        for ts_code, pos in state.positions.items()
                    )
                    if total_value > 0:
                        prev_weights = pd.Series({
                            ts_code: (pos.shares * (price_data.get((ts_code, trade_date), {}).get('close', pos.cost_price) if price_data else pos.cost_price)) / total_value
                            for ts_code, pos in state.positions.items()
                        })

            # 每日mark-to-market
            price_dict = {}
            if price_data:
                for ts_code in state.positions:
                    stock_key = (ts_code, trade_date)
                    stock_info = price_data.get(stock_key, {})
                    if 'close' in stock_info:
                        price_dict[ts_code] = stock_info['close']

            if price_dict or state.positions:
                self.calc_nav(state, trade_date, price_dict)

        # 计算回测指标
        metrics = self.calc_metrics(state.nav_history, state.trade_records, benchmark_nav)

        return {
            'nav_history': state.nav_history,
            'trade_records': state.trade_records,
            'metrics': metrics,
            'initial_capital': initial_capital,
            'final_value': state.cash + sum(pos.market_value for pos in state.positions.values()),
            'total_trades': len(state.trade_records),
            'total_days': len(state.nav_history),
        }

    # ==================== 自适应调仓 ====================

    def should_rebalance_adaptive(self, trade_date: date,
                                   current_weights: pd.Series,
                                   target_weights: pd.Series,
                                   tracking_error_threshold: float = 0.02,
                                   min_rebalance_days: int = 10,
                                   last_rebalance_date: Optional[date] = None,
                                   trading_days: Optional[List[date]] = None) -> bool:
        """
        自适应调仓: 基于跟踪误差阈值触发
        当实际组合与目标组合的跟踪误差超过阈值时才调仓
        比固定频率调仓更贴近机构实盘操作

        Args:
            trade_date: 当前交易日
            current_weights: 当前持仓权重
            target_weights: 目标权重
            tracking_error_threshold: 跟踪误差阈值 (权重偏差的L2范数)
            min_rebalance_days: 最小调仓间隔天数
            last_rebalance_date: 上次调仓日期
            trading_days: 交易日列表
        """
        # 最小间隔检查
        if last_rebalance_date is not None and trading_days is not None:
            days_since = sum(1 for d in trading_days if last_rebalance_date < d <= trade_date)
            if days_since < min_rebalance_days:
                return False

        # 跟踪误差 = L2范数(current - target)
        common = current_weights.index.intersection(target_weights.index)
        if len(common) == 0:
            return True

        diff = current_weights.reindex(common, fill_value=0) - target_weights.reindex(common, fill_value=0)
        tracking_error = np.sqrt((diff ** 2).sum())

        return tracking_error > tracking_error_threshold

    # ==================== 行业约束检查 ====================

    def check_industry_constraints(self, target_weights: pd.Series,
                                    industry_data: Dict[str, str],
                                    max_industry_weight: float = 0.30) -> Dict[str, Any]:
        """
        行业权重约束检查
        单个行业权重不超过阈值

        Args:
            target_weights: 目标权重 {ts_code: weight}
            industry_data: 行业映射 {ts_code: industry_name}
            max_industry_weight: 单行业最大权重

        Returns:
            {is_valid, violations, adjusted_weights}
        """
        industry_weights = {}
        for ts_code, weight in target_weights.items():
            industry = industry_data.get(ts_code, 'unknown')
            industry_weights[industry] = industry_weights.get(industry, 0) + weight

        violations = {ind: w for ind, w in industry_weights.items() if w > max_industry_weight}
        is_valid = len(violations) == 0

        adjusted = target_weights.copy()
        if not is_valid:
            # 按行业缩放: 超限行业按比例缩减
            for industry, total_w in violations.items():
                scale = max_industry_weight / total_w
                for ts_code in target_weights.index:
                    if industry_data.get(ts_code) == industry:
                        adjusted[ts_code] *= scale
            # 归一化
            if adjusted.sum() > 0:
                adjusted = adjusted / adjusted.sum()

        return {
            'is_valid': is_valid,
            'violations': violations,
            'adjusted_weights': adjusted,
        }


# ==================== 事件驱动回测引擎 ====================

class EventDrivenBacktestEngine(ABShareBacktestEngine):
    """
    事件驱动回测引擎
    支持自定义事件处理器、多组合并行回测、订单追踪
    """

    def __init__(self, db: Optional[Session] = None,
                 commission_rate: float = DEFAULT_COMMISSION_RATE,
                 stamp_tax_rate: float = DEFAULT_STAMP_TAX_RATE,
                 slippage_rate: float = DEFAULT_SLIPPAGE_RATE) -> None:
        super().__init__(db, commission_rate, stamp_tax_rate, slippage_rate)
        self.event_handlers: Dict[BacktestEventType, List[Callable]] = {
            et: [] for et in BacktestEventType
        }
        self.order_book = OrderBook()
        self.all_order_books: Dict[date, OrderBook] = {}

    def register_handler(self, event_type: BacktestEventType, handler: Callable) -> None:
        """注册事件处理器"""
        self.event_handlers[event_type].append(handler)

    def _emit_event(self, event: BacktestEvent) -> None:
        """触发事件"""
        for handler in self.event_handlers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.warning(f"Event handler failed: {e}")

    def run_backtest_event_driven(self,
                                   signal_generator: SignalGenerator,
                                   universe: List[str],
                                   start_date: date, end_date: date,
                                   rebalance_freq: str = 'monthly',
                                   initial_capital: float = 1000000.0,
                                   trading_days: Optional[List[date]] = None,
                                   price_data: Optional[Dict[Tuple[str, date], Dict[str, Any]]] = None,
                                   max_turnover: float = 1.0,
                                   benchmark_nav: Optional[List[Dict[str, Any]]] = None,
                                   industry_data: Optional[Dict[str, str]] = None,
                                   max_industry_weight: float = 0.30,
                                   use_next_day_open: bool = True) -> Dict[str, Any]:
        """
        事件驱动回测主循环
        完整链路: 信号→订单→成交→NAV，记录未成交订单和行业约束

        Args:
            use_next_day_open: 是否使用次日开盘价成交 (True=实盘真实T+1, False=当日收盘价)
        """
        state = BacktestState(cash=initial_capital, initial_capital=initial_capital)
        prev_weights = pd.Series(dtype=float)

        if trading_days is None:
            trading_days = pd.bdate_range(start_date, end_date).date.tolist()

        # 构建交易日索引映射，用于查找下一交易日
        trading_day_to_idx = {td: i for i, td in enumerate(trading_days)}

        for trade_date in trading_days:
            if trade_date < start_date or trade_date > end_date:
                continue

            self.order_book.clear()

            # MARKET_OPEN事件
            self._emit_event(BacktestEvent(BacktestEventType.MARKET_OPEN, trade_date))

            is_rebalance = self.should_rebalance(trade_date, rebalance_freq, trading_days)

            if is_rebalance:
                # REBALANCE事件
                self._emit_event(BacktestEvent(BacktestEventType.REBALANCE, trade_date))

                try:
                    target_weights = signal_generator(trade_date, universe, state)
                except Exception as e:
                    logger.warning(f"Signal generator failed on {trade_date}: {e}")
                    target_weights = {}

                if target_weights:
                    target_w = pd.Series(target_weights)

                    # 行业约束
                    if industry_data is not None:
                        constraint_result = self.check_industry_constraints(
                            target_w, industry_data, max_industry_weight
                        )
                        if not constraint_result['is_valid']:
                            target_w = constraint_result['adjusted_weights']

                    # 换手率控制
                    if not prev_weights.empty and max_turnover < 1.0:
                        turnover = (target_w.subtract(prev_weights, fill_value=0).abs().sum()) / 2
                        if turnover > max_turnover:
                            alpha = max_turnover / turnover
                            target_w = prev_weights.reindex(target_w.index, fill_value=0) + alpha * (
                                target_w - prev_weights.reindex(target_w.index, fill_value=0)
                            )
                            if target_w.sum() > 0:
                                target_w = target_w / target_w.sum()

                    current_total = state.cash + sum(
                        pos.market_value for pos in state.positions.values()
                    )

                    # T+1执行: 信号T日收盘生成 → T+1日开盘价成交
                    if use_next_day_open:
                        current_idx = trading_day_to_idx.get(trade_date, -1)
                        if current_idx >= 0 and current_idx + 1 < len(trading_days):
                            exec_date = trading_days[current_idx + 1]
                        else:
                            exec_date = trade_date
                    else:
                        exec_date = trade_date

                    # 生成卖出订单
                    for ts_code in list(state.positions.keys()):
                        if ts_code not in target_w or target_w[ts_code] < 1e-6:
                            pos = state.positions[ts_code]
                            stock_key = (ts_code, exec_date)
                            stock_info = price_data.get(stock_key, {}) if price_data else {}
                            if use_next_day_open:
                                sell_price = stock_info.get('open', stock_info.get('close', pos.cost_price))
                            else:
                                sell_price = stock_info.get('close', pos.cost_price)

                            order = Order(
                                order_id=f"sell_{ts_code}_{exec_date}",
                                ts_code=ts_code, direction='sell',
                                target_amount=pos.shares * sell_price,
                                price=sell_price, trade_date=exec_date,
                            )

                            # 可交易性检查
                            tradable, reason = self.is_tradable(ts_code, exec_date, 'sell', stock_info)
                            if not tradable:
                                order.reject_reason = reason
                                self.order_book.add_rejected(order)
                                continue

                            result = self.execute_sell(state, ts_code, pos.shares, sell_price, exec_date, stock_info)
                            if result:
                                order.status = OrderStatus.FILLED
                                order.filled_amount = result['amount']
                                order.filled_price = sell_price
                            self.order_book.add_order(order)

                    # 生成买入订单
                    for ts_code, weight in target_w.items():
                        if weight < 1e-6:
                            continue

                        target_amount = weight * current_total
                        stock_key = (ts_code, exec_date)
                        stock_info = price_data.get(stock_key, {}) if price_data else {}
                        if use_next_day_open:
                            buy_price = stock_info.get('open', stock_info.get('close', 0))
                        else:
                            buy_price = stock_info.get('close', 0)

                        if buy_price <= 0:
                            continue

                        current_amount = 0
                        if ts_code in state.positions:
                            current_amount = state.positions[ts_code].shares * buy_price

                        if target_amount > current_amount * 1.05:
                            order = Order(
                                order_id=f"buy_{ts_code}_{exec_date}",
                                ts_code=ts_code, direction='buy',
                                target_amount=target_amount - current_amount,
                                price=buy_price, trade_date=exec_date,
                            )

                            tradable, reason = self.is_tradable(ts_code, exec_date, 'buy', stock_info)
                            if not tradable:
                                order.reject_reason = reason
                                self.order_book.add_rejected(order)
                                continue

                            result = self.execute_buy(state, ts_code, target_amount - current_amount, buy_price, exec_date, stock_info)
                            if result:
                                order.status = OrderStatus.FILLED
                                order.filled_amount = result['amount']
                                order.filled_price = buy_price
                            self.order_book.add_order(order)

                    # FILL事件
                    self._emit_event(BacktestEvent(
                        BacktestEventType.FILL, trade_date,
                        {'filled': self.order_book.filled_orders(), 'rejected': self.order_book.rejected_orders}
                    ))

                    # 更新权重
                    total_value = state.cash + sum(
                        pos.shares * (price_data.get((ts_code, trade_date), {}).get('close', pos.cost_price) if price_data else pos.cost_price)
                        for ts_code, pos in state.positions.items()
                    )
                    if total_value > 0:
                        prev_weights = pd.Series({
                            ts_code: (pos.shares * (price_data.get((ts_code, trade_date), {}).get('close', pos.cost_price) if price_data else pos.cost_price)) / total_value
                            for ts_code, pos in state.positions.items()
                        })

            # RISK_CHECK事件
            self._emit_event(BacktestEvent(BacktestEventType.RISK_CHECK, trade_date, {
                'positions': dict(state.positions), 'cash': state.cash
            }))

            # mark-to-market
            price_dict = {}
            if price_data:
                for ts_code in state.positions:
                    stock_key = (ts_code, trade_date)
                    stock_info = price_data.get(stock_key, {})
                    if 'close' in stock_info:
                        price_dict[ts_code] = stock_info['close']

            if price_dict or state.positions:
                self.calc_nav(state, trade_date, price_dict)

            # MARKET_CLOSE事件
            self._emit_event(BacktestEvent(BacktestEventType.MARKET_CLOSE, trade_date))

            # 保存当日订单簿
            self.all_order_books[trade_date] = OrderBook(
                orders=list(self.order_book.orders),
                rejected_orders=list(self.order_book.rejected_orders),
            )

        metrics = self.calc_metrics(state.nav_history, state.trade_records, benchmark_nav)

        # 统计被拒订单
        total_rejected = sum(len(ob.rejected_orders) for ob in self.all_order_books.values())
        total_filled = sum(len(ob.filled_orders()) for ob in self.all_order_books.values())

        return {
            'nav_history': state.nav_history,
            'trade_records': state.trade_records,
            'metrics': metrics,
            'initial_capital': initial_capital,
            'final_value': state.cash + sum(pos.market_value for pos in state.positions.values()),
            'total_trades': len(state.trade_records),
            'total_days': len(state.nav_history),
            'total_filled_orders': total_filled,
            'total_rejected_orders': total_rejected,
            'order_fill_rate': round(total_filled / (total_filled + total_rejected), 4) if (total_filled + total_rejected) > 0 else 1.0,
        }

    # ==================== 多组合并行回测 ====================

    def run_multi_portfolio_backtest(self,
                                      signal_generators: Dict[str, SignalGenerator],
                                      universe: List[str],
                                      start_date: date, end_date: date,
                                      rebalance_freq: str = 'monthly',
                                      initial_capital: float = 1000000.0,
                                      trading_days: Optional[List[date]] = None,
                                      price_data: Optional[Dict[Tuple[str, date], Dict[str, Any]]] = None,
                                      benchmark_nav: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
        """
        多组合并行回测
        同一universe下不同策略同时回测，用于策略比较

        Args:
            signal_generators: {strategy_name: signal_generator}
        """
        results = {}
        for name, sg in signal_generators.items():
            results[name] = self.run_backtest(
                signal_generator=sg,
                universe=universe,
                start_date=start_date,
                end_date=end_date,
                rebalance_freq=rebalance_freq,
                initial_capital=initial_capital,
                trading_days=trading_days,
                price_data=price_data,
                benchmark_nav=benchmark_nav,
            )
        return results