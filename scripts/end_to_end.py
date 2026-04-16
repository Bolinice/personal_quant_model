"""
端到端量化策略流程
数据获取 → 因子计算 → 因子分析 → 风险模型 → 组合优化 → 回测 → 绩效分析
"""
import sys
sys.path.insert(0, '.')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from app.db.base import SessionLocal
from app.models.market import StockDaily, StockBasic, IndexDaily
from app.core.risk_model import BarraRiskModel
from app.core.portfolio_optimizer import PortfolioOptimizer
from app.core.logging import logger


# ==================== Step 1: 数据获取 ====================

def load_data(db, n_stocks=50, lookback=180):
    """从数据库加载行情数据"""
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=lookback)).strftime('%Y-%m-%d')

    stocks = db.query(StockBasic).filter(StockBasic.list_status == 'L').limit(n_stocks).all()
    ts_codes = [s.ts_code for s in stocks]

    data = db.query(StockDaily).filter(
        StockDaily.ts_code.in_(ts_codes),
        StockDaily.trade_date >= start_date,
        StockDaily.trade_date <= end_date
    ).order_by(StockDaily.ts_code, StockDaily.trade_date).all()

    df = pd.DataFrame([{
        'ts_code': d.ts_code,
        'trade_date': d.trade_date,
        'close': float(d.close) if d.close else None,
        'pct_chg': float(d.pct_chg) if d.pct_chg else None,
        'volume': float(d.vol) if d.vol else None,
        'amount': float(d.amount) if d.amount else None,
    } for d in data]).drop_duplicates(subset=['ts_code', 'trade_date'], keep='first')

    # 加载指数
    idx_data = db.query(IndexDaily).filter(
        IndexDaily.index_code == '000300.SH',
        IndexDaily.trade_date >= start_date,
        IndexDaily.trade_date <= end_date
    ).order_by(IndexDaily.trade_date).all()

    idx_df = pd.DataFrame([{
        'trade_date': d.trade_date,
        'close': float(d.close) if d.close else None,
        'pct_chg': float(d.pct_chg) if d.pct_chg else None,
    } for d in idx_data])

    return df, idx_df, ts_codes


# ==================== Step 2: 因子计算 ====================

def calc_all_factors(price_df):
    """计算全部因子"""
    results = []
    for ts_code in price_df['ts_code'].unique():
        s = price_df[price_df['ts_code'] == ts_code].sort_values('trade_date')
        if len(s) < 60:
            continue

        close = s['close'].values
        pct = s['pct_chg'].values
        vol = s['volume'].values
        amt = s['amount'].values

        # 风格因子
        size = np.log(np.mean(amt[-20:])) if len(amt) >= 20 and np.mean(amt[-20:]) > 0 else None
        momentum = close[-1] / close[-21] - 1 if len(close) >= 21 else None
        volatility = np.std(pct[-20:] / 100) * np.sqrt(252) if len(pct) >= 20 else None
        turnover = np.mean(vol[-20:]) if len(vol) >= 20 else None
        value = 1.0 / close[-1] if close[-1] > 0 else None
        growth = close[-1] / close[-11] - 1 if len(close) >= 11 else None
        quality = np.sum(pct[-20:] > 0) / 20 if len(pct) >= 20 else None

        # Alpha因子
        # RSI
        gains = np.maximum(pct[-14:], 0)
        losses = np.maximum(-pct[-14:], 0)
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
        rsi = 100 - 100 / (1 + avg_gain / avg_loss)

        # 量价背离 (价格涨但量缩 = 负, 价格涨量涨 = 正)
        price_chg_5d = close[-1] / close[-6] - 1 if len(close) >= 6 else 0
        vol_chg_5d = np.mean(vol[-5:]) / np.mean(vol[-10:-5]) - 1 if len(vol) >= 10 else 0
        vol_price_diverg = price_chg_5d - vol_chg_5d

        # 均线偏离
        ma20 = np.mean(close[-20:]) if len(close) >= 20 else close[-1]
        ma_deviation = (close[-1] - ma20) / ma20

        # 反转因子
        reversal_5d = close[-1] / close[-6] - 1 if len(close) >= 6 else None

        results.append({
            'ts_code': ts_code,
            'size': size, 'momentum': momentum, 'volatility': volatility,
            'turnover': turnover, 'value': value, 'growth': growth, 'quality': quality,
            'rsi': rsi, 'vol_price_diverg': vol_price_diverg,
            'ma_deviation': ma_deviation, 'reversal_5d': reversal_5d,
        })

    return pd.DataFrame(results).set_index('ts_code')


# ==================== Step 3: 因子分析 ====================

