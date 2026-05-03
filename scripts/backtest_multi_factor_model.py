"""
多因子选股模型回测脚本
集成 MultiFactorModel 与 ABShareBacktestEngine，实现完整的历史回测
"""
import sys
sys.path.insert(0, '.')

import argparse
import time
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.multi_factor_model import MultiFactorModel
from app.core.backtest_engine import ABShareBacktestEngine, BacktestState
from app.core.performance_analyzer import PerformanceAnalyzer
from scripts.script_utils import build_in_clause


def load_universe(conn, universe_type: str = 'hs300') -> list[str]:
    """加载股票池"""
    if universe_type == 'hs300':
        rows = conn.execute(text(
            "SELECT ts_code FROM index_components WHERE index_code = '000300.SH'"
        )).fetchall()
        codes = [r[0] for r in rows]
        print(f"  沪深300成分股: {len(codes)} 只")
    elif universe_type == 'zz500':
        rows = conn.execute(text(
            "SELECT ts_code FROM index_components WHERE index_code = '000905.SH'"
        )).fetchall()
        codes = [r[0] for r in rows]
        print(f"  中证500成分股: {len(codes)} 只")
    elif universe_type == 'all':
        rows = conn.execute(text(
            "SELECT ts_code FROM stock_basic "
            "WHERE list_status = 'L' "
            "AND (name IS NULL OR (name NOT LIKE '%ST%' AND name NOT LIKE '%*ST%'))"
        )).fetchall()
        codes = [r[0] for r in rows]
        print(f"  全A股(在市,非ST): {len(codes)} 只")
    else:
        raise ValueError(f"Unknown universe type: {universe_type}")

    return codes


def load_trading_days(conn, start_date: str, end_date: str) -> list[date]:
    """加载交易日历"""
    rows = conn.execute(text(
        "SELECT cal_date FROM trading_calendar "
        "WHERE is_open = true AND cal_date >= :start_date AND cal_date <= :end_date "
        "ORDER BY cal_date"
    ), {"start_date": start_date, "end_date": end_date}).fetchall()

    trading_days = [pd.Timestamp(r[0]).date() for r in rows]
    print(f"  交易日: {len(trading_days)} 天")
    return trading_days


def load_price_data(conn, universe: list[str], start_date: str, end_date: str) -> dict:
    """加载价格数据"""
    in_clause, in_params = build_in_clause(universe)

    query = text(f"""
        SELECT ts_code, trade_date, open, close, pre_close, pct_chg, vol, amount
        FROM stock_daily
        WHERE ts_code IN ({in_clause})
            AND trade_date >= :start_date
            AND trade_date <= :end_date
        ORDER BY ts_code, trade_date
    """)

    params = {**in_params, "start_date": start_date, "end_date": end_date}
    df = pd.read_sql(query, conn, params=params)
    df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date

    print(f"  价格数据: {len(df)} 条, {df['ts_code'].nunique()} 只股票")

    # 转换为回测引擎需要的格式: {(ts_code, trade_date): {close, open, pct_chg, ...}}
    price_dict = {}
    for _, row in df.iterrows():
        key = (row['ts_code'], row['trade_date'])
        price_dict[key] = {
            'open': float(row['open']),
            'close': float(row['close']),
            'pre_close': float(row['pre_close']),
            'pct_chg': float(row['pct_chg']),
            'volume': float(row['vol']) if pd.notna(row['vol']) else 0.0,
            'amount': float(row['amount']) if pd.notna(row['amount']) else 0.0,
            'is_suspended': False,  # 简化处理，实际应从数据库查询
            'is_st': False,
        }

    return price_dict


