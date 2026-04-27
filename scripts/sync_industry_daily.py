"""
同步行业级别数据 (行业动量/资金流/估值偏离)
数据源: AKShare行业板块数据 + Tushare行业分类

用法:
  python scripts/sync_industry_daily.py              # 全量同步最近1年
  python scripts/sync_industry_daily.py --days 365   # 指定天数
"""

import sys
import time
import logging
import argparse
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.core.config import settings
from app.data_sources.tushare_source import TushareDataSource
from app.data_sources.akshare_source import AKShareDataSource
from app.db.base import SessionLocal
from app.models.market.industry_daily import IndustryDaily

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def safe_float(val):
    try:
        if pd.isna(val):
            return None
        v = float(val)
        return v if np.isfinite(v) else None
    except (ValueError, TypeError):
        return None


def compute_industry_stats(db) -> pd.DataFrame:
    """
    从stock_daily + stock_daily_basic + stock_industry计算行业级别统计
    """
    # 获取行业分类映射
    industry_map = {}
    for r in db.execute(text(
        "SELECT ts_code, industry_name, industry_code FROM stock_industry "
        "WHERE standard='sw' AND level='L1'"
    )).fetchall():
        industry_map[r[0]] = {'name': r[1], 'code': r[2]}

    if not industry_map:
        # 回退到stock_basic的industry字段
        for r in db.execute(text(
            "SELECT ts_code, industry FROM stock_basic WHERE list_status='L' AND industry IS NOT NULL"
        )).fetchall():
            if r[1]:
                industry_map[r[0]] = {'name': r[1], 'code': r[1]}

    if not industry_map:
        logger.warning("无行业分类数据!")
        return pd.DataFrame()

    # 获取最近30天的日线数据
    cutoff = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    daily_df = pd.DataFrame([
        {'ts_code': r[0], 'trade_date': r[1], 'close': float(r[2]) if r[2] else None,
         'pct_chg': float(r[3]) if r[3] else None, 'amount': float(r[4]) if r[4] else None,
         'vol': float(r[5]) if r[5] else None}
        for r in db.execute(text(
            f"SELECT ts_code, trade_date, close, pct_chg, amount, vol "
            f"FROM stock_daily WHERE trade_date >= '{cutoff}'"
        )).fetchall()
    ])

    if daily_df.empty:
        return pd.DataFrame()

    # 添加行业信息
    daily_df['industry_name'] = daily_df['ts_code'].map(
        lambda x: industry_map.get(x, {}).get('name', None)
    )
    daily_df['industry_code'] = daily_df['ts_code'].map(
        lambda x: industry_map.get(x, {}).get('code', None)
    )
    daily_df = daily_df.dropna(subset=['industry_name'])

    if daily_df.empty:
        return pd.DataFrame()

    # 获取每日指标 (PE/PB/换手率)
    basic_df = pd.DataFrame([
        {'ts_code': r[0], 'trade_date': r[1], 'pe_ttm': float(r[2]) if r[2] else None,
         'pb': float(r[3]) if r[3] else None, 'turnover_rate': float(r[4]) if r[4] else None,
         'total_mv': float(r[5]) if r[5] else None}
        for r in db.execute(text(
            f"SELECT ts_code, trade_date, pe_ttm, pb, turnover_rate, total_mv "
            f"FROM stock_daily_basic WHERE trade_date >= '{cutoff}'"
        )).fetchall()
    ])

    if not basic_df.empty:
        daily_df = daily_df.merge(basic_df, on=['ts_code', 'trade_date'], how='left')

    # 按行业+日期聚合
    grouped = daily_df.groupby(['industry_code', 'industry_name', 'trade_date'])

    result = pd.DataFrame()
    result['industry_code'] = grouped['industry_code'].first()
    result['industry_name'] = grouped['industry_name'].first()
    result['trade_date'] = grouped['trade_date'].first()

    # 行业1月收益率: 按行业分组计算20日收益率
    # 先按行业计算每日平均收益率
    daily_ret = daily_df.copy()
    daily_ret['daily_return'] = daily_ret['pct_chg'] / 100 if 'pct_chg' in daily_ret.columns else None

    if 'daily_return' in daily_ret.columns and daily_ret['daily_return'].notna().any():
        industry_daily_ret = daily_ret.groupby(['industry_code', 'trade_date'])['daily_return'].mean()
        # 20日累计收益率
        industry_cum_ret = industry_daily_ret.groupby('industry_code').apply(
            lambda s: (1 + s).rolling(20, min_periods=10).apply(lambda x: x.prod() - 1, raw=True)
        )
        result['industry_return_1m'] = industry_cum_ret.values if len(industry_cum_ret) == len(result) else None

    # 行业净资金流入: 按行业汇总amount变化
    if 'amount' in daily_df.columns and daily_ret['amount'].notna().any():
        result['industry_net_inflow'] = grouped['amount'].sum() / 10000  # 万元

    # 行业PE: 按行业加权平均(按市值加权)
    if 'pe_ttm' in daily_df.columns and 'total_mv' in daily_df.columns:
        # 市值加权PE
        def weighted_pe(g):
            pe = g['pe_ttm']
            mv = g['total_mv']
            valid = pe.notna() & mv.notna() & (mv > 0)
            if valid.sum() == 0:
                return None
            return (pe[valid] * mv[valid]).sum() / mv[valid].sum()
        result['industry_pe'] = grouped.apply(weighted_pe)

    # 行业PB: 市值加权
    if 'pb' in daily_df.columns and 'total_mv' in daily_df.columns:
        def weighted_pb(g):
            pb = g['pb']
            mv = g['total_mv']
            valid = pb.notna() & mv.notna() & (mv > 0)
            if valid.sum() == 0:
                return None
            return (pb[valid] * mv[valid]).sum() / mv[valid].sum()
        result['industry_pb'] = grouped.apply(weighted_pb)

    # 行业换手率: 简单平均
    if 'turnover_rate' in daily_df.columns:
        result['industry_turnover'] = grouped['turnover_rate'].mean()

    # 行业3年PE均值: 需要历史数据
    # 简化: 从已有数据计算滚动均值
    if 'industry_pe' in result.columns:
        result['industry_pe_mean_3y'] = result.groupby('industry_code')['industry_pe'].transform(
            lambda s: s.rolling(60, min_periods=30).mean()  # ~3年(约60个有效周)
        )

    return result.reset_index(drop=True)


