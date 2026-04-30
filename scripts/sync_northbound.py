"""
同步北向资金数据
数据源: Tushare hsgt_top10 + AKShare stock_hsgt_hold_stock_em
"""
import sys
sys.path.insert(0, '.')

import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from scripts.script_utils import safe_date

from app.db.base import SessionLocal
from app.models.market.stock_northbound import StockNorthbound
from app.data_sources.tushare_source import TushareDataSource
from app.core.config import settings


def safe_float(val):
    try:
        if isinstance(val, str):
            val = val.replace(',', '').replace('%', '')
        v = float(val) if pd.notna(val) and val not in ('False', '', '-') else None
        return v
    except (ValueError, TypeError):
        return None


def format_ts_code(code: str) -> str:
    code = str(code).zfill(6)
    if code.startswith('6') or code.startswith('9'):
        return f"{code}.SH"
    else:
        return f"{code}.SZ"


def sync_northbound_holding():
    """同步北向持股数据（AKShare 东方财富）"""
    trade_date = datetime.now().date()
    print(f"同步北向持股数据 {trade_date}")

    try:
        import akshare as ak
        df = ak.stock_hsgt_hold_stock_em(market="北向")
    except Exception as e:
        print(f"获取北向持股失败: {e}")
        return

    if df.empty:
        print("无数据")
        return

    print(f"获取到 {len(df)} 条数据")

    db = SessionLocal()
    try:
        existing = set(r[0] for r in db.execute(text(
            "SELECT ts_code FROM stock_northbound WHERE trade_date = :d"
        ), {"d": trade_date}).fetchall())

        new_records = []
        for _, row in df.iterrows():
            code = str(row.get('代码', '')).zfill(6)
            if not code:
                continue
            ts_code = format_ts_code(code)

            if ts_code in existing:
                continue

            new_records.append(StockNorthbound(
                ts_code=ts_code,
                trade_date=trade_date,
                north_holding=safe_float(row.get('今日持股-股数')),
                north_holding_pct=safe_float(row.get('今日持股-占流通股比')),
                north_holding_mv=safe_float(row.get('今日持股-市值')),
            ))

        if new_records:
            db.bulk_save_objects(new_records)
            db.commit()

        print(f"新增 {len(new_records)} 条记录 (已存在 {len(existing)} 条)")
    except Exception as e:
        print(f"同步失败: {e}")
        db.rollback()
    finally:
        db.close()


def sync_northbound_trade(days: int = 30):
    """同步北向交易数据（Tushare hsgt_top10）"""
    source = TushareDataSource(token=settings.TUSHARE_TOKEN)
    if not source.connect():
        print("Tushare 连接失败!")
        return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days + 10)

    # 获取交易日历
    cal_df = source.get_trading_calendar(
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )

    if not cal_df.empty:
        trade_dates = cal_df[cal_df['is_open'] == 1]['cal_date'].tolist()
    else:
        trade_dates = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                trade_dates.append(current.strftime('%Y%m%d'))
            current += timedelta(days=1)

    print(f"同步北向交易数据，{len(trade_dates)} 个交易日")

    db = SessionLocal()
    try:
        total = len(trade_dates)
        success = 0
        total_rows = 0

        for i, td in enumerate(trade_dates):
            try:
                df = source.get_hsgt_top10(td)
                if df is None or df.empty:
                    continue

                # 检查是否已存在
                existing = set(r[0] for r in db.execute(text(
                    "SELECT ts_code FROM stock_northbound WHERE trade_date = :d"
                ), {"d": safe_date(td)}).fetchall())

                new_records = []
                for _, row in df.iterrows():
                    ts_code = row.get('ts_code', '')
                    if not ts_code or ts_code in existing:
                        continue

                    new_records.append(StockNorthbound(
                        ts_code=ts_code,
                        trade_date=safe_date(td),
                        north_net_buy=safe_float(row.get('net_amount')),
                        north_buy=safe_float(row.get('buy')),
                        north_sell=safe_float(row.get('sell')),
                    ))

                if new_records:
                    db.bulk_save_objects(new_records)
                    db.commit()
                    total_rows += len(new_records)

                success += 1
                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{total}] 成功:{success} 新增:{total_rows}条")

                time.sleep(0.3)

            except Exception as e:
                print(f"  {td} 失败: {e}")

        print(f"完成! 成功:{success}/{total} 新增:{total_rows}条")

    except Exception as e:
        print(f"同步失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['holding', 'trade', 'all'], default='all')
    parser.add_argument('--days', type=int, default=30)
    args = parser.parse_args()

    if args.mode in ('holding', 'all'):
        sync_northbound_holding()
    if args.mode in ('trade', 'all'):
        sync_northbound_trade(args.days)
