"""
风格因子数据准备脚本
==================
用途: 为残差动量因子计算准备风格因子数据

风格因子包括:
- size: 市值因子 (log_mv)
- value: 价值因子 (ep_ttm, bp)
- momentum: 动量因子 (ret_3m_skip1, ret_6m_skip1)
- volatility: 波动率因子 (vol_60d)
- liquidity: 流动性因子 (turnover_60d)

输出: data/style_factors/{trade_date}.parquet
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.base import SessionLocal
from app.models.market.stock_daily import StockDaily
from app.models.market.stock_daily_basic import StockDailyBasic
from app.models.market.stock_financial import StockFinancial
from app.core.logging import logger


def _safe_divide(numerator, denominator, eps: float = 1e-8):
    """安全除法，处理Decimal和None类型"""
    # 转换为float并处理None
    if isinstance(denominator, pd.Series):
        denominator = denominator.astype(float)
    denom = np.where(np.abs(denominator) < eps, np.nan, denominator)
    return numerator / denom


def fetch_price_data(session, trade_date: date, lookback_days: int = 150) -> pd.DataFrame:
    """
    获取价格数据

    Args:
        session: 数据库会话
        trade_date: 交易日期
        lookback_days: 回看天数（用于计算动量和波动率）

    Returns:
        价格数据DataFrame
    """
    start_date = trade_date - timedelta(days=lookback_days)

    stmt = select(StockDaily).where(
        StockDaily.trade_date >= start_date,
        StockDaily.trade_date <= trade_date
    )

    result = session.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return pd.DataFrame()

    data = [{
        'ts_code': r.ts_code,
        'trade_date': r.trade_date,
        'close': float(r.close) if r.close is not None else None,
        'pct_chg': float(r.pct_chg) if r.pct_chg is not None else None,
        'vol': float(r.vol) if r.vol is not None else None,
        'amount': float(r.amount) if r.amount is not None else None,
    } for r in rows]

    return pd.DataFrame(data)


def fetch_basic_data(session, trade_date: date) -> pd.DataFrame:
    """
    获取基本面数据（市值、换手率等）

    Args:
        session: 数据库会话
        trade_date: 交易日期

    Returns:
        基本面数据DataFrame
    """
    stmt = select(StockDailyBasic).where(StockDailyBasic.trade_date == trade_date)

    result = session.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return pd.DataFrame()

    data = [{
        'ts_code': r.ts_code,
        'trade_date': r.trade_date,
        'total_mv': float(r.total_mv) if r.total_mv is not None else None,
        'circ_mv': float(r.circ_mv) if r.circ_mv is not None else None,
        'turnover_rate': float(r.turnover_rate) if r.turnover_rate is not None else None,
        'pe_ttm': float(r.pe_ttm) if r.pe_ttm is not None else None,
        'pb': float(r.pb) if r.pb is not None else None,
    } for r in rows]

    return pd.DataFrame(data)


def fetch_financial_data(session, trade_date: date) -> pd.DataFrame:
    """
    获取财务数据（用于计算价值因子）

    Args:
        session: 数据库会话
        trade_date: 交易日期

    Returns:
        财务数据DataFrame
    """
    # 使用StockFinancial模型，获取PIT数据（ann_date <= trade_date）
    stmt = select(StockFinancial).where(
        StockFinancial.ann_date <= trade_date
    )
    result = session.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return pd.DataFrame()

    # 转换为DataFrame
    data = [{
        'ts_code': r.ts_code,
        'end_date': r.end_date,
        'ann_date': r.ann_date,
        'net_profit_ttm': r.net_profit_ttm,
        'revenue_ttm': r.revenue_ttm,
        'total_assets': r.total_assets,
        'total_equity': r.total_equity,
    } for r in rows]

    df = pd.DataFrame(data)

    if df.empty:
        return pd.DataFrame()

    # 对每只股票，选择最新的财务数据（按ann_date降序，取第一条）
    df = df.sort_values(['ts_code', 'ann_date'], ascending=[True, False])
    df = df.groupby('ts_code').first().reset_index()

    return df


def calc_size_factor(basic_df: pd.DataFrame) -> pd.DataFrame:
    """计算市值因子"""
    result = pd.DataFrame()
    result['ts_code'] = basic_df['ts_code']

    if 'total_mv' in basic_df.columns:
        # log(市值)，单位：亿元，转换为float避免Decimal类型问题
        result['log_mv'] = np.log(basic_df['total_mv'].astype(float) + 1)

    return result


def calc_value_factors(basic_df: pd.DataFrame, financial_df: pd.DataFrame) -> pd.DataFrame:
    """计算价值因子"""
    result = pd.DataFrame()
    result['ts_code'] = basic_df['ts_code']

    # 从basic_df直接获取PE和PB的倒数，转换为float
    if 'pe_ttm' in basic_df.columns:
        result['ep_ttm'] = _safe_divide(1.0, basic_df['pe_ttm'].astype(float))

    if 'pb' in basic_df.columns:
        result['bp'] = _safe_divide(1.0, basic_df['pb'].astype(float))

    if 'pb' in basic_df.columns:
        result['bp'] = _safe_divide(1.0, basic_df['pb'])

    return result


def calc_momentum_factors(price_df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
    """计算动量因子"""
    result = pd.DataFrame()

    if price_df.empty or 'close' not in price_df.columns:
        return result

    # 按股票和日期排序
    price_df = price_df.sort_values(['ts_code', 'trade_date'])

    # 筛选目标日期的数据
    target_df = price_df[price_df['trade_date'] == trade_date].copy()

    if target_df.empty:
        return result

    result['ts_code'] = target_df['ts_code']

    # 按股票分组计算
    grouped = price_df.groupby('ts_code')

    for ts_code in target_df['ts_code'].unique():
        stock_data = grouped.get_group(ts_code)
        stock_data = stock_data.sort_values('trade_date')

        # 获取目标日期的索引
        target_idx = stock_data[stock_data['trade_date'] == trade_date].index
        if len(target_idx) == 0:
            continue

        target_idx = target_idx[0]
        target_pos = stock_data.index.get_loc(target_idx)

        # 计算3个月动量 (跳过最近1个月)
        if target_pos >= 60:
            close_t_20 = stock_data.iloc[target_pos - 20]['close']
            close_t_60 = stock_data.iloc[target_pos - 60]['close']
            ret_3m_skip1 = close_t_20 / close_t_60 - 1
            result.loc[result['ts_code'] == ts_code, 'ret_3m_skip1'] = ret_3m_skip1

        # 计算6个月动量 (跳过最近1个月)
        if target_pos >= 120:
            close_t_20 = stock_data.iloc[target_pos - 20]['close']
            close_t_120 = stock_data.iloc[target_pos - 120]['close']
            ret_6m_skip1 = close_t_20 / close_t_120 - 1
            result.loc[result['ts_code'] == ts_code, 'ret_6m_skip1'] = ret_6m_skip1

    return result


def calc_volatility_factors(price_df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
    """计算波动率因子"""
    result = pd.DataFrame()

    if price_df.empty or 'close' not in price_df.columns:
        return result

    # 按股票和日期排序
    price_df = price_df.sort_values(['ts_code', 'trade_date'])

    # 筛选目标日期的数据
    target_df = price_df[price_df['trade_date'] == trade_date].copy()

    if target_df.empty:
        return result

    result['ts_code'] = target_df['ts_code']

    # 按股票分组计算
    grouped = price_df.groupby('ts_code')

    for ts_code in target_df['ts_code'].unique():
        stock_data = grouped.get_group(ts_code)
        stock_data = stock_data.sort_values('trade_date')

        # 计算日收益率
        stock_data['daily_ret'] = stock_data['close'].pct_change()

        # 获取目标日期的索引
        target_idx = stock_data[stock_data['trade_date'] == trade_date].index
        if len(target_idx) == 0:
            continue

        target_idx = target_idx[0]
        target_pos = stock_data.index.get_loc(target_idx)

        # 计算60日波动率
        if target_pos >= 60:
            recent_returns = stock_data.iloc[target_pos - 60:target_pos]['daily_ret']
            vol_60d = recent_returns.std() * np.sqrt(252)  # 年化
            result.loc[result['ts_code'] == ts_code, 'vol_60d'] = vol_60d

    return result


def calc_liquidity_factors(price_df: pd.DataFrame, basic_df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
    """计算流动性因子"""
    result = pd.DataFrame()

    if basic_df.empty or 'turnover_rate' not in basic_df.columns:
        return result

    result['ts_code'] = basic_df['ts_code']

    # 按股票和日期排序
    price_df = price_df.sort_values(['ts_code', 'trade_date'])

    # 按股票分组计算
    grouped = price_df.groupby('ts_code')

    for ts_code in basic_df['ts_code'].unique():
        if ts_code not in grouped.groups:
            continue

        stock_data = grouped.get_group(ts_code)
        stock_data = stock_data.sort_values('trade_date')

        # 获取目标日期的索引
        target_idx = stock_data[stock_data['trade_date'] == trade_date].index
        if len(target_idx) == 0:
            continue

        target_idx = target_idx[0]
        target_pos = stock_data.index.get_loc(target_idx)

        # 计算60日平均换手率
        if target_pos >= 60:
            # 从basic_df获取换手率数据
            basic_stock = basic_df[basic_df['ts_code'] == ts_code]
            if not basic_stock.empty and 'turnover_rate' in basic_stock.columns:
                turnover_60d = basic_stock['turnover_rate'].values[0]
                result.loc[result['ts_code'] == ts_code, 'turnover_60d'] = turnover_60d

    return result


def prepare_style_factors(trade_date: date, output_dir: Path) -> pd.DataFrame:
    """
    准备风格因子数据

    Args:
        trade_date: 交易日期
        output_dir: 输出目录

    Returns:
        风格因子DataFrame
    """
    print(f"准备 {trade_date} 的风格因子数据...")

    db = SessionLocal()
    try:
        # 1. 获取原始数据
        print("  - 获取价格数据...")
        price_df = fetch_price_data(db, trade_date, lookback_days=150)

        print("  - 获取基本面数据...")
        basic_df = fetch_basic_data(db, trade_date)

        print("  - 获取财务数据...")
        financial_df = fetch_financial_data(db, trade_date)

        if price_df.empty or basic_df.empty:
            print("  ✗ 数据不足，跳过")
            return pd.DataFrame()

        # 2. 计算各类风格因子
        print("  - 计算市值因子...")
        size_factors = calc_size_factor(basic_df)

        print("  - 计算价值因子...")
        value_factors = calc_value_factors(basic_df, financial_df)

        print("  - 计算动量因子...")
        momentum_factors = calc_momentum_factors(price_df, trade_date)

        print("  - 计算波动率因子...")
        volatility_factors = calc_volatility_factors(price_df, trade_date)

        print("  - 计算流动性因子...")
        liquidity_factors = calc_liquidity_factors(price_df, basic_df, trade_date)

        # 3. 合并所有因子
        style_factors = size_factors
        for df in [value_factors, momentum_factors, volatility_factors, liquidity_factors]:
            if not df.empty:
                style_factors = pd.merge(style_factors, df, on='ts_code', how='outer')

        # 添加交易日期
        style_factors['trade_date'] = trade_date

        # 4. 保存到文件
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{trade_date.strftime('%Y%m%d')}.parquet"
        style_factors.to_parquet(output_file, index=False)

        print(f"  ✓ 完成，共 {len(style_factors)} 只股票，{len(style_factors.columns)-2} 个因子")
        print(f"  ✓ 保存到: {output_file}")

        return style_factors
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="准备风格因子数据")
    parser.add_argument(
        '--date',
        type=str,
        help='交易日期 (YYYY-MM-DD)，默认为最近一个交易日'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='起始日期 (YYYY-MM-DD)，用于批量准备'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='结束日期 (YYYY-MM-DD)，用于批量准备'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/style_factors',
        help='输出目录，默认为 data/style_factors'
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    if args.start_date and args.end_date:
        # 批量准备
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()

        print(f"批量准备风格因子数据: {start_date} 至 {end_date}")

        # 获取交易日历
        db = SessionLocal()
        try:
            stmt = select(StockDaily.trade_date).distinct().where(
                StockDaily.trade_date >= start_date,
                StockDaily.trade_date <= end_date
            ).order_by(StockDaily.trade_date)

            result = db.execute(stmt)
            trade_dates = [row[0] for row in result]
        finally:
            db.close()

        print(f"共 {len(trade_dates)} 个交易日")

        for trade_date in trade_dates:
            prepare_style_factors(trade_date, output_dir)

    else:
        # 单日准备
        if args.date:
            trade_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        else:
            # 默认使用最近一个交易日
            db = SessionLocal()
            try:
                stmt = select(StockDaily.trade_date).distinct().order_by(
                    StockDaily.trade_date.desc()
                ).limit(1)
                result = db.execute(stmt)
                trade_date = result.scalar()
            finally:
                db.close()

        prepare_style_factors(trade_date, output_dir)


if __name__ == '__main__':
    main()
