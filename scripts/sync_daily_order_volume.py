"""
同步stock_daily的大单成交量字段 (large_order_volume, super_large_order_volume, turnover_rate)
数据源: Tushare moneyflow接口 (提供各档位成交量)

用法:
  python scripts/sync_daily_order_volume.py              # 全量同步最近30天
  python scripts/sync_daily_order_volume.py --days 60    # 指定天数
  python scripts/sync_daily_order_volume.py --ts-code 000001.SZ  # 单只股票
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


def sync_daily_order_volume(source: TushareDataSource, ts_code: str,
                             start_date: str, end_date: str) -> int:
    """从Tushare moneyflow获取大单成交量并更新stock_daily"""
    db = SessionLocal()
    try:
        # 获取资金流向数据 (含各档位成交量)
        df = source._pro.moneyflow(
            ts_code=ts_code,
            start_date=source._format_date(start_date),
            end_date=source._format_date(end_date)
        )
        if df is None or df.empty:
            return 0

        # moneyflow字段: buy_elg_vol(超大单买量), sell_elg_vol(超大单卖量),
        # buy_lg_vol(大单买量), sell_lg_vol(大单卖量)
        updated = 0
        for _, row in df.iterrows():
            trade_date_raw = str(row.get('trade_date', ''))
            if not trade_date_raw or len(trade_date_raw) < 8:
                continue
            # 转换为date
            td = pd.Timestamp(trade_date_raw).date()

            # 大单成交量 = 大单买量 + 大单卖量
            large_vol = safe_float(row.get('buy_lg_vol', 0)) or 0
            large_vol += safe_float(row.get('sell_lg_vol', 0)) or 0
            # 超大单成交量 = 超大单买量 + 超大单卖量
            super_large_vol = safe_float(row.get('buy_elg_vol', 0)) or 0
            super_large_vol += safe_float(row.get('sell_elg_vol', 0)) or 0

            if large_vol == 0 and super_large_vol == 0:
                continue

            # 更新stock_daily
            result = db.execute(
                text(
                    "UPDATE stock_daily SET "
                    "large_order_volume = :lv, super_large_order_volume = :slv "
                    "WHERE ts_code = :tc AND trade_date = :td"
                ),
                {"lv": large_vol, "slv": super_large_vol, "tc": ts_code, "td": td}
            )
            if result.rowcount > 0:
                updated += result.rowcount

        db.commit()
        return updated
    except Exception as e:
        db.rollback()
        logger.warning(f"{ts_code} 失败: {e}")
        return -1
    finally:
        db.close()


def sync_daily_turnover(source: TushareDataSource, start_date: str, end_date: str) -> int:
    """从stock_daily_basic同步换手率到stock_daily.turnover_rate"""
    db = SessionLocal()
    try:
        # 批量更新: 从stock_daily_basic取turnover_rate写入stock_daily
        result = db.execute(text(
            "UPDATE stock_daily sd "
            "SET turnover_rate = sdb.turnover_rate "
            "FROM stock_daily_basic sdb "
            "WHERE sd.ts_code = sdb.ts_code "
            "AND sd.trade_date::text = sdb.trade_date "
            "AND sd.turnover_rate IS NULL "
            "AND sdb.turnover_rate IS NOT NULL "
            f"AND sd.trade_date >= '{start_date}' "
            f"AND sd.trade_date <= '{end_date}'"
        ))
        db.commit()
        logger.info(f"[turnover_rate] 更新 {result.rowcount} 行")
        return result.rowcount
    except Exception as e:
        db.rollback()
        logger.error(f"[turnover_rate] 失败: {e}")
        return 0
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description='同步stock_daily大单成交量')
    parser.add_argument('--days', type=int, default=30, help='同步天数')
    parser.add_argument('--ts-code', type=str, help='指定单只股票')
    parser.add_argument('--workers', type=int, default=4, help='并发线程数')
    parser.add_argument('--limit', type=int, default=0, help='限制股票数量(0=全部)')
    args = parser.parse_args()

    source = TushareDataSource(settings.TUSHARE_TOKEN)
    if not source.connect():
        logger.error("Tushare连接失败!")
        sys.exit(1)

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=args.days + 10)).strftime('%Y-%m-%d')

    # Step 1: 同步换手率
    logger.info("Step 1: 同步换手率到stock_daily...")
    sync_daily_turnover(source, start_date, end_date)

    # Step 2: 同步大单成交量
    logger.info("Step 2: 同步大单成交量...")

    if args.ts_code:
        count = sync_daily_order_volume(source, args.ts_code, start_date, end_date)
        logger.info(f"  {args.ts_code}: 更新 {count} 行")
        return

    # 获取股票列表
    db = SessionLocal()
    try:
        ts_codes = [
            r[0] for r in db.execute(text(
                "SELECT ts_code FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
            )).fetchall()
        ]
    finally:
        db.close()

    if args.limit > 0:
        ts_codes = ts_codes[:args.limit]

    total = 0
    failed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for ts_code in ts_codes:
            future = executor.submit(sync_daily_order_volume, source, ts_code, start_date, end_date)
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
            if done % 100 == 0 and done > 0:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                logger.info(f"进度: {done}/{len(futures)} 更新:{total} 失败:{failed} 速度:{rate:.1f}/s")

    elapsed = time.time() - t0
    logger.info(f"完成! 更新 {total} 行, 失败 {failed}, 耗时 {elapsed:.1f}s")


if __name__ == '__main__':
    main()
