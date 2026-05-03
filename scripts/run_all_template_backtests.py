"""
为每个模板策略运行独立的回测
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import sessionmaker
from app.db.base import engine
from app.core.multi_factor_model import MultiFactorModel
from app.core.backtest_engine import BacktestEngine
from app.core.performance_analyzer import PerformanceAnalyzer
from app.models.stock_pool import StockPool
from app.models.trading_calendar import TradingCalendar
from app.models.stock_daily import StockDaily
from app.models.index_daily import IndexDaily

# 模板策略配置
TEMPLATE_STRATEGIES = [
    {
        "name": "价值成长组合",
        "code": "VALUE_GROWTH",
        "factor_groups": ["valuation", "growth"],
        "top_n": 30,
        "description": "结合估值和成长因子，寻找价值被低估且具有成长潜力的股票",
    },
    {
        "name": "动量质量组合",
        "code": "MOMENTUM_QUALITY",
        "factor_groups": ["momentum", "quality"],
        "top_n": 20,
        "description": "结合动量和质量因子，选择趋势向上且基本面优质的股票",
    },
    {
        "name": "低波红利组合",
        "code": "LOW_VOL_DIVIDEND",
        "factor_groups": ["volatility", "valuation"],
        "top_n": 25,
        "description": "结合低波动率和估值因子，构建防御性投资组合",
    },
]


def load_universe(session, universe_type="hs300"):
    """加载股票池"""
    stocks = session.query(StockPool).filter_by(pool_type=universe_type).all()
    return [s.ts_code for s in stocks]


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
            IndexDaily.ts_code == benchmark_code,
            IndexDaily.trade_date >= start_date,
            IndexDaily.trade_date <= end_date,
        )
        .order_by(IndexDaily.trade_date)
        .all()
    )
    return {b.trade_date: b.close for b in benchmark}


def run_backtest(strategy_config, universe_type="hs300", start_date="2024-01-01", end_date="2024-12-31"):
    """运行单个策略的回测"""
    print(f"\n{'='*80}")
    print(f"运行回测: {strategy_config['name']}")
    print(f"因子组合: {', '.join(strategy_config['factor_groups'])}")
    print(f"持仓数量: {strategy_config['top_n']}")
    print(f"{'='*80}\n")

    # 创建数据库会话
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

        # 5. 创建多因子模型
        print("创建多因子模型...")
        model = MultiFactorModel(
            session=session,
            factor_groups=strategy_config["factor_groups"],
            weighting_method="equal_weight",
            neutralize_industry=True,
            neutralize_market_cap=True,
        )

        # 6. 创建信号生成器
        def create_signal_generator(top_n):
            def signal_generator(trade_date, total_value, current_holdings):
                result = model.run(
                    ts_codes=ts_codes,
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
        backtest = BacktestEngine(
            initial_capital=1000000,
            commission_rate=0.0003,
            slippage_rate=0.0001,
            price_data=price_data,
        )

        result = backtest.run(
            signal_generator=create_signal_generator(strategy_config["top_n"]),
            trading_days=trading_days,
            rebalance_freq="monthly",
        )

        # 8. 计算绩效指标
        print("计算绩效指标...")
        analyzer = PerformanceAnalyzer()
        nav_series = {item["trade_date"]: item["nav"] for item in result.nav_history}
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
            "win_rate": analyzer.calc_win_rate(result.trades),
            "trade_count": len(result.trades),
            "turnover_rate": result.turnover_rate,
        }

        # 9. 保存结果
        output = {
            "strategy": {
                "name": strategy_config["name"],
                "code": strategy_config["code"],
                "description": strategy_config["description"],
            },
            "config": {
                "universe_type": universe_type,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": 1000000,
                "rebalance_freq": "monthly",
                "factor_groups": strategy_config["factor_groups"],
                "top_n": strategy_config["top_n"],
                "method": "equal_weight",
            },
            "metrics": metrics,
            "nav_history": result.nav_history,
        }

        output_file = project_root / f"backtest_{strategy_config['code'].lower()}_{start_date}_{end_date}.json"
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

        return output_file

    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 80)
    print("运行所有模板策略回测")
    print("=" * 80)

    result_files = []
    for strategy in TEMPLATE_STRATEGIES:
        try:
            result_file = run_backtest(strategy)
            result_files.append(result_file)
        except Exception as e:
            print(f"\n✗ 策略 {strategy['name']} 回测失败: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*80}")
    print(f"完成！共生成 {len(result_files)} 个回测结果文件")
    print(f"{'='*80}")
