"""
同步全市场每日基本面数据（PE/PB/市值/换手率等）
数据源: Tushare daily_basic（代理API，全接口权限）
每日收盘后运行
"""
import sys
sys.path.insert(0, '.')

import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.market.stock_daily_basic import StockDailyBasic
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


def sync_daily_basic_by_date(trade_date: str, source: TushareDataSource):
    """按交易日同步全市场每日基本面"""
    db = SessionLocal()
    try:
        # 检查是否已存在
        existing = set(r[0] for r in db.execute(text(
            "SELECT ts_code FROM stock_daily_basic WHERE trade_date = :d"
        ), {"d": trade_date}).fetchall())

        if existing:
            print(f"  {trade_date}: 已存在 {len(existing)} 条，跳过")
            return 0

        # 获取数据
        df = source.get_daily_basic(trade_date=trade_date)
        if df.empty:
            print(f"  {trade_date}: 无数据")
            return 0

        new_records = []
        for _, row in df.iterrows():
            ts_code = row.get('ts_code', '')
            if not ts_code:
                continue
            new_records.append(StockDailyBasic(
                ts_code=ts_code,
                trade_date=trade_date,
                close=safe_float(row.get('close')),
                turnover_rate=safe_float(row.get('turnover_rate')),
                turnover_rate_f=safe_float(row.get('turnover_rate_f')),
                volume_ratio=safe_float(row.get('volume_ratio')),
                pe=safe_float(row.get('pe')),
                pe_ttm=safe_float(row.get('pe_ttm')),
                pb=safe_float(row.get('pb')),
                ps=safe_float(row.get('ps')),
                ps_ttm=safe_float(row.get('ps_ttm')),
                dv_ratio=safe_float(row.get('dv_ratio')),
                dv_ttm=safe_float(row.get('dv_ttm')),
                total_mv=safe_float(row.get('total_mv')),
                circ_mv=safe_float(row.get('circ_mv')),
            ))

        if new_records:
            db.bulk_save_objects(new_records)
            db.commit()

        print(f"  {trade_date}: 新增 {len(new_records)} 条")
        return len(new_records)

    except Exception as e:
        print(f"  {trade_date}: 失败 - {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def sync_daily_basic_by_stock(ts_code: str, start_date: str, end_date: str,
                               source: TushareDataSource):
    """按股票同步每日基本面（用于补历史数据）"""
    db = SessionLocal()
    try:
        df = source.get_daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df.empty:
            return 0

        # 获取已存在的日期
        existing_dates = set(r[0] for r in db.execute(text(
            "SELECT trade_date FROM stock_daily_basic WHERE ts_code = :c"
        ), {"c": ts_code}).fetchall())

        new_records = []
        for _, row in df.iterrows():
            trade_date = row.get('trade_date', '')
            if trade_date in existing_dates:
                continue
            new_records.append(StockDailyBasic(
                ts_code=ts_code,
                trade_date=trade_date,
                close=safe_float(row.get('close')),
                turnover_rate=safe_float(row.get('turnover_rate')),
                turnover_rate_f=safe_float(row.get('turnover_rate_f')),
                volume_ratio=safe_float(row.get('volume_ratio')),
                pe=safe_float(row.get('pe')),
                pe_ttm=safe_float(row.get('pe_ttm')),
                pb=safe_float(row.get('pb')),
                ps=safe_float(row.get('ps')),
                ps_ttm=safe_float(row.get('ps_ttm')),
                dv_ratio=safe_float(row.get('dv_ratio')),
                dv_ttm=safe_float(row.get('dv_ttm')),
                total_mv=safe_float(row.get('total_mv')),
                circ_mv=safe_float(row.get('circ_mv')),
            ))

        if new_records:
            db.bulk_save_objects(new_records)
            db.commit()

        return len(new_records)

    except Exception as e:
        print(f"  {ts_code}: 失败 - {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='同步每日基本面数据')
    parser.add_argument('--mode', choices=['date', 'stock', 'recent'], default='recent',
                        help='date=按日期全市场, stock=按股票补历史, recent=最近N天')
    parser.add_argument('--trade-date', type=str, help='指定交易日期 (mode=date)')
    parser.add_argument('--ts-code', type=str, help='指定股票代码 (mode=stock)')
    parser.add_argument('--days', type=int, default=30, help='同步最近N天 (mode=recent)')
    parser.add_argument('--start-date', type=str, help='开始日期 (mode=stock)')
    parser.add_argument('--end-date', type=str, help='结束日期 (mode=stock)')
    args = parser.parse_args()

    source = TushareDataSource(token=settings.TUSHARE_TOKEN)
    if not source.connect():
        print("Tushare 连接失败!")
        return

    if args.mode == 'date':
        trade_date = args.trade_date or datetime.now().strftime('%Y%m%d')
        sync_daily_basic_by_date(trade_date, source)

    elif args.mode == 'stock':
        if not args.ts_code:
            print("请指定 --ts-code")
            return
        start = args.start_date or '20200101'
        end = args.end_date or datetime.now().strftime('%Y%m%d')
        count = sync_daily_basic_by_stock(args.ts_code, start, end, source)
        print(f"  {args.ts_code}: 新增 {count} 条")

    elif args.mode == 'recent':
        # 获取交易日历
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days + 10)  # 多取几天确保覆盖

        cal_df = source.get_trading_calendar(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        if cal_df.empty:
            # 回退：用工作日
            trade_dates = []
            current = end_date - timedelta(days=args.days)
            while current <= end_date:
                if current.weekday() < 5:
                    trade_dates.append(current.strftime('%Y%m%d'))
                current += timedelta(days=1)
        else:
            trade_dates = cal_df[cal_df['is_open'] == 1]['cal_date'].tolist()

        print(f"同步最近 {len(trade_dates)} 个交易日的每日基本面数据")
        total = 0
        for i, td in enumerate(trade_dates):
            count = sync_daily_basic_by_date(td, source)
            total += count
            time.sleep(0.3)  # 限速

        print(f"\n完成! 共新增 {total} 条记录")


if __name__ == '__main__':
    main()
