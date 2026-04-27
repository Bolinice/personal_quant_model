"""
同步全A股原始财务报表数据 (利润表+资产负债表+现金流量表)
补充stock_financial表的原始字段: revenue, operating_cash_flow, goodwill,
total_equity_prev, total_assets_prev, TTM数据, 多期统计

用法:
  python scripts/sync_financial_raw.py              # 全量同步
  python scripts/sync_financial_raw.py --incremental # 增量(仅最近2年)
"""

import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.core.config import settings
from app.data_sources.tushare_source import TushareDataSource
from app.db.base import SessionLocal

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


def compute_ttm_and_prev(financial_df: pd.DataFrame) -> pd.DataFrame:
    """
    从连续季报计算TTM、上期数据、多期统计

    输入: 按ts_code, end_date排序的财务数据
    输出: 补充了total_equity_prev, total_assets_prev, TTM, 多期统计的DataFrame
    """
    if financial_df.empty:
        return financial_df

    df = financial_df.sort_values(['ts_code', 'end_date']).copy()

    # 上期数据: 按股票分组shift(1)
    grouped = df.groupby('ts_code')
    df['total_equity_prev'] = grouped['total_equity'].shift(1)
    df['total_assets_prev'] = grouped['total_assets'].shift(1)

    # TTM计算: 最近4个季度滚动求和
    # 对于季度数据: TTM = Q1 + Q2 + Q3 + Q4 (同一财年)
    # 简化实现: rolling(4)求和
    for col, ttm_col in [
        ('operating_revenue', 'revenue_ttm'),
        ('net_profit', 'net_profit_ttm'),
        ('deduct_net_profit', 'deduct_net_profit_ttm'),
        ('operating_cash_flow', 'ocf_ttm'),
    ]:
        if col in df.columns:
            df[ttm_col] = grouped[col].transform(
                lambda s: s.rolling(4, min_periods=4).sum()
            )

    # 同比4季前数据 (用于成长因子)
    if 'operating_revenue' in df.columns:
        df['revenue_yoy_4q'] = grouped['operating_revenue'].shift(4)
    if 'net_profit' in df.columns:
        df['net_profit_yoy_4q'] = grouped['net_profit'].shift(4)

    # 多期统计: 近8季净利均值和标准差
    if 'net_profit' in df.columns:
        df['net_profit_mean_8q'] = grouped['net_profit'].transform(
            lambda s: s.rolling(8, min_periods=4).mean()
        )
        df['net_profit_std_8q'] = grouped['net_profit'].transform(
            lambda s: s.rolling(8, min_periods=4).std()
        )

    return df


def fetch_raw_financial(source: TushareDataSource, ts_code: str) -> dict:
    """
    获取单只股票的原始财务报表数据 (利润表+资产负债表+现金流量表)
    返回合并后的dict列表
    """
    result = {}
    try:
        # 利润表
        income_df = source._pro.income(
            ts_code=ts_code,
            fields='ts_code,ann_date,f_ann_date,end_date,total_revenue,revenue,'
                   'total_cogs,oper_cost,sell_exp,admin_exp,fin_exp,'
                   'total_profit,n_income,n_net_profit,'
                   'update_flag'
        )
        if income_df is not None and not income_df.empty:
            result['income'] = income_df
    except Exception as e:
        logger.warning(f"[income] {ts_code} 失败: {e}")

    try:
        # 资产负债表
        bs_df = source._pro.balancesheet(
            ts_code=ts_code,
            fields='ts_code,ann_date,f_ann_date,end_date,'
                   'total_assets,total_liab,total_hldr_eqy_exc_min_int,'
                   'total_cur_assets,total_cur_liab,'
                   'goodwill,'
                   'update_flag'
        )
        if bs_df is not None and not bs_df.empty:
            result['balancesheet'] = bs_df
    except Exception as e:
        logger.warning(f"[balancesheet] {ts_code} 失败: {e}")

    try:
        # 现金流量表
        cf_df = source._pro.cashflow(
            ts_code=ts_code,
            fields='ts_code,ann_date,f_ann_date,end_date,'
                   'n_cashflow_act,'
                   'update_flag'
        )
        if cf_df is not None and not cf_df.empty:
            result['cashflow'] = cf_df
    except Exception as e:
        logger.warning(f"[cashflow] {ts_code} 失败: {e}")

    try:
        # 财务指标 (补充比率)
        fi_df = source._pro.fina_indicator(
            ts_code=ts_code,
            fields='ts_code,ann_date,end_date,'
                   'roe,roa,grossprofit_margin,netprofit_margin,'
                   'debt_to_assets,current_ratio,quick_ratio,'
                   'eps,bps,'
                   'or_yoy,netprofit_yoy,dt_netprofit_yoy'
        )
        if fi_df is not None and not fi_df.empty:
            result['indicator'] = fi_df
    except Exception as e:
        logger.warning(f"[indicator] {ts_code} 失败: {e}")

    return result