def analyze_factors(factor_df, price_df):
    """IC分析筛选有效因子"""
    factor_cols = [c for c in factor_df.columns if c != 'trade_date']
    dates = sorted(price_df['trade_date'].unique())
    results = []

    for factor_col in factor_cols:
        ic_list = []
        for i in range(len(dates) - 1):
            date, next_date = dates[i], dates[i + 1]

            f_val = factor_df[factor_col] if 'trade_date' not in factor_df.columns else \
                factor_df[factor_df['trade_date'] == date].set_index('ts_code')[factor_col]

            ret_next = price_df[price_df['trade_date'] == next_date].set_index('ts_code')['pct_chg'] / 100

            aligned = pd.DataFrame({'f': f_val, 'r': ret_next}).dropna()
            if len(aligned) < 10:
                continue

            ic = aligned['f'].rank().corr(aligned['r'].rank())
            ic_list.append(ic)

        if not ic_list:
            continue

        ic_series = pd.Series(ic_list)
        results.append({
            'factor': factor_col,
            'ic_mean': ic_series.mean(),
            'ic_std': ic_series.std(),
            'icir': ic_series.mean() / ic_series.std() if ic_series.std() > 0 else 0,
            'ic_positive_ratio': (ic_series > 0).mean(),
        })

    return pd.DataFrame(results).sort_values('icir', key=abs, ascending=False)


# ==================== Step 4: 风险模型 ====================

def build_risk_model(price_df, style_data):
    """构建风险模型"""
    risk_model = BarraRiskModel()

    # 行业分配
    industry_data = pd.Series('主板', index=style_data.index)

    # 构建暴露矩阵
    exposure = risk_model.build_factor_exposure(price_df, style_data, industry_data)

    # 截面回归
    factor_returns = risk_model.fit_factor_returns_series(price_df, exposure)
    if factor_returns.empty:
        return None

    # 估计协方差
    risk_model.estimate_factor_cov()
    risk_model.estimate_specific_var()
    risk_model.estimate_cov_matrix()

    return risk_model


# ==================== Step 5: 组合优化 ====================

def optimize_portfolio(expected_returns, cov_matrix, optimizer, method='mean_variance'):
    """组合优化"""
    stocks = expected_returns.index.intersection(cov_matrix.index)
    mu = expected_returns.reindex(stocks)
    sigma = cov_matrix.loc[stocks, stocks]

    if method == 'mean_variance':
        return optimizer.mean_variance_optimize(mu, sigma, risk_aversion=1.0, max_position=0.10)
    elif method == 'risk_parity':
        return optimizer.risk_parity_optimize(sigma, max_position=0.10)
    elif method == 'min_variance':
        return optimizer.min_variance_optimize(sigma, max_position=0.10)


# ==================== Step 6: 回测 ====================

def backtest_strategy(price_df, weights, rebalance_freq=20):
    """回测：按权重买入持有，定期调仓"""
    dates = sorted(price_df['trade_date'].unique())
    if len(dates) < 2:
        return None

    holdings = {}
    cash = 100000.0
    nav_history = []

    for i, date in enumerate(dates):
        day = price_df[price_df['trade_date'] == date].set_index('ts_code')

        # 持仓市值
        pos_value = sum(
            holdings.get(s, 0) * day.loc[s, 'close']
            for s in holdings if s in day.index and pd.notna(day.loc[s, 'close'])
        )
        nav = cash + pos_value
        nav_history.append({'date': date, 'nav': nav})

        # 调仓
        if i % rebalance_freq == 0:
            # 清仓
            for s in list(holdings.keys()):
                if s in day.index and pd.notna(day.loc[s, 'close']):
                    cash += holdings[s] * day.loc[s, 'close'] * 0.999
            holdings = {}

            # 按权重买入
            for s in weights.index:
                if s in day.index and pd.notna(day.loc[s, 'close']):
                    price = day.loc[s, 'close']
                    target_value = nav * weights[s] * 0.95
                    shares = int(target_value / price / 100) * 100
                    if shares >= 100:
                        cost = shares * price * 1.0003
                        if cost <= cash:
                            holdings[s] = shares
                            cash -= cost

    return pd.DataFrame(nav_history)


# ==================== Step 7: 绩效分析 ====================

