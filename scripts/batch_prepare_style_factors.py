#!/usr/bin/env python3
"""
批量准备历史风格因子数据
用于残差动量因子计算和回测验证
"""

import sys
from pathlib import Path
from datetime import datetime, date
from typing import List

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.base import SessionLocal
from app.models.market.stock_daily import StockDaily
from sqlalchemy import distinct
import pandas as pd
import numpy as np


def get_trading_dates(start_date: datetime, end_date: datetime) -> List[datetime]:
    """获取指定日期范围内的所有交易日"""
    db = SessionLocal()
    try:
        trade_dates = db.query(distinct(StockDaily.trade_date))\
            .filter(StockDaily.trade_date >= start_date)\
            .filter(StockDaily.trade_date <= end_date)\
            .order_by(StockDaily.trade_date)\
            .all()
        # 转换为datetime对象（数据库返回的是date对象）
        return [datetime.combine(d[0], datetime.min.time()) if isinstance(d[0], date) and not isinstance(d[0], datetime) else d[0] for d in trade_dates]
    finally:
        db.close()


def get_basic_data(trade_date: datetime) -> pd.DataFrame:
    """获取基本面数据（市值、换手率等）"""
    from app.models.market.stock_daily_basic import StockDailyBasic

    db = SessionLocal()
    try:
        records = db.query(StockDailyBasic)\
            .filter(StockDailyBasic.trade_date == trade_date)\
            .all()

        if not records:
            return pd.DataFrame()

        data = []
        for r in records:
            data.append({
                'ts_code': r.ts_code,
                'trade_date': r.trade_date,
                'total_mv': float(r.total_mv) if r.total_mv else None,
                'circ_mv': float(r.circ_mv) if r.circ_mv else None,
                'turnover_rate': float(r.turnover_rate) if r.turnover_rate else None,
                'turnover_rate_f': float(r.turnover_rate_f) if r.turnover_rate_f else None,
                'pe_ttm': float(r.pe_ttm) if r.pe_ttm else None,
                'pb': float(r.pb) if r.pb else None,
            })

        df = pd.DataFrame(data)
        # 转换为float类型
        numeric_cols = ['total_mv', 'circ_mv', 'turnover_rate', 'turnover_rate_f', 'pe_ttm', 'pb']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df
    finally:
        db.close()


def get_financial_data(trade_date: datetime) -> pd.DataFrame:
    """获取财务数据（PIT对齐）"""
    from app.models.market.stock_financial import StockFinancial

    db = SessionLocal()
    try:
        # PIT对齐：只取公告日期<=trade_date的最新财报
        records = db.query(StockFinancial)\
            .filter(StockFinancial.ann_date <= trade_date)\
            .all()

        if not records:
            return pd.DataFrame()

        data = []
        for r in records:
            data.append({
                'ts_code': r.ts_code,
                'end_date': r.end_date,
                'ann_date': r.ann_date,
                'total_revenue': float(r.total_revenue) if r.total_revenue else None,
                'net_profit': float(r.net_profit) if r.net_profit else None,
                'total_assets': float(r.total_assets) if r.total_assets else None,
                'total_liab': float(r.total_liab) if r.total_liab else None,
            })

        df = pd.DataFrame(data)
        # 转换为float类型
        numeric_cols = ['total_revenue', 'net_profit', 'total_assets', 'total_liab']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(float)

        # 每只股票取最新财报
        df = df.sort_values(['ts_code', 'ann_date', 'end_date'])
        df = df.groupby('ts_code').tail(1)

        return df
    finally:
        db.close()


def get_price_data(trade_date: datetime, lookback_days: int = 120) -> pd.DataFrame:
    """获取价格数据（用于计算动量和波动率）"""
    from datetime import timedelta

    db = SessionLocal()
    try:
        start_date = trade_date - timedelta(days=lookback_days * 2)  # 预留足够的日历日

        records = db.query(StockDaily)\
            .filter(StockDaily.trade_date >= start_date)\
            .filter(StockDaily.trade_date <= trade_date)\
            .order_by(StockDaily.ts_code, StockDaily.trade_date)\
            .all()

        if not records:
            return pd.DataFrame()

        data = []
        for r in records:
            data.append({
                'ts_code': r.ts_code,
                'trade_date': r.trade_date,
                'close': float(r.close) if r.close else None,
                'vol': float(r.vol) if r.vol else None,
            })

        df = pd.DataFrame(data)
        # 转换为float类型
        numeric_cols = ['close', 'vol']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(float)
        return df
    finally:
        db.close()


def _safe_divide(numerator, denominator, default=np.nan):
    """安全除法，处理None和零除"""
    if numerator is None or denominator is None:
        return default
    if denominator == 0:
        return default
    return numerator / denominator


