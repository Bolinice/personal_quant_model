"""
为全能增强组合运行回测
"""
import json
import sys
from datetime import datetime, date
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import sessionmaker
from app.db.base import engine
from app.core.multi_factor_model import MultiFactorModel
from app.core.backtest_engine import ABShareBacktestEngine
from app.core.performance_analyzer import PerformanceAnalyzer
from app.models.stock_pools import StockPool
from app.models.market.trading_calendar import TradingCalendar
from app.models.market.stock_daily import StockDaily
from app.models.market.index_daily import IndexDaily


def load_universe(session, universe_type="hs300"):
    """加载股票池 - 从最近的快照获取"""
    # 映射pool_type到pool_id
    pool_map = {
        'hs300': 1,
        'zz500': 2,
        'zz1000': 3
    }

    pool_id = pool_map.get(universe_type.lower())
    if not pool_id:
        return []

    # 获取最近的快照
    from app.models.stock_pools import StockPoolSnapshot
    import json

    snapshot = session.query(StockPoolSnapshot).filter_by(
        pool_id=pool_id
    ).order_by(StockPoolSnapshot.trade_date.desc()).first()

    if not snapshot or not snapshot.securities:
        return []

    # 从JSON中提取股票代码
    securities = json.loads(snapshot.securities) if isinstance(snapshot.securities, str) else snapshot.securities
    return [s['ts_code'] for s in securities]


def load_trading_days(session, start_date, end_date):
    """加载交易日历"""
    days = (
        session.query(TradingCalendar.cal_date)
        .filter(
            TradingCalendar.cal_date >= start_date,
            TradingCalendar.cal_date <= end_date,
            TradingCalendar.is_open == True,
        )
        .order_by(TradingCalendar.cal_date)
        .all()
    )
    return [d[0] for d in days]


def load_price_data(session, ts_codes, start_date, end_date):
    """加载价格数据"""
    prices = (
        session.query(StockDaily)
        .filter(
            StockDaily.ts_code.in_(ts_codes),
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date,
        )
        .all()
    )

    price_dict = {}
    for p in prices:
        key = (p.ts_code, p.trade_date)
        price_dict[key] = {
            "open": p.open,
            "high": p.high,
            "low": p.low,
            "close": p.close,
            "volume": p.vol,
        }
    return price_dict


def load_benchmark(session, benchmark_code, start_date, end_date):
    """加载基准指数数据"""
    benchmark = (
        session.query(IndexDaily)
        .filter(
            IndexDaily.index_code == benchmark_code,
            IndexDaily.trade_date >= start_date,
            IndexDaily.trade_date <= end_date,
        )
        .order_by(IndexDaily.trade_date)
        .all()
    )
    return {b.trade_date: b.close for b in benchmark}


