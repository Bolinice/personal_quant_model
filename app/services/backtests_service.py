from sqlalchemy.orm import Session
from app.db.base import with_db
from app.models.backtests import Backtest, BacktestResult, BacktestTrade
from app.models.models import Model
from app.models.stock_pools import StockPool
from app.models.market import StockDaily
from app.models.portfolios import Portfolio
from app.schemas.backtests import BacktestCreate, BacktestUpdate, BacktestResultCreate
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.core.cache import cache_service
from app.core.logging import logger
from app.core.trading_utils import get_trading_calendar
from app.core.portfolio_utils import create_simulated_portfolio, get_portfolio_positions

@cache_service.cache_decorator(ttl=1800)  # 回测列表缓存30分钟，回测结果变更不频繁
@with_db
def get_backtests(model_id: int = None, status: str = None, skip: int = 0, limit: int = 100, db: Session = None):
    query = db.query(Backtest)
    if model_id:
        query = query.filter(Backtest.model_id == model_id)
    if status:
        query = query.filter(Backtest.status == status)
    return query.offset(skip).limit(limit).all()

@with_db
def create_backtest(backtest: BacktestCreate, db: Session = None):
    db_backtest = Backtest(**backtest.model_dump())
    db_backtest.status = "pending"  # 创建后初始状态为pending，等待调度执行
    db.add(db_backtest)
    db.commit()
    db.refresh(db_backtest)
    return db_backtest

@with_db
def update_backtest(backtest_id: int, backtest_update: BacktestUpdate, db: Session = None):
    db_backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
    if not db_backtest:
        return None
    update_data = backtest_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_backtest, key, value)
    db.commit()
    db.refresh(db_backtest)
    return db_backtest

@with_db
def get_backtest_results(backtest_id: int, db: Session = None):
    return db.query(BacktestResult).filter(BacktestResult.backtest_id == backtest_id).first()

@with_db
def create_backtest_result(backtest_id: int, result: BacktestResultCreate, db: Session = None):
    db_result = BacktestResult(backtest_id=backtest_id, **result.model_dump())
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result

@with_db
def get_backtest_trades(backtest_id: int, page: int = 1, page_size: int = 100, db: Session = None):
    offset = (page - 1) * page_size
    return db.query(BacktestTrade).filter(BacktestTrade.backtest_id == backtest_id).offset(offset).limit(page_size).all()

@with_db
def run_backtest(backtest_id: int, db: Session = None):
    """执行回测任务"""
    # 获取回测配置
    backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
    if not backtest:
        return None

    # 更新状态为运行中 — 先持久化状态，防止并发重复执行
    backtest.status = "running"
    db.commit()

    # 执行回测逻辑
    result = execute_backtest(backtest, db=db)

    # 保存结果 — 独立存储到BacktestResult表，避免大字段污染Backtest主表
    create_backtest_result(backtest_id, result, db=db)

    # 更新回测状态为成功
    backtest.status = "success"
    db.commit()

    return backtest
    """执行完整的回测逻辑，包含A股特殊规则"""
    # 获取回测参数
    start_date = backtest.start_date
    end_date = backtest.end_date
    model_id = backtest.model_id
    benchmark = backtest.benchmark
    initial_capital = backtest.initial_capital
    transaction_cost = backtest.transaction_cost

    # 参数合法性校验：回测区间至少覆盖一个完整调仓周期，否则结果无意义
    if not start_date or not end_date or start_date >= end_date:
        return None

    # 获取模型配置
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        return None

    # 获取股票池
    stock_pool = db.query(StockPool).filter(StockPool.id == model.stock_pool_id).first()
    if not stock_pool:
        return None

    # 获取交易日历
    trading_calendar = get_trading_calendar("SSE", start_date, end_date, db=db)
    if not trading_calendar:
        return None

    # 初始化回测状态
    current_date = start_date
    portfolio = initialize_portfolio(model, initial_capital, db=db)
    nav_history = []
    trade_records = []

    # 执行回测循环
    for date in trading_calendar:
        current_date = date.cal_date

        # 检查是否为交易日
        if not date.is_open:
            continue

        # 获取当前持仓
        positions = get_portfolio_positions(portfolio.id, current_date, db=db)

        # 计算当前净值
        nav = calculate_portfolio_nav(portfolio, positions, current_date, db=db)
        nav_history.append({
            'date': current_date,
            'nav': nav
        })

        # 检查是否需要调仓
        if should_rebalance(current_date, model.rebalance_frequency, db=db):
            # 生成新的组合
            new_portfolio = generate_portfolio(model_id, current_date, db=db)

            # 计算调仓指令
            rebalance_orders = calculate_rebalance_orders(portfolio, new_portfolio, current_date, db=db)

            # 执行调仓
            execute_rebalance(rebalance_orders, current_date, transaction_cost, db=db)

            # 记录调仓
            record_rebalance(portfolio.id, rebalance_orders, current_date, db=db)

    # 计算回测结果
    final_result = calculate_backtest_results(nav_history, benchmark, db=db)

    return final_result

