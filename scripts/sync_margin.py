"""
同步融资融券数据
数据源: Tushare margin / margin_detail（代理API，全接口权限）
"""
import sys
sys.path.insert(0, '.')

import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.market.stock_margin import StockMargin
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


def sync_margin_by_date(trade_date: str, source: TushareDataSource):
    """按交易日同步融资融券汇总"""
    db = SessionLocal()
    try:
        existing = set(r[0] for r in db.execute(text(
            "SELECT ts_code FROM stock_margin WHERE trade_date = :d"
        ), {"d": trade_date}).fetchall())

        if existing:
            print(f"  {trade_date}: 已存在 {len(existing)} 条，跳过")
            return 0

        # Tushare margin 接口获取汇总数据
        try:
            df = source._pro.margin(trade_date=trade_date)
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            print(f"  {trade_date}: 无数据")
            return 0

        new_records = []
        for _, row in df.iterrows():
            ts_code = row.get('ts_code', '')
            if not ts_code or ts_code in existing:
                continue
            new_records.append(StockMargin(
                ts_code=ts_code,
                trade_date=trade_date,
                margin_buy=safe_float(row.get('rzye')),  # 融资余额
                margin_balance=safe_float(row.get('rzrqye')),  # 融资融券余额
                margin_sell=safe_float(row.get('rqye')),  # 融券余额
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


def sync_margin_detail(ts_code: str, start_date: str, end_date: str,
                        source: TushareDataSource):
    """按股票同步融资融券明细"""
    db = SessionLocal()
    try:
        try:
            df = source._pro.margin_detail(
                ts_code=ts_code,
                start_date=source._format_date(start_date),
                end_date=source._format_date(end_date)
            )
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return 0

        existing_dates = set(r[0] for r in db.execute(text(
            "SELECT trade_date FROM stock_margin WHERE ts_code = :c"
        ), {"c": ts_code}).fetchall())

        new_records = []
        for _, row in df.iterrows():
            trade_date = row.get('trade_date', '')
            if trade_date in existing_dates:
                continue
            new_records.append(StockMargin(
                ts_code=ts_code,
                trade_date=trade_date,
                margin_buy=safe_float(row.get('rzye')),  # 融资余额
                margin_sell=safe_float(row.get('rqye')),  # 融券余额
                margin_sell_vol=safe_float(row.get('rqyl')),  # 融券余量
                margin_balance=safe_float(row.get('rzrqye')),  # 融资融券余额
                margin_buy_vol=safe_float(row.get('rzbuy')),  # 融资买入额
                margin_repay=safe_float(row.get('rzrepay')),  # 融资偿还额
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
    parser = argparse.ArgumentParser(description='同步融资融券数据')
    parser.add_argument('--mode', choices=['date', 'detail', 'recent'], default='recent',
                        help='date=按日期汇总, detail=按股票明细, recent=最近N天')
    parser.add_argument('--trade-date', type=str, help='指定交易日期 (mode=date)')
    parser.add_argument('--ts-code', type=str, help='指定股票代码 (mode=detail)')
    parser.add_argument('--days', type=int, default=30, help='同步最近N天 (mode=recent)')
    args = parser.parse_args()

    source = TushareDataSource(token=settings.TUSHARE_TOKEN)
    if not source.connect():
        print("Tushare 连接失败!")
        return

    if args.mode == 'date':
        trade_date = args.trade_date or datetime.now().strftime('%Y%m%d')
        sync_margin_by_date(trade_date, source)

    elif args.mode == 'detail':
        if not args.ts_code:
            print("请指定 --ts-code")
            return
        end = datetime.now().strftime('%Y%m%d')
        start = (datetime.now() - timedelta(days=args.days + 10)).strftime('%Y%m%d')
        count = sync_margin_detail(args.ts_code, start, end, source)
        print(f"  {args.ts_code}: 新增 {count} 条")

    elif args.mode == 'recent':
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days + 10)

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

        print(f"同步最近 {len(trade_dates)} 个交易日的融资融券数据")
        total = 0
        for i, td in enumerate(trade_dates):
            count = sync_margin_by_date(td, source)
            total += count
            time.sleep(0.3)

        print(f"\n完成! 共新增 {total} 条记录")


if __name__ == '__main__':
    main()
