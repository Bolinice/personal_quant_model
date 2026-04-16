"""
风险模型测试
用真实数据验证Barra风险模型和组合优化
"""
import sys
sys.path.insert(0, '.')

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from app.db.base import SessionLocal
from app.models.market import StockDaily, StockBasic
from app.core.risk_model import BarraRiskModel
from app.core.portfolio_optimizer import PortfolioOptimizer
from app.core.logging import logger


def get_stock_data(db, ts_codes, start_date, end_date):
    """批量获取股票数据"""
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
        'close': float(d.close) if d.close else None,
        'pct_chg': float(d.pct_chg) if d.pct_chg else None,
        'volume': float(d.vol) if d.vol else None,
        'amount': float(d.amount) if d.amount else None,
    } for d in data])

    # 去重：同一股票同一日期只保留一条
    df = df.drop_duplicates(subset=['ts_code', 'trade_date'], keep='first')

    return df


def calc_style_factors(price_df):
    """计算风格因子"""
    results = []

    for ts_code in price_df['ts_code'].unique():
        stock_df = price_df[price_df['ts_code'] == ts_code].sort_values('trade_date')

        if len(stock_df) < 60:
            continue

        close = stock_df['close'].values
        volume = stock_df['volume'].values
        amount = stock_df['amount'].values
        pct_chg = stock_df['pct_chg'].values

        # Size: log(市值) 估算
        avg_amount = np.mean(amount[-20:]) if len(amount) >= 20 else None
        size = np.log(avg_amount) if avg_amount and avg_amount > 0 else None

        # Momentum: 过去20日收益率
        momentum = close[-1] / close[-21] - 1 if len(close) >= 21 else None

        # Volatility: 20日波动率
        volatility = np.std(pct_chg[-20:] / 100) * np.sqrt(252) if len(pct_chg) >= 20 else None

        # Turnover: 换手率估算 (成交额/市值)
        turnover = np.mean(volume[-20:]) if len(volume) >= 20 else None

        # Value: 1/价格 (低价股效应)
        value = 1.0 / close[-1] if close[-1] > 0 else None

        # Growth: 近期涨幅
        growth = close[-1] / close[-11] - 1 if len(close) >= 11 else None

        # Quality: 近期收益稳定性 (正收益天数比例)
        pos_days = np.sum(pct_chg[-20:] > 0) if len(pct_chg) >= 20 else None
        quality = pos_days / 20 if pos_days is not None else None

        results.append({
            'ts_code': ts_code,
            'size': size,
            'momentum': momentum,
            'volatility': volatility,
            'turnover': turnover,
            'value': value,
            'growth': growth,
            'quality': quality,
        })

    return pd.DataFrame(results).set_index('ts_code')


def assign_industry(ts_codes):
    """模拟行业分配（按代码首字母分组）"""
    industries = []
    for code in ts_codes:
        prefix = code[:3]
        if prefix.startswith('60'):
            industries.append('主板沪市')
        elif prefix.startswith('00'):
            industries.append('主板深市')
        elif prefix.startswith('30'):
            industries.append('创业板')
        else:
            industries.append('其他')
    return pd.Series(industries, index=ts_codes)