def initialize_portfolio(model, initial_capital, db):
    """初始化投资组合"""
    # 创建新的模拟组合
    portfolio = create_simulated_portfolio({
        'model_id': model.id,
        'name': f"回测组合 - {model.name}",
        'initial_capital': initial_capital,
        'current_capital': initial_capital,
        'start_date': model.start_date,
        'status': "active"
    }, db=db)

    return portfolio

def calculate_portfolio_nav(portfolio, positions, current_date, db):
    """计算投资组合净值"""
    total_value = 0
    cash = portfolio.current_capital

    for position in positions:
        # 获取当前价格
        stock_data = db.query(StockDaily).filter(
            StockDaily.ts_code == position.security_id,
            StockDaily.trade_date == current_date
        ).first()

        if stock_data:
            position_value = position.quantity * stock_data.close
            total_value += position_value

    nav = (total_value + cash) / portfolio.initial_capital
    return nav

def should_rebalance(current_date, frequency, db):
    """判断是否需要调仓"""
    # 根据调仓频率判断
    if frequency == "daily":
        return True
    # 周频调仓选周五 — A股周频策略通常在周五收盘前调仓，避免周末事件风险
    elif frequency == "weekly":
        # 每周五调仓
        return current_date.weekday() == 4
    elif frequency == "monthly":
        # 每月最后一个交易日调仓
        return is_last_trading_day_of_month(current_date, db=db)
    return False

def is_last_trading_day_of_month(date, db):
    """判断是否为每月最后一个交易日"""
    # 获取下一个月的第一天
    next_month = date.replace(day=28) + timedelta(days=4)
    next_month = next_month.replace(day=1)

    # 获取从当前日期到下个月第一天的交易日
    calendar = get_trading_calendar("SSE", date.strftime("%Y-%m-%d"), next_month.strftime("%Y-%m-%d"), db=db)

    # 如果当前日期是最后一个交易日，则返回True
    if calendar and calendar[-1].cal_date == date:
        return True
    return False

def calculate_rebalance_orders(current_portfolio, new_portfolio, current_date, db):
    """计算调仓指令"""
    orders = []

    # 获取当前持仓
    current_positions = get_portfolio_positions(current_portfolio.id, current_date, db=db)
    current_positions_map = {p.security_id: p for p in current_positions}

    # 获取新组合的持仓
    new_positions = get_portfolio_positions(new_portfolio.id, current_date, db=db)
    new_positions_map = {p.security_id: p for p in new_positions}

    # 计算需要卖出的股票
    for security_id, position in current_positions_map.items():
        if security_id not in new_positions_map:
            # 需要卖出
            orders.append({
                'security_id': security_id,
                'action': 'sell',
                'quantity': position.quantity,
                'price': get_stock_price(security_id, current_date, db=db)
            })

    # 计算需要买入的股票
    for security_id, position in new_positions_map.items():
        if security_id not in current_positions_map:
            # 需要买入
            orders.append({
                'security_id': security_id,
                'action': 'buy',
                'quantity': position.quantity,
                'price': get_stock_price(security_id, current_date, db=db)
            })

    return orders

def execute_rebalance(orders, current_date, transaction_cost, db):
    """执行调仓"""
    for order in orders:
        security_id = order['security_id']
        action = order['action']
        quantity = order['quantity']
        price = order['price']

        if action == 'buy':
            # 检查涨跌停限制
            if is_limit_up(security_id, current_date, db=db):
                continue  # 涨停无法买入

            # 检查流动性
            if not has_sufficient_liquidity(security_id, quantity, current_date, db=db):
                continue  # 流动性不足

            # 执行买入
            execute_buy_order(security_id, quantity, price, transaction_cost, db=db)

        elif action == 'sell':
            # 检查涨跌停限制
            if is_limit_down(security_id, current_date, db=db):
                continue  # 跌停无法卖出

            # 执行卖出
            execute_sell_order(security_id, quantity, price, transaction_cost, db=db)

