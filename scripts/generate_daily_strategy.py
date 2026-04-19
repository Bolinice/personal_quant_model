"""
生成当日策略报告 - 为4个股票池计算评分并写入数据库
用法: python scripts/generate_daily_strategy.py
"""
import sys
sys.path.insert(0, '.')

import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.factor_preprocess import FactorPreprocessor

# ==================== 股票池配置 ====================
UNIVERSE_CONFIG = {
    'HS300': {
        'name': '沪深300',
        'model_code': 'HS300_ENHANCED_V1',
        'model_name': '沪深300增强模型',
        'benchmark': '000300.SH',
        'index_code': '000300.SH',
        'top_n': 10,
        'max_position': 0.15,
    },
    'ZZ500': {
        'name': '中证500',
        'model_code': 'ZZ500_ENHANCED_V1',
        'model_name': '中证500增强模型',
        'benchmark': '000905.SH',
        'index_code': '000905.SH',
        'top_n': 20,
        'max_position': 0.08,
    },
    'ZZ1000': {
        'name': '中证1000',
        'model_code': 'ZZ1000_ENHANCED_V1',
        'model_name': '中证1000增强模型',
        'benchmark': '000852.SH',
        'index_code': '000852.SH',
        'top_n': 30,
        'max_position': 0.06,
    },
    'ALL_A': {
        'name': '全A股',
        'model_code': 'ALL_A_ENHANCED_V1',
        'model_name': '全A股增强模型',
        'benchmark': '000001.SH',
        'top_n': 30,
        'max_position': 0.06,
    },
}

# 因子方向
FACTOR_DIR = {
    'roe': 1, 'roa': 1, 'gross_profit_margin': 1, 'net_profit_margin': 1,
    'ret_1m_reversal': -1, 'ret_3m_skip1': 1, 'ret_6m_skip1': 1,
    'vol_20d': -1, 'vol_60d': -1,
    'amihud_20d': -1, 'zero_return_ratio': -1,
    'overnight_return': -1,
}


def load_universe(conn, universe_key):
    cfg = UNIVERSE_CONFIG[universe_key]
    if universe_key == 'ALL_A':
        rows = conn.execute(text(
            "SELECT sb.ts_code FROM stock_basic sb "
            "WHERE sb.list_status = 'L' "
            "AND (sb.name IS NULL OR (sb.name NOT LIKE '%ST%' AND sb.name NOT LIKE '%*ST%'))"
        )).fetchall()
    else:
        index_code = cfg['index_code']
        rows = conn.execute(text(
            "SELECT ts_code FROM index_components WHERE index_code = :idx"
        ), {'idx': index_code}).fetchall()
    return [r[0] for r in rows]