def main():
    print("=" * 70)
    print("Barra风险模型 + 组合优化 测试")
    print("=" * 70)

    db = SessionLocal()

    # 1. 获取数据
    print("\n[1] 获取数据...")
    stocks = db.query(StockBasic).filter(StockBasic.list_status == 'L').limit(50).all()
    ts_codes = [s.ts_code for s in stocks]

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

    price_df = get_stock_data(db, ts_codes, start_date, end_date)
    print(f"    股票数: {len(ts_codes)}, 数据量: {len(price_df)}")

    if price_df.empty:
        print("    无数据，请先同步数据")
        return

    # 2. 计算风格因子
    print("\n[2] 计算风格因子...")
    style_data = calc_style_factors(price_df)
    print(f"    有效股票数: {len(style_data)}")
    print(f"    风格因子: {style_data.columns.tolist()}")

    # 3. 构建因子暴露矩阵
    print("\n[3] 构建因子暴露矩阵...")
    risk_model = BarraRiskModel()

    # 行业数据
    industry_data = assign_industry(style_data.index)

    # 构建暴露矩阵
    exposure = risk_model.build_factor_exposure(
        returns_df=price_df,
        style_data=style_data,
        industry_data=industry_data
    )
    print(f"    因子暴露矩阵: {exposure.shape[0]} 股票 × {exposure.shape[1]} 因子")
    print(f"    行业因子: {[c for c in exposure.columns if c not in BarraRiskModel.STYLE_FACTORS]}")
    print(f"    风格因子: {[c for c in exposure.columns if c in BarraRiskModel.STYLE_FACTORS]}")

    # 4. 截面回归求因子收益率
    print("\n[4] 截面回归求因子收益率...")
    factor_returns = risk_model.fit_factor_returns_series(price_df, exposure)
    if not factor_returns.empty:
        print(f"    因子收益率时间序列: {len(factor_returns)} 期 × {factor_returns.shape[1]} 因子")
        print(f"\n    因子收益率统计:")
        stats_df = factor_returns.agg(['mean', 'std']).T * 252  # 年化
        stats_df.columns = ['年化均值', '年化标准差']
        print(stats_df.to_string())
    else:
        print("    未能计算因子收益率")
        return

    # 5. 估计协方差矩阵
    print("\n[5] 估计协方差矩阵...")
    factor_cov = risk_model.estimate_factor_cov()
    print(f"    因子协方差矩阵: {factor_cov.shape}")

    specific_var = risk_model.estimate_specific_var()
    print(f"    特质方差: {len(specific_var)} 只股票")

    cov_matrix = risk_model.estimate_cov_matrix()
    print(f"    完整协方差矩阵: {cov_matrix.shape}")

    # 6. 风险分解
    print("\n[6] 风险分解...")
    # 等权组合
    stocks_in_cov = cov_matrix.index[:30]  # 取30只测试
    equal_weights = pd.Series(1.0 / len(stocks_in_cov), index=stocks_in_cov)

    risk_decomp = risk_model.risk_decompose(equal_weights)
    print(f"    等权组合风险分解:")
    print(f"      总风险(方差): {risk_decomp['total_risk']:.6f}")
    print(f"      总波动率(日): {risk_decomp['total_vol']:.4f}")
    print(f"      总波动率(年): {risk_decomp['total_vol'] * np.sqrt(252):.2%}")
    print(f"      行业风险占比: {risk_decomp['industry_pct']:.2%}")
    print(f"      风格风险占比: {risk_decomp['style_pct']:.2%}")
    print(f"      特质风险占比: {risk_decomp['specific_pct']:.2%}")

    # 风险贡献
    rc = risk_model.calc_marginal_risk_contribution(equal_weights)
    print(f"\n    Top 5 风险贡献股票:")
    top_rc = rc.nlargest(5)
    for stock, val in top_rc.items():
        print(f"      {stock}: {val:.6f} ({val / rc.sum() * 100:.1f}%)")

    # 7. 组合优化
    print("\n[7] 组合优化...")
    optimizer = PortfolioOptimizer()

    # 期望收益: 用过去60日累计收益率年化
    latest_date = price_df['trade_date'].max()
    recent_data = price_df[price_df['trade_date'] >= pd.Timestamp(latest_date) - timedelta(days=90)]

    # 计算每只股票的累计收益
    expected_returns_list = []
    for ts_code in recent_data['ts_code'].unique():
        stock_data = recent_data[recent_data['ts_code'] == ts_code].sort_values('trade_date')
        if len(stock_data) >= 20:
            # pct_chg 可能是百分比形式(如 1.0 = 1%)
            pct = stock_data['pct_chg'].iloc[-20:] / 100
            cum_return = (1 + pct).prod() - 1
            # 年化
            annual_return = (1 + cum_return) ** (252 / 20) - 1
            expected_returns_list.append({'ts_code': ts_code, 'return': annual_return})

    expected_returns = pd.Series(
        {r['ts_code']: r['return'] for r in expected_returns_list}
    ).reindex(stocks_in_cov).fillna(0)

    # 限制极端值: 年化收益在 [-50%, 50%]
    expected_returns = expected_returns.clip(-0.5, 0.5)

    # 截取协方差子矩阵
    sub_cov = cov_matrix.loc[stocks_in_cov, stocks_in_cov]

    # 均值方差优化
    print("\n    均值方差优化:")
    mv_weights = optimizer.mean_variance_optimize(
        expected_returns, sub_cov,
        risk_aversion=1.0, max_position=0.10
    )
    mv_result = optimizer.analyze_optimization(mv_weights, expected_returns, sub_cov)
    print(f"      期望收益: {mv_result['expected_return']:.2%}")
    print(f"      波动率: {mv_result['volatility']:.2%}")
    print(f"      夏普比率: {mv_result['sharpe_ratio']:.2f}")
    print(f"      有效持仓数: {mv_result['effective_positions']:.1f}")
    print(f"      非零持仓: {mv_result['non_zero_positions']}")

    # 风险平价优化
    print("\n    风险平价优化:")
    rp_weights = optimizer.risk_parity_optimize(sub_cov, max_position=0.10)
    rp_result = optimizer.analyze_optimization(rp_weights, expected_returns, sub_cov)
    print(f"      期望收益: {rp_result['expected_return']:.2%}")
    print(f"      波动率: {rp_result['volatility']:.2%}")
    print(f"      夏普比率: {rp_result['sharpe_ratio']:.2f}")
    print(f"      有效持仓数: {rp_result['effective_positions']:.1f}")

    # 最小方差优化
    print("\n    最小方差优化:")
    minvar_weights = optimizer.min_variance_optimize(sub_cov, max_position=0.10)
    minvar_result = optimizer.analyze_optimization(minvar_weights, expected_returns, sub_cov)
    print(f"      期望收益: {minvar_result['expected_return']:.2%}")
    print(f"      波动率: {minvar_result['volatility']:.2%}")
    print(f"      夏普比率: {minvar_result['sharpe_ratio']:.2f}")
    print(f"      有效持仓数: {minvar_result['effective_positions']:.1f}")

    # 最大去相关优化
    print("\n    最大去相关优化:")
    decor_weights = optimizer.max_decorrelation_optimize(sub_cov, max_position=0.10)
    decor_result = optimizer.analyze_optimization(decor_weights, expected_returns, sub_cov)
    print(f"      期望收益: {decor_result['expected_return']:.2%}")
    print(f"      波动率: {decor_result['volatility']:.2%}")
    print(f"      夏普比率: {decor_result['sharpe_ratio']:.2f}")
    print(f"      有效持仓数: {decor_result['effective_positions']:.1f}")

    # 8. 对比等权组合
    print("\n[8] 等权组合对比:")
    eq_result = optimizer.analyze_optimization(equal_weights, expected_returns, sub_cov)
    print(f"      期望收益: {eq_result['expected_return']:.2%}")
    print(f"      波动率: {eq_result['volatility']:.2%}")
    print(f"      夏普比率: {eq_result['sharpe_ratio']:.2f}")

    # 9. 风险平价组合的风险分解
    print("\n[9] 风险平价组合风险分解:")
    rp_decomp = risk_model.risk_decompose(rp_weights)
    print(f"      总波动率(年): {rp_decomp['total_vol'] * np.sqrt(252):.2%}")
    print(f"      行业风险占比: {rp_decomp['industry_pct']:.2%}")
    print(f"      风格风险占比: {rp_decomp['style_pct']:.2%}")
    print(f"      特质风险占比: {rp_decomp['specific_pct']:.2%}")

    # 汇总
    print("\n" + "=" * 70)
    print("优化方法对比汇总")
    print("=" * 70)
    summary = pd.DataFrame([
        {'method': '等权', **{k: eq_result[k] for k in ['expected_return', 'volatility', 'sharpe_ratio']}},
        {'method': '均值方差', **{k: mv_result[k] for k in ['expected_return', 'volatility', 'sharpe_ratio']}},
        {'method': '风险平价', **{k: rp_result[k] for k in ['expected_return', 'volatility', 'sharpe_ratio']}},
        {'method': '最小方差', **{k: minvar_result[k] for k in ['expected_return', 'volatility', 'sharpe_ratio']}},
        {'method': '最大去相关', **{k: decor_result[k] for k in ['expected_return', 'volatility', 'sharpe_ratio']}},
    ])
    summary['expected_return'] = summary['expected_return'].apply(lambda x: f"{x:.2%}")
    summary['volatility'] = summary['volatility'].apply(lambda x: f"{x:.2%}")
    summary['sharpe_ratio'] = summary['sharpe_ratio'].apply(lambda x: f"{x:.2f}")
    print(summary.to_string(index=False))

    db.close()
    print("\n测试完成!")


if __name__ == "__main__":
    main()
