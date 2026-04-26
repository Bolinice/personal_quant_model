"""
用 AKShare 东方财富接口补齐 stock_financial 缺失字段
补齐: total_equity, total_assets, goodwill, operating_cash_flow,
      operating_revenue, operating_cost, net_profit, gross_profit_margin
"""
import sys

import os

# 清除代理环境变量，防止 tushare 请求走 macOS 系统代理超时
for _k in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
    os.environ.pop(_k, None)

sys.path.insert(0, '.')

import time
import pandas as pd
from sqlalchemy import text
from app.db.base import SessionLocal
from app.models.market.stock_financial import StockFinancial


BATCH_SIZE = 50
DELAY = 1.0


def safe_float(val):
    try:
        if isinstance(val, str):
            val = val.replace(',', '').replace('%', '')
        v = float(val) if pd.notna(val) and val not in ('False', '', '-') else None
        return v
    except (ValueError, TypeError):
        return None


def backfill_stock_em(ts_code: str) -> int:
    """用 AKShare EM 接口补齐单只股票"""
    import akshare as ak
    db = SessionLocal()
    try:
        code = ts_code.split('.')[0]

        # 1. 资产负债表 -> total_assets, total_equity, goodwill
        try:
            bs_df = ak.stock_balance_sheet_by_report_em(symbol=code)
        except Exception:
            bs_df = pd.DataFrame()

        bs_map = {}
        if bs_df is not None and not bs_df.empty:
            for _, row in bs_df.iterrows():
                ed = str(row.get('REPORT_DATE', row.get('报告期', '')))[:10].replace('-', '')
                if not ed:
                    continue
                bs_map[ed] = {
                    'total_assets': safe_float(row.get('TOTAL_ASSETS', row.get('资产总计'))),
                    'total_equity': safe_float(row.get('TOTAL_EQUITY', row.get('所有者权益合计'))),
                    'goodwill': safe_float(row.get('GOODWILL', row.get('商誉'))),
                }

        # 2. 利润表 -> operating_revenue, operating_cost, net_profit
        try:
            inc_df = ak.stock_profit_sheet_by_report_em(symbol=code)
        except Exception:
            inc_df = pd.DataFrame()

        inc_map = {}
        if inc_df is not None and not inc_df.empty:
            for _, row in inc_df.iterrows():
                ed = str(row.get('REPORT_DATE', row.get('报告期', '')))[:10].replace('-', '')
                if not ed:
                    continue
                inc_map[ed] = {
                    'operating_revenue': safe_float(row.get('OPERATE_INCOME', row.get('营业收入'))),
                    'operating_cost': safe_float(row.get('OPERATE_COST', row.get('营业成本'))),
                    'net_profit': safe_float(row.get('NETPROFIT', row.get('净利润'))),
                }

        # 3. 现金流量表 -> operating_cash_flow
        try:
            cf_df = ak.stock_cash_flow_sheet_by_report_em(symbol=code)
        except Exception:
            cf_df = pd.DataFrame()

        cf_map = {}
        if cf_df is not None and not cf_df.empty:
            for _, row in cf_df.iterrows():
                ed = str(row.get('REPORT_DATE', row.get('报告期', '')))[:10].replace('-', '')
                if not ed:
                    continue
                cf_map[ed] = {
                    'operating_cash_flow': safe_float(row.get('NETCASH_OPERATE', row.get('经营活动产生的现金流量净额'))),
                }

        # 更新数据库
        records = db.query(StockFinancial).filter(StockFinancial.ts_code == ts_code).all()
        updated = 0
        for rec in records:
            ed = str(rec.end_date).replace('-', '')[:8]
            changed = False

            if ed in bs_map:
                for col in ['total_assets', 'total_equity', 'goodwill']:
                    if getattr(rec, col) is None and bs_map[ed].get(col):
                        setattr(rec, col, bs_map[ed][col])
                        changed = True

            if ed in inc_map:
                for col in ['operating_revenue', 'operating_cost', 'net_profit']:
                    if getattr(rec, col) is None and inc_map[ed].get(col):
                        setattr(rec, col, inc_map[ed][col])
                        changed = True

            if ed in cf_map:
                if rec.operating_cash_flow is None and cf_map[ed].get('operating_cash_flow'):
                    rec.operating_cash_flow = cf_map[ed]['operating_cash_flow']
                    changed = True

            # 计算 gross_profit_margin
            if rec.gross_profit_margin is None and rec.operating_revenue and rec.operating_cost and rec.operating_revenue != 0:
                rec.gross_profit_margin = (rec.operating_revenue - rec.operating_cost) / rec.operating_revenue * 100
                changed = True

            if changed:
                updated += 1

        if updated > 0:
            db.commit()
        return updated

    except Exception:
        db.rollback()
        return -1
    finally:
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='AKShare补齐stock_financial缺失字段')
    parser.add_argument('--ts-code', type=str, help='指定单只股票')
    parser.add_argument('--limit', type=int, default=0, help='限制处理数(0=全部)')
    args = parser.parse_args()

    if args.ts_code:
        count = backfill_stock_em(args.ts_code)
        print(f"  {args.ts_code}: 更新 {count} 条")
        return

    db = SessionLocal()
    try:
        codes = [r[0] for r in db.execute(text(
            "SELECT DISTINCT sf.ts_code FROM stock_financial sf "
            "WHERE sf.total_equity IS NULL OR sf.total_assets IS NULL OR sf.goodwill IS NULL "
            "ORDER BY sf.ts_code"
        )).fetchall()]
    finally:
        db.close()

    total = len(codes)
    if args.limit > 0:
        codes = codes[:args.limit]
        total = len(codes)
    print(f"需补齐 {total} 只股票")

    success = 0
    fail = 0
    total_updated = 0
    t_start = time.time()

    for i, ts_code in enumerate(codes):
        count = backfill_stock_em(ts_code)
        if count > 0:
            success += 1
            total_updated += count
        elif count < 0:
            fail += 1

        if (i + 1) % BATCH_SIZE == 0 or (i + 1) == total:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{total}] 成功:{success} 失败:{fail} 更新:{total_updated}条 速度:{rate:.1f}只/s ETA:{eta/60:.0f}min")

        time.sleep(DELAY)

    elapsed = time.time() - t_start
    print(f"\n完成! 成功:{success} 失败:{fail} 更新:{total_updated}条 耗时:{elapsed/60:.1f}min")


if __name__ == '__main__':
    main()