def calc_factors(trade_date, stock_daily, financial, universe_codes):
    """计算截面因子并返回评分"""
    td = pd.Timestamp(trade_date)
    start_date = td - timedelta(days=400)

    codes_set = set(universe_codes)
    price_window = stock_daily[
        (stock_daily['trade_date'] >= start_date) &
        (stock_daily['trade_date'] <= td) &
        (stock_daily['ts_code'].isin(codes_set))
    ].copy()

    if price_window.empty:
        return pd.DataFrame()

    fin_latest = financial[financial['end_date'] <= td].copy()
    if not fin_latest.empty:
        fin_latest = fin_latest.sort_values('end_date').groupby('ts_code').last()

    price_window = price_window.sort_values(['ts_code', 'trade_date'])
    stock_counts = price_window.groupby('ts_code').size()
    valid_stocks = stock_counts[stock_counts >= 60].index
    price_window = price_window[price_window['ts_code'].isin(valid_stocks)]

    if price_window.empty:
        return pd.DataFrame()

    close = price_window.set_index(['ts_code', 'trade_date'])['close'].unstack(level=0)
    grouped = price_window.groupby('ts_code')

    results = {}
    for ts_code in valid_stocks:
        if ts_code not in close.columns:
            continue
        c = close[ts_code].dropna()
        row = {}
        if len(c) >= 20:
            row['ret_1m_reversal'] = c.iloc[-1] / c.iloc[-20] - 1
        if len(c) >= 60:
            row['ret_3m_skip1'] = c.iloc[-20] / c.iloc[-60] - 1 if c.iloc[-60] != 0 else np.nan
        if len(c) >= 120:
            row['ret_6m_skip1'] = c.iloc[-20] / c.iloc[-120] - 1 if c.iloc[-120] != 0 else np.nan
        results[ts_code] = row

    for ts_code, group in grouped:
        if ts_code not in results:
            continue
        group = group.sort_values('trade_date')
        row = results[ts_code]
        close_s = group['close']
        open_ = group['open']
        amount = group['amount']
        daily_ret = close_s.pct_change().dropna()

        if len(daily_ret) >= 20:
            row['vol_20d'] = daily_ret.iloc[-20:].std() * np.sqrt(252)
        if len(daily_ret) >= 60:
            row['vol_60d'] = daily_ret.iloc[-60:].std() * np.sqrt(252)
        if len(group) >= 20 and (amount.iloc[-20:] > 0).all():
            abs_ret = close_s.pct_change().abs()
            amihud = (abs_ret / amount.replace(0, np.nan)).iloc[-20:].mean()
            row['amihud_20d'] = amihud if not np.isnan(amihud) else np.nan
        if len(daily_ret) >= 20:
            row['zero_return_ratio'] = (daily_ret.iloc[-20:].abs() < 0.001).mean()
        if len(group) >= 20 and (close_s.iloc[:-1] > 0).all():
            overnight = open_.iloc[1:].values / close_s.iloc[:-1].values - 1
            row['overnight_return'] = np.mean(overnight[-20:])
        if ts_code in fin_latest.index:
            f = fin_latest.loc[ts_code]
            row['roe'] = f.get('roe')
            row['roa'] = f.get('roa')
            row['gross_profit_margin'] = f.get('gross_profit_margin')
            row['net_profit_margin'] = f.get('net_profit_ratio')

    if not results:
        return pd.DataFrame()

    factor_df = pd.DataFrame(results).T
    factor_df.index.name = 'ts_code'

    # 预处理: MAD去极值 + Z-score标准化 + 方向调整
    preprocessor = FactorPreprocessor()
    factor_cols = [c for c in factor_df.columns if c in FACTOR_DIR]

    for col in factor_cols:
        series = factor_df[col].dropna()
        if len(series) < 10:
            continue
        median = series.median()
        mad = (series - median).abs().median()
        if mad > 0:
            upper = median + 3 * 1.4826 * mad
            lower = median - 3 * 1.4826 * mad
            factor_df[col] = factor_df[col].clip(lower, upper)
        mean = factor_df[col].mean()
        std = factor_df[col].std()
        if std > 0:
            factor_df[col] = (factor_df[col] - mean) / std
        direction = FACTOR_DIR.get(col, 1)
        if direction < 0:
            factor_df[col] = -factor_df[col]

    # 等权综合评分
    valid_cols = [c for c in factor_cols if c in factor_df.columns]
    factor_df['total_score'] = factor_df[valid_cols].mean(axis=1)
    factor_df['rank'] = factor_df['total_score'].rank(ascending=False)
    factor_df['quantile'] = factor_df['total_score'].rank(pct=True)

    return factor_df


def ensure_models(conn):
    """确保4个股票池都有对应的模型记录"""
    for code, cfg in UNIVERSE_CONFIG.items():
        existing = conn.execute(text(
            "SELECT id FROM models WHERE model_code = :mc"
        ), {'mc': cfg['model_code']}).fetchone()
        if not existing:
            conn.execute(text(
                "INSERT INTO models (model_code, model_name, model_type, description, version, status) "
                "VALUES (:mc, :mn, :mt, :desc, '1.0', 'active')"
            ), {
                'mc': cfg['model_code'],
                'mn': cfg['model_name'],
                'mt': code.lower(),
                'desc': f"基于多因子的{cfg['name']}增强策略",
            })
            conn.commit()
            print(f"  创建模型: {cfg['model_code']}")