def save_industry_daily(df: pd.DataFrame, db) -> int:
    """保存行业级别数据"""
    if df.empty:
        return 0

    existing = set(
        (r[0], r[1])
        for r in db.query(IndustryDaily.industry_code, IndustryDaily.trade_date).all()
    )

    new_records = []
    for _, row in df.iterrows():
        ic = row.get('industry_code', '')
        td = row.get('trade_date')
        if not ic or not td:
            continue

        td_date = pd.Timestamp(td).date() if not isinstance(td, datetime) else td

        if (ic, td_date) in existing:
            continue

        new_records.append(IndustryDaily(
            industry_code=ic,
            industry_name=str(row.get('industry_name', '')),
            trade_date=td_date,
            industry_return_1m=safe_float(row.get('industry_return_1m')),
            industry_net_inflow=safe_float(row.get('industry_net_inflow')),
            industry_pe=safe_float(row.get('industry_pe')),
            industry_pe_mean_3y=safe_float(row.get('industry_pe_mean_3y')),
            industry_pb=safe_float(row.get('industry_pb')),
            industry_turnover=safe_float(row.get('industry_turnover')),
        ))

    if new_records:
        db.bulk_save_objects(new_records)
        db.commit()

    return len(new_records)


def main():
    parser = argparse.ArgumentParser(description='同步行业级别数据')
    parser.add_argument('--days', type=int, default=365, help='同步天数')
    args = parser.parse_args()

    db = SessionLocal()
    try:
        logger.info("计算行业级别统计...")
        df = compute_industry_stats(db)
        if df.empty:
            logger.warning("无数据可同步!")
            return

        logger.info(f"计算完成: {len(df)} 条行业数据")
        count = save_industry_daily(df, db)
        logger.info(f"保存完成: 新增 {count} 条")
    except Exception as e:
        db.rollback()
        logger.error(f"失败: {e}")
    finally:
        db.close()


if __name__ == '__main__':
    main()