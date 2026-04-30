"""
同步个股资金流向数据
数据源: Tushare moneyflow（代理API）+ AKShare stock_individual_fund_flow
"""
import sys
sys.path.insert(0, '.')

import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from scripts.script_utils import safe_date

from app.db.base import SessionLocal
from app.models.market.stock_money_flow import StockMoneyFlow
from app.data_sources.tushare_source import TushareDataSource
from app.core.config import settings


BATCH_SIZE = 50
DELAY = 0.3


def safe_float(val):
    try:
        if isinstance(val, str):
            val = val.replace(',', '').replace('%', '').replace('万', 'e4').replace('亿', 'e8')
        v = float(val) if pd.notna(val) and val not in ('False', '', '-') else None
        return v
    except (ValueError, TypeError):
        return None


def sync_money_flow_tushare(ts_code: str, start_date: str, end_date: str,
                             source: TushareDataSource) -> int:
    """使用 Tushare moneyflow 接口同步"""
    db = SessionLocal()
    try:
        try:
            df = source._pro.moneyflow(
                ts_code=ts_code,
                start_date=source._format_date(start_date),
                end_date=source._format_date(end_date)
            )
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return 0

        existing_dates = set(r[0] for r in db.query(StockMoneyFlow.trade_date).filter(
            StockMoneyFlow.ts_code == ts_code,
        ).all())

        new_records = []
        for _, row in df.iterrows():
            trade_date = safe_date(row.get('trade_date'))
            if trade_date in existing_dates:
                continue
            new_records.append(StockMoneyFlow(
                ts_code=ts_code,
                trade_date=trade_date,
                smart_net_inflow=safe_float(row.get('buy_sm_amount', 0)) - safe_float(row.get('sell_sm_amount', 0)),
                large_net_inflow=safe_float(row.get('buy_lg_amount', 0)) - safe_float(row.get('sell_lg_amount', 0)),
                super_large_net_inflow=safe_float(row.get('buy_elg_amount', 0)) - safe_float(row.get('sell_elg_amount', 0)),
                medium_net_inflow=safe_float(row.get('buy_md_amount', 0)) - safe_float(row.get('sell_md_amount', 0)),
                small_net_inflow=safe_float(row.get('buy_sm_amount', 0)) - safe_float(row.get('sell_sm_amount', 0)),
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


def sync_money_flow_akshare(ts_code: str) -> int:
    """使用 AKShare 同步单只股票资金流向"""
    db = SessionLocal()
    try:
        import akshare as ak
        code = ts_code.split('.')[0]
        market = 'sz' if ts_code.endswith('.SZ') else 'sh'

        df = ak.stock_individual_fund_flow(stock=code, market=market)
        if df is None or df.empty:
            return 0

        dates_in_df = []
        for _, row in df.iterrows():
            try:
                d = str(row.get('日期', ''))
                if d and len(d) >= 10:
                    dates_in_df.append(safe_date(d))
            except Exception:
                continue

        if not dates_in_df:
            return 0

        existing_dates = set(r[0] for r in db.query(StockMoneyFlow.trade_date).filter(
            StockMoneyFlow.ts_code == ts_code,
            StockMoneyFlow.trade_date.in_(dates_in_df),
        ).all())

        new_records = []
        for _, row in df.iterrows():
            try:
                d = str(row.get('日期', ''))
                if not d or len(d) < 10:
                    continue
                trade_date = safe_date(d)
            except Exception:
                continue

            if trade_date in existing_dates:
                continue

            new_records.append(StockMoneyFlow(
                ts_code=ts_code,
                trade_date=trade_date,
                smart_net_inflow=safe_float(row.get('主力净流入-净额')),
                smart_net_pct=safe_float(row.get('主力净流入-净占比')),
                super_large_net_inflow=safe_float(row.get('超大单净流入-净额')),
                super_large_net_pct=safe_float(row.get('超大单净流入-净占比')),
                large_net_inflow=safe_float(row.get('大单净流入-净额')),
                large_net_pct=safe_float(row.get('大单净流入-净占比')),
                medium_net_inflow=safe_float(row.get('中单净流入-净额')),
                medium_net_pct=safe_float(row.get('中单净流入-净占比')),
                small_net_inflow=safe_float(row.get('小单净流入-净额')),
                small_net_pct=safe_float(row.get('小单净流入-净占比')),
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
    parser = argparse.ArgumentParser(description='同步资金流向数据')
    parser.add_argument('--source', choices=['tushare', 'akshare', 'auto'], default='auto',
                        help='数据源: tushare, akshare, auto(优先tushare)')
    parser.add_argument('--ts-code', type=str, help='指定单只股票')
    parser.add_argument('--days', type=int, default=30, help='同步天数(tushare)')
    args = parser.parse_args()

    source = TushareDataSource(token=settings.TUSHARE_TOKEN)
    tushare_ok = source.connect()

    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=args.days + 10)).strftime('%Y%m%d')

    if args.ts_code:
        # 同步单只股票
        ts_code = args.ts_code
        if args.source in ('tushare', 'auto') and tushare_ok:
            count = sync_money_flow_tushare(ts_code, start_date, end_date, source)
            print(f"  {ts_code} (tushare): 新增 {count} 条")
        if (args.source == 'akshare' or (count <= 0 and args.source == 'auto')):
            count = sync_money_flow_akshare(ts_code)
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

    # 检查已同步的股票
    db2 = SessionLocal()
    try:
        existing_codes = set(r[0] for r in db2.execute(text(
            'SELECT DISTINCT ts_code FROM stock_money_flow'
        )).fetchall())
    finally:
        db2.close()

    missing = [c for c in all_codes if c not in existing_codes]
    total = len(missing)
    print(f"需同步 {total} 只股票的资金流向数据")

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
            count = sync_money_flow_tushare(ts_code, start_date, end_date, source)
        if count <= 0 and args.source in ('akshare', 'auto'):
            count = sync_money_flow_akshare(ts_code)

        if count > 0:
            success += 1
            total_rows += count
        elif count == 0:
            pass  # skip
        else:
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