def save_scores(conn, model_id, trade_date, factor_df, top_n):
    """保存评分到model_scores表"""
    # 先删除该模型该日期的旧评分
    conn.execute(text(
        "DELETE FROM model_scores WHERE model_id = :mid AND trade_date = :td"
    ), {'mid': model_id, 'td': trade_date})

    top_stocks = factor_df.nsmallest(top_n, 'rank')
    selected_set = set(top_stocks.index)

    count = 0
    for ts_code, row in factor_df.iterrows():
        score = row.get('total_score', 0)
        rank = row.get('rank', 0)
        quantile = row.get('quantile', 0)
        is_selected = ts_code in selected_set

        if pd.isna(score):
            continue

        conn.execute(text(
            "INSERT INTO model_scores "
            "(model_id, security_id, trade_date, score, rank, quantile, is_selected) "
            "VALUES (:mid, :sid, :td, :score, :rank, :quantile, :selected)"
        ), {
            'mid': model_id, 'sid': ts_code, 'td': trade_date,
            'score': float(score), 'rank': int(rank) if not pd.isna(rank) else None,
            'quantile': float(quantile) if not pd.isna(quantile) else None,
            'selected': is_selected,
        })
        count += 1

    conn.commit()
    return count


def save_performance(conn, model_id, trade_date, factor_df, stock_daily, index_daily, benchmark, top_n):
    """计算并保存策略表现到model_performance表"""
    # 删除旧记录
    conn.execute(text(
        "DELETE FROM model_performance WHERE model_id = :mid AND trade_date = :td"
    ), {'mid': model_id, 'td': trade_date})

    top_stocks = factor_df.nsmallest(top_n, 'rank')
    selected_codes = list(top_stocks.index)

    # 计算当日组合收益
    td = pd.Timestamp(trade_date)
    prev_td = td - timedelta(days=5)  # 向前找前一个交易日

    daily_return = None
    if selected_codes:
        codes_str = ','.join(f"'{c}'" for c in selected_codes)
        ret_rows = conn.execute(text(
            f"SELECT ts_code, pct_chg FROM stock_daily "
            f"WHERE trade_date = :td AND ts_code IN ({codes_str})"
        ), {'td': str(trade_date)}).fetchall()
        if ret_rows:
            daily_return = np.mean([float(r[1]) for r in ret_rows if r[1] is not None]) / 100

    # 计算累计收益 (简化: 从30天前开始)
    cum_return = None
    if daily_return is not None:
        start_date = trade_date - timedelta(days=30)
        cum_rows = conn.execute(text(
            "SELECT trade_date, pct_chg FROM stock_daily "
            f"WHERE trade_date >= :sd AND trade_date <= :td AND ts_code IN ({codes_str}) "
            "ORDER BY trade_date"
        ), {'sd': str(start_date), 'td': str(trade_date)}).fetchall()
        if cum_rows:
            daily_rets_df = pd.DataFrame(cum_rows, columns=['date', 'pct'])
            avg_daily = daily_rets_df.groupby('date')['pct'].mean() / 100
            cum_return = (1 + avg_daily).prod() - 1

    # 计算IC (简化: 用评分和次日收益的相关性)
    ic_val = None
    rank_ic_val = None

    # 计算波动率和夏普
    sharpe = None
    max_dd = None
    if daily_return is not None:
        # 用近20天数据估算
        start_date = trade_date - timedelta(days=30)
        ret_rows = conn.execute(text(
            "SELECT trade_date, AVG(pct_chg) as avg_ret FROM stock_daily "
            f"WHERE trade_date >= :sd AND trade_date <= :td AND ts_code IN ({codes_str}) "
            "GROUP BY trade_date ORDER BY trade_date"
        ), {'sd': str(start_date), 'td': str(trade_date)}).fetchall()
        if len(ret_rows) >= 10:
            rets = np.array([float(r[1]) / 100 for r in ret_rows])
            vol = rets.std() * np.sqrt(252)
            if vol > 0:
                sharpe = rets.mean() / rets.std() * np.sqrt(252)
            # 最大回撤
            cum = (1 + rets).cumprod()
            peak = np.maximum.accumulate(cum)
            dd = (cum - peak) / peak
            max_dd = float(dd.min())

    # 换手率 (简化: 设为默认值)
    turnover = 0.05

    conn.execute(text(
        "INSERT INTO model_performance "
        "(model_id, trade_date, daily_return, cumulative_return, max_drawdown, "
        "sharpe_ratio, ic, rank_ic, turnover, num_selected) "
        "VALUES (:mid, :td, :dr, :cr, :mdd, :sr, :ic, :ric, :to, :ns)"
    ), {
        'mid': model_id, 'td': trade_date,
        'dr': daily_return, 'cr': cum_return, 'mdd': max_dd,
        'sr': sharpe, 'ic': ic_val, 'ric': rank_ic_val,
        'to': turnover, 'ns': len(selected_codes),
    })
    conn.commit()