def load_benchmark(conn, benchmark_code: str, start_date: str, end_date: str) -> list[dict]:
    """加载基准指数数据"""
    query = text("""
        SELECT trade_date, close
        FROM index_daily
        WHERE index_code = :benchmark_code
            AND trade_date >= :start_date
            AND trade_date <= :end_date
        ORDER BY trade_date
    """)

    df = pd.read_sql(query, conn, params={
        "benchmark_code": benchmark_code,
        "start_date": start_date,
        "end_date": end_date
    })
    df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date

    # 计算基准净值（归一化到1.0开始）
    if len(df) > 0:
        initial_close = df.iloc[0]['close']
        benchmark_nav = [
            {'trade_date': row['trade_date'], 'nav': float(row['close']) / initial_close}
            for _, row in df.iterrows()
        ]
        print(f"  基准指数({benchmark_code}): {len(benchmark_nav)} 条")
        return benchmark_nav

    return []


def create_signal_generator(model: MultiFactorModel, universe: list[str], total_value: float, top_n: int = 30):
    """创建信号生成器，供回测引擎调用"""

    def signal_generator(trade_date: date, universe_list: list[str], state: BacktestState) -> dict[str, float]:
        """
        生成目标权重信号

        Args:
            trade_date: 交易日期
            universe_list: 股票池
            state: 回测状态

        Returns:
            {ts_code: target_weight} 目标权重字典
        """
        try:
            # 使用多因子模型生成选股结果
            result = model.run(
                ts_codes=universe,
                trade_date=trade_date.strftime('%Y%m%d'),
                total_value=total_value,
                current_holdings={},  # 回测引擎会处理持仓变化
                top_n=top_n,
                exclude_list=[]
            )

            # 从组合结果中提取目标持仓（股数）
            target_holdings = result.get('target_holdings', {})

            # 转换为权重：股数 * 价格 / 总价值
            target_weights = {}
            if target_holdings:
                # 获取价格数据
                from sqlalchemy import text
                ts_codes_list = list(target_holdings.keys())
                price_query = text("""
                    SELECT DISTINCT ON (ts_code) ts_code, close as price
                    FROM stock_daily
                    WHERE ts_code = ANY(:ts_codes)
                        AND trade_date <= :trade_date
                    ORDER BY ts_code, trade_date DESC
                """)
                price_result = model.db.execute(
                    price_query,
                    {"ts_codes": ts_codes_list, "trade_date": trade_date.strftime('%Y%m%d')}
                )
                prices = {row[0]: float(row[1]) for row in price_result.fetchall()}

                # 计算每只股票的市值
                total_value_calc = sum(target_holdings[ts] * prices.get(ts, 0) for ts in target_holdings)

                # 转换为权重
                if total_value_calc > 0:
                    target_weights = {
                        ts: (target_holdings[ts] * prices.get(ts, 0)) / total_value_calc
                        for ts in target_holdings
                        if prices.get(ts, 0) > 0
                    }

            return target_weights

        except Exception as e:
            print(f"  警告: {trade_date} 信号生成失败: {e}")
            return {}

    return signal_generator


