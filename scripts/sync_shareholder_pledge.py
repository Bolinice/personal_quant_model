"""
同步股权质押数据
数据源: Tushare share_pledge + AKShare stock_share_pledge_em
"""
import sys
sys.path.insert(0, '.')

import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.market.stock_shareholder_pledge import StockShareholderPledge
from app.data_sources.tushare_source import TushareDataSource
from app.core.config import settings


BATCH_SIZE = 50
DELAY = 0.3


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


def sync_pledge_tushare(ts_code: str, start_date: str, end_date: str,
                         source: TushareDataSource) -> int:
    """使用 Tushare share_pledge 接口同步"""
    db = SessionLocal()
    try:
        try:
            df = source._pro.share_pledge(
                ts_code=ts_code,
                start_date=source._format_date(start_date),
                end_date=source._format_date(end_date)
            )
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return 0

        existing_dates = set(r[0] for r in db.query(StockShareholderPledge.trade_date).filter(
            StockShareholderPledge.ts_code == ts_code,
        ).all())

        new_records = []
        for _, row in df.iterrows():
            trade_date = str(row.get('end_date', ''))[:8]
            if not trade_date or trade_date in existing_dates:
                continue
            new_records.append(StockShareholderPledge(
                ts_code=ts_code,
                trade_date=trade_date,
                pledge_ratio=safe_float(row.get('p_ratio')),
                total_pledge_shares=safe_float(row.get('pledge_amount')),
                total_shares=safe_float(row.get('total_share')),
                pledgor_count=safe_int(row.get('pledge_count')),
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


def sync_pledge_akshare(ts_code: str) -> int:
    """使用 AKShare 同步股权质押数据"""
    db = SessionLocal()
    try:
        import akshare as ak
        code = ts_code.split('.')[0]
        df = ak.stock_share_pledge_em(symbol=code)
        if df is None or df.empty:
            return 0

        existing_dates = set(r[0] for r in db.query(StockShareholderPledge.trade_date).filter(
            StockShareholderPledge.ts_code == ts_code,
        ).all())

        new_records = []
        for _, row in df.iterrows():
            d = str(row.get('最新日期', row.get('日期', '')))[:10].replace('-', '')
            if not d or d in existing_dates:
                continue
            new_records.append(StockShareholderPledge(
                ts_code=ts_code,
                trade_date=d,
                pledge_ratio=safe_float(row.get('质押比例', row.get('质押比例(%)'))),
                total_pledge_shares=safe_float(row.get('质押数量', row.get('质押股数'))),
                pledgor_count=safe_int(row.get('质押次数', row.get('质押笔数'))),
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
    parser = argparse.ArgumentParser(description='同步股权质押数据')
    parser.add_argument('--source', choices=['tushare', 'akshare', 'auto'], default='auto',
                        help='数据源: tushare, akshare, auto(优先tushare)')
    parser.add_argument('--ts-code', type=str, help='指定单只股票')
    parser.add_argument('--days', type=int, default=365, help='同步天数(tushare)')
    args = parser.parse_args()

    source = TushareDataSource(token=settings.TUSHARE_TOKEN)
    tushare_ok = source.connect()

    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=args.days + 10)).strftime('%Y%m%d')

    if args.ts_code:
        ts_code = args.ts_code
        count = 0
        if args.source in ('tushare', 'auto') and tushare_ok:
            count = sync_pledge_tushare(ts_code, start_date, end_date, source)
            print(f"  {ts_code} (tushare): 新增 {count} 条")
        if (args.source == 'akshare' or (count <= 0 and args.source == 'auto')):
            count = sync_pledge_akshare(ts_code)
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
            'SELECT DISTINCT ts_code FROM stock_shareholder_pledge'
        )).fetchall())
    finally:
        db2.close()

    missing = [c for c in all_codes if c not in existing_codes]
    total = len(missing)
    print(f"需同步 {total} 只股票的股权质押数据")

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
            count = sync_pledge_tushare(ts_code, start_date, end_date, source)
        if count <= 0 and args.source in ('akshare', 'auto'):
            count = sync_pledge_akshare(ts_code)

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