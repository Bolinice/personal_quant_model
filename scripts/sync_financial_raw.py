"""
同步全A股原始财务报表数据 (利润表+资产负债表+现金流量表)
补充stock_financial表的原始字段: revenue, operating_cash_flow, goodwill,
total_equity_prev, total_assets_prev, TTM数据, 多期统计

用法:
  python scripts/sync_financial_raw.py              # 全量同步
  python scripts/sync_financial_raw.py --incremental # 增量(仅最近2年)
  python scripts/sync_financial_raw.py --limit 10    # 限制股票数量
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
from app.db.base import SessionLocal
from scripts.script_utils import safe_date

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


def fetch_one_stock(pro, ts_code: str) -> pd.DataFrame:
    """
    获取单只股票的利润表+资产负债表+现金流量表，合并为标准化的DataFrame
    """
    dfs = {}

    # 利润表
    try:
        df = pro.income(
            ts_code=ts_code,
            fields='ts_code,ann_date,f_ann_date,end_date,'
                   'total_revenue,revenue,oper_cost,'
                   'total_profit,n_income,'
                   'update_flag'
        )
        if df is not None and not df.empty:
            dfs['income'] = df
    except Exception as e:
        logger.debug(f"[income] {ts_code}: {e}")

    # 资产负债表
    try:
        df = pro.balancesheet(
            ts_code=ts_code,
            fields='ts_code,ann_date,f_ann_date,end_date,'
                   'total_assets,total_liab,total_hldr_eqy_exc_min_int,'
                   'total_cur_assets,total_cur_liab,'
                   'goodwill,'
                   'update_flag'
        )
        if df is not None and not df.empty:
            dfs['bs'] = df
    except Exception as e:
        logger.debug(f"[bs] {ts_code}: {e}")

    # 现金流量表
    try:
        df = pro.cashflow(
            ts_code=ts_code,
            fields='ts_code,ann_date,f_ann_date,end_date,'
                   'n_cashflow_act,'
                   'update_flag'
        )
        if df is not None and not df.empty:
            dfs['cf'] = df
    except Exception as e:
        logger.debug(f"[cf] {ts_code}: {e}")

    # 财务指标
    try:
        df = pro.fina_indicator(
            ts_code=ts_code,
            fields='ts_code,ann_date,end_date,'
                   'roe,roa,grossprofit_margin,netprofit_margin,'
                   'debt_to_assets,current_ratio,quick_ratio,'
                   'or_yoy,netprofit_yoy,dt_netprofit_yoy'
        )
        if df is not None and not df.empty:
            dfs['fi'] = df
    except Exception as e:
        logger.debug(f"[fi] {ts_code}: {e}")

    if not dfs:
        return pd.DataFrame()

    # 统一end_date格式为date对象
    for key, df in dfs.items():
        df['end_date'] = pd.to_datetime(df['end_date']).dt.date

    # 收集ann_date (优先f_ann_date)
    ann_date_map = {}
    for key in ['income', 'bs', 'cf']:
        if key in dfs:
            for _, row in dfs[key].iterrows():
                k = (str(row['ts_code']), row['end_date'])
                fad = row.get('f_ann_date')
                ad = row.get('ann_date')
                if pd.notna(fad) and fad:
                    ann_date_map[k] = safe_date(fad)
                elif pd.notna(ad) and ad:
                    ann_date_map[k] = safe_date(ad)

    # 以income为基准合并
    base_key = 'income' if 'income' in dfs else list(dfs.keys())[0]
    merged = dfs[base_key][['ts_code', 'end_date']].copy()

    # 逐表合并
    if 'income' in dfs:
        inc = dfs['income'][['ts_code', 'end_date', 'total_revenue', 'revenue',
                             'oper_cost', 'total_profit', 'n_income']].copy()
        inc = inc.rename(columns={
            'revenue': 'operating_revenue',
            'oper_cost': 'operating_cost',
            'n_income': 'net_profit',
        })
        merged = merged.merge(inc, on=['ts_code', 'end_date'], how='outer')

    if 'bs' in dfs:
        bs = dfs['bs'][['ts_code', 'end_date', 'total_assets', 'total_liab',
                         'total_hldr_eqy_exc_min_int', 'total_cur_assets',
                         'total_cur_liab', 'goodwill']].copy()
        bs = bs.rename(columns={
            'total_hldr_eqy_exc_min_int': 'total_equity',
            'total_cur_assets': 'current_assets',
            'total_cur_liab': 'current_liabilities',
            'total_liab': 'total_liabilities',
        })
        merged = merged.merge(bs, on=['ts_code', 'end_date'], how='outer')

    if 'cf' in dfs:
        cf = dfs['cf'][['ts_code', 'end_date', 'n_cashflow_act']].copy()
        cf = cf.rename(columns={'n_cashflow_act': 'operating_cash_flow'})
        merged = merged.merge(cf, on=['ts_code', 'end_date'], how='outer')

    if 'fi' in dfs:
        fi = dfs['fi'][['ts_code', 'end_date', 'roe', 'roa', 'grossprofit_margin',
                         'netprofit_margin', 'debt_to_assets', 'current_ratio',
                         'or_yoy', 'netprofit_yoy', 'dt_netprofit_yoy']].copy()
        fi = fi.rename(columns={
            'grossprofit_margin': 'gross_profit_margin',
            'netprofit_margin': 'net_profit_margin',
            'or_yoy': 'revenue_yoy',
            'netprofit_yoy': 'net_profit_yoy',
            'dt_netprofit_yoy': 'yoy_deduct_net_profit',
        })
        merged = merged.merge(fi, on=['ts_code', 'end_date'], how='outer')

    # 计算gross_profit
    if 'operating_revenue' in merged.columns and 'operating_cost' in merged.columns:
        rev = pd.to_numeric(merged['operating_revenue'], errors='coerce')
        cost = pd.to_numeric(merged['operating_cost'], errors='coerce')
        merged['gross_profit'] = rev - cost

    # 添加ann_date
    merged['ann_date'] = merged.apply(
        lambda r: ann_date_map.get((r['ts_code'], r['end_date'])), axis=1
    )

    # 确保数值列为float
    numeric_cols = ['total_revenue', 'operating_revenue', 'operating_cost', 'gross_profit',
                    'total_profit', 'net_profit', 'total_assets', 'total_equity',
                    'current_assets', 'current_liabilities', 'total_liabilities',
                    'goodwill', 'operating_cash_flow', 'roe', 'roa',
                    'gross_profit_margin', 'net_profit_margin', 'debt_to_assets',
                    'current_ratio', 'revenue_yoy', 'net_profit_yoy', 'yoy_deduct_net_profit']
    for col in numeric_cols:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors='coerce')

    # 计算上期数据
    merged = merged.sort_values(['ts_code', 'end_date'])
    if 'total_equity' in merged.columns:
        merged['total_equity_prev'] = merged.groupby('ts_code')['total_equity'].shift(1)
    if 'total_assets' in merged.columns:
        merged['total_assets_prev'] = merged.groupby('ts_code')['total_assets'].shift(1)

    # 计算TTM (最近4季滚动求和)
    for src_col, ttm_col in [
        ('operating_revenue', 'revenue_ttm'),
        ('net_profit', 'net_profit_ttm'),
        ('operating_cash_flow', 'ocf_ttm'),
    ]:
        if src_col in merged.columns:
            merged[ttm_col] = merged.groupby('ts_code')[src_col].transform(
                lambda s: s.rolling(4, min_periods=4).sum()
            )

    # 同比4季前
    if 'operating_revenue' in merged.columns:
        merged['revenue_yoy_4q'] = merged.groupby('ts_code')['operating_revenue'].shift(4)
    if 'net_profit' in merged.columns:
        merged['net_profit_yoy_4q'] = merged.groupby('ts_code')['net_profit'].shift(4)

    # 多期统计
    if 'net_profit' in merged.columns:
        merged['net_profit_mean_8q'] = merged.groupby('ts_code')['net_profit'].transform(
            lambda s: s.rolling(8, min_periods=4).mean()
        )
        merged['net_profit_std_8q'] = merged.groupby('ts_code')['net_profit'].transform(
            lambda s: s.rolling(8, min_periods=4).std()
        )

    return merged


def save_to_db(merged_df: pd.DataFrame, db) -> int:
    """将合并后的数据写入stock_financial表 (upsert)"""
    from app.models.market import StockFinancial

    if merged_df.empty:
        return 0

    ts_code = merged_df['ts_code'].iloc[0]

    # 查询已有记录
    existing = {}
    for r in db.query(StockFinancial.id, StockFinancial.end_date).filter(
        StockFinancial.ts_code == ts_code
    ).all():
        existing[r[1]] = r[0]

    count = 0
    for _, row in merged_df.iterrows():
        end_date = safe_date(row.get('end_date'))
        if not end_date:
            continue

        ann_date_val = safe_date(row.get('ann_date'))

        data = {
            'ts_code': ts_code,
            'end_date': end_date,
            'ann_date': ann_date_val,
            'total_revenue': safe_float(row.get('total_revenue')),
            'operating_revenue': safe_float(row.get('operating_revenue')),
            'operating_cost': safe_float(row.get('operating_cost')),
            'gross_profit': safe_float(row.get('gross_profit')),
            'total_profit': safe_float(row.get('total_profit')),
            'net_profit': safe_float(row.get('net_profit')),
            'revenue_yoy': safe_float(row.get('revenue_yoy')),
            'net_profit_yoy': safe_float(row.get('net_profit_yoy')),
            'yoy_deduct_net_profit': safe_float(row.get('yoy_deduct_net_profit')),
            'total_assets': safe_float(row.get('total_assets')),
            'total_equity': safe_float(row.get('total_equity')),
            'current_assets': safe_float(row.get('current_assets')),
            'current_liabilities': safe_float(row.get('current_liabilities')),
            'total_liabilities': safe_float(row.get('total_liabilities')),
            'goodwill': safe_float(row.get('goodwill')),
            'operating_cash_flow': safe_float(row.get('operating_cash_flow')),
            'roe': safe_float(row.get('roe')),
            'roa': safe_float(row.get('roa')),
            'gross_profit_margin': safe_float(row.get('gross_profit_margin')),
            'net_profit_margin': safe_float(row.get('net_profit_margin')),
            'current_ratio': safe_float(row.get('current_ratio')),
            'debt_to_assets': safe_float(row.get('debt_to_assets')),
            'total_equity_prev': safe_float(row.get('total_equity_prev')),
            'total_assets_prev': safe_float(row.get('total_assets_prev')),
            'revenue_ttm': safe_float(row.get('revenue_ttm')),
            'net_profit_ttm': safe_float(row.get('net_profit_ttm')),
            'ocf_ttm': safe_float(row.get('ocf_ttm')),
            'revenue_yoy_4q': safe_float(row.get('revenue_yoy_4q')),
            'net_profit_yoy_4q': safe_float(row.get('net_profit_yoy_4q')),
            'net_profit_mean_8q': safe_float(row.get('net_profit_mean_8q')),
            'net_profit_std_8q': safe_float(row.get('net_profit_std_8q')),
        }

        if end_date in existing:
            record = db.query(StockFinancial).get(existing[end_date])
            if record:
                for k, v in data.items():
                    if k not in ('ts_code', 'end_date') and v is not None:
                        setattr(record, k, v)
        else:
            db.add(StockFinancial(**data))

        count += 1

    db.commit()
    return count


def main():
    parser = argparse.ArgumentParser(description='同步全A股原始财务报表数据')
    parser.add_argument('--incremental', action='store_true', help='增量同步(仅最近2年)')
    parser.add_argument('--workers', type=int, default=1, help='并发线程数(Tushare限流建议1)')
    parser.add_argument('--limit', type=int, default=0, help='限制股票数量(0=全部)')
    args = parser.parse_args()

    source = TushareDataSource(settings.TUSHARE_TOKEN)
    if not source.connect():
        logger.error("Tushare连接失败!")
        sys.exit(1)
    pro = source._pro
    # 使用代理API
    pro._DataApi__http_url = "http://tsy.xiaodefa.cn"

    # 获取股票列表
    db = SessionLocal()
    try:
        if args.incremental:
            cutoff = (datetime.now() - timedelta(days=730)).strftime('%Y%m%d')
            ts_codes = [
                r[0] for r in db.execute(text(
                    "SELECT DISTINCT ts_code FROM stock_financial WHERE ann_date >= :cutoff ORDER BY ts_code"
                ), {"cutoff": safe_date(cutoff)}).fetchall()
            ]
            logger.info(f"增量模式: {len(ts_codes)} 只股票")
        else:
            ts_codes = [
                r[0] for r in db.execute(text(
                    "SELECT ts_code FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
                )).fetchall()
            ]
            logger.info(f"全量模式: {len(ts_codes)} 只股票")
    finally:
        db.close()

    if args.limit > 0:
        ts_codes = ts_codes[:args.limit]

    total = 0
    failed = 0
    t0 = time.time()

    for i, ts_code in enumerate(ts_codes):
        try:
            merged = fetch_one_stock(pro, ts_code)
            if merged.empty:
                continue

            db2 = SessionLocal()
            try:
                n = save_to_db(merged, db2)
                total += n
            except Exception as e:
                db2.rollback()
                logger.warning(f"{ts_code} 写入失败: {e}")
                failed += 1
            finally:
                db2.close()
        except Exception as e:
            logger.warning(f"{ts_code} 获取失败: {e}")
            failed += 1

        # Tushare限流
        time.sleep(0.35)

        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(ts_codes) - i - 1) / rate / 60 if rate > 0 else 0
            logger.info(f"进度: {i+1}/{len(ts_codes)} 更新:{total} 失败:{failed} 速度:{rate:.1f}/s ETA:{eta:.0f}min")

    elapsed = time.time() - t0
    logger.info(f"完成! 更新 {total} 条, 失败 {failed}, 耗时 {elapsed/60:.1f}min")


if __name__ == '__main__':
    main()