def calculate_style_factors(trade_date: datetime) -> pd.DataFrame:
    """计算单日风格因子"""
    # 1. 获取基本面数据
    basic_df = get_basic_data(trade_date)
    if basic_df.empty:
        print(f"  {trade_date}: 无基本面数据")
        return pd.DataFrame()

    # 2. 获取财务数据
    financial_df = get_financial_data(trade_date)

    # 3. 获取价格数据
    price_df = get_price_data(trade_date, lookback_days=120)

    # 合并数据
    result = basic_df[['ts_code', 'trade_date', 'circ_mv', 'turnover_rate_f', 'pe_ttm', 'pb']].copy()

    # 计算log_mv（对数市值）
    result['log_mv'] = result['circ_mv'].apply(lambda x: np.log(x) if x and x > 0 else np.nan)

    # 计算EP（盈利收益率 = 1/PE）
    result['ep_ttm'] = result['pe_ttm'].apply(lambda x: 1.0 / x if x and x > 0 else np.nan)

    # 计算BP（账面市值比 = 1/PB）
    result['bp'] = result['pb'].apply(lambda x: 1.0 / x if x and x > 0 else np.nan)

    # 合并财务数据计算更多因子
    if not financial_df.empty:
        result = result.merge(financial_df[['ts_code', 'net_profit', 'total_assets']],
                             on='ts_code', how='left')

    # 计算动量和波动率因子
    if not price_df.empty:
        # 按股票分组计算
        momentum_data = []
        volatility_data = []

        for ts_code in result['ts_code'].unique():
            stock_prices = price_df[price_df['ts_code'] == ts_code].sort_values('trade_date')

            if len(stock_prices) < 2:
                momentum_data.append({'ts_code': ts_code, 'ret_3m_skip1': np.nan})
                volatility_data.append({'ts_code': ts_code, 'vol_60d': np.nan})
                continue

            # 计算3个月动量（跳过最近1个月）
            # 取最近60个交易日的数据
            recent_60d = stock_prices.tail(60)
            if len(recent_60d) >= 40:  # 至少40个交易日
                # 跳过最近20个交易日，计算之前40个交易日的收益
                skip_1m = recent_60d.iloc[:-20] if len(recent_60d) > 20 else recent_60d
                if len(skip_1m) >= 2:
                    ret_3m = (skip_1m['close'].iloc[-1] / skip_1m['close'].iloc[0]) - 1
                else:
                    ret_3m = np.nan
            else:
                ret_3m = np.nan

            momentum_data.append({'ts_code': ts_code, 'ret_3m_skip1': ret_3m})

            # 计算60日波动率
            if len(recent_60d) >= 20:
                returns = recent_60d['close'].pct_change().dropna()
                vol_60d = returns.std() * np.sqrt(252) if len(returns) > 0 else np.nan
            else:
                vol_60d = np.nan

            volatility_data.append({'ts_code': ts_code, 'vol_60d': vol_60d})

        momentum_df = pd.DataFrame(momentum_data)
        volatility_df = pd.DataFrame(volatility_data)

        result = result.merge(momentum_df, on='ts_code', how='left')
        result = result.merge(volatility_df, on='ts_code', how='left')

    # 计算60日平均换手率
    result['turnover_60d'] = result['turnover_rate_f']  # 简化版，使用当日换手率

    # 选择最终因子列
    factor_cols = ['ts_code', 'trade_date', 'log_mv', 'ep_ttm', 'bp', 'ret_3m_skip1', 'vol_60d', 'turnover_60d']
    result = result[factor_cols]

    # 删除所有因子都为NaN的行
    result = result.dropna(subset=['log_mv', 'ep_ttm', 'bp'], how='all')

    return result


def main():
    """批量准备风格因子数据"""
    # 设置日期范围
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2026, 4, 17)

    print(f"批量准备风格因子数据")
    print(f"日期范围: {start_date.date()} 至 {end_date.date()}")
    print("=" * 60)

    # 获取所有交易日
    trade_dates = get_trading_dates(start_date, end_date)
    print(f"找到 {len(trade_dates)} 个交易日")
    print()

    # 创建输出目录
    output_dir = Path('data/style_factors')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 批量处理
    success_count = 0
    fail_count = 0

    for i, trade_date in enumerate(trade_dates, 1):
        try:
            # 检查文件是否已存在
            output_file = output_dir / f"{trade_date.strftime('%Y%m%d')}.parquet"
            if output_file.exists():
                print(f"[{i}/{len(trade_dates)}] {trade_date.date()}: 已存在，跳过")
                success_count += 1
                continue

            # 计算风格因子
            factors_df = calculate_style_factors(trade_date)

            if factors_df.empty:
                print(f"[{i}/{len(trade_dates)}] {trade_date.strftime('%Y-%m-%d')}: 无数据")
                fail_count += 1
                continue

            # 保存为Parquet格式
            factors_df.to_parquet(output_file, index=False)

            print(f"[{i}/{len(trade_dates)}] {trade_date.strftime('%Y-%m-%d')}: 成功 ({len(factors_df)} 只股票)")
            success_count += 1

        except Exception as e:
            print(f"[{i}/{len(trade_dates)}] {trade_date.strftime('%Y-%m-%d')}: 失败 - {e}")
            fail_count += 1

    print()
    print("=" * 60)
    print(f"批量处理完成")
    print(f"成功: {success_count} 个交易日")
    print(f"失败: {fail_count} 个交易日")
    print(f"输出目录: {output_dir.absolute()}")


if __name__ == '__main__':
    main()
