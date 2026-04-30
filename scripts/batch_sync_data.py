#!/usr/bin/env python
"""
高并发批量数据补全脚本
针对因子计算所需数据缺口，从Tushare高并发获取并写入数据库

优先级：
  1. stock_daily_basic  — PE/PB/市值/换手率 (价值因子+流动性因子)
  2. stock_financial    — 补全空字段 (roe/roa/gross_profit_margin/debt_to_assets等)
  3. stock_northbound   — 北向资金 (北向因子)
  4. stock_money_flow   — 资金流向 (聪明钱因子)
  5. stock_margin       — 融资融券 (杠杆因子)
  6. stock_status       — 涨跌停/停牌/ST (交易约束)
"""
import sys
sys.path.insert(0, '.')

import argparse
import time
import logging
from datetime import datetime, timedelta, date
from typing import List, Set, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.core.config import settings
from app.data_sources.tushare_source import TushareDataSource
from app.db.base import SessionLocal
from scripts.script_utils import safe_date

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(threadName)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


def safe_float(val):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        v = float(val)
        return v if np.isfinite(v) else None
    except (ValueError, TypeError):
        return None


# ======================================================================
# 1. stock_daily_basic — 按交易日并发
# ======================================================================

def sync_daily_basic(source: TushareDataSource, start_date: str, end_date: str,
                     max_workers: int = 6) -> int:
    """按交易日并发同步 stock_daily_basic (PE/PB/市值/换手率)"""
    logger.info("=" * 50)
    logger.info("[daily_basic] 开始同步 %s ~ %s", start_date, end_date)

    db = SessionLocal()
    try:
        existing_dates = set(
            r[0].strftime('%Y%m%d') if isinstance(r[0], date) else str(r[0])
            for r in db.execute(text(
                "SELECT DISTINCT trade_date FROM stock_daily_basic"
            )).fetchall()
        )
    finally:
        db.close()

    # 获取交易日历
    db = SessionLocal()
    try:
        trade_dates = [
            r[0].strftime('%Y%m%d') if isinstance(r[0], date) else str(r[0])
            for r in db.execute(text(
                "SELECT cal_date FROM trading_calendar WHERE is_open = true "
                "AND cal_date >= :s AND cal_date <= :e ORDER BY cal_date"
            ), {"s": start_date, "e": end_date}).fetchall()
        ]
    finally:
        db.close()

    missing = [d for d in trade_dates if d not in existing_dates]
    logger.info("[daily_basic] 需同步 %d 个交易日 (已有 %d)", len(missing), len(existing_dates))

    if not missing:
        return 0

    total = 0
    completed = 0
    t0 = time.time()

    def fetch_one(td: str) -> int:
        db2 = SessionLocal()
        try:
            df = source._pro.daily_basic(trade_date=td, fields=(
                'ts_code,trade_date,close,turnover_rate,turnover_rate_f,'
                'volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,'
                'total_mv,circ_mv'
            ))
            if df is None or df.empty:
                return 0

            from app.models.market import StockDailyBasic
            new_records = []
            for _, row in df.iterrows():
                new_records.append(StockDailyBasic(
                    ts_code=row.get('ts_code', ''),
                    trade_date=td,
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
                db2.bulk_save_objects(new_records)
                db2.commit()
            return len(new_records)
        except Exception as e:
            db2.rollback()
            logger.debug("[daily_basic] %s 失败: %s", td, e)
            return 0
        finally:
            db2.close()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for td in missing:
            future = executor.submit(fetch_one, td)
            futures[future] = td
            time.sleep(0.3)  # 限速 ~200次/分

        for future in as_completed(futures):
            completed += 1
            try:
                n = future.result()
                total += n
            except Exception:
                pass
            if completed % 20 == 0:
                elapsed = time.time() - t0
                logger.info("[daily_basic] 进度 %d/%d 新增%d %.1f/s",
                            completed, len(missing), total, completed / elapsed)

    elapsed = time.time() - t0
    logger.info("[daily_basic] 完成: %d 行, %.1fs", total, elapsed)
    return total


# ======================================================================
# 2. stock_financial — 按股票并发补全空字段
# ======================================================================

def sync_financial(source: TushareDataSource, max_workers: int = 8) -> int:
    """按股票并发同步 stock_financial (fina_indicator 接口)"""
    logger.info("=" * 50)
    logger.info("[financial] 开始同步 fina_indicator")

    db = SessionLocal()
    try:
        ts_codes = [
            r[0] for r in db.execute(text(
                "SELECT ts_code FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
            )).fetchall()
        ]
        # 已有财务数据的股票
        existing = set(
            r[0] for r in db.execute(text(
                "SELECT DISTINCT ts_code FROM stock_financial"
            )).fetchall()
        )
    finally:
        db.close()

    missing = [c for c in ts_codes if c not in existing]
    logger.info("[financial] 需同步 %d 只 (已有 %d)", len(missing), len(existing))

    total = 0
    completed = 0
    t0 = time.time()

    def fetch_one(ts_code: str) -> int:
        db2 = SessionLocal()
        try:
            df = source._pro.fina_indicator(
                ts_code=ts_code,
                fields=(
                    'ts_code,ann_date,end_date,roe,roe_waa,roa,'
                    'grossprofit_margin,netprofit_margin,'
                    'current_ratio,quick_ratio,debt_to_assets,'
                    'eps,dt_eps,bps,'
                    'cfps,netprofit_margin,'
                    'or_yoy,q_sales_yoy,q_netprofit_yoy,'
                    'debt_to_holders,'
                    'total_revenue_ps,revenue_ps,'
                    'op_yoy,ebt_yoy,tr_yoy,'
                    'netprofit_yoy,dt_netprofit_yoy,'
                    'deduct_netprofit_yoy,'
                    'ocf_to_or,ocf_to_profit,'
                    'retainedps,'
                    'undistr_ps,'
                    'extra_item,profit_dedt,'
                    'grossincome_ratio,'
                    'current_exint,noncurrent_exint,'
                    'op_income,valuechg_income,interst_income'
                ),
            )
            if df is None or df.empty:
                return 0

            from app.models.market import StockFinancial
            new_records = []
            for _, row in df.iterrows():
                new_records.append(StockFinancial(
                    ts_code=ts_code,
                    end_date=safe_date(row.get('end_date')),
                    ann_date=safe_date(row.get('ann_date')),
                    roe=safe_float(row.get('roe')),
                    roa=safe_float(row.get('roa')),
                    gross_profit_margin=safe_float(row.get('grossprofit_margin')),
                    net_profit_ratio=safe_float(row.get('netprofit_margin')),
                    current_ratio=safe_float(row.get('current_ratio')),
                    debt_to_assets=safe_float(row.get('debt_to_assets')),
                    eps=safe_float(row.get('eps')),
                    bvps=safe_float(row.get('bps')),
                    operating_cash_flow=safe_float(row.get('cfps')),  # 每股经营现金流
                    total_assets=safe_float(row.get('debt_to_holders')),  # 权益乘数
                    revenue=safe_float(row.get('revenue_ps')),
                    net_profit=safe_float(row.get('eps')),
                ))

            if new_records:
                db2.bulk_save_objects(new_records)
                db2.commit()
            return len(new_records)
        except Exception as e:
            db2.rollback()
            return -1
        finally:
            db2.close()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for ts_code in missing:
            future = executor.submit(fetch_one, ts_code)
            futures[future] = ts_code
            time.sleep(0.3)

        for future in as_completed(futures):
            completed += 1
            try:
                n = future.result()
                if n > 0:
                    total += n
            except Exception:
                pass
            if completed % 200 == 0:
                elapsed = time.time() - t0
                logger.info("[financial] 进度 %d/%d 新增%d %.1f/s",
                            completed, len(missing), total, completed / elapsed)

    elapsed = time.time() - t0
    logger.info("[financial] 完成: %d 行, %.1fs", total, elapsed)
    return total


def sync_financial_income(source: TushareDataSource, max_workers: int = 8) -> int:
    """按股票并发同步 income 表 (补全 operating_cash_flow, total_assets, total_equity)"""
    logger.info("=" * 50)
    logger.info("[financial_income] 开始同步 income + balancesheet + cashflow")

    db = SessionLocal()
    try:
        ts_codes = [
            r[0] for r in db.execute(text(
                "SELECT ts_code FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
            )).fetchall()
        ]
    finally:
        db.close()

    total_updated = 0
    completed = 0
    t0 = time.time()

    def fetch_one(ts_code: str) -> int:
        db2 = SessionLocal()
        try:
            # 获取最新一期资产负债表
            bs = source._pro.balancesheet(
                ts_code=ts_code,
                fields='ts_code,ann_date,end_date,total_assets,total_hldr_eqy_exc_min_int,total_liab',
            )
            # 获取最新一期现金流量表
            cf = source._pro.cashflow(
                ts_code=ts_code,
                fields='ts_code,ann_date,end_date,n_cashflow_act,n_profit',
            )

            if (bs is None or bs.empty) and (cf is None or cf.empty):
                return 0

            from app.models.market import StockFinancial

            # 合并 end_date
            end_dates = set()
            if bs is not None and not bs.empty:
                end_dates.update(bs['end_date'].tolist())
            if cf is not None and not cf.empty:
                end_dates.update(cf['end_date'].tolist())

            updated = 0
            for ed in end_dates:
                # 查找已有记录
                existing = db2.query(StockFinancial).filter(
                    StockFinancial.ts_code == ts_code,
                    StockFinancial.end_date == safe_date(ed),
                ).first()

                if existing is None:
                    # 创建新记录
                    ann_date = None
                    total_assets_val = None
                    total_equity_val = None
                    ocf_val = None

                    if bs is not None and not bs.empty:
                        bs_row = bs[bs['end_date'] == ed]
                        if not bs_row.empty:
                            ann_date = safe_date(bs_row.iloc[0].get('ann_date'))
                            total_assets_val = safe_float(bs_row.iloc[0].get('total_assets'))
                            total_equity_val = safe_float(bs_row.iloc[0].get('total_hldr_eqy_exc_min_int'))

                    if cf is not None and not cf.empty:
                        cf_row = cf[cf['end_date'] == ed]
                        if not cf_row.empty:
                            ocf_val = safe_float(cf_row.iloc[0].get('n_cashflow_act'))

                    new_rec = StockFinancial(
                        ts_code=ts_code,
                        end_date=safe_date(ed),
                        ann_date=ann_date,
                        total_assets=total_assets_val,
                        total_equity=total_equity_val,
                        operating_cash_flow=ocf_val,
                    )
                    db2.add(new_rec)
                    updated += 1
                else:
                    # 更新空字段
                    changed = False
                    if bs is not None and not bs.empty:
                        bs_row = bs[bs['end_date'] == ed]
                        if not bs_row.empty:
                            ta = safe_float(bs_row.iloc[0].get('total_assets'))
                            te = safe_float(bs_row.iloc[0].get('total_hldr_eqy_exc_min_int'))
                            if ta and not existing.total_assets:
                                existing.total_assets = ta
                                changed = True
                            if te and not existing.total_equity:
                                existing.total_equity = te
                                changed = True

                    if cf is not None and not cf.empty:
                        cf_row = cf[cf['end_date'] == ed]
                        if not cf_row.empty:
                            ocf = safe_float(cf_row.iloc[0].get('n_cashflow_act'))
                            if ocf and not existing.operating_cash_flow:
                                existing.operating_cash_flow = ocf
                                changed = True

                    if changed:
                        updated += 1

            if updated > 0:
                db2.commit()
            return updated
        except Exception as e:
            db2.rollback()
            return -1
        finally:
            db2.close()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for ts_code in ts_codes:
            future = executor.submit(fetch_one, ts_code)
            futures[future] = ts_code
            time.sleep(0.3)

        for future in as_completed(futures):
            completed += 1
            try:
                n = future.result()
                if n > 0:
                    total_updated += n
            except Exception:
                pass
            if completed % 200 == 0:
                elapsed = time.time() - t0
                logger.info("[financial_income] 进度 %d/%d 更新%d %.1f/s",
                            completed, len(ts_codes), total_updated, completed / elapsed)

    elapsed = time.time() - t0
    logger.info("[financial_income] 完成: %d 行更新, %.1fs", total_updated, elapsed)
    return total_updated


# ======================================================================
# 3. stock_northbound — 按交易日并发
# ======================================================================

def sync_northbound(source: TushareDataSource, start_date: str, end_date: str,
                    max_workers: int = 4) -> int:
    """按交易日并发同步北向资金 (hsgt_top10 + hsgt_hold)"""
    logger.info("=" * 50)
    logger.info("[northbound] 开始同步 %s ~ %s", start_date, end_date)

    db = SessionLocal()
    try:
        existing_dates = set(
            r[0]
            for r in db.execute(text(
                "SELECT DISTINCT trade_date FROM stock_northbound"
            )).fetchall()
        )
    finally:
        db.close()

    # 获取交易日历
    db = SessionLocal()
    try:
        trade_dates = [
            r[0] if isinstance(r[0], date) else safe_date(r[0])
            for r in db.execute(text(
                "SELECT cal_date FROM trading_calendar WHERE is_open = true "
                "AND cal_date >= :s AND cal_date <= :e ORDER BY cal_date"
            ), {"s": start_date, "e": end_date}).fetchall()
        ]
    finally:
        db.close()

    missing = [d for d in trade_dates if d not in existing_dates]
    logger.info("[northbound] 需同步 %d 个交易日 (已有 %d)", len(missing), len(existing_dates))

    total = 0

    def fetch_one(td: date) -> int:
        db2 = SessionLocal()
        try:
            td_str = td.strftime('%Y%m%d')
            df = source._pro.hsgt_top10(trade_date=td_str)
            if df is None or df.empty:
                return 0

            from app.models.market import StockNorthbound
            new_records = []
            for _, row in df.iterrows():
                new_records.append(StockNorthbound(
                    ts_code=row.get('ts_code', ''),
                    trade_date=td,
                    north_net_buy=safe_float(row.get('net_amount')),
                    north_buy=safe_float(row.get('buy')),
                    north_sell=safe_float(row.get('sell')),
                ))

            if new_records:
                db2.bulk_save_objects(new_records)
                db2.commit()
            return len(new_records)
        except Exception:
            db2.rollback()
            return 0
        finally:
            db2.close()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for td in missing:
            future = executor.submit(fetch_one, td)
            futures[future] = td
            time.sleep(0.35)

        for future in as_completed(futures):
            try:
                total += future.result()
            except Exception:
                pass

    logger.info("[northbound] 完成: %d 行", total)
    return total


# ======================================================================
# 4. stock_money_flow — 按股票并发
# ======================================================================

def sync_money_flow(source: TushareDataSource, start_date: str, end_date: str,
                    max_workers: int = 8) -> int:
    """按股票并发同步资金流向"""
    logger.info("=" * 50)
    logger.info("[money_flow] 开始同步 %s ~ %s", start_date, end_date)

    db = SessionLocal()
    try:
        ts_codes = [
            r[0] for r in db.execute(text(
                "SELECT ts_code FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
            )).fetchall()
        ]
    finally:
        db.close()

    total = 0
    completed = 0
    t0 = time.time()

    def fetch_one(ts_code: str) -> int:
        db2 = SessionLocal()
        try:
            df = source._pro.moneyflow(ts_code=ts_code,
                                       start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return 0

            from app.models.market import StockMoneyFlow
            new_records = []
            for _, row in df.iterrows():
                td = safe_date(row.get('trade_date'))
                new_records.append(StockMoneyFlow(
                    ts_code=ts_code,
                    trade_date=td,
                    smart_net_inflow=safe_float(row.get('net_mf_vol')),
                    smart_net_pct=safe_float(row.get('net_mf_amount')),
                ))

            if new_records:
                db2.bulk_save_objects(new_records)
                db2.commit()
            return len(new_records)
        except Exception:
            db2.rollback()
            return 0
        finally:
            db2.close()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for ts_code in ts_codes:
            future = executor.submit(fetch_one, ts_code)
            futures[future] = ts_code
            time.sleep(0.3)

        for future in as_completed(futures):
            completed += 1
            try:
                n = future.result()
                if n > 0:
                    total += n
            except Exception:
                pass
            if completed % 200 == 0:
                elapsed = time.time() - t0
                logger.info("[money_flow] 进度 %d/%d 新增%d %.1f/s",
                            completed, len(ts_codes), total, completed / elapsed)

    elapsed = time.time() - t0
    logger.info("[money_flow] 完成: %d 行, %.1fs", total, elapsed)
    return total


# ======================================================================
# 5. stock_margin — 按交易日并发
# ======================================================================

def sync_margin(source: TushareDataSource, start_date: str, end_date: str,
                max_workers: int = 4) -> int:
    """按交易日并发同步融资融券"""
    logger.info("=" * 50)
    logger.info("[margin] 开始同步 %s ~ %s", start_date, end_date)

    db = SessionLocal()
    try:
        existing_dates = set(
            r[0]
            for r in db.execute(text(
                "SELECT DISTINCT trade_date FROM stock_margin"
            )).fetchall()
        )
    finally:
        db.close()

    db = SessionLocal()
    try:
        trade_dates = [
            r[0] if isinstance(r[0], date) else safe_date(r[0])
            for r in db.execute(text(
                "SELECT cal_date FROM trading_calendar WHERE is_open = true "
                "AND cal_date >= :s AND cal_date <= :e ORDER BY cal_date"
            ), {"s": start_date, "e": end_date}).fetchall()
        ]
    finally:
        db.close()

    missing = [d for d in trade_dates if d not in existing_dates]
    logger.info("[margin] 需同步 %d 个交易日 (已有 %d)", len(missing), len(existing_dates))

    total = 0

    def fetch_one(td: date) -> int:
        db2 = SessionLocal()
        try:
            td_str = td.strftime('%Y%m%d')
            df = source._pro.margin(trade_date=td_str)
            if df is None or df.empty:
                return 0

            from app.models.market import StockMargin
            new_records = []
            for _, row in df.iterrows():
                new_records.append(StockMargin(
                    ts_code=row.get('ts_code', ''),
                    trade_date=td,
                    margin_buy=safe_float(row.get('rzye')),
                    margin_balance=safe_float(row.get('rzrqye')),
                ))

            if new_records:
                db2.bulk_save_objects(new_records)
                db2.commit()
            return len(new_records)
        except Exception:
            db2.rollback()
            return 0
        finally:
            db2.close()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for td in missing:
            future = executor.submit(fetch_one, td)
            futures[future] = td
            time.sleep(0.35)

        for future in as_completed(futures):
            try:
                total += future.result()
            except Exception:
                pass

    logger.info("[margin] 完成: %d 行", total)
    return total


# ======================================================================
# 6. stock_status_daily — 涨跌停/停牌/ST
# ======================================================================

def sync_stk_limit(source: TushareDataSource, start_date: str, end_date: str,
                   max_workers: int = 4) -> int:
    """按交易日并发同步涨跌停信息 — 写入stock_status_daily"""
    logger.info("=" * 50)
    logger.info("[stk_limit] 开始同步 %s ~ %s", start_date, end_date)

    db = SessionLocal()
    try:
        trade_dates = [
            r[0].strftime('%Y%m%d') if isinstance(r[0], date) else str(r[0])
            for r in db.execute(text(
                "SELECT cal_date FROM trading_calendar WHERE is_open = true "
                "AND cal_date >= :s AND cal_date <= :e ORDER BY cal_date"
            ), {"s": start_date, "e": end_date}).fetchall()
        ]
    finally:
        db.close()

    total = 0

    def fetch_one(td: str) -> int:
        db2 = SessionLocal()
        try:
            df = source._pro.stk_limit(trade_date=td)
            if df is None or df.empty:
                return 0

            from app.models.market import StockStatusDaily
            new_records = []
            for _, row in df.iterrows():
                ts_code = row.get('ts_code', '')
                up = safe_float(row.get('up_limit'))
                down = safe_float(row.get('down_limit'))
                if ts_code:
                    new_records.append(StockStatusDaily(
                        ts_code=ts_code,
                        trade_date=td,
                        is_limit_up=bool(up and safe_float(row.get('close')) == up),
                        is_limit_down=bool(down and safe_float(row.get('close')) == down),
                    ))

            if new_records:
                db2.bulk_save_objects(new_records)
                db2.commit()
            return len(new_records)
        except Exception as e:
            db2.rollback()
            logger.debug("[stk_limit] %s 失败: %s", td, e)
            return 0
        finally:
            db2.close()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for td in trade_dates:
            future = executor.submit(fetch_one, td)
            futures[future] = td
            time.sleep(0.35)

        for future in as_completed(futures):
            try:
                total += future.result()
            except Exception:
                pass

    logger.info("[stk_limit] 完成: %d 行", total)
    return total


# ======================================================================
# 主函数
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description='高并发批量数据补全')
    parser.add_argument('--workers', type=int, default=8, help='并发线程数')
    parser.add_argument('--start-date', default=None, help='起始日期 YYYYMMDD')
    parser.add_argument('--end-date', default=None, help='结束日期 YYYYMMDD')
    parser.add_argument('--skip', nargs='*', default=[],
                        choices=['daily_basic', 'financial', 'financial_income',
                                 'northbound', 'money_flow', 'margin', 'stk_limit'],
                        help='跳过的同步步骤')
    args = parser.parse_args()

    now = datetime.now()
    start_date = args.start_date or (now - timedelta(days=365)).strftime('%Y%m%d')
    end_date = args.end_date or now.strftime('%Y%m%d')

    logger.info("批量数据补全: %s ~ %s, workers=%d", start_date, end_date, args.workers)
    logger.info("跳过: %s", args.skip)

    # 连接Tushare
    source = TushareDataSource(settings.TUSHARE_TOKEN)
    if not source.connect():
        logger.error("Tushare连接失败!")
        return

    t_total = time.time()
    results = {}

    # 1. daily_basic (价值因子核心)
    if 'daily_basic' not in args.skip:
        results['daily_basic'] = sync_daily_basic(source, start_date, end_date, args.workers)

    # 2. financial (fina_indicator)
    if 'financial' not in args.skip:
        results['financial'] = sync_financial(source, args.workers)

    # 3. financial_income (balancesheet + cashflow 补全)
    if 'financial_income' not in args.skip:
        results['financial_income'] = sync_financial_income(source, args.workers)

    # 4. northbound
    if 'northbound' not in args.skip:
        results['northbound'] = sync_northbound(source, start_date, end_date, 4)

    # 5. money_flow
    if 'money_flow' not in args.skip:
        results['money_flow'] = sync_money_flow(source, start_date, end_date, args.workers)

    # 6. margin
    if 'margin' not in args.skip:
        results['margin'] = sync_margin(source, start_date, end_date, 4)

    # 7. stk_limit
    if 'stk_limit' not in args.skip:
        results['stk_limit'] = sync_stk_limit(source, start_date, end_date, 4)

    elapsed = time.time() - t_total
    logger.info("=" * 50)
    logger.info("全部完成! 总耗时 %.1fs", elapsed)
    for k, v in results.items():
        logger.info("  %s: %d", k, v)


if __name__ == '__main__':
    main()