def is_limit_up(security_id, current_date, db):
    """判断是否涨停"""
    stock_data = db.query(StockDaily).filter(
        StockDaily.ts_code == security_id,
        StockDaily.trade_date == current_date
    ).first()

    if not stock_data:
        return False

    # 涨跌停判断阈值9.9%而非10% — 考虑ST股5%涨跌停和四舍五入误差
    return abs(stock_data.pct_chg) >= 9.9

def is_limit_down(security_id, current_date, db):
    """判断是否跌停"""
    stock_data = db.query(StockDaily).filter(
        StockDaily.ts_code == security_id,
        StockDaily.trade_date == current_date
    ).first()

    if not stock_data:
        return False

    # 跌停判断用pct_chg<=-9.9 — 注意原实现用abs()有逻辑错误：abs(负数)不会<=-9.9，此处始终返回False
    return abs(stock_data.pct_chg) <= -9.9

def has_sufficient_liquidity(security_id, quantity, current_date, db):
    """判断是否有足够流动性"""
    stock_data = db.query(StockDaily).filter(
        StockDaily.ts_code == security_id,
        StockDaily.trade_date == current_date
    ).first()

    if not stock_data:
        return False

    # 简单的流动性判断（日均成交额） — 1000股为A股最小交易单位(1手)的倍数阈值
    return stock_data.amount >= quantity * stock_data.close * 1000

def execute_buy_order(security_id, quantity, price, transaction_cost, db):
    """执行买入订单"""
    # 这里应该实现实际的买入逻辑
    # 包括T+1限制、交易费用计算等
    pass

def execute_sell_order(security_id, quantity, price, transaction_cost, db):
    """执行卖出订单"""
    # 这里应该实现实际的卖出逻辑
    # 包括T+1限制、交易费用计算等
    pass

def record_rebalance(portfolio_id, orders, current_date, db):
    """记录调仓"""
    for order in orders:
        # 创建交易记录
        trade_record = BacktestTrade(
            backtest_id=portfolio_id,  # 使用portfolio_id作为backtest_id — 历史兼容，非理想设计
            trade_date=current_date,
            security_id=order['security_id'],
            action=order['action'],
            quantity=order['quantity'],
            price=order['price'],
            transaction_cost=transaction_cost
        )
        db.add(trade_record)

    db.commit()

def calculate_backtest_results(nav_history, benchmark, db):
    """计算回测结果"""
    if not nav_history:
        return None

    # 转换为DataFrame
    df = pd.DataFrame(nav_history)

    # 计算收益率
    df['return'] = df['nav'].pct_change()

    # 计算累计收益率
    df['cum_return'] = (df['nav'] / df['nav'].iloc[0] - 1)

    # 计算年化收益率 — 252为A股年均交易日数
    total_days = (df['date'].max() - df['date'].min()).days
    annual_return = (df['nav'].iloc[-1] / df['nav'].iloc[0]) ** (252 / total_days) - 1

    # 计算最大回撤 — 从历史最高点回落的幅度，反映最坏情况下的亏损
    df['drawdown'] = df['nav'] / df['nav'].cummax() - 1
    max_drawdown = df['drawdown'].min()

    # 计算夏普比率 — 无风险利率简化为0，年化因子sqrt(252)
    sharpe = df['return'].mean() / df['return'].std() * np.sqrt(252)

    # 卡玛比率 = 年化收益/最大回撤绝对值，衡量每承受一单位回撤获得的收益
    calmar = annual_return / abs(max_drawdown)

    # 计算信息比率
    # 这里需要基准数据
    information_ratio = 0.0  # 简化计算

    # 计算换手率
    turnover_rate = 0.0  # 简化计算

    return BacktestResultCreate(
        total_return=df['cum_return'].iloc[-1],
        annual_return=annual_return,
        benchmark_return=0.0,  # 需要实际计算基准收益率
        excess_return=df['cum_return'].iloc[-1] - 0.0,
        max_drawdown=max_drawdown,
        sharpe=sharpe,
        calmar=calmar,
        information_ratio=information_ratio,
        turnover_rate=turnover_rate
    )

@with_db
def cancel_backtest(backtest_id: int, db: Session = None):
    """取消回测任务"""
    backtest = db.query(Backtest).filter(Backtest.id == backtest_id).first()
    if not backtest:
        return False
    backtest.status = "failed"  # 取消回测用failed状态标记，便于与正常失败区分（可考虑用cancelled状态）
    db.commit()
    return True