def analyze_performance(nav_df, benchmark_nav_df=None):
    """绩效分析"""
    nav = nav_df.set_index('date')['nav']
    returns = nav.pct_change().dropna()

    total_return = nav.iloc[-1] / nav.iloc[0] - 1
    annual_return = (1 + total_return) ** (252 / len(nav)) - 1

    cummax = nav.cummax()
    drawdown = (nav - cummax) / cummax
    max_dd = drawdown.min()

    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    sortino_down = returns[returns < 0].std() * np.sqrt(252) if (returns < 0).any() else 0.001
    sortino = returns.mean() * 252 / sortino_down if sortino_down > 0 else 0

    win_rate = (returns > 0).mean()

    result = {
        'total_return': total_return,
        'annual_return': annual_return,
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'win_rate': win_rate,
        'volatility': returns.std() * np.sqrt(252),
    }

    # 基准对比
    if benchmark_nav_df is not None and not benchmark_nav_df.empty:
        if 'date' in benchmark_nav_df.columns:
            bm_nav = benchmark_nav_df.set_index('date')['close']
        elif 'trade_date' in benchmark_nav_df.columns:
            bm_nav = benchmark_nav_df.set_index('trade_date')['close']
        else:
            bm_nav = None

        if bm_nav is not None:
            bm_ret = bm_nav.pct_change().dropna()
            bm_annual = (bm_nav.iloc[-1] / bm_nav.iloc[0]) ** (252 / len(bm_nav)) - 1

            result['benchmark_return'] = bm_annual
            result['excess_return'] = annual_return - bm_annual

            # 信息比率
            common = returns.index.intersection(bm_ret.index)
            if len(common) > 0:
                excess = returns.loc[common] - bm_ret.loc[common]
                result['information_ratio'] = excess.mean() / excess.std() * np.sqrt(252) if excess.std() > 0 else 0

    return result


# ==================== Main ====================

