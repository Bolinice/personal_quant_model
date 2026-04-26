"""
同步股票每日状态数据 (ST/涨跌停/停牌等)
数据源: Tushare stk_limit + daily_basic (判断ST/停牌)
"""
import sys
sys.path.insert(0, '.')

import time
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.market.stock_status_daily import StockStatusDaily
from app.data_sources.tushare_source import TushareDataSource
from app.core.config import settings


DELAY = 0.3


def sync_status_daily(trade_date: str, source: TushareDataSource) -> int:
    """同步单日股票状态"""
    db = SessionLocal()
    try:
        # 检查是否已存在
        existing = db.execute(text(
            "SELECT COUNT(*) FROM stock_status_daily WHERE trade_date = :d"
        ), {"d": trade_date}).scalar()
        if existing > 0:
            return 0

        # 获取当日行情 (判断涨跌停)
        try:
            daily_df = source._pro.daily(
                trade_date=source._format_date(trade_date),
                fields='ts_code,close,pre_close,pct_chg'
            )
        except Exception:
            daily_df = pd.DataFrame()

        if daily_df is None or daily_df.empty:
            return 0

        # 获取 ST 信息 (从 stock_basic 的 name 字段判断)
        try:
            basic_df = source._pro.stock_basic(
                exchange='', list_status='L',
                fields='ts_code,name'
            )
        except Exception:
            basic_df = pd.DataFrame()

        st_map = {}
        if basic_df is not None and not basic_df.empty:
            for _, row in basic_df.iterrows():
                name = str(row.get('name', ''))
                is_st = 'ST' in name or '*ST' in name
                is_star_st = '*ST' in name
                st_map[row['ts_code']] = (is_st, is_star_st)

        # 获取停牌信息 (vol=0 视为停牌)
        new_records = []
        for _, row in daily_df.iterrows():
            ts_code = row.get('ts_code', '')
            if not ts_code:
                continue

            is_st, is_star_st = st_map.get(ts_code, (False, False))
            pct_chg = float(row.get('pct_chg', 0)) if pd.notna(row.get('pct_chg')) else 0

            # 涨跌停判断
            is_limit_up = False
            is_limit_down = False
            if is_st:
                is_limit_up = pct_chg >= 4.9
                is_limit_down = pct_chg <= -4.9
            else:
                # 创业板/科创板 20%
                code = ts_code.split('.')[0]
                if code.startswith('3') or code.startswith('688'):
                    is_limit_up = pct_chg >= 19.9
                    is_limit_down = pct_chg <= -19.9
                else:
                    is_limit_up = pct_chg >= 9.9
                    is_limit_down = pct_chg <= -9.9

            # 停牌: close=0 或 vol=0
            close = float(row.get('close', 0)) if pd.notna(row.get('close')) else 0
            is_suspended = close == 0

            risk_flag = None
            if is_star_st:
                risk_flag = '*ST'
            elif is_st:
                risk_flag = 'ST'

            new_records.append(StockStatusDaily(
                ts_code=ts_code,
                trade_date=trade_date,
                is_st=is_st,
                is_star_st=is_star_st,
                is_suspended=is_suspended,
                is_limit_up=is_limit_up,
                is_limit_down=is_limit_down,
                risk_flag=risk_flag,
            ))

        if new_records:
            db.bulk_save_objects(new_records)
            db.commit()
        return len(new_records)

    except Exception as e:
        print(f"  {trade_date}: 失败 - {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='同步股票每日状态数据')
    parser.add_argument('--days', type=int, default=30, help='同步最近N天')
    args = parser.parse_args()

    source = TushareDataSource(token=settings.TUSHARE_TOKEN)
    if not source.connect():
        print("Tushare 连接失败!")
        return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days + 10)

    cal_df = source.get_trading_calendar(
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )

    if not cal_df.empty:
        trade_dates = cal_df[cal_df['is_open'] == 1]['trade_date'].tolist()
    else:
        trade_dates = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                trade_dates.append(current.strftime('%Y%m%d'))
            current += timedelta(days=1)

    print(f"同步 {len(trade_dates)} 个交易日的股票状态数据")
    total = 0
    for i, td in enumerate(trade_dates):
        count = sync_status_daily(td, source)
        total += count
        if (i + 1) % 5 == 0 or (i + 1) == len(trade_dates):
            print(f"  [{i+1}/{len(trade_dates)}] 新增:{total}条")
        time.sleep(DELAY)

    print(f"\n完成! 共新增 {total} 条记录")


if __name__ == '__main__':
    main()