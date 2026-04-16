"""
简单回测测试
使用真实数据进行回测验证
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from app.db.base import SessionLocal
from app.models.market import StockDaily, IndexDaily, StockBasic
from sqlalchemy import func
import pandas as pd
import numpy as np

def get_stock_data(db, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取股票数据"""
    query = db.query(StockDaily).filter(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date >= start_date,
        StockDaily.trade_date <= end_date
    ).order_by(StockDaily.trade_date)

    records = query.all()
    if not records:
        return pd.DataFrame()

    data = [{
        'trade_date': r.trade_date,
        'open': float(r.open) if r.open else None,
        'high': float(r.high) if r.high else None,
        'low': float(r.low) if r.low else None,
        'close': float(r.close) if r.close else None,
        'volume': float(r.vol) if r.vol else None,
    } for r in records]

    df = pd.DataFrame(data)
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df.set_index('trade_date', inplace=True)
    return df


def simple_moving_average_strategy(df: pd.DataFrame, short_window: int = 5, long_window: int = 20) -> pd.DataFrame:
    """简单均线策略"""
    df = df.copy()
    df['ma_short'] = df['close'].rolling(window=short_window).mean()
    df['ma_long'] = df['close'].rolling(window=long_window).mean()

    # 生成信号
    df['signal'] = 0
    df.loc[df['ma_short'] > df['ma_long'], 'signal'] = 1
    df.loc[df['ma_short'] < df['ma_long'], 'signal'] = -1

    return df


def backtest(df: pd.DataFrame, initial_capital: float = 100000) -> dict:
    """简单回测"""
    df = df.copy()
    df['returns'] = df['close'].pct_change()
    df['strategy_returns'] = df['signal'].shift(1) * df['returns']

    # 计算累计收益
    df['cum_returns'] = (1 + df['returns']).cumprod()
    df['cum_strategy_returns'] = (1 + df['strategy_returns']).cumprod()

    # 计算各项指标
    total_return = df['cum_strategy_returns'].iloc[-1] - 1
    benchmark_return = df['cum_returns'].iloc[-1] - 1

    # 年化收益
    days = len(df)
    annual_return = (1 + total_return) ** (252 / days) - 1

    # 最大回撤
    cum_values = df['cum_strategy_returns']
    running_max = cum_values.cummax()
    drawdown = (cum_values - running_max) / running_max
    max_drawdown = drawdown.min()

    # 夏普比率
    risk_free_rate = 0.03
    excess_returns = df['strategy_returns'].dropna() - risk_free_rate / 252
    sharpe_ratio = np.sqrt(252) * excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0

    # 胜率
    winning_days = (df['strategy_returns'] > 0).sum()
    total_trading_days = (df['signal'] != 0).sum()
    win_rate = winning_days / total_trading_days if total_trading_days > 0 else 0

    return {
        'total_return': total_return,
        'benchmark_return': benchmark_return,
        'annual_return': annual_return,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'win_rate': win_rate,
        'final_capital': initial_capital * (1 + total_return),
    }


def main():
    print("=" * 60)
    print("简单回测测试 - 使用真实数据")
    print("=" * 60)

    db = SessionLocal()

    # 获取有足够数据的股票
    stock_counts = db.query(
        StockDaily.ts_code,
        func.count(StockDaily.id).label('count')
    ).group_by(StockDaily.ts_code).having(func.count(StockDaily.id) >= 50).all()

    print(f"\n找到 {len(stock_counts)} 只有足够数据的股票")

    # 选择几只股票进行测试
    test_stocks = ['600000.SH', '600036.SH', '000001.SZ', '000002.SZ']

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    print(f"\n回测区间: {start_date} ~ {end_date}")
    print(f"策略: 双均线策略 (5日/20日)")
    print("-" * 60)

    results = []
    for ts_code in test_stocks:
        # 获取股票名称
        stock = db.query(StockBasic).filter(StockBasic.ts_code == ts_code).first()
        stock_name = stock.name if stock else ts_code

        df = get_stock_data(db, ts_code, start_date, end_date)
        if df.empty or len(df) < 20:
            print(f"{ts_code} {stock_name}: 数据不足")
            continue

        df = simple_moving_average_strategy(df)
        result = backtest(df)

        results.append({
            'ts_code': ts_code,
            'name': stock_name,
            **result
        })

        print(f"\n{ts_code} {stock_name}")
        print(f"  总收益: {result['total_return']*100:.2f}%")
        print(f"  基准收益: {result['benchmark_return']*100:.2f}%")
        print(f"  年化收益: {result['annual_return']*100:.2f}%")
        print(f"  最大回撤: {result['max_drawdown']*100:.2f}%")
        print(f"  夏普比率: {result['sharpe_ratio']:.2f}")
        print(f"  胜率: {result['win_rate']*100:.1f}%")

    # 汇总
    if results:
        print("\n" + "=" * 60)
        print("汇总统计")
        print("=" * 60)

        avg_return = np.mean([r['total_return'] for r in results])
        avg_benchmark = np.mean([r['benchmark_return'] for r in results])
        avg_sharpe = np.mean([r['sharpe_ratio'] for r in results])

        print(f"平均策略收益: {avg_return*100:.2f}%")
        print(f"平均基准收益: {avg_benchmark*100:.2f}%")
        print(f"平均夏普比率: {avg_sharpe:.2f}")

        # 超额收益
        excess_return = avg_return - avg_benchmark
        print(f"超额收益: {excess_return*100:.2f}%")

    db.close()
    print("\n回测测试完成!")


if __name__ == "__main__":
    main()
