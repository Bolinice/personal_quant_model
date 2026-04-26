"""
同步机构持仓数据
数据源: Tushare stk_holdernumber + AKShare stock_institute_hold_detail_em
按季度周期同步
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
from app.models.market.stock_institutional_holding import StockInstitutionalHolding
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


def sync_institutional_tushare(ts_code: str, source: TushareDataSource) -> int:
    """使用 Tushare stk_holdernumber 接口同步"""
    db = SessionLocal()
    try:
        try:
            df = source._pro.stk_holdernumber(
                ts_code=ts_code,
                start_date='20200101',
                end_date=datetime.now().strftime('%Y%m%d')
            )
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return 0

        existing_dates = set(r[0] for r in db.query(StockInstitutionalHolding.trade_date).filter(
            StockInstitutionalHolding.ts_code == ts_code,
        ).all())

        new_records = []
        for _, row in df.iterrows():
            trade_date = str(row.get('end_date', ''))[:8]
            if not trade_date or trade_date in existing_dates:
                continue
            new_records.append(StockInstitutionalHolding(
                ts_code=ts_code,
                trade_date=trade_date,
                ann_date=str(row.get('ann_date', ''))[:8] if pd.notna(row.get('ann_date')) else None,
                hold_ratio=safe_float(row.get('hold_ratio')),
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


def sync_institutional_akshare(ts_code: str) -> int:
    """使用 AKShare 同步机构持仓"""
    db = SessionLocal()
    try:
        import akshare as ak
        code = ts_code.split('.')[0]

        new_records = []
        # 按季度获取
        for year in range(2020, 2026):
            for q in range(1, 5):
                quarter = f"{year}{q}"
                try:
                    df = ak.stock_institute_hold_detail(stock=code, quarter=quarter)
                except Exception:
                    df = pd.DataFrame()

                if df is None or df.empty:
                    continue

                # 计算汇总: 所有机构的持股比例之和
                if '持股比例' in df.columns:
                    total_ratio = df['持股比例'].sum()
                    end_date = f"{year}{['0331','0630','0930','1231'][q-1]}"
                    existing = db.query(StockInstitutionalHolding).filter(
                        StockInstitutionalHolding.ts_code == ts_code,
                        StockInstitutionalHolding.trade_date == end_date,
                    ).first()
                    if existing:
                        continue
                    new_records.append(StockInstitutionalHolding(
                        ts_code=ts_code,
                        trade_date=end_date,
                        ann_date=end_date,
                        hold_ratio=total_ratio,
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description='同步机构持仓数据')
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
            count = sync_institutional_tushare(ts_code, source)
            print(f"  {ts_code} (tushare): 新增 {count} 条")
        if (args.source == 'akshare' or (count <= 0 and args.source == 'auto')):
            count = sync_institutional_akshare(ts_code)
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
            'SELECT DISTINCT ts_code FROM stock_institutional_holding'
        )).fetchall())
    finally:
        db2.close()

    missing = [c for c in all_codes if c not in existing_codes]
    total = len(missing)
    print(f"需同步 {total} 只股票的机构持仓数据")

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
            count = sync_institutional_tushare(ts_code, source)
        if count <= 0 and args.source in ('akshare', 'auto'):
            count = sync_institutional_akshare(ts_code)

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