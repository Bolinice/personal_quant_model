"""
量化分析流程测试
使用真实数据验证因子计算、因子分析、回测全流程
"""
import sys
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.db.base import SessionLocal
from app.models.market import StockDaily, StockBasic, IndexDaily
from app.core.logging import logger


def get_stock_data(db, ts_codes, start_date, end_date):
    """批量获取股票数据"""
    from sqlalchemy import func

    data = db.query(StockDaily).filter(
        StockDaily.ts_code.in_(ts_codes),
        StockDaily.trade_date >= start_date,
        StockDaily.trade_date <= end_date
    ).order_by(StockDaily.ts_code, StockDaily.trade_date).all()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'ts_code': d.ts_code,
        'trade_date': d.trade_date,
        'open': float(d.open) if d.open else None,
        'high': float(d.high) if d.high else None,
        'low': float(d.low) if d.low else None,
        'close': float(d.close) if d.close else None,
        'volume': float(d.vol) if d.vol else None,
        'amount': float(d.amount) if d.amount else None,
        'pct_chg': float(d.pct_chg) if d.pct_chg else None,
    } for d in data])

    return df


def calc_factors_from_data(df):
    """从行情数据计算因子"""
    results = []

    for ts_code in df['ts_code'].unique():
        stock_df = df[df['ts_code'] == ts_code].sort_values('trade_date')

        if len(stock_df) < 60:
            continue

        # 计算各类因子
        close = stock_df['close'].values
        volume = stock_df['volume'].values
        amount = stock_df['amount'].values
        pct_chg = stock_df['pct_chg'].values

        # 动量因子
        mom_20d = close[-1] / close[-21] - 1 if len(close) >= 21 else None
        mom_60d = close[-1] / close[-61] - 1 if len(close) >= 61 else None

        # 波动率因子
        vol_20d = np.std(pct_chg[-20:] / 100) * np.sqrt(252) if len(pct_chg) >= 20 else None
        vol_60d = np.std(pct_chg[-60:] / 100) * np.sqrt(252) if len(pct_chg) >= 60 else None

        # 流动性因子
        avg_amount_20d = np.mean(amount[-20:]) / 1e8 if len(amount) >= 20 else None

        # 反转因子（过去N日收益率）
        reversal_5d = close[-1] / close[-6] - 1 if len(close) >= 6 else None

        # 均线偏离
        ma20 = np.mean(close[-20:]) if len(close) >= 20 else None
        ma_deviation = (close[-1] - ma20) / ma20 if ma20 else None

        results.append({
            'ts_code': ts_code,
            'mom_20d': mom_20d,
            'mom_60d': mom_60d,
            'vol_20d': vol_20d,
            'vol_60d': vol_60d,
            'avg_amount_20d': avg_amount_20d,
            'reversal_5d': reversal_5d,
            'ma_deviation': ma_deviation,
        })

    return pd.DataFrame(results)


def calc_ic(factor_values, returns):
    """计算IC"""
    # 去重
    factor_values = factor_values[~factor_values.index.duplicated(keep='first')]
    returns = returns[~returns.index.duplicated(keep='first')]

    aligned = pd.DataFrame({
        'factor': factor_values,
        'return': returns
    }).dropna()

    if len(aligned) < 10:
        return np.nan

    # Rank IC
    return aligned['factor'].rank().corr(aligned['return'].rank())


def calc_group_returns(factor_values, returns, n_groups=5):
    """分层回测"""
    # 去重
    factor_values = factor_values[~factor_values.index.duplicated(keep='first')]
    returns = returns[~returns.index.duplicated(keep='first')]

    aligned = pd.DataFrame({
        'factor': factor_values,
        'return': returns
    }).dropna()

    if len(aligned) < n_groups * 2:
        return None, np.nan

    # 分组
    aligned['group'] = pd.qcut(aligned['factor'], n_groups, labels=False, duplicates='drop')

    # 各组平均收益
    group_returns = aligned.groupby('group')['return'].mean()

    # 多空收益
    long_short = group_returns.iloc[-1] - group_returns.iloc[0]

    return group_returns, long_short


