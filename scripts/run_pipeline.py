#!/usr/bin/env python
"""
端到端流水线脚本
数据获取 → 标准化清洗 → 因子计算 → 因子预处理 → 多因子评分 → 择时信号 → 组合构建 → 回测 → 绩效分析 → 报告生成
不依赖数据库，全部在内存中运行
"""
import sys
sys.path.insert(0, '.')

import argparse
import os
from datetime import datetime, date, timedelta
import numpy as np
import pandas as pd


def run_pipeline(stocks: list, index_code: str, start_date: str, end_date: str,
                 top_n: int = 30, rebalance_freq: str = 'monthly',
                 initial_capital: float = 1_000_000):
    """运行完整端到端流水线"""

    # ==================== 1. 数据获取 ====================
    print("=" * 60)
    print("1. 数据获取")
    print("=" * 60)

    from app.data_sources.crawler_source import CrawlerDataSource
    from app.data_sources.normalizer import DataNormalizer
    from app.data_sources.cleaner import DataCleaner

    source = CrawlerDataSource()
    connected = source.connect()
    if not connected:
        print("ERROR: 数据源连接失败")
        return

    normalizer = DataNormalizer()
    cleaner = DataCleaner()

    # 获取股票日线
    stock_data = {}
    for code in stocks:
        df_raw = source.get_stock_daily(code, start_date, end_date)
        if df_raw.empty:
            print(f"  {code}: 无数据")
            continue
        df_norm = normalizer.normalize_stock_daily(df_raw, 'crawler')
        df_clean, report = cleaner.clean_stock_daily(df_norm)
        stock_data[code] = df_clean
        print(f"  {code}: {len(df_clean)} 天 | {df_clean['trade_date'].min()} ~ {df_clean['trade_date'].max()}")

    # 获取指数日线（基准）
    df_idx_raw = source.get_index_daily(index_code, start_date, end_date)
    df_idx_norm = normalizer.normalize_index_daily(df_idx_raw, 'crawler')
    df_idx_clean, _ = cleaner.clean_index_daily(df_idx_norm)
    print(f"  {index_code}(基准): {len(df_idx_clean)} 天")

    if not stock_data:
        print("ERROR: 无股票数据")
        return

    # ==================== 2. 因子计算 ====================
    print("\n" + "=" * 60)
    print("2. 因子计算与预处理")
    print("=" * 60)

    from app.core.factor_engine import FactorEngine

    # 为每只股票计算因子（使用时间序列数据）
    all_factor_scores = {}

    for code, df in stock_data.items():
        # 构建行情DataFrame
        price_df = df.copy()
        price_df['ts_code'] = code

        # 计算因子
        factor_df = FactorEngine.calc_factors_from_data(price_df)

        if factor_df.empty:
            print(f"  {code}: 无因子数据")
            continue

        # 取最后一行（最新日期的因子值）
        last_row = factor_df.iloc[[-1]].copy()
        last_row['ts_code'] = code
        all_factor_scores[code] = last_row

        factor_cols = [c for c in factor_df.columns if c not in ['security_id', 'ts_code']]
        available = [c for c in factor_cols if not last_row[c].isna().all()]
        print(f"  {code}: {len(available)} 个因子可用")

    # ==================== 3. 多因子评分 ====================
    print("\n" + "=" * 60)
    print("3. 多因子评分")
    print("=" * 60)

    from app.core.model_scorer import MultiFactorScorer

    if all_factor_scores:
        # 合并所有股票的因子得分
        scores_df = pd.concat(all_factor_scores.values(), ignore_index=True)
        scores_df = scores_df.set_index('ts_code')

        # 计算综合评分
        scored = MultiFactorScorer.score_from_factor_df(scores_df, method='equal')
        scored = scored.sort_values('total_score', ascending=False)

        print(f"  评分方法: 等权加权")
        print(f"  评分范围: {scored['total_score'].min():.3f} ~ {scored['total_score'].max():.3f}")

        # 选 Top N
        top_stocks = scored.head(top_n)
        print(f"\n  Top {top_n} 股票:")
        for code, row in top_stocks.iterrows():
            print(f"    {code}: score={row['total_score']:.3f} rank={int(row['rank'])}")
    else:
        # 因子数据不足，用所有股票等权
        top_stocks = pd.DataFrame({
            'total_score': [0.0] * len(stocks),
            'rank': range(1, len(stocks) + 1),
        }, index=stocks)
        print(f"  因子数据不足，使用全部 {len(stocks)} 只股票等权组合")

    # ==================== 4. 择时信号 ====================
    print("\n" + "=" * 60)
    print("4. 择时信号")
    print("=" * 60)

    from app.core.timing_engine import TimingEngine, TimingSignalType

    timing_engine = TimingEngine()

    # 使用指数数据计算择时信号
    if not df_idx_clean.empty:
        close = df_idx_clean.set_index('trade_date')['close'].sort_index()

        # 均线择时
        ma_signal = timing_engine.ma_cross_signal(close, short_window=20, long_window=60)
        # 波动率择时
        vol_signal = timing_engine.volatility_signal(close, window=20)
        # 回撤控制
        dd_signal = timing_engine.drawdown_control_signal(close, max_drawdown=0.10)

        # 融合信号
        fused = timing_engine.fuse_signals({
            'ma': ma_signal,
            'volatility': vol_signal,
            'drawdown': dd_signal,
        }, method='equal')

        latest_signal = fused.iloc[-1]
        target_exposure = timing_engine.calc_target_exposure(fused, base_exposure=0.8)

        print(f"  均线信号: {ma_signal.iloc[-1]}")
        print(f"  波动率信号: {vol_signal.iloc[-1]}")
        print(f"  回撤控制: {dd_signal.iloc[-1]}")
        print(f"  融合信号: {latest_signal}")
        print(f"  目标仓位: {target_exposure.iloc[-1]:.1%}")

        # 市场状态
        regime = timing_engine.identify_market_regime(close)
        print(f"  市场状态: {regime.iloc[-1]}")
    else:
        latest_signal = TimingSignalType.NEUTRAL
        target_exposure_val = 0.8
        print("  无指数数据，使用默认中性信号")

    # ==================== 5. 组合构建 ====================
    print("\n" + "=" * 60)
    print("5. 组合构建")
    print("=" * 60)

    # 等权组合
    selected_codes = top_stocks.index.tolist()
    n_selected = len(selected_codes)
    weights = pd.Series(1.0 / n_selected, index=selected_codes)

    print(f"  持仓数量: {n_selected}")
    print(f"  权重方法: 等权")
    print(f"  单只权重: {1.0/n_selected:.2%}")

    # ==================== 6. 回测 ====================
    print("\n" + "=" * 60)
    print("6. 回测")
    print("=" * 60)

    from app.core.backtest_engine import ABShareBacktestEngine, BacktestState

    bt_engine = ABShareBacktestEngine()

    # 准备回测数据
    # 使用第一只股票的日期作为回测时间轴
    first_code = list(stock_data.keys())[0]
    bt_dates = stock_data[first_code]['trade_date'].sort_values().tolist()

    # 构建价格字典 {trade_date: {ts_code: close}}
    price_map = {}
    for trade_date in bt_dates:
        price_map[trade_date] = {}
        for code, df in stock_data.items():
            row = df[df['trade_date'] == trade_date]
            if not row.empty:
                price_map[trade_date][code] = float(row['close'].iloc[0])

    # 基准净值
    benchmark_nav = []
    if not df_idx_clean.empty:
        idx_close = df_idx_clean.set_index('trade_date')['close'].sort_index()
        first_close = idx_close.iloc[0]
        for trade_date in bt_dates:
            if trade_date in idx_close.index:
                benchmark_nav.append({
                    'trade_date': trade_date,
                    'nav': float(idx_close.loc[trade_date]) / first_close,
                })

    # 运行回测
    state = BacktestState(initial_capital=initial_capital)
    trading_days = [datetime.strptime(d, '%Y-%m-%d').date() for d in bt_dates]

    # 初始建仓（第一个交易日）
    first_date_str = bt_dates[0]
    first_date = datetime.strptime(first_date_str, '%Y-%m-%d').date()
    per_stock_capital = initial_capital * 0.95 / n_selected  # 留5%现金
    for code in selected_codes:
        price = price_map.get(first_date_str, {}).get(code)
        if price and price > 0:
            stock_info = {'is_suspended': False, 'pct_chg': 0, 'is_st': False}
            bt_engine.execute_buy(state, code, per_stock_capital, price, first_date, stock_info)

    # 逐日计算净值
    for i, trade_date_str in enumerate(bt_dates):
        trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d').date()
        if trade_date_str in price_map:
            bt_engine.calc_nav(state, trade_date, price_map[trade_date_str])

    # 计算回测指标
    metrics = bt_engine.calc_metrics(state.nav_history, state.trade_records, benchmark_nav)

    if metrics:
        print(f"  总收益率: {metrics.get('total_return', 0):.2%}")
        print(f"  年化收益: {metrics.get('annual_return', 0):.2%}")
        print(f"  最大回撤: {metrics.get('max_drawdown', 0):.2%}")
        print(f"  夏普比率: {metrics.get('sharpe', 0):.2f}")
        print(f"  索提诺比率: {metrics.get('sortino', 0):.2f}")
        print(f"  卡玛比率: {metrics.get('calmar', 0):.2f}")
        print(f"  换手率: {metrics.get('turnover_rate', 0):.2%}")
        print(f"  胜率: {metrics.get('win_rate', 0):.2%}")
        print(f"  盈亏比: {metrics.get('profit_loss_ratio', 0):.2f}")
        print(f"  交易次数: {metrics.get('total_trades', 0)}")
        print(f"  总成本: ¥{metrics.get('total_cost', 0):,.2f}")
        if 'alpha' in metrics:
            print(f"  Alpha: {metrics['alpha']:.2%}")
            print(f"  Beta: {metrics['beta']:.2f}")
            print(f"  信息比率: {metrics['information_ratio']:.2f}")

    # ==================== 7. 绩效分析 ====================
    print("\n" + "=" * 60)
    print("7. 绩效分析")
    print("=" * 60)

    from app.core.performance_analyzer import PerformanceAnalyzer

    analyzer = PerformanceAnalyzer()

    if state.nav_history:
        nav_series = pd.Series(
            {h['trade_date']: h['nav'] for h in state.nav_history}
        ).sort_index()

        # 基准净值序列
        bm_nav = None
        if benchmark_nav:
            bm_nav = pd.Series(
                {h['trade_date']: h['nav'] for h in benchmark_nav}
            ).sort_index()

        perf = analyzer.analyze_performance(nav_series, bm_nav)

        print(f"  年化收益: {perf['annual_return']:.2%}")
        print(f"  波动率: {perf['volatility']:.2%}")
        print(f"  最大回撤: {perf['max_drawdown']:.2%}")
        print(f"  夏普: {perf['sharpe_ratio']:.2f}")
        print(f"  索提诺: {perf['sortino_ratio']:.2f}")
        print(f"  卡玛: {perf['calmar_ratio']:.2f}")
        print(f"  VaR(95%): {perf['var_95']:.2%}")
        print(f"  CVaR(95%): {perf['cvar_95']:.2%}")
    else:
        perf = {}

    # ==================== 8. 风险分析 ====================
    print("\n" + "=" * 60)
    print("8. 风险分析")
    print("=" * 60)

    from app.core.risk_model import RiskModel

    risk_model = RiskModel()

    # 计算组合风险
    if len(stock_data) >= 2:
        # 构建收益率矩阵
        returns_dict = {}
        for code, df in stock_data.items():
            if 'close' in df.columns:
                ret = df.set_index('trade_date')['close'].sort_index().pct_change().dropna()
                returns_dict[code] = ret

        if returns_dict:
            returns_df = pd.DataFrame(returns_dict).dropna()
            if len(returns_df) > 30:
                # Ledoit-Wolf 压缩协方差
                cov = risk_model.ledoit_wolf_shrinkage(returns_df)
                w = np.array([weights.get(c, 0) for c in returns_df.columns])
                if w.sum() > 0:
                    w = w / w.sum()
                    port_vol = risk_model.portfolio_volatility(w, cov.values)
                    print(f"  组合年化波动率: {port_vol * np.sqrt(252):.2%}")

                    # VaR
                    port_returns = returns_df.values @ w
                    port_ret_series = pd.Series(port_returns)
                    var_95 = risk_model.historical_var(port_ret_series, 0.95)
                    cvar_95 = risk_model.conditional_var(port_ret_series, 0.95)
                    print(f"  历史VaR(95%): {var_95:.2%}")
                    print(f"  CVaR(95%): {cvar_95:.2%}")

    # ==================== 9. 生成报告 ====================
    print("\n" + "=" * 60)
    print("9. 生成报告")
    print("=" * 60)

    os.makedirs('output', exist_ok=True)
    report_date = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = f'output/pipeline_report_{report_date}.md'

    report_lines = [
        f"# 端到端流水线报告",
        f"",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"回测区间: {start_date} ~ {end_date}",
        f"基准指数: {index_code}",
        f"初始资金: ¥{initial_capital:,.0f}",
        f"",
        f"## 1. 组合持仓",
        f"",
        f"| 股票 | 权重 |",
        f"|------|------|",
    ]
    for code in selected_codes:
        report_lines.append(f"| {code} | {weights[code]:.2%} |")

    report_lines.extend([
        f"",
        f"## 2. 择时信号",
        f"",
    ])
    if not df_idx_clean.empty:
        report_lines.extend([
            f"- 融合信号: **{latest_signal}**",
            f"- 目标仓位: {target_exposure.iloc[-1]:.1%}",
            f"- 市场状态: {regime.iloc[-1]}",
        ])
    else:
        report_lines.append(f"- 信号: 中性（无指数数据）")

    report_lines.extend([
        f"",
        f"## 3. 回测结果",
        f"",
    ])
    if metrics:
        report_lines.extend([
            f"| 指标 | 值 |",
            f"|------|-----|",
            f"| 总收益率 | {metrics.get('total_return', 0):.2%} |",
            f"| 年化收益 | {metrics.get('annual_return', 0):.2%} |",
            f"| 最大回撤 | {metrics.get('max_drawdown', 0):.2%} |",
            f"| 夏普比率 | {metrics.get('sharpe', 0):.2f} |",
            f"| 索提诺比率 | {metrics.get('sortino', 0):.2f} |",
            f"| 卡玛比率 | {metrics.get('calmar', 0):.2f} |",
            f"| 换手率 | {metrics.get('turnover_rate', 0):.2%} |",
            f"| 胜率 | {metrics.get('win_rate', 0):.2%} |",
            f"| 盈亏比 | {metrics.get('profit_loss_ratio', 0):.2f} |",
            f"| 交易次数 | {metrics.get('total_trades', 0)} |",
            f"| 总成本 | ¥{metrics.get('total_cost', 0):,.2f} |",
        ])
        if 'alpha' in metrics:
            report_lines.extend([
                f"| Alpha | {metrics['alpha']:.2%} |",
                f"| Beta | {metrics['beta']:.2f} |",
                f"| 信息比率 | {metrics['information_ratio']:.2f} |",
            ])

    report_lines.extend([
        f"",
        f"## 4. 绩效分析",
        f"",
    ])
    if perf:
        report_lines.extend([
            f"| 指标 | 值 |",
            f"|------|-----|",
            f"| 年化收益 | {perf['annual_return']:.2%} |",
            f"| 波动率 | {perf['volatility']:.2%} |",
            f"| 最大回撤 | {perf['max_drawdown']:.2%} |",
            f"| 夏普 | {perf['sharpe_ratio']:.2f} |",
            f"| 索提诺 | {perf['sortino_ratio']:.2f} |",
            f"| 卡玛 | {perf['calmar_ratio']:.2f} |",
            f"| VaR(95%) | {perf['var_95']:.2%} |",
            f"| CVaR(95%) | {perf['cvar_95']:.2%} |",
        ])

    # 净值曲线数据
    if state.nav_history:
        report_lines.extend([
            f"",
            f"## 5. 净值曲线",
            f"",
            f"| 日期 | 净值 | 总价值 | 回撤 |",
            f"|------|------|--------|------|",
        ])
        for h in state.nav_history[::max(1, len(state.nav_history)//20)]:  # 最多20行
            dd = h.get('drawdown', 0)
            report_lines.append(
                f"| {h['trade_date']} | {h['nav']:.4f} | ¥{h['total_value']:,.0f} | {dd:.2%} |"
            )

    report_content = "\n".join(report_lines)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"  报告已保存: {report_path}")

    # ==================== 完成 ====================
    print("\n" + "=" * 60)
    print("流水线完成!")
    print("=" * 60)

    return {
        'metrics': metrics,
        'performance': perf,
        'report_path': report_path,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="端到端流水线")
    parser.add_argument("--stocks", nargs='+', default=['600000.SH', '600036.SH', '000001.SZ', '601318.SH', '000858.SZ'],
                        help="股票代码列表")
    parser.add_argument("--index", default='000001.SH', help="基准指数代码")
    parser.add_argument("--start", default='2024-06-01', help="开始日期")
    parser.add_argument("--end", default='2025-04-18', help="结束日期")
    parser.add_argument("--top-n", type=int, default=30, help="持仓数量")
    parser.add_argument("--capital", type=float, default=1_000_000, help="初始资金")

    args = parser.parse_args()

    run_pipeline(
        stocks=args.stocks,
        index_code=args.index,
        start_date=args.start,
        end_date=args.end,
        top_n=args.top_n,
        initial_capital=args.capital,
    )