def main():
    print("=" * 70)
    print("端到端量化策略流程")
    print("=" * 70)

    db = SessionLocal()

    # Step 1: 数据
    print("\n[Step 1] 加载数据...")
    price_df, idx_df, ts_codes = load_data(db, n_stocks=50, lookback=180)
    print(f"    股票: {len(ts_codes)}, 行情: {len(price_df)} 条, 指数: {len(idx_df)} 条")

    # Step 2: 因子计算
    print("\n[Step 2] 计算因子...")
    factor_df = calc_all_factors(price_df)
    factor_cols = [c for c in factor_df.columns]
    print(f"    有效股票: {len(factor_df)}, 因子数: {len(factor_cols)}")
    print(f"    因子: {factor_cols}")

    # Step 3: 因子分析
    print("\n[Step 3] 因子IC分析...")
    ic_results = analyze_factors(factor_df, price_df)
    print(f"\n    因子IC排名 (按|ICIR|排序):")
    print(ic_results[['factor', 'ic_mean', 'icir', 'ic_positive_ratio']].to_string(index=False))

    # 选出有效因子 (|ICIR| > 0.3 或 |IC均值| > 0.03)
    valid_factors = ic_results[
        (abs(ic_results['icir']) > 0.3) | (abs(ic_results['ic_mean']) > 0.03)
    ]['factor'].tolist()
    print(f"\n    有效因子: {valid_factors}")

    # Step 4: 风险模型
    print("\n[Step 4] 构建风险模型...")
    style_cols = [c for c in BarraRiskModel.STYLE_FACTORS if c in factor_df.columns]
    risk_model = build_risk_model(price_df, factor_df[style_cols])

    if risk_model is None or risk_model.cov_matrix is None:
        print("    风险模型构建失败，使用简化方法")
        risk_model = None
    else:
        print(f"    协方差矩阵: {risk_model.cov_matrix.shape}")

    # Step 5: 组合优化 - 多策略
    print("\n[Step 5] 组合优化...")

    # 期望收益: 用有效因子的综合得分
    latest_date = price_df['trade_date'].max()
    recent = price_df[price_df['trade_date'] >= pd.Timestamp(latest_date) - timedelta(days=90)]

    # 计算每只股票的综合得分
    scores = pd.Series(0.0, index=factor_df.index)
    for factor_col in valid_factors:
        if factor_col in factor_df.columns:
            values = factor_df[factor_col]
            # 用ICIR作为权重
            icir = ic_results[ic_results['factor'] == factor_col]['icir'].values
            weight = icir[0] if len(icir) > 0 else 0
            # 标准化
            std_val = (values - values.mean()) / values.std() if values.std() > 0 else values - values.mean()
            scores += weight * std_val

    # 期望收益: 用近期动量估算
    expected_returns_list = []
    for ts_code in recent['ts_code'].unique():
        s = recent[recent['ts_code'] == ts_code].sort_values('trade_date')
        if len(s) >= 20:
            pct = s['pct_chg'].iloc[-20:] / 100
            cum = (1 + pct).prod() - 1
            annual = (1 + cum) ** (252 / 20) - 1
            expected_returns_list.append({'ts_code': ts_code, 'return': annual})

    expected_returns = pd.Series(
        {r['ts_code']: r['return'] for r in expected_returns_list}
    ).clip(-0.5, 0.5)

    optimizer = PortfolioOptimizer()
    strategies = {}

    # 策略1: 均值方差优化
    if risk_model is not None:
        stocks = expected_returns.index.intersection(risk_model.cov_matrix.index)[:30]
        mu = expected_returns.reindex(stocks).fillna(0)
        sigma = risk_model.cov_matrix.loc[stocks, stocks]

        w = optimizer.mean_variance_optimize(mu, sigma, risk_aversion=1.0, max_position=0.10)
        strategies['均值方差'] = w

        # 策略2: 风险平价
        w = optimizer.risk_parity_optimize(sigma, max_position=0.10)
        strategies['风险平价'] = w

        # 策略3: 最小方差
        w = optimizer.min_variance_optimize(sigma, max_position=0.10)
        strategies['最小方差'] = w

    # 策略4: 因子打分选股 + 等权
    top_stocks = scores.nlargest(20).index.tolist()
    strategies['因子打分(等权)'] = pd.Series(1/20, index=top_stocks)

    # 策略5: 因子打分 + 风险平价
    if risk_model is not None:
        top_in_cov = [s for s in top_stocks if s in risk_model.cov_matrix.index]
        if len(top_in_cov) >= 5:
            sigma = risk_model.cov_matrix.loc[top_in_cov, top_in_cov]
            w = optimizer.risk_parity_optimize(sigma, max_position=0.10)
            strategies['因子打分+风险平价'] = w

    print(f"    生成 {len(strategies)} 个策略:")
    for name, w in strategies.items():
        print(f"      {name}: {len(w)} 只股票, 最大权重 {w.max():.2%}")

    # Step 6: 回测
    print("\n[Step 6] 回测...")
    backtest_results = {}

    for name, w in strategies.items():
        nav_df = backtest_strategy(price_df, w, rebalance_freq=20)
        if nav_df is not None and len(nav_df) > 10:
            backtest_results[name] = nav_df

    # 基准回测 (等权持有全部股票)
    all_stocks = price_df['ts_code'].unique()[:20]
    eq_weights = pd.Series(1/len(all_stocks), index=all_stocks)
    benchmark_nav = backtest_strategy(price_df, eq_weights, rebalance_freq=999)  # 买入持有

    print(f"    回测完成: {len(backtest_results)} 个策略 + 1 个基准")

    # Step 7: 绩效分析
    print("\n[Step 7] 绩效分析...")
    perf_results = []

    for name, nav_df in backtest_results.items():
        perf = analyze_performance(nav_df, idx_df)
        perf['strategy'] = name
        perf_results.append(perf)

    # 基准
    if benchmark_nav is not None:
        perf = analyze_performance(benchmark_nav, idx_df)
        perf['strategy'] = '基准(等权持有)'
        perf_results.append(perf)

    perf_df = pd.DataFrame([{k: v for k, v in p.items() if not isinstance(v, (pd.Series, pd.DataFrame))} for p in perf_results])

    # 排序
    perf_df = perf_df.sort_values('sharpe_ratio', ascending=False)

    # 输出
    print("\n" + "=" * 70)
    print("策略绩效对比")
    print("=" * 70)

    for _, row in perf_df.iterrows():
        print(f"\n  {row['strategy']}:")
        print(f"    年化收益: {row['annual_return']:.2%}  |  波动率: {row['volatility']:.2%}")
        print(f"    夏普比率: {row['sharpe_ratio']:.2f}  |  索提诺: {row.get('sortino_ratio', 0):.2f}")
        print(f"    最大回撤: {row['max_drawdown']:.2%}  |  胜率: {row['win_rate']:.1%}")
        if 'excess_return' in row and pd.notna(row.get('excess_return')):
            print(f"    超额收益: {row['excess_return']:.2%}  |  信息比率: {row.get('information_ratio', 0):.2f}")

    # 最优策略
    best = perf_df.iloc[0]
    print(f"\n{'=' * 70}")
    print(f"最优策略: {best['strategy']}")
    print(f"  年化收益: {best['annual_return']:.2%}, 夏普比率: {best['sharpe_ratio']:.2f}, 最大回撤: {best['max_drawdown']:.2%}")
    print("=" * 70)

    # Step 8: 风险归因 (最优策略)
    if risk_model is not None:
        best_name = best['strategy']
        if best_name in strategies:
            best_weights = strategies[best_name]
            decomp = risk_model.risk_decompose(best_weights)
            print(f"\n[风险归因] {best_name}:")
            print(f"  年化波动率: {decomp['total_vol'] * np.sqrt(252):.2%}")
            print(f"  行业风险: {decomp['industry_pct']:.1%}  |  风格风险: {decomp['style_pct']:.1%}  |  特质风险: {decomp['specific_pct']:.1%}")

    db.close()
    print("\n端到端流程完成!")


if __name__ == "__main__":
    main()