def run_factor_analysis(factor_df, return_df, factor_col):
    """运行因子分析"""
    dates = sorted(factor_df['trade_date'].unique())

    ic_series = []
    group_returns_list = []

    for i, date in enumerate(dates[:-1]):
        next_date = dates[i + 1]

        # 当日因子值
        factor_today = factor_df[factor_df['trade_date'] == date].set_index('ts_code')[factor_col]

        # 次日收益率
        ret_next = return_df[return_df['trade_date'] == next_date].set_index('ts_code')['pct_chg'] / 100

        # 计算IC
        ic = calc_ic(factor_today, ret_next)
        ic_series.append({'date': date, 'ic': ic})

        # 分层回测
        group_ret, ls = calc_group_returns(factor_today, ret_next)
        if group_ret is not None:
            group_returns_list.append({
                'date': date,
                **{f'group_{g}': r for g, r in group_ret.items()},
                'long_short': ls
            })

    ic_df = pd.DataFrame(ic_series)
    group_df = pd.DataFrame(group_returns_list)

    # IC统计
    ic_stats = {
        'ic_mean': ic_df['ic'].mean(),
        'ic_std': ic_df['ic'].std(),
        'icir': ic_df['ic'].mean() / ic_df['ic'].std() if ic_df['ic'].std() > 0 else 0,
        'ic_positive_ratio': (ic_df['ic'] > 0).mean(),
    }

    return ic_df, group_df, ic_stats


def simple_backtest(prices_df, initial_capital=100000, rebalance_days=20):
    """简单回测 - 买入持有策略"""
    dates = sorted(prices_df['trade_date'].unique())

    if len(dates) < 2:
        return {'total_return': 0, 'annual_return': 0, 'max_drawdown': 0, 'sharpe_ratio': 0, 'nav_df': pd.DataFrame()}

    # 首日等权买入
    first_date = dates[0]
    day_prices = prices_df[prices_df['trade_date'] == first_date]

    holdings = {}
    cash = initial_capital
    n_stocks = len(day_prices)

    if n_stocks == 0:
        return {'total_return': 0, 'annual_return': 0, 'max_drawdown': 0, 'sharpe_ratio': 0, 'nav_df': pd.DataFrame()}

    per_stock = initial_capital * 0.95 / n_stocks

    for _, row in day_prices.iterrows():
        ts_code = row['ts_code']
        price = row['close']
        if price and price > 0:
            shares = int(per_stock / price / 100) * 100
            if shares >= 100:
                cost = shares * price * 1.0003
                if cost <= cash:
                    holdings[ts_code] = shares
                    cash -= cost

    # 计算每日净值
    nav_history = []
    for date in dates:
        day_prices = prices_df[prices_df['trade_date'] == date]

        position_value = 0
        for ts_code, shares in holdings.items():
            price_row = day_prices[day_prices['ts_code'] == ts_code]
            if not price_row.empty:
                price = price_row['close'].iloc[0]
                if price:
                    position_value += shares * price

        total_nav = cash + position_value
        nav_history.append({
            'date': date,
            'nav': total_nav,
            'cash': cash,
            'position_value': position_value
        })

    nav_df = pd.DataFrame(nav_history)

    if len(nav_df) < 2:
        return {'total_return': 0, 'annual_return': 0, 'max_drawdown': 0, 'sharpe_ratio': 0, 'nav_df': nav_df}

    # 计算指标
    nav_df['return'] = nav_df['nav'].pct_change()
    total_return = nav_df['nav'].iloc[-1] / initial_capital - 1
    annual_return = (1 + total_return) ** (252 / len(nav_df)) - 1

    # 最大回撤
    nav_df['cummax'] = nav_df['nav'].cummax()
    nav_df['drawdown'] = (nav_df['nav'] - nav_df['cummax']) / nav_df['cummax']
    max_drawdown = nav_df['drawdown'].min()

    # 夏普比率
    returns = nav_df['return'].dropna()
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

    return {
        'total_return': total_return,
        'annual_return': annual_return,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe,
        'nav_df': nav_df
    }