def run_backtest(
    universe_type: str = 'hs300',
    start_date: str = '2024-01-01',
    end_date: str = '2024-12-31',
    initial_capital: float = 1000000.0,
    rebalance_freq: str = 'monthly',
    factor_groups: list[str] = None,
    top_n: int = 30,
    method: str = 'equal_weight',
):
    """运行多因子模型回测"""

    print("=" * 80)
    print("多因子选股模型回测")
    print("=" * 80)

    # 默认因子组
    if factor_groups is None:
        factor_groups = ['valuation', 'quality', 'growth', 'momentum']

    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)

    print("\n[1] 加载数据...")
    t0 = time.time()

    with engine.connect() as conn:
        # 加载股票池
        universe = load_universe(conn, universe_type)

        # 加载交易日历
        trading_days = load_trading_days(conn, start_date, end_date)

        # 加载价格数据
        price_data = load_price_data(conn, universe, start_date, end_date)

        # 加载基准数据
        benchmark_code = '000300.SH' if universe_type == 'hs300' else '000905.SH'
        benchmark_nav = load_benchmark(conn, benchmark_code, start_date, end_date)

    print(f"  数据加载耗时: {time.time() - t0:.1f}s")

    # 初始化多因子模型（使用Session）
    print("\n[2] 初始化多因子模型...")
    db_session = SessionLocal()
    try:
        model = MultiFactorModel(
            db=db_session,
            factor_groups=factor_groups,
            weighting_method=method,
            neutralize_industry=True,
            neutralize_market_cap=True,
        )

        # 创建信号生成器
        signal_generator = create_signal_generator(model, universe, initial_capital, top_n)

        # 初始化回测引擎
        print("\n[3] 初始化回测引擎...")
        backtest_engine = ABShareBacktestEngine(
            db=None,  # 不需要数据库连接，数据已预加载
            commission_rate=0.00025,  # 万2.5
            stamp_tax_rate=0.001,     # 千1
            slippage_rate=0.001,      # 0.1%
        )

        # 运行回测
        print(f"\n[4] 运行回测 ({start_date} ~ {end_date})...")
        print(f"  股票池: {universe_type}")
        print(f"  调仓频率: {rebalance_freq}")
        print(f"  初始资金: {initial_capital:,.0f}")
        print(f"  因子组: {', '.join(factor_groups)}")
        print(f"  选股数量: {top_n}")
        print(f"  合成方法: {method}")

        t0 = time.time()

        backtest_result = backtest_engine.run_backtest(
            signal_generator=signal_generator,
            universe=universe,
            start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
            end_date=datetime.strptime(end_date, '%Y-%m-%d').date(),
            rebalance_freq=rebalance_freq,
            initial_capital=initial_capital,
            trading_days=trading_days,
            price_data=price_data,
            benchmark_nav=benchmark_nav,
            use_next_day_open=True,  # 使用次日开盘价成交（更真实）
        )

        print(f"  回测耗时: {time.time() - t0:.1f}s")

        # 计算绩效指标
        print("\n[5] 计算绩效指标...")

        # 检查回测结果
        if not backtest_result.get('nav_history'):
            print("  ✗ 回测失败：没有生成净值历史")
            return

        performance = PerformanceAnalyzer()

        # 转换净值历史为 pandas Series
        nav_df = pd.DataFrame(backtest_result['nav_history'])
        nav_df['trade_date'] = pd.to_datetime(nav_df['trade_date'])
        nav_df = nav_df.set_index('trade_date')
        nav_series = nav_df['nav']

        # 计算收益率序列
        returns = nav_series.pct_change().dropna()

        # 转换基准净值
        benchmark_df = pd.DataFrame(benchmark_nav)
        benchmark_df['trade_date'] = pd.to_datetime(benchmark_df['trade_date'])
        benchmark_df = benchmark_df.set_index('trade_date')
        benchmark_series = benchmark_df['nav']
        benchmark_returns = benchmark_series.pct_change().dropna()

        # 计算各项指标
        total_return = performance.calc_total_return(nav_series)
        annual_return = performance.calc_annual_return(nav_series)
        volatility = performance.calc_volatility(returns)
        sharpe_ratio = performance.calc_sharpe_ratio(returns)
        max_drawdown, dd_start, dd_end = performance.calc_max_drawdown(nav_series)
        calmar_ratio = performance.calc_calmar_ratio(annual_return, max_drawdown)

        # 基准相关指标
        benchmark_return = performance.calc_total_return(benchmark_series)
        excess_return = performance.calc_excess_return(total_return, benchmark_return)
        information_ratio = performance.calc_information_ratio(returns, benchmark_returns)
        win_rate = performance.calc_win_rate(returns)

        # 交易相关指标
        trade_count = len(backtest_result['trade_records'])
        total_cost = sum(t.get('cost', 0) for t in backtest_result['trade_records'])

        # 计算换手率（简化版本）
        turnover_rate = 0.0
        if trade_count > 0 and initial_capital > 0:
            total_trade_value = sum(abs(t.get('amount', 0)) for t in backtest_result['trade_records'])
            turnover_rate = total_trade_value / initial_capital / len(nav_series) * 252  # 年化换手率

        # 汇总指标
        metrics = {
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'benchmark_return': benchmark_return,
            'excess_return': excess_return,
            'information_ratio': information_ratio,
            'win_rate': win_rate,
            'trade_count': trade_count,
            'turnover_rate': turnover_rate,
            'total_cost': total_cost,
        }

        # 打印结果
        print("\n" + "=" * 80)
        print("回测结果")
        print("=" * 80)

        print(f"\n总收益率: {metrics.get('total_return', 0) * 100:.2f}%")
        print(f"年化收益率: {metrics.get('annual_return', 0) * 100:.2f}%")
        print(f"年化波动率: {metrics.get('annual_volatility', 0) * 100:.2f}%")
        print(f"夏普比率: {metrics.get('sharpe_ratio', 0):.2f}")
        print(f"最大回撤: {metrics.get('max_drawdown', 0) * 100:.2f}%")
        print(f"卡玛比率: {metrics.get('calmar_ratio', 0):.2f}")

        if 'benchmark_return' in metrics:
            print(f"\n基准收益率: {metrics.get('benchmark_return', 0) * 100:.2f}%")
            print(f"超额收益: {metrics.get('excess_return', 0) * 100:.2f}%")
            print(f"信息比率: {metrics.get('information_ratio', 0):.2f}")
            print(f"胜率: {metrics.get('win_rate', 0) * 100:.2f}%")

        print(f"\n交易次数: {metrics.get('trade_count', 0)}")
        print(f"换手率: {metrics.get('turnover_rate', 0) * 100:.2f}%")
        print(f"总交易成本: {metrics.get('total_cost', 0):,.2f}")

        # 保存结果
        print("\n[6] 保存结果...")
        result_file = f"backtest_result_{universe_type}_{start_date}_{end_date}.json"

        import json
        with open(result_file, 'w') as f:
            # 转换日期对象为字符串
            result_to_save = {
                'config': {
                    'universe_type': universe_type,
                    'start_date': start_date,
                    'end_date': end_date,
                    'initial_capital': initial_capital,
                    'rebalance_freq': rebalance_freq,
                    'factor_groups': factor_groups,
                    'top_n': top_n,
                    'method': method,
                },
                'metrics': metrics,
                'nav_history': [
                    {k: (v.isoformat() if isinstance(v, date) else v) for k, v in record.items()}
                    for record in backtest_result['nav_history']
                ],
            }
            json.dump(result_to_save, f, indent=2, ensure_ascii=False)

        print(f"  结果已保存到: {result_file}")

        return backtest_result, metrics

    finally:
        db_session.close()


