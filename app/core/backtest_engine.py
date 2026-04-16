"""
A股回测引擎
实现完整的A股回测逻辑：T+1限制、涨跌停处理、停牌处理、交易成本等
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, with_db
from app.models.backtests import Backtest, BacktestResult, BacktestTrade
from app.models.models import Model
from app.models.market import StockDaily, TradingCalendar
from app.core.logging import logger


class ABShareBacktestEngine:
    """A股回测引擎"""

    # A股交易成本
    COMMISSION_RATE = 0.0003  # 佣金率 0.03%
    STAMP_TAX_RATE = 0.001    # 印花税率 0.1%（仅卖出）
    TRANSFER_FEE_RATE = 0.00001  # 过户费率 0.001%

    # 涨跌停限制
    MAIN_BOARD_LIMIT = 0.10   # 主板涨跌停 10%
    GEM_LIMIT = 0.20          # 创业板涨跌停 20%
    STAR_LIMIT = 0.20         # 科创板涨跌停 20%

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    def get_trading_calendar(self, start_date: str, end_date: str) -> List[datetime]:
        """获取交易日历"""
        calendars = self.db.query(TradingCalendar).filter(
            TradingCalendar.exchange == 'SSE',
            TradingCalendar.cal_date >= start_date,
            TradingCalendar.cal_date <= end_date,
            TradingCalendar.is_open == True
        ).order_by(TradingCalendar.cal_date).all()

        return [c.cal_date for c in calendars]

    def get_stock_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票数据"""
        data = self.db.query(StockDaily).filter(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date
        ).order_by(StockDaily.trade_date).all()

        if not data:
            return pd.DataFrame()

        return pd.DataFrame([{
            'trade_date': d.trade_date,
            'open': float(d.open) if d.open else None,
            'high': float(d.high) if d.high else None,
            'low': float(d.low) if d.low else None,
            'close': float(d.close) if d.close else None,
            'volume': float(d.vol) if d.vol else None,
            'amount': float(d.amount) if d.amount else None,
            'pct_chg': float(d.pct_chg) if d.pct_chg else None,
            'pre_close': float(d.pre_close) if d.pre_close else None,
        } for d in data])

    def is_limit_up(self, pct_chg: float, board_type: str = 'main') -> bool:
        """判断是否涨停"""
        limit = self.MAIN_BOARD_LIMIT
        if board_type == 'gem':
            limit = self.GEM_LIMIT
        elif board_type == 'star':
            limit = self.STAR_LIMIT

        return pct_chg >= (limit - 0.001) * 100  # 允许小误差

    def is_limit_down(self, pct_chg: float, board_type: str = 'main') -> bool:
        """判断是否跌停"""
        limit = self.MAIN_BOARD_LIMIT
        if board_type == 'gem':
            limit = self.GEM_LIMIT
        elif board_type == 'star':
            limit = self.STAR_LIMIT

        return pct_chg <= -(limit - 0.001) * 100

    def calc_transaction_cost(self, amount: float, is_buy: bool) -> float:
        """
        计算交易成本

        Args:
            amount: 成交金额
            is_buy: 是否买入

        Returns:
            交易成本
        """
        cost = amount * self.COMMISSION_RATE  # 佣金
        cost += amount * self.TRANSFER_FEE_RATE  # 过户费

        if not is_buy:
            cost += amount * self.STAMP_TAX_RATE  # 印花税（仅卖出）

        return cost

    def round_lot(self, shares: float) -> int:
        """
        将股数调整为100股整数倍（A股交易单位）

        Args:
            shares: 股数

        Returns:
            调整后的股数
        """
        return int(shares // 100) * 100

    # ==================== 回测核心逻辑 ====================

    def run_backtest(self, backtest_id: int) -> Dict:
        """
        运行回测

        Args:
            backtest_id: 回测ID

        Returns:
            回测结果
        """
        # 获取回测配置
        backtest = self.db.query(Backtest).filter(Backtest.id == backtest_id).first()
        if not backtest:
            raise ValueError(f"Backtest {backtest_id} not found")

        # 初始化回测状态
        initial_capital = backtest.initial_capital
        cash = initial_capital
        positions = {}  # {ts_code: {'shares': int, 'cost_price': float}}
        nav_history = []
        trade_records = []

        # 获取交易日历
        trading_days = self.get_trading_calendar(
            backtest.start_date.strftime('%Y-%m-%d'),
            backtest.end_date.strftime('%Y-%m-%d')
        )

        if not trading_days:
            raise ValueError("No trading days found")

        # 获取目标组合历史
        # 这里简化处理，实际应该根据模型生成每日目标组合
        # 假设我们有一个函数来获取每日目标组合
        target_portfolios = self._get_target_portfolios(backtest.model_id, trading_days)

        # 回测循环
        for i, trade_date in enumerate(trading_days):
            date_str = trade_date.strftime('%Y-%m-%d')

            # 1. 更新持仓市值
            position_value = 0
            for ts_code, pos in positions.items():
                stock_data = self.get_stock_data(ts_code, date_str, date_str)
                if not stock_data.empty:
                    price = stock_data['close'].iloc[0]
                    position_value += pos['shares'] * price

            # 2. 计算当日净值
            total_nav = cash + position_value
            nav_history.append({
                'date': date_str,
                'nav': total_nav,
                'cash': cash,
                'position_value': position_value
            })

            # 3. 检查是否需要调仓
            if date_str in target_portfolios:
                target_portfolio = target_portfolios[date_str]

                # 生成调仓指令
                orders = self._generate_rebalance_orders(
                    positions, target_portfolio, cash, date_str
                )

                # 执行调仓（T+1：次日执行）
                if i + 1 < len(trading_days):
                    next_date = trading_days[i + 1].strftime('%Y-%m-%d')
                    cash, new_positions, trades = self._execute_orders(
                        orders, positions, cash, next_date
                    )
                    positions = new_positions
                    trade_records.extend(trades)

        # 计算回测结果
        result = self._calculate_backtest_metrics(
            nav_history, trade_records, backtest.benchmark, initial_capital
        )

        return result

    def _get_target_portfolios(self, model_id: int, trading_days: List[datetime]) -> Dict:
        """获取目标组合历史（简化实现）"""
        # 这里应该调用模型评分和组合生成逻辑
        # 简化：假设每周调仓，等权持有20只股票
        from app.core.model_scorer import get_model_portfolio

        portfolios = {}

        # 每周调仓
        for i, trade_date in enumerate(trading_days):
            if i % 5 == 0:  # 每5个交易日调仓
                date_str = trade_date.strftime('%Y-%m-%d')
                try:
                    portfolio = get_model_portfolio(model_id, date_str, top_n=20, db=self.db)
                    if not portfolio.empty:
                        portfolios[date_str] = portfolio
                except Exception as e:
                    logger.warning(f"Failed to get portfolio for {date_str}: {e}")

        return portfolios

    def _generate_rebalance_orders(self, current_positions: Dict,
                                   target_portfolio: pd.DataFrame,
                                   cash: float, trade_date: str) -> List[Dict]:
        """生成调仓指令"""
        orders = []

        # 当前持仓
        current_stocks = set(current_positions.keys())
        target_stocks = set(target_portfolio['security_id'].tolist())

        # 需要卖出的股票
        to_sell = current_stocks - target_stocks
        for ts_code in to_sell:
            orders.append({
                'ts_code': ts_code,
                'action': 'sell',
                'shares': current_positions[ts_code]['shares'],
                'reason': 'not in target'
            })

        # 需要买入的股票
        to_buy = target_stocks - current_stocks
        for ts_code in to_buy:
            weight = target_portfolio[target_portfolio['security_id'] == ts_code]['weight'].iloc[0]
            # 估算可用资金
            estimated_cash = cash + sum(
                current_positions[s]['shares'] * 100  # 简化估算
                for s in to_sell
            )
            target_value = estimated_cash * weight / (1 + self.COMMISSION_RATE)
            orders.append({
                'ts_code': ts_code,
                'action': 'buy',
                'target_value': target_value,
                'reason': 'new position'
            })

        # 需要调整仓位的股票
        to_adjust = current_stocks & target_stocks
        for ts_code in to_adjust:
            current_value = current_positions[ts_code]['shares'] * 100  # 简化
            target_weight = target_portfolio[target_portfolio['security_id'] == ts_code]['weight'].iloc[0]
            # 简化处理，这里可以添加更精确的调整逻辑

        return orders

    def _execute_orders(self, orders: List[Dict], positions: Dict,
                       cash: float, trade_date: str) -> Tuple[float, Dict, List[Dict]]:
        """执行调仓指令"""
        new_positions = positions.copy()
        trades = []

        # 先执行卖出
        for order in orders:
            if order['action'] != 'sell':
                continue

            ts_code = order['ts_code']
            shares = order['shares']

            # 获取当日价格
            stock_data = self.get_stock_data(ts_code, trade_date, trade_date)
            if stock_data.empty:
                continue

            price = stock_data['open'].iloc[0]  # 开盘价成交
            pct_chg = stock_data['pct_chg'].iloc[0]

            # 检查是否跌停（无法卖出）
            if self.is_limit_down(pct_chg):
                logger.warning(f"{ts_code} limit down on {trade_date}, cannot sell")
                continue

            # 计算成交金额和成本
            amount = shares * price
            cost = self.calc_transaction_cost(amount, is_buy=False)

            # 更新现金和持仓
            cash += amount - cost
            del new_positions[ts_code]

            trades.append({
                'date': trade_date,
                'ts_code': ts_code,
                'action': 'sell',
                'shares': shares,
                'price': price,
                'amount': amount,
                'cost': cost
            })

        # 再执行买入
        for order in orders:
            if order['action'] != 'buy':
                continue

            ts_code = order['ts_code']
            target_value = order['target_value']

            # 获取当日价格
            stock_data = self.get_stock_data(ts_code, trade_date, trade_date)
            if stock_data.empty:
                continue

            price = stock_data['open'].iloc[0]
            pct_chg = stock_data['pct_chg'].iloc[0]

            # 检查是否涨停（无法买入）
            if self.is_limit_up(pct_chg):
                logger.warning(f"{ts_code} limit up on {trade_date}, cannot buy")
                continue

            # 计算可买入股数（考虑交易成本）
            max_amount = cash / (1 + self.COMMISSION_RATE + self.TRANSFER_FEE_RATE)
            buy_amount = min(target_value, max_amount)
            shares = self.round_lot(buy_amount / price)

            if shares < 100:  # 最小交易单位
                continue

            # 计算成本
            amount = shares * price
            cost = self.calc_transaction_cost(amount, is_buy=True)

            if amount + cost > cash:
                continue

            # 更新现金和持仓
            cash -= (amount + cost)
            new_positions[ts_code] = {
                'shares': shares,
                'cost_price': price
            }

            trades.append({
                'date': trade_date,
                'ts_code': ts_code,
                'action': 'buy',
                'shares': shares,
                'price': price,
                'amount': amount,
                'cost': cost
            })

        return cash, new_positions, trades

    def _calculate_backtest_metrics(self, nav_history: List[Dict],
                                   trade_records: List[Dict],
                                   benchmark: str,
                                   initial_capital: float) -> Dict:
        """计算回测指标"""
        nav_df = pd.DataFrame(nav_history)

        if nav_df.empty:
            return {}

        # 计算收益率
        nav_df['return'] = nav_df['nav'].pct_change()
        nav_df['cum_return'] = nav_df['nav'] / initial_capital - 1

        # 年化收益
        total_days = len(nav_df)
        annual_return = (nav_df['nav'].iloc[-1] / initial_capital) ** (252 / total_days) - 1

        # 最大回撤
        nav_df['cummax'] = nav_df['nav'].cummax()
        nav_df['drawdown'] = (nav_df['nav'] - nav_df['cummax']) / nav_df['cummax']
        max_drawdown = nav_df['drawdown'].min()

        # 夏普比率
        if nav_df['return'].std() > 0:
            sharpe = nav_df['return'].mean() / nav_df['return'].std() * np.sqrt(252)
        else:
            sharpe = 0

        # 卡玛比率
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # 换手率
        total_buy = sum(t['amount'] for t in trade_records if t['action'] == 'buy')
        avg_nav = nav_df['nav'].mean()
        turnover_rate = total_buy / avg_nav if avg_nav > 0 else 0

        # 胜率
        win_days = (nav_df['return'] > 0).sum()
        total_trade_days = nav_df['return'].notna().sum()
        win_rate = win_days / total_trade_days if total_trade_days > 0 else 0

        return {
            'total_return': nav_df['cum_return'].iloc[-1],
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'turnover_rate': turnover_rate,
            'win_rate': win_rate,
            'nav_history': nav_df[['date', 'nav', 'cum_return', 'drawdown']].to_dict('records'),
            'trade_records': trade_records
        }

    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()


@with_db
def run_backtest_task(backtest_id: int, db: Session = None) -> Optional[BacktestResult]:
    """
    运行回测任务

    Args:
        backtest_id: 回测ID
        db: 数据库会话

    Returns:
        回测结果
    """
    # 更新回测状态
    backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
    if not backtest:
        logger.error(f"Backtest {backtest_id} not found")
        return None

    backtest.status = 'running'
    db.commit()

    try:
        engine = ABShareBacktestEngine(db)
        result = engine.run_backtest(backtest_id)

        # 保存结果
        backtest_result = BacktestResult(
            backtest_id=backtest_id,
            total_return=result['total_return'],
            annual_return=result['annual_return'],
            max_drawdown=result['max_drawdown'],
            sharpe_ratio=result['sharpe_ratio'],
            calmar_ratio=result['calmar_ratio'],
            turnover_rate=result['turnover_rate'],
            win_rate=result['win_rate']
        )

        db.add(backtest_result)

        # 保存交易记录
        for trade in result['trade_records']:
            trade_record = BacktestTrade(
                backtest_id=backtest_id,
                trade_date=trade['date'],
                security_id=trade['ts_code'],
                action=trade['action'],
                quantity=trade['shares'],
                price=trade['price'],
                transaction_cost=trade['cost']
            )
            db.add(trade_record)

        backtest.status = 'completed'
        db.commit()

        logger.info(f"Backtest {backtest_id} completed: annual_return={result['annual_return']:.2%}")

        return backtest_result

    except Exception as e:
        logger.error(f"Backtest {backtest_id} failed: {e}")
        backtest.status = 'failed'
        db.commit()
        return None