def merge_and_save(ts_code: str, raw_data: dict, db) -> int:
    """
    合并原始报表数据并写入stock_financial表
    """
    from app.models.market import StockFinancial

    if not raw_data:
        return 0

    # 以利润表的end_date为基准合并
    base_df = None
    for key in ['income', 'indicator', 'balancesheet', 'cashflow']:
        if key in raw_data and raw_data[key] is not None and not raw_data[key].empty:
            df = raw_data[key].copy()
            if 'end_date' in df.columns:
                if base_df is None:
                    base_df = df
                else:
                    # 合并: 同一ts_code+end_date的记录
                    base_df = base_df.merge(
                        df, on=['ts_code', 'end_date'], how='outer',
                        suffixes=('', f'_{key}')
                    )

    if base_df is None or base_df.empty:
        return 0

    # 处理ann_date: 优先f_ann_date(首次公告日), 回退ann_date
    if 'f_ann_date' in base_df.columns:
        base_df['ann_date_final'] = base_df['f_ann_date'].fillna(base_df.get('ann_date'))
    elif 'ann_date' in base_df.columns:
        base_df['ann_date_final'] = base_df['ann_date']
    else:
        base_df['ann_date_final'] = None

    # 计算TTM和上期数据
    merged = compute_ttm_and_prev(base_df)

    # 查询已有记录
    existing = {
        r[0]: r[1]
        for r in db.query(StockFinancial.end_date, StockFinancial.id)
        .filter(StockFinancial.ts_code == ts_code)
        .all()
    }

    new_count = 0
    updated_count = 0

    for _, row in merged.iterrows():
        end_date = str(row.get('end_date', ''))
        if not end_date or len(end_date) < 8:
            continue

        # 格式化end_date
        if '-' in end_date:
            end_date_fmt = end_date[:10].replace('-', '')
        else:
            end_date_fmt = str(end_date)[:8]

        ann_date_val = row.get('ann_date_final')
        if pd.notna(ann_date_val) and ann_date_val:
            ann_date_str = str(ann_date_val)[:8]
        else:
            ann_date_str = None

        record_data = {
            'ts_code': ts_code,
            'end_date': end_date_fmt,
            'ann_date': ann_date_str,
            # 利润表
            'total_revenue': safe_float(row.get('total_revenue')),
            'operating_revenue': safe_float(row.get('revenue')),
            'operating_cost': safe_float(row.get('oper_cost')),
            'gross_profit': safe_float(row.get('revenue')) and safe_float(row.get('oper_cost'))
                and (safe_float(row.get('revenue')) - safe_float(row.get('oper_cost'))),
            'total_profit': safe_float(row.get('total_profit')),
            'net_profit': safe_float(row.get('n_net_profit') or row.get('n_income')),
            'revenue_yoy': safe_float(row.get('or_yoy')),
            'net_profit_yoy': safe_float(row.get('netprofit_yoy')),
            'yoy_deduct_net_profit': safe_float(row.get('dt_netprofit_yoy')),
            # 资产负债表
            'total_assets': safe_float(row.get('total_assets')),
            'total_equity': safe_float(row.get('total_hldr_eqy_exc_min_int')),
            'current_assets': safe_float(row.get('total_cur_assets')),
            'current_liabilities': safe_float(row.get('total_cur_liab')),
            'total_liabilities': safe_float(row.get('total_liab')),
            'goodwill': safe_float(row.get('goodwill')),
            # 现金流量表
            'operating_cash_flow': safe_float(row.get('n_cashflow_act')),
            # 财务指标
            'roe': safe_float(row.get('roe')),
            'roa': safe_float(row.get('roa')),
            'gross_profit_margin': safe_float(row.get('grossprofit_margin')),
            'net_profit_margin': safe_float(row.get('netprofit_margin')),
            'current_ratio': safe_float(row.get('current_ratio')),
            'debt_to_assets': safe_float(row.get('debt_to_assets')),
            # 上期数据
            'total_equity_prev': safe_float(row.get('total_equity_prev')),
            'total_assets_prev': safe_float(row.get('total_assets_prev')),
            # TTM数据
            'revenue_ttm': safe_float(row.get('revenue_ttm')),
            'net_profit_ttm': safe_float(row.get('net_profit_ttm')),
            'deduct_net_profit_ttm': safe_float(row.get('deduct_net_profit_ttm')),
            'ocf_ttm': safe_float(row.get('ocf_ttm')),
            'revenue_yoy_4q': safe_float(row.get('revenue_yoy_4q')),
            'net_profit_yoy_4q': safe_float(row.get('net_profit_yoy_4q')),
            # 多期统计
            'net_profit_mean_8q': safe_float(row.get('net_profit_mean_8q')),
            'net_profit_std_8q': safe_float(row.get('net_profit_std_8q')),
        }

        # 计算gross_profit如果原始字段可用
        rev = safe_float(row.get('revenue'))
        cost = safe_float(row.get('oper_cost'))
        if rev is not None and cost is not None:
            record_data['gross_profit'] = rev - cost

        if end_date_fmt in existing:
            # 更新已有记录
            record = db.query(StockFinancial).get(existing[end_date_fmt])
            if record:
                for k, v in record_data.items():
                    if k != 'ts_code' and k != 'end_date':
                        setattr(record, k, v)
                updated_count += 1
        else:
            # 新增记录
            db.add(StockFinancial(**record_data))
            new_count += 1

    db.commit()
    return new_count + updated_count


