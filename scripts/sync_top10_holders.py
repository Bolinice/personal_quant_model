"""
同步前十大股东数据
数据源: Tushare top10_holders + AKShare stock_gdfx_top_10_em
按季度周期同步 (0331/0630/0930/1231)
"""
import sys
import os

# 清除代理环境变量，防止 tushare 请求走 macOS 系统代理超时
for _k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
    os.environ.pop(_k, None)

sys.path.insert(0, '.')

import time
import pandas as pd
from datetime import datetime
from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.market.stock_top10_holders import StockTop10Holders
from app.data_sources.tushare_source import TushareDataSource
from app.core.config import settings


BATCH_SIZE = 50
DELAY = 0.3
# 季度报告期
PERIODS = ['20200331', '20200630', '20200930', '20201231',
           '20210331', '20210630', '20210930', '20211231',
           '20220331', '20220630', '20220930', '20221231',
           '20230331', '20230630', '20230930', '20231231',
           '20240331', '20240630', '20240930', '20241231',
           '20250331', '20250630', '20250930', '20251231']


def safe_float(val):
    try:
        if isinstance(val, str):
            val = val.replace(',', '').replace('%', '')
        v = float(val) if pd.notna(val) and val not in ('False', '', '-') else None
        return v
    except (ValueError, TypeError):
        return None


def safe_int(val):
    try:
        return int(val) if pd.notna(val) else None
    except (ValueError, TypeError):
        return None


def sync_top10_tushare(ts_code: str, source: TushareDataSource) -> int:
    """使用 Tushare top10_holders 接口同步"""
    db = SessionLocal()
    try:
        new_records = []
        for period in PERIODS:
            # 检查是否已存在
            existing = db.query(StockTop10Holders).filter(
                StockTop10Holders.ts_code == ts_code,
                StockTop10Holders.end_date == period,
            ).first()
            if existing:
                continue

            try:
                df = source._pro.top10_holders(ts_code=ts_code, period=period)
            except Exception:
                df = pd.DataFrame()

            if df is None or df.empty:
                continue

            for rank_val, (_, row) in enumerate(df.iterrows(), 1):
                new_records.append(StockTop10Holders(
                    ts_code=ts_code,
                    end_date=period,
                    ann_date=str(row.get('ann_date', ''))[:8] if pd.notna(row.get('ann_date')) else None,
                    holder_name=str(row.get('holder_name', ''))[:100],
                    hold_amount=safe_float(row.get('hold_amount')),
                    hold_ratio=safe_float(row.get('hold_ratio')),
                    rank=rank_val,
                ))

            time.sleep(0.1)

        if new_records:
            db.bulk_save_objects(new_records)
            db.commit()
        return len(new_records)

    except Exception:
        db.rollback()
        return -1
    finally:
        db.close()


def sync_top10_akshare(ts_code: str) -> int:
    """使用 AKShare 同步前十大股东"""
    db = SessionLocal()
    try:
        import akshare as ak
        code = ts_code.split('.')[0]

        new_records = []
        try:
            df = ak.stock_gdfx_top_10_em(symbol=code)
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return 0

        # AKShare返回所有报告期数据, 按end_date分组
        for end_date, group in df.groupby('报告期' if '报告期' in df.columns else df.columns[1]):
            ed = str(end_date)[:10].replace('-', '')
            if not ed:
                continue
            existing = db.query(StockTop10Holders).filter(
                StockTop10Holders.ts_code == ts_code,
                StockTop10Holders.end_date == ed,
            ).first()
            if existing:
                continue

            for rank_val, (_, row) in enumerate(group.iterrows(), 1):
                new_records.append(StockTop10Holders(
                    ts_code=ts_code,
                    end_date=ed,
                    ann_date=ed,
                    holder_name=str(row.get('股东名称', ''))[:100],
                    hold_amount=safe_float(row.get('持股数', row.get('持有股数'))),
                    hold_ratio=safe_float(row.get('持股比例', row.get('持有比例'))),
                    rank=rank_val,
                ))

        if new_records:
            db.bulk_save_objects(new_records)
            db.commit()
        return len(new_records)

    except Exception:
        db.rollback()
        return -1
    finally:
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='同步前十大股东数据')
    parser.add_argument('--source', choices=['tushare', 'akshare', 'auto'], default='auto',
                        help='数据源: tushare, akshare, auto(优先tushare)')
    parser.add_argument('--ts-code', type=str, help='指定单只股票')
    args = parser.parse_args()

    source = TushareDataSource(token=settings.TUSHARE_TOKEN)
    tushare_ok = source.connect()

    if args.ts_code:
        ts_code = args.ts_code
        count = 0
        if args.source in ('tushare', 'auto') and tushare_ok:
            count = sync_top10_tushare(ts_code, source)
            print(f"  {ts_code} (tushare): 新增 {count} 条")
        if (args.source == 'akshare' or (count <= 0 and args.source == 'auto')):
            count = sync_top10_akshare(ts_code)
            print(f"  {ts_code} (akshare): 新增 {count} 条")
        return

    # 批量同步
    db = SessionLocal()
    try:
        all_codes = [r[0] for r in db.execute(text(
            "SELECT ts_code FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
        )).fetchall()]
    finally:
        db.close()

    db2 = SessionLocal()
    try:
        existing_codes = set(r[0] for r in db2.execute(text(
            'SELECT DISTINCT ts_code FROM stock_top10_holders'
        )).fetchall())
    finally:
        db2.close()

    missing = [c for c in all_codes if c not in existing_codes]
    total = len(missing)
    print(f"需同步 {total} 只股票的前十大股东数据")

    if total == 0:
        print("所有股票已同步")
        return

    success = 0
    fail = 0
    total_rows = 0
    t_start = time.time()

    for i, ts_code in enumerate(missing):
        count = 0
        if args.source in ('tushare', 'auto') and tushare_ok:
            count = sync_top10_tushare(ts_code, source)
        if count <= 0 and args.source in ('akshare', 'auto'):
            count = sync_top10_akshare(ts_code)

        if count > 0:
            success += 1
            total_rows += count
        elif count < 0:
            fail += 1

        if (i + 1) % BATCH_SIZE == 0 or (i + 1) == total:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{total}] 成功:{success} 失败:{fail} "
                  f"新增:{total_rows}条 速度:{rate:.1f}只/s ETA:{eta/60:.0f}min")

        time.sleep(DELAY)

    elapsed = time.time() - t_start
    print(f"\n完成! 成功:{success} 失败:{fail} 新增:{total_rows}条 耗时:{elapsed/60:.1f}min")


if __name__ == '__main__':
    main()