def main():
    print("=" * 70)
    print("量化分析流程测试")
    print("=" * 70)

    db = SessionLocal()

    # 1. 获取股票池
    print("\n[1] 获取股票池...")
    stocks = db.query(StockBasic).filter(
        StockBasic.list_status == 'L'
    ).limit(100).all()  # 取前100只测试

    ts_codes = [s.ts_code for s in stocks]
    print(f"    股票数量: {len(ts_codes)}")

    # 2. 获取行情数据
    print("\n[2] 获取行情数据...")
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

    price_df = get_stock_data(db, ts_codes, start_date, end_date)
    print(f"    数据量: {len(price_df)} 条")
    print(f"    日期范围: {price_df['trade_date'].min()} ~ {price_df['trade_date'].max()}")

    if price_df.empty:
        print("    无数据，请先同步数据")
        return

    # 3. 计算因子
    print("\n[3] 计算因子...")
    # 按日期计算因子
    all_factor_df = []
    dates = sorted(price_df['trade_date'].unique())

    for date in dates[-30:]:  # 最近30天
        day_data = price_df[price_df['trade_date'] <= date]
        factor_df = calc_factors_from_data(day_data)
        if not factor_df.empty:
            factor_df['trade_date'] = date
            all_factor_df.append(factor_df)

    factor_df = pd.concat(all_factor_df, ignore_index=True)
    print(f"    因子数据量: {len(factor_df)} 条")
    print(f"    因子列表: {[c for c in factor_df.columns if c not in ['ts_code', 'trade_date']]}")

    # 4. 因子分析
    print("\n[4] 因子分析...")
    factor_cols = ['mom_20d', 'mom_60d', 'vol_20d', 'reversal_5d', 'ma_deviation']

    analysis_results = []
    for factor_col in factor_cols:
        if factor_col not in factor_df.columns:
            continue

        ic_df, group_df, ic_stats = run_factor_analysis(factor_df, price_df, factor_col)

        print(f"\n    {factor_col}:")
        print(f"      IC均值: {ic_stats['ic_mean']:.4f}")
        print(f"      ICIR: {ic_stats['icir']:.4f}")
        print(f"      IC正向比例: {ic_stats['ic_positive_ratio']:.2%}")

        analysis_results.append({
            'factor': factor_col,
            **ic_stats
        })

    analysis_df = pd.DataFrame(analysis_results)

    # 5. 筛选有效因子
    print("\n[5] 筛选有效因子...")
    valid_factors = analysis_df[
        (abs(analysis_df['ic_mean']) > 0.02) &
        (abs(analysis_df['icir']) > 0.5)
    ]
    print(f"    有效因子数量: {len(valid_factors)}")
    if not valid_factors.empty:
        print(f"    有效因子: {valid_factors['factor'].tolist()}")

    # 6. 简单回测
    print("\n[6] 简单回测...")
    # 使用低波动率因子选股（vol_20d IC为负，说明低波动率股票收益更好）
    latest_date = price_df['trade_date'].max()
    latest_factors = factor_df[factor_df['trade_date'] == latest_date]

    if not latest_factors.empty and 'vol_20d' in latest_factors.columns:
        # 选择波动率最低的股票（低波动异象）
        low_vol_stocks = latest_factors.nsmallest(20, 'vol_20d')['ts_code'].tolist()

        # 获取这些股票的历史数据
        backtest_df = price_df[price_df['ts_code'].isin(low_vol_stocks)]

        if not backtest_df.empty:
            result = simple_backtest(backtest_df)

            print(f"\n    低波动策略回测结果:")
            print(f"      总收益: {result['total_return']:.2%}")
            print(f"      年化收益: {result['annual_return']:.2%}")
            print(f"      最大回撤: {result['max_drawdown']:.2%}")
            print(f"      夏普比率: {result['sharpe_ratio']:.2f}")

    # 对比：高动量策略
    if not latest_factors.empty and 'mom_20d' in latest_factors.columns:
        # 选择动量最高的股票
        high_mom_stocks = latest_factors.nlargest(20, 'mom_20d')['ts_code'].tolist()

        backtest_df = price_df[price_df['ts_code'].isin(high_mom_stocks)]

        if not backtest_df.empty:
            result = simple_backtest(backtest_df)

            print(f"\n    高动量策略回测结果:")
            print(f"      总收益: {result['total_return']:.2%}")
            print(f"      年化收益: {result['annual_return']:.2%}")
            print(f"      最大回撤: {result['max_drawdown']:.2%}")
            print(f"      夏普比率: {result['sharpe_ratio']:.2f}")

    # 基准：等权持有所有股票
    all_stocks = price_df['ts_code'].unique()[:20]
    benchmark_df = price_df[price_df['ts_code'].isin(all_stocks)]

    if not benchmark_df.empty:
        result = simple_backtest(benchmark_df)

        print(f"\n    基准(等权)回测结果:")
        print(f"      总收益: {result['total_return']:.2%}")
        print(f"      年化收益: {result['annual_return']:.2%}")
        print(f"      最大回撤: {result['max_drawdown']:.2%}")
        print(f"      夏普比率: {result['sharpe_ratio']:.2f}")

    # 7. 汇总
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

    print("\n因子分析汇总:")
    print(analysis_df.to_string(index=False))

    db.close()


if __name__ == "__main__":
    main()