def main():
    parser = argparse.ArgumentParser(description='同步全A股原始财务报表数据')
    parser.add_argument('--incremental', action='store_true', help='增量同步(仅最近2年)')
    parser.add_argument('--workers', type=int, default=4, help='并发线程数')
    parser.add_argument('--limit', type=int, default=0, help='限制股票数量(0=全部)')
    args = parser.parse_args()

    source = TushareDataSource(settings.TUSHARE_TOKEN)
    if not source.connect():
        logger.error("Tushare连接失败!")
        sys.exit(1)

    # 获取股票列表
    db = SessionLocal()
    try:
        if args.incremental:
            # 增量: 只同步最近2年有更新的股票
            cutoff = (datetime.now() - timedelta(days=730)).strftime('%Y%m%d')
            ts_codes = [
                r[0] for r in db.execute(text(
                    "SELECT DISTINCT ts_code FROM stock_financial "
                    f"WHERE ann_date >= '{cutoff}' ORDER BY ts_code"
                )).fetchall()
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

    def process_one(ts_code: str) -> int:
        db2 = SessionLocal()
        try:
            raw = fetch_raw_financial(source, ts_code)
            if not raw:
                return 0
            return merge_and_save(ts_code, raw, db2)
        except Exception as e:
            db2.rollback()
            logger.warning(f"{ts_code} 失败: {e}")
            return -1
        finally:
            db2.close()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for ts_code in ts_codes:
            future = executor.submit(process_one, ts_code)
            futures[future] = ts_code
            time.sleep(0.35)

        for future in as_completed(futures):
            try:
                n = future.result()
                if n > 0:
                    total += n
                elif n < 0:
                    failed += 1
            except Exception:
                failed += 1

            done = total + failed
            if done % 50 == 0 and done > 0:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                logger.info(f"进度: {done}/{len(futures)} 更新:{total} 失败:{failed} 速度:{rate:.1f}/s")

    elapsed = time.time() - t0
    logger.info(f"完成! 更新 {total} 条, 失败 {failed}, 耗时 {elapsed:.1f}s")


if __name__ == '__main__':
    main()