def run_all_weather_backtest(
    universe_type="hs300",
    start_date="2024-04-01",
    end_date="2024-12-31"
):
    """运行全能增强组合回测"""

    print(f"\n{'='*80}")
    print(f"运行回测: 全能增强组合")
    print(f"因子组合: 11个因子组，44个因子")
    print(f"持仓数量: 50")
    print(f"{'='*80}\n")

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. 加载股票池
        print("加载股票池...")
        ts_codes = load_universe(session, universe_type)
        print(f"  股票池大小: {len(ts_codes)}")

        # 2. 加载交易日历
        print("加载交易日历...")
        trading_days = load_trading_days(session, start_date, end_date)
        print(f"  交易日数量: {len(trading_days)}")

        # 3. 加载价格数据
        print("加载价格数据...")
        price_data = load_price_data(session, ts_codes, start_date, end_date)
        print(f"  价格数据条数: {len(price_data)}")

        # 4. 加载基准数据
        print("加载基准数据...")
        benchmark_code = "000300.SH"
        benchmark_data = load_benchmark(session, benchmark_code, start_date, end_date)
        print(f"  基准数据条数: {len(benchmark_data)}")

        # 5. 创建多因子模型 - 全能增强配置
        print("创建多因子模型...")
        factor_groups = [
            "valuation",
            "growth",
            "quality",
            "momentum",
            "earnings_quality",
            "smart_money",
            "northbound",
            "sentiment",
            "volatility",
            "liquidity",
            "ashare_specific",
        ]

        model = MultiFactorModel(
            db=session,
            factor_groups=factor_groups,
            weighting_method="equal",
            neutralize_industry=True,
            neutralize_market_cap=True,
        )

        # 6. 创建信号生成器
        def create_signal_generator(top_n):
            def signal_generator(trade_date, universe, state):
                # state是BacktestState对象，直接访问属性
                total_value = state.cash + sum(
                    pos.shares * pos.current_price
                    for pos in state.positions.values()
                )
                current_holdings = {
                    ts_code: pos.shares
                    for ts_code, pos in state.positions.items()
                }

                result = model.run(
                    ts_codes=list(universe),
                    trade_date=trade_date,
                    total_value=total_value,
                    current_holdings=current_holdings,
                    top_n=top_n,
                    exclude_list=[],
                )

                target_holdings = result["target_holdings"]
                if not target_holdings:
                    return {}

                # 查询价格数据
                weights = {}
                total_market_value = 0
                for ts_code, shares in target_holdings.items():
                    price_key = (ts_code, trade_date)
                    if price_key in price_data:
                        price = price_data[price_key]["close"]
                        market_value = shares * price
                        weights[ts_code] = market_value
                        total_market_value += market_value

                # 归一化为权重
                if total_market_value > 0:
                    weights = {k: v / total_market_value for k, v in weights.items()}

                return weights

            return signal_generator

        # 7. 运行回测
        print("运行回测...")
        backtest = ABShareBacktestEngine(
            db=session,
            commission_rate=0.0003,
            slippage_rate=0.0001,
        )

        # 转换日期格式
        start_date_obj = date.fromisoformat(start_date)
        end_date_obj = date.fromisoformat(end_date)
        trading_days_obj = [date.fromisoformat(d) if isinstance(d, str) else d for d in trading_days]

        result = backtest.run_backtest(
            signal_generator=create_signal_generator(50),
            universe=ts_codes,
            start_date=start_date_obj,
            end_date=end_date_obj,
            trading_days=trading_days_obj,
            price_data=price_data,
            initial_capital=1000000,
            rebalance_freq="monthly",
        )

        # 8. 计算绩效指标
        print("计算绩效指标...")
        analyzer = PerformanceAnalyzer()
        nav_series = {item["trade_date"]: item["nav"] for item in result["nav_history"]}
        benchmark_series = benchmark_data

        metrics = {
            "total_return": analyzer.calc_total_return(nav_series),
            "annual_return": analyzer.calc_annual_return(nav_series),
            "annual_volatility": analyzer.calc_volatility(nav_series),
            "sharpe_ratio": analyzer.calc_sharpe_ratio(nav_series),
            "max_drawdown": analyzer.calc_max_drawdown(nav_series),
            "calmar_ratio": analyzer.calc_calmar_ratio(nav_series),
            "benchmark_return": analyzer.calc_total_return(benchmark_series),
            "excess_return": analyzer.calc_total_return(nav_series) - analyzer.calc_total_return(benchmark_series),
            "information_ratio": analyzer.calc_information_ratio(nav_series, benchmark_series),
            "win_rate": analyzer.calc_win_rate(result["trade_records"]),
            "trade_count": len(result["trade_records"]),
            "turnover_rate": result.get("turnover_rate", 0),
        }

        # 9. 保存结果
        output = {
            "strategy": {
                "name": "全能增强组合",
                "code": "ALL_WEATHER",
                "description": "综合基本面、技术面、资金面、风险面的多维度因子，构建攻守兼备的全天候策略",
            },
            "config": {
                "universe_type": universe_type,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": 1000000,
                "rebalance_freq": "monthly",
                "factor_groups": factor_groups,
                "top_n": 50,
                "method": "equal_weight",
                "total_factors": 44,
            },
            "metrics": metrics,
            "nav_history": result["nav_history"],
        }

        output_file = project_root / f"backtest_all_weather_{start_date}_{end_date}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n回测完成！结果已保存到: {output_file}")
        print(f"\n绩效指标:")
        print(f"  总收益: {metrics['total_return']:.2%}")
        print(f"  年化收益: {metrics['annual_return']:.2%}")
        print(f"  夏普比率: {metrics['sharpe_ratio']:.2f}")
        print(f"  最大回撤: {metrics['max_drawdown']:.2%}")
        print(f"  卡玛比率: {metrics['calmar_ratio']:.2f}")
        print(f"  超额收益: {metrics['excess_return']:.2%}")
        print(f"  信息比率: {metrics['information_ratio']:.2f}")
        print(f"  胜率: {metrics['win_rate']:.2%}")

        return output_file

    except Exception as e:
        print(f"\n✗ 回测失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 80)
    print("全能增强组合回测")
    print("=" * 80)
    run_all_weather_backtest()
