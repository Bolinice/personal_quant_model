"""
补齐 stock_financial 缺失字段
数据源: Tushare balancesheet + income + cashflow + fina_indicator
补齐: total_equity, total_assets, operating_cash_flow, gross_profit_margin,
      goodwill, revenue_yoy, net_profit_yoy, deduct_net_profit_yoy, gross_profit 等
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
from app.models.market.stock_financial import StockFinancial
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


def backfill_stock(ts_code: str, source: TushareDataSource) -> int:
    """补齐单只股票的缺失字段"""
    db = SessionLocal()
    try:
        # 1. 获取 balancesheet (total_equity, total_assets, goodwill)
        try:
            bs_df = source._pro.balancesheet(
                ts_code=ts_code,
                fields='ts_code,ann_date,end_date,total_assets,total_hldr_eqy_exc_min_int,goodwill'
            )
        except Exception:
            bs_df = pd.DataFrame()

        # 2. 获取 income (revenue, operating_revenue, operating_cost, total_revenue, deduct_net_profit)
        try:
            inc_df = source._pro.income(
                ts_code=ts_code,
                fields='ts_code,ann_date,end_date,total_revenue,revenue,oper_cost,total_cogs,net_profit,n_income_attr_p'
            )
        except Exception:
            inc_df = pd.DataFrame()

        # 3. 获取 cashflow (operating_cash_flow)
        try:
            cf_df = source._pro.cashflow(
                ts_code=ts_code,
                fields='ts_code,ann_date,end_date,n_cashflow_act'
            )
        except Exception:
            cf_df = pd.DataFrame()

        # 4. 获取 fina_indicator (yoy数据, gross_profit_margin)
        try:
            fi_df = source._pro.fina_indicator(
                ts_code=ts_code,
                fields='ts_code,ann_date,end_date,grossprofit_margin,or_yoy,netprofit_yoy,deduct_netprofit_yoy,ocfps'
            )
        except Exception:
            fi_df = pd.DataFrame()

        # 构建 end_date -> 额外字段 的映射
        bs_map = {}
        if bs_df is not None and not bs_df.empty:
            for _, row in bs_df.iterrows():
                ed = str(row.get('end_date', ''))[:8]
                if ed:
                    bs_map[ed] = {
                        'total_assets': safe_float(row.get('total_assets')),
                        'total_equity': safe_float(row.get('total_hldr_eqy_exc_min_int')),
                        'goodwill': safe_float(row.get('goodwill')),
                    }

        inc_map = {}
        if inc_df is not None and not inc_df.empty:
            for _, row in inc_df.iterrows():
                ed = str(row.get('end_date', ''))[:8]
                if ed:
                    inc_map[ed] = {
                        'operating_revenue': safe_float(row.get('revenue')),
                        'operating_cost': safe_float(row.get('oper_cost')),
                        'total_revenue': safe_float(row.get('total_revenue')),
                        'deduct_net_profit': safe_float(row.get('n_income_attr_p')),
                    }

        cf_map = {}
        if cf_df is not None and not cf_df.empty:
            for _, row in cf_df.iterrows():
                ed = str(row.get('end_date', ''))[:8]
                if ed:
                    cf_map[ed] = {
                        'operating_cash_flow': safe_float(row.get('n_cashflow_act')),
                    }

        fi_map = {}
        if fi_df is not None and not fi_df.empty:
            for _, row in fi_df.iterrows():
                ed = str(row.get('end_date', ''))[:8]
                if ed:
                    fi_map[ed] = {
                        'gross_profit_margin': safe_float(row.get('grossprofit_margin')),
                        'revenue_yoy': safe_float(row.get('or_yoy')),
                        'net_profit_yoy': safe_float(row.get('netprofit_yoy')),
                        'yoy_deduct_net_profit': safe_float(row.get('deduct_netprofit_yoy')),
                    }

        # 更新数据库中已有的记录
        records = db.query(StockFinancial).filter(
            StockFinancial.ts_code == ts_code
        ).all()

        updated = 0
        for rec in records:
            ed = str(rec.end_date).replace('-', '')[:8]
            changed = False

            # balancesheet 字段
            if ed in bs_map:
                if rec.total_assets is None and bs_map[ed].get('total_assets'):
                    rec.total_assets = bs_map[ed]['total_assets']
                    changed = True
                if rec.total_equity is None and bs_map[ed].get('total_equity'):
                    rec.total_equity = bs_map[ed]['total_equity']
                    changed = True
                if rec.goodwill is None and bs_map[ed].get('goodwill'):
                    rec.goodwill = bs_map[ed]['goodwill']
                    changed = True

            # income 字段
            if ed in inc_map:
                if rec.operating_revenue is None and inc_map[ed].get('operating_revenue'):
                    rec.operating_revenue = inc_map[ed]['operating_revenue']
                    changed = True
                if rec.operating_cost is None and inc_map[ed].get('operating_cost'):
                    rec.operating_cost = inc_map[ed]['operating_cost']
                    changed = True
                if rec.total_revenue is None and inc_map[ed].get('total_revenue'):
                    rec.total_revenue = inc_map[ed]['total_revenue']
                    changed = True
                if rec.deduct_net_profit is None and inc_map[ed].get('deduct_net_profit'):
                    rec.deduct_net_profit = inc_map[ed]['deduct_net_profit']
                    changed = True

            # cashflow 字段
            if ed in cf_map:
                if rec.operating_cash_flow is None and cf_map[ed].get('operating_cash_flow'):
                    rec.operating_cash_flow = cf_map[ed]['operating_cash_flow']
                    changed = True

            # fina_indicator 字段
            if ed in fi_map:
                if rec.gross_profit_margin is None and fi_map[ed].get('gross_profit_margin'):
                    rec.gross_profit_margin = fi_map[ed]['gross_profit_margin']
                    changed = True
                if rec.revenue_yoy is None and fi_map[ed].get('revenue_yoy'):
                    rec.revenue_yoy = fi_map[ed]['revenue_yoy']
                    changed = True
                if rec.net_profit_yoy is None and fi_map[ed].get('net_profit_yoy'):
                    rec.net_profit_yoy = fi_map[ed]['net_profit_yoy']
                    changed = True
                if rec.yoy_deduct_net_profit is None and fi_map[ed].get('yoy_deduct_net_profit'):
                    rec.yoy_deduct_net_profit = fi_map[ed]['yoy_deduct_net_profit']
                    changed = True
                if rec.operating_cash_flow is None and fi_map[ed].get('operating_cash_flow'):
                    rec.operating_cash_flow = fi_map[ed]['operating_cash_flow']
                    changed = True

            if changed:
                updated += 1

        if updated > 0:
            db.commit()
        return updated

    except Exception as e:
        db.rollback()
        return -1
    finally:
        db.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='补齐stock_financial缺失字段')
    parser.add_argument('--ts-code', type=str, help='指定单只股票')
    parser.add_argument('--limit', type=int, default=0, help='限制处理股票数(0=全部)')
    args = parser.parse_args()

    source = TushareDataSource(token=settings.TUSHARE_TOKEN)
    if not source.connect():
        print("Tushare 连接失败!")
        return

    if args.ts_code:
        count = backfill_stock(args.ts_code, source)
        print(f"  {args.ts_code}: 更新 {count} 条记录")
        return

    # 获取需要补齐的股票列表
    db = SessionLocal()
    try:
        # 找出 total_equity 或 total_assets 为空的记录
        codes = [r[0] for r in db.execute(text(
            "SELECT DISTINCT ts_code FROM stock_financial "
            "WHERE total_equity IS NULL OR total_assets IS NULL OR goodwill IS NULL "
            "ORDER BY ts_code"
        )).fetchall()]
    finally:
        db.close()

    total = len(codes)
    if args.limit > 0:
        codes = codes[:args.limit]
        total = len(codes)
    print(f"需补齐 {total} 只股票的缺失字段")

    if total == 0:
        print("所有字段已补齐")
        return

    success = 0
    fail = 0
    total_updated = 0
    t_start = time.time()

    for i, ts_code in enumerate(codes):
        count = backfill_stock(ts_code, source)

        if count > 0:
            success += 1
            total_updated += count
        elif count < 0:
            fail += 1

        if (i + 1) % BATCH_SIZE == 0 or (i + 1) == total:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{total}] 成功:{success} 失败:{fail} "
                  f"更新:{total_updated}条 速度:{rate:.1f}只/s ETA:{eta/60:.0f}min")

        time.sleep(DELAY)

    elapsed = time.time() - t_start
    print(f"\n完成! 成功:{success} 失败:{fail} 更新:{total_updated}条 耗时:{elapsed/60:.1f}min")


if __name__ == '__main__':
    main()