"""
同步分析师一致预期数据
数据源: Tushare consensus_data + AKShare stock_analyst_detail_em
"""
import sys
import os

# 清除代理环境变量，防止 tushare 请求走 macOS 系统代理超时
for _k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
    os.environ.pop(_k, None)

sys.path.insert(0, '.')

import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.market.stock_analyst_consensus import StockAnalystConsensus
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


def sync_analyst_tushare(ts_code: str, start_date: str, end_date: str,
                          source: TushareDataSource) -> int:
    """使用 Tushare consensus_data 接口同步"""
    db = SessionLocal()
    try:
        try:
            df = source._pro.consensus_data(
                ts_code=ts_code,
                start_date=source._format_date(start_date),
                end_date=source._format_date(end_date)
            )
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return 0

        existing_dates = set(r[0] for r in db.query(StockAnalystConsensus.effective_date).filter(
            StockAnalystConsensus.ts_code == ts_code,
        ).all())

        new_records = []
        for _, row in df.iterrows():
            effective_date = str(row.get('end_date', ''))[:8]
            if not effective_date or effective_date in existing_dates:
                continue
            new_records.append(StockAnalystConsensus(
                ts_code=ts_code,
                effective_date=effective_date,
                ann_date=str(row.get('ann_date', ''))[:8] if pd.notna(row.get('ann_date')) else None,
                consensus_eps_fy0=safe_float(row.get('consensus_eps_fy0')),
                consensus_eps_fy1=safe_float(row.get('consensus_eps_fy1')),
                consensus_eps_fy2=safe_float(row.get('consensus_eps_fy2')),
                analyst_coverage=safe_int(row.get('num_analysts')),
                rating_mean=safe_float(row.get('rating_mean')),
                target_price_mean=safe_float(row.get('target_price_mean')),
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


def sync_analyst_akshare(ts_code: str = None) -> int:
    """使用 AKShare 同步分析师一致预期 (stock_institute_recommend)"""
    db = SessionLocal()
    try:
        import akshare as ak

        # 使用一致预期选股获取全市场数据
        try:
            df = ak.stock_institute_recommend(symbol='一致预期选股')
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return 0

        # 格式化日期
        today = datetime.now().strftime('%Y%m%d')

        def format_ts_code(code):
            code = str(code).zfill(6)
            if code.startswith('6') or code.startswith('9'):
                return f"{code}.SH"
            else:
                return f"{code}.SZ"

        existing_codes = set(r[0] for r in db.query(StockAnalystConsensus.ts_code).filter(
            StockAnalystConsensus.effective_date == today,
        ).all())

        new_records = []
        for _, row in df.iterrows():
            code = str(row.get('股票代码', row.get('代码', '')))
            if not code:
                continue
            tc = format_ts_code(code)
            if tc in existing_codes:
                continue
            if ts_code and tc != ts_code:
                continue

            new_records.append(StockAnalystConsensus(
                ts_code=tc,
                effective_date=today,
                ann_date=today,
                consensus_eps_fy0=safe_float(row.get('一致预期EPS(今年)', row.get('今年EPS'))),
                consensus_eps_fy1=safe_float(row.get('一致预期EPS(明年)', row.get('明年EPS'))),
                analyst_coverage=safe_int(row.get('评级机构数', row.get('研究机构数'))),
                rating_mean=safe_float(row.get('综合评级', row.get('评级'))),
                target_price_mean=safe_float(row.get('目标价', row.get('综合目标价'))),
            ))

        if new_records:
            db.bulk_save_objects(new_records)
            db.commit()
        return len(new_records)

    except Exception as e:
        print(f"  AKShare analyst sync error: {e}")
        db.rollback()
        return -1
    finally:
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='同步分析师一致预期数据')
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
            count = sync_analyst_tushare(ts_code, start_date, end_date, source)
            print(f"  {ts_code} (tushare): 新增 {count} 条")
        if (args.source == 'akshare' or (count <= 0 and args.source == 'auto')):
            count = sync_analyst_akshare(ts_code)
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
            'SELECT DISTINCT ts_code FROM stock_analyst_consensus'
        )).fetchall())
    finally:
        db2.close()

    missing = [c for c in all_codes if c not in existing_codes]
    total = len(missing)
    print(f"需同步 {total} 只股票的分析师一致预期数据")

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
            count = sync_analyst_tushare(ts_code, start_date, end_date, source)
        if count <= 0 and args.source in ('akshare', 'auto'):
            count = sync_analyst_akshare(ts_code)

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