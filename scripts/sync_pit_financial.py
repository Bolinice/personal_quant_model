"""
同步PIT财务数据 (Point-in-Time)
数据源: Tushare fina_indicator + income + balancesheet + cashflow
按公告日(ann_date)严格管理, 预告/快报/正式报表优先级
"""
import sys

import os

# 清除代理环境变量，防止 tushare 请求走 macOS 系统代理超时
for _k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
    os.environ.pop(_k, None)

sys.path.insert(0, '.')

import time
import pandas as pd
from datetime import datetime
from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.pit_financial import PITFinancial
from app.data_sources.tushare_source import TushareDataSource
from app.core.config import settings


BATCH_SIZE = 50
DELAY = 0.3


def safe_float(val):
    try:
        if isinstance(val, str):
            val = val.replace('%', '').replace(',', '')
        v = float(val) if pd.notna(val) and val not in ('False', '', '-') else None
        return v
    except (ValueError, TypeError):
        return None


def sync_pit_stock(ts_code: str, source: TushareDataSource) -> int:
    """同步单只股票的PIT财务数据"""
    db = SessionLocal()
    try:
        # 获取 fina_indicator
        try:
            df = source._pro.fina_indicator(
                ts_code=ts_code,
                start_date='20200101',
                end_date=datetime.now().strftime('%Y%m%d'),
                fields='ts_code,ann_date,end_date,roe,roa,grossprofit_margin,netprofit_margin,current_ratio,debt_to_assets,eps,bps'
            )
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return 0

        # 获取 balancesheet (total_assets, total_equity, goodwill)
        try:
            bs_df = source._pro.balancesheet(
                ts_code=ts_code,
                fields='ts_code,ann_date,end_date,total_assets,total_hldr_eqy_exc_min_int,goodwill'
            )
        except Exception:
            bs_df = pd.DataFrame()

        # 获取 income (revenue, net_profit)
        try:
            inc_df = source._pro.income(
                ts_code=ts_code,
                fields='ts_code,ann_date,end_date,total_revenue,n_income_attr_p'
            )
        except Exception:
            inc_df = pd.DataFrame()

        # 获取 cashflow (operating_cashflow)
        try:
            cf_df = source._pro.cashflow(
                ts_code=ts_code,
                fields='ts_code,ann_date,end_date,n_cashflow_act'
            )
        except Exception:
            cf_df = pd.DataFrame()

        # 构建 end_date -> 额外字段 的映射
        bs_map = {}
        if bs_df is not None and not bs_df.empty:
            for _, row in bs_df.iterrows():
                ed = str(row.get('end_date', ''))
                if ed:
                    bs_map[ed] = {
                        'total_assets': safe_float(row.get('total_assets')),
                        'total_equity': safe_float(row.get('total_hldr_eqy_exc_min_int')),
                        'goodwill': safe_float(row.get('goodwill')),
                    }

        inc_map = {}
        if inc_df is not None and not inc_df.empty:
            for _, row in inc_df.iterrows():
                ed = str(row.get('end_date', ''))
                if ed:
                    inc_map[ed] = {
                        'revenue': safe_float(row.get('total_revenue')),
                        'net_profit': safe_float(row.get('n_income_attr_p')),
                    }

        cf_map = {}
        if cf_df is not None and not cf_df.empty:
            for _, row in cf_df.iterrows():
                ed = str(row.get('end_date', ''))
                if ed:
                    cf_map[ed] = {
                        'operating_cashflow': safe_float(row.get('n_cashflow_act')),
                    }

        # 写入 PIT 表
        existing = set(r[0] for r in db.execute(text(
            "SELECT CONCAT(ts_code, '_', end_date, '_', effective_date) FROM pit_financial"
        )).fetchall())

        new_records = []
        for _, row in df.iterrows():
            ed = str(row.get('end_date', ''))
            ann_date = str(row.get('ann_date', ''))
            ts = ts_code
            key = f"{ts}_{ed}_{ann_date}"
            if key in existing:
                continue

            # 从辅助表获取额外字段
            bs = bs_map.get(ed, {})
            inc = inc_map.get(ed, {})
            cf = cf_map.get(ed, {})

            new_records.append(PITFinancial(
                stock_id=0,  # 占位, 实际用 ts_code 关联
                report_period=pd.Timestamp(ed).date() if ed else None,
                effective_date=pd.Timestamp(ann_date).date() if ann_date else None,
                announce_date=pd.Timestamp(ann_date).date() if ann_date else None,
                source_priority=3,  # 正式报表
                revenue=inc.get('revenue'),
                net_profit=inc.get('net_profit'),
                total_assets=bs.get('total_assets'),
                total_equity=bs.get('total_equity'),
                operating_cashflow=cf.get('operating_cashflow'),
                gross_margin=safe_float(row.get('grossprofit_margin')),
                roe=safe_float(row.get('roe')),
                roa=safe_float(row.get('roa')),
                pe_ttm=safe_float(row.get('eps')),  # eps as proxy
                pb=safe_float(row.get('bps')),  # bps as proxy
                asset_liability_ratio=safe_float(row.get('debt_to_assets')),
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
    parser = argparse.ArgumentParser(description='同步PIT财务数据')
    parser.add_argument('--ts-code', type=str, help='指定单只股票')
    parser.add_argument('--limit', type=int, default=0, help='限制处理股票数')
    args = parser.parse_args()

    source = TushareDataSource(token=settings.TUSHARE_TOKEN)
    if not source.connect():
        print("Tushare 连接失败!")
        return

    if args.ts_code:
        count = sync_pit_stock(args.ts_code, source)
        print(f"  {args.ts_code}: 新增 {count} 条")
        return

    db = SessionLocal()
    try:
        codes = [r[0] for r in db.execute(text(
            "SELECT ts_code FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
        )).fetchall()]
    finally:
        db.close()

    # 检查已同步的股票
    db2 = SessionLocal()
    try:
        existing = set(r[0] for r in db2.execute(text(
            "SELECT DISTINCT ts_code FROM pit_financial"
        )).fetchall()) if db2.execute(text("SELECT COUNT(*) FROM pit_financial")).scalar() > 0 else set()
    except:
        existing = set()
    finally:
        db2.close()

    missing = [c for c in codes if c not in existing]
    total = len(missing)
    if args.limit > 0:
        missing = missing[:args.limit]
        total = len(missing)
    print(f"需同步 {total} 只股票的PIT财务数据")

    success = 0
    fail = 0
    total_rows = 0
    t_start = time.time()

    for i, ts_code in enumerate(missing):
        count = sync_pit_stock(ts_code, source)
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