def main():
    parser = argparse.ArgumentParser(description='多因子选股模型回测')
    parser.add_argument('--universe', type=str, default='hs300',
                       choices=['hs300', 'zz500', 'all'],
                       help='股票池类型')
    parser.add_argument('--start-date', type=str, default='2024-01-01',
                       help='回测开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2024-12-31',
                       help='回测结束日期 (YYYY-MM-DD)')
    parser.add_argument('--capital', type=float, default=1000000.0,
                       help='初始资金')
    parser.add_argument('--rebalance', type=str, default='monthly',
                       choices=['daily', 'weekly', 'biweekly', 'monthly'],
                       help='调仓频率')
    parser.add_argument('--factors', type=str, nargs='+',
                       default=['valuation', 'quality', 'growth', 'momentum'],
                       help='因子组')
    parser.add_argument('--top-n', type=int, default=30,
                       help='选股数量')
    parser.add_argument('--method', type=str, default='equal_weight',
                       choices=['equal_weight', 'ic_weight', 'ir_weight'],
                       help='因子合成方法')

    args = parser.parse_args()

    run_backtest(
        universe_type=args.universe,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.capital,
        rebalance_freq=args.rebalance,
        factor_groups=args.factors,
        top_n=args.top_n,
        method=args.method,
    )


if __name__ == '__main__':
    main()