def main():
    engine = create_engine(settings.DATABASE_URL)

    with engine.connect() as conn:
        # 获取最新交易日
        latest_date = conn.execute(text(
            "SELECT MAX(trade_date) FROM stock_daily"
        )).scalar()
        trade_date = pd.Timestamp(latest_date).date()
        print(f"最新交易日: {trade_date}")

        # 确保模型存在
        print("\n[1] 确保模型记录...")
        ensure_models(conn)

        # 加载日线和财务数据
        print("\n[2] 加载市场数据...")
        stock_daily = pd.read_sql(text(
            "SELECT ts_code, trade_date, open, close, pct_chg, vol, amount "
            "FROM stock_daily WHERE trade_date >= :sd ORDER BY ts_code, trade_date"
        ), conn, params={'sd': str(trade_date - timedelta(days=400))})
        stock_daily['trade_date'] = pd.to_datetime(stock_daily['trade_date'])
        print(f"  股票日线: {len(stock_daily)} 条")

        financial = pd.read_sql(text(
            "SELECT ts_code, end_date, revenue, net_profit, roe, roa, "
            "gross_profit_margin, net_profit_ratio "
            "FROM stock_financial ORDER BY ts_code, end_date"
        ), conn)
        financial['end_date'] = pd.to_datetime(financial['end_date'])
        print(f"  财务数据: {len(financial)} 条")

        index_daily = pd.read_sql(text(
            "SELECT index_code, trade_date, close, pct_chg FROM index_daily ORDER BY trade_date"
        ), conn)
        index_daily['trade_date'] = pd.to_datetime(index_daily['trade_date'])

        # 为每个股票池计算评分
        print(f"\n[3] 计算当日策略评分...")
        for code, cfg in UNIVERSE_CONFIG.items():
            print(f"\n  --- {cfg['name']} ---")
            universe = load_universe(conn, code)
            print(f"  股票池: {len(universe)} 只")

            factor_df = calc_factors(trade_date, stock_daily, financial, universe)
            if factor_df.empty:
                print(f"  因子计算失败，跳过")
                continue
            print(f"  因子计算完成: {len(factor_df)} 只, {len(factor_df.columns)-3} 个因子")

            # 获取模型ID
            model_row = conn.execute(text(
                "SELECT id FROM models WHERE model_code = :mc"
            ), {'mc': cfg['model_code']}).fetchone()
            model_id = model_row[0]

            # 保存评分
            n_scores = save_scores(conn, model_id, trade_date, factor_df, cfg['top_n'])
            print(f"  保存评分: {n_scores} 条, Top{cfg['top_n']}入选")

            # 保存表现
            save_performance(conn, model_id, trade_date, factor_df, stock_daily, index_daily, cfg['benchmark'], cfg['top_n'])
            print(f"  保存策略表现")

            # 打印Top10
            top10 = factor_df.nsmallest(10, 'rank')[['total_score', 'rank']]
            print(f"\n  Top10持仓:")
            for ts_code, row in top10.iterrows():
                print(f"    {ts_code}  得分:{row['total_score']:.4f}  排名:{int(row['rank'])}")

    print(f"\n完成! 数据已写入 model_scores 和 model_performance 表")


if __name__ == '__main__':
    main()
