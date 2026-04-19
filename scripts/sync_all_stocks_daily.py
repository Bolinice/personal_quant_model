"""
批量同步全A股日线数据
使用AKShare腾讯接口，支持断点续传
优化: 批量存在性检查 + 线程并行
"""
import sys
sys.path.insert(0, '.')

import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from app.db.base import SessionLocal
import akshare as ak
from concurrent.futures import ThreadPoolExecutor, as_completed

BATCH_SIZE = 50
DELAY = 0.3  # 请求间隔秒数
START_DATE = '2024-04-01'
END_DATE = '2026-04-19'
MAX_WORKERS = 4  # 并行线程数


def get_missing_codes(db) -> list[tuple[str, str, str]]:
    """获取需要同步的股票代码"""
    existing = set([r[0] for r in db.execute(text('SELECT DISTINCT ts_code FROM stock_daily')).fetchall()])
    all_codes = db.execute(text(
        "SELECT ts_code, symbol, name FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
    )).fetchall()
    missing = [(c[0], c[1], c[2]) for c in all_codes if c[0] not in existing]
    return missing


def sync_stock_daily(ts_code: str, symbol: str) -> int:
    """同步单只股票日线数据 - 优化版: 批量存在性检查"""
    from app.models.market import StockDaily

    db = SessionLocal()
    try:
        # 构造腾讯接口的symbol
        if ts_code.endswith('.SH'):
            tx_symbol = f'sh{symbol}'
        elif ts_code.endswith('.SZ'):
            tx_symbol = f'sz{symbol}'
        else:
            return 0

        df = ak.stock_zh_a_hist_tx(symbol=tx_symbol, start_date=START_DATE, end_date=END_DATE)
        if df.empty:
            return 0

        # 批量获取已存在的日期 (替代逐行SELECT)
        dates_in_df = [pd.Timestamp(row['date']).date() for _, row in df.iterrows()]
        if not dates_in_df:
            return 0

        existing_dates = set(r[0] for r in db.query(StockDaily.trade_date).filter(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date.in_(dates_in_df),
        ).all())

        # 批量插入不存在的记录
        new_records = []
        for _, row in df.iterrows():
            trade_date = pd.Timestamp(row['date']).date()
            if trade_date not in existing_dates:
                new_records.append(StockDaily(
                    ts_code=ts_code,
                    trade_date=trade_date,
                    open=float(row.get('open', 0)),
                    high=float(row.get('high', 0)),
                    low=float(row.get('low', 0)),
                    close=float(row.get('close', 0)),
                    pre_close=float(row.get('close', 0)),
                    change=0,
                    pct_chg=0,
                    vol=float(row.get('volume', 0)),
                    amount=float(row.get('amount', 0)),
                    data_source='akshare',
                ))

        if new_records:
            db.bulk_save_objects(new_records)
            db.commit()

        return len(new_records)
    except Exception:
        db.rollback()
        return -1  # 标记失败
    finally:
        db.close()


def main():
    db = SessionLocal()
    missing = get_missing_codes(db)
    db.close()

    total = len(missing)
    print(f"需同步 {total} 只股票的日线数据 ({START_DATE} ~ {END_DATE})")

    success = 0
    fail = 0
    skip = 0
    total_rows = 0
    t_start = time.time()
    completed = 0

    # 使用线程池并行同步
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for ts_code, symbol, name in missing:
            future = executor.submit(sync_stock_daily, ts_code, symbol)
            futures[future] = (ts_code, symbol, name)
            time.sleep(DELAY)  # 限速

        for future in as_completed(futures):
            ts_code, symbol, name = futures[future]
            try:
                count = future.result()
            except Exception:
                count = -1

            completed += 1
            if count > 0:
                success += 1
                total_rows += count
            elif count == 0:
                skip += 1
            else:
                fail += 1

            if completed % BATCH_SIZE == 0 or completed == total:
                elapsed = time.time() - t_start
                rate = completed / elapsed
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"  [{completed}/{total}] 成功:{success} 跳过:{skip} 失败:{fail} "
                      f"新增:{total_rows}条 速度:{rate:.1f}只/s ETA:{eta/60:.0f}min")

    elapsed = time.time() - t_start
    print(f"\n完成! 成功:{success} 跳过:{skip} 失败:{fail} 新增:{total_rows}条 耗时:{elapsed/60:.1f}min")

    # 补全pre_close, change, pct_chg
    print("\n补全计算字段...")
    db = SessionLocal()
    db.execute(text('''
        UPDATE stock_daily SET pre_close = (
            SELECT sd2.close FROM stock_daily sd2
            WHERE sd2.ts_code = stock_daily.ts_code
            AND sd2.trade_date < stock_daily.trade_date
            ORDER BY sd2.trade_date DESC LIMIT 1
        )
        WHERE pre_close = 0 OR pre_close IS NULL
    '''))
    db.commit()
    db.execute(text('UPDATE stock_daily SET change = close - pre_close WHERE pre_close > 0'))
    db.commit()
    db.execute(text('''
        UPDATE stock_daily SET pct_chg = ROUND((close - pre_close) / pre_close * 100, 4)
        WHERE pre_close > 0
    '''))
    db.commit()
    db.close()
    print("计算字段补全完成")


if __name__ == '__main__':
    main()
