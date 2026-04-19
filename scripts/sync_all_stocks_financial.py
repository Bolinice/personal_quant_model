"""
批量同步全A股财务数据
使用同花顺财务摘要接口，支持断点续传
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
DELAY = 0.3
MAX_WORKERS = 4


def safe_float(val):
    try:
        if isinstance(val, str):
            val = val.replace('%', '').replace('万', 'e4').replace('亿', 'e8').replace(',', '')
        v = float(val) if pd.notna(val) and val not in ('False', '') else None
        return v
    except (ValueError, TypeError):
        return None


def get_missing_codes(db) -> list[str]:
    """获取需要同步财务数据的股票代码"""
    existing = set([r[0] for r in db.execute(text('SELECT DISTINCT ts_code FROM stock_financial')).fetchall()])
    all_codes = [r[0] for r in db.execute(text(
        "SELECT ts_code FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
    )).fetchall()]
    return [c for c in all_codes if c not in existing]


def sync_financial(ts_code: str) -> int:
    """同步单只股票财务数据 - 优化版: 批量存在性检查"""
    from app.models.market import StockFinancial

    db = SessionLocal()
    try:
        symbol = ts_code.split('.')[0]

        # 优先用 stock_financial_analysis_indicator
        try:
            df = ak.stock_financial_analysis_indicator(symbol=symbol, start_year='2023')
            if not df.empty and '日期' in df.columns:
                return _save_indicator_data(db, ts_code, df)
        except Exception:
            pass

        # 回退到同花顺财务摘要
        try:
            df = ak.stock_financial_abstract_ths(symbol=symbol, indicator='按报告期')
            if not df.empty and '报告期' in df.columns:
                return _save_ths_data(db, ts_code, df)
        except Exception:
            pass

        return 0
    except Exception:
        db.rollback()
        return -1
    finally:
        db.close()


def _save_indicator_data(db, ts_code: str, df: pd.DataFrame) -> int:
    from app.models.market import StockFinancial

    # 批量获取已存在的end_date
    end_dates = []
    for _, row in df.iterrows():
        end_date_str = str(row.get('日期', ''))
        if end_date_str and len(end_date_str) >= 10:
            try:
                end_dates.append(pd.Timestamp(end_date_str).date())
            except Exception:
                continue

    if not end_dates:
        return 0

    existing_dates = set(r[0] for r in db.query(StockFinancial.end_date).filter(
        StockFinancial.ts_code == ts_code,
        StockFinancial.end_date.in_(end_dates),
    ).all())

    new_records = []
    for _, row in df.iterrows():
        end_date_str = str(row.get('日期', ''))
        if not end_date_str or len(end_date_str) < 10:
            continue
        try:
            end_date = pd.Timestamp(end_date_str).date()
        except Exception:
            continue

        if end_date not in existing_dates:
            new_records.append(StockFinancial(
                ts_code=ts_code,
                end_date=end_date,
                ann_date=end_date,
                revenue=safe_float(row.get('营业收入(元)')),
                net_profit=safe_float(row.get('净利润(元)')),
                roe=safe_float(row.get('净资产收益率(%)')),
                roa=safe_float(row.get('总资产净利率(%)')),
                gross_profit=safe_float(row.get('营业利润(元)')),
                gross_profit_margin=safe_float(row.get('销售毛利率(%)')),
                eps=safe_float(row.get('摊薄每股收益(元)')),
                bvps=safe_float(row.get('每股净资产_调整前(元)')),
                net_profit_ratio=safe_float(row.get('销售净利率(%)')),
                current_ratio=safe_float(row.get('流动比率')),
                quick_ratio=safe_float(row.get('速动比率')),
                asset_liability_ratio=safe_float(row.get('资产负债率(%)')),
            ))

    if new_records:
        db.bulk_save_objects(new_records)
        db.commit()
    return len(new_records)


def _save_ths_data(db, ts_code: str, df: pd.DataFrame) -> int:
    from app.models.market import StockFinancial

    df['报告期'] = pd.to_datetime(df['报告期'])
    two_years_ago = pd.Timestamp.now() - pd.Timedelta(days=730)
    df = df[df['报告期'] >= two_years_ago]

    # 批量获取已存在的end_date
    end_dates = [row['报告期'].date() for _, row in df.iterrows()]
    if not end_dates:
        return 0

    existing_dates = set(r[0] for r in db.query(StockFinancial.end_date).filter(
        StockFinancial.ts_code == ts_code,
        StockFinancial.end_date.in_(end_dates),
    ).all())

    new_records = []
    for _, row in df.iterrows():
        end_date = row['报告期'].date()

        if end_date not in existing_dates:
            new_records.append(StockFinancial(
                ts_code=ts_code,
                end_date=end_date,
                ann_date=end_date,
                revenue=safe_float(row.get('营业总收入')),
                net_profit=safe_float(row.get('净利润')),
                gross_profit=safe_float(row.get('营业利润')),
                roe=safe_float(row.get('净资产收益率')),
                eps=safe_float(row.get('基本每股收益')),
                bvps=safe_float(row.get('每股净资产')),
                asset_liability_ratio=safe_float(row.get('资产负债率')),
            ))

    if new_records:
        db.bulk_save_objects(new_records)
        db.commit()
    return len(new_records)


def main():
    db = SessionLocal()
    missing = get_missing_codes(db)
    db.close()

    total = len(missing)
    print(f"需同步 {total} 只股票的财务数据")

    success = 0
    fail = 0
    skip = 0
    total_rows = 0
    t_start = time.time()
    completed = 0

    # 使用线程池并行同步
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for ts_code in missing:
            future = executor.submit(sync_financial, ts_code)
            futures[future] = ts_code
            time.sleep(DELAY)

        for future in as_completed(futures):
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


if __name__ == '__main__':
    main()
