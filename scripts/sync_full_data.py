#!/usr/bin/env python
"""
补全数据库真实数据
1. 更多指数日线 (上证50/创业板指/科创50/上证指数/深证成指)
2. 扩展交易日历到2年
3. 全A股基础信息 (5500+只)
4. 财务数据 (沪深300成分股)
5. 行业分类
6. 扩展股票日线到2年
"""
import sys
sys.path.insert(0, '.')

import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.logging import logger
from app.db.base import SessionLocal

import akshare as ak


def sync_index_daily_extended():
    """补全更多指数日线数据"""
    print("\n[1] 补全指数日线...")
    db = SessionLocal()
    count = 0

    indices = [
        ('sh000001', '000001.SH', '上证指数'),
        ('sh000016', '000016.SH', '上证50'),
        ('sh000300', '000300.SH', '沪深300'),
        ('sh000905', '000905.SH', '中证500'),
        ('sh000852', '000852.SH', '中证1000'),
        ('sh000688', '000688.SH', '科创50'),
        ('sz399001', '399001.SZ', '深证成指'),
        ('sz399006', '399006.SZ', '创业板指'),
    ]

    for symbol, index_code, name in indices:
        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df.empty:
                print(f"  {name}: 无数据")
                continue

            # 只取近2年
            df.index = pd.to_datetime(df.index)
            two_years_ago = pd.Timestamp.now() - timedelta(days=730)
            df = df[df.index >= two_years_ago]

            from app.models.market import IndexDaily
            for dt, row in df.iterrows():
                trade_date = dt.date()
                existing = db.query(IndexDaily).filter(
                    IndexDaily.index_code == index_code,
                    IndexDaily.trade_date == trade_date
                ).first()

                if not existing:
                    daily = IndexDaily(
                        index_code=index_code,
                        trade_date=trade_date,
                        open=float(row.get('open', 0)),
                        high=float(row.get('high', 0)),
                        low=float(row.get('low', 0)),
                        close=float(row.get('close', 0)),
                        pre_close=0,
                        change=0,
                        pct_chg=0,
                        vol=float(row.get('volume', 0)),
                        amount=float(row.get('amount', 0)),
                        data_source='akshare',
                    )
                    db.add(daily)
                    count += 1

            db.commit()
            print(f"  {name}({index_code}): +{count} 条" if count > 0 else f"  {name}({index_code}): 已是最新")
            count = 0
        except Exception as e:
            print(f"  {name}: 失败 - {str(e)[:60]}")
            db.rollback()

    db.close()


def sync_trading_calendar_extended():
    """扩展交易日历到2年"""
    print("\n[2] 扩展交易日历...")
    db = SessionLocal()
    count = 0

    try:
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=730)).strftime('%Y%m%d')
        df = ak.tool_trade_date_hist_sina()
        df['trade_date'] = pd.to_datetime(df['trade_date'])

        two_years_ago = pd.Timestamp.now() - timedelta(days=730)
        df = df[df['trade_date'] >= two_years_ago]

        from app.models.market import TradingCalendar
        for _, row in df.iterrows():
            trade_date = row['trade_date'].date()
            existing = db.query(TradingCalendar).filter(
                TradingCalendar.exchange == 'SSE',
                TradingCalendar.cal_date == trade_date
            ).first()

            if not existing:
                cal = TradingCalendar(
                    exchange='SSE',
                    cal_date=trade_date,
                    is_open=True,
                )
                db.add(cal)
                count += 1

        db.commit()
        print(f"  新增 {count} 条交易日历")
    except Exception as e:
        print(f"  失败: {str(e)[:60]}")
        db.rollback()

    db.close()


def sync_stock_basic_full():
    """补全全A股基础信息"""
    print("\n[3] 补全全A股基础信息...")
    db = SessionLocal()
    count = 0

    try:
        df = ak.stock_info_a_code_name()
        from app.models.market import StockBasic

        for _, row in df.iterrows():
            code = row['code']
            # 转换为ts_code格式
            if code.startswith('6'):
                ts_code = code + '.SH'
            elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
                ts_code = code + '.SZ'
            elif code.startswith('8') or code.startswith('4'):
                ts_code = code + '.BJ'
            else:
                continue

            name = row['name']

            existing = db.query(StockBasic).filter(
                StockBasic.ts_code == ts_code
            ).first()

            if not existing:
                stock = StockBasic(
                    ts_code=ts_code,
                    symbol=code,
                    name=name,
                    list_status='L',
                )
                db.add(stock)
                count += 1
            else:
                # 更新名称
                if existing.name != name:
                    existing.name = name

            if count > 0 and count % 1000 == 0:
                db.commit()

        db.commit()
        print(f"  新增 {count} 只股票基础信息 (全A股{len(df)}只)")
    except Exception as e:
        print(f"  失败: {str(e)[:60]}")
        db.rollback()

    db.close()


def sync_financial_data():
    """同步沪深300成分股财务数据"""
    print("\n[4] 同步财务数据 (沪深300成分股)...")
    db = SessionLocal()
    count = 0

    # 获取已有股票代码
    codes = [r[0] for r in db.execute(text("SELECT DISTINCT ts_code FROM stock_daily")).fetchall()]
    print(f"  需同步 {len(codes)} 只股票的财务数据")

    from app.models.market import StockFinancial

    for i, ts_code in enumerate(codes):
        try:
            symbol = ts_code.split('.')[0]
            df = ak.stock_financial_analysis_indicator(symbol=symbol, start_year='2023')
            if df.empty:
                continue

            for _, row in df.iterrows():
                end_date_str = str(row.get('日期', ''))
                if not end_date_str or len(end_date_str) < 10:
                    continue
                end_date = pd.Timestamp(end_date_str).date()

                existing = db.query(StockFinancial).filter(
                    StockFinancial.ts_code == ts_code,
                    StockFinancial.end_date == end_date
                ).first()

                if not existing:
                    # 提取关键字段
                    def safe_float(val):
                        try:
                            v = float(val) if pd.notna(val) else None
                            return v
                        except (ValueError, TypeError):
                            return None

                    financial = StockFinancial(
                        ts_code=ts_code,
                        end_date=end_date,
                        ann_date=end_date,  # 简化
                        revenue=safe_float(row.get('营业收入(元)')),
                        net_profit=safe_float(row.get('净利润(元)')),
                        roe=safe_float(row.get('净资产收益率(%)')),
                        roa=safe_float(row.get('总资产利润率(%)')),
                        gross_profit=safe_float(row.get('营业利润(元)')),
                        total_assets=safe_float(row.get('总资产(元)')),
                        total_equity=safe_float(row.get('所有者权益合计(元)')),
                        operating_cash_flow=safe_float(row.get('经营活动产生的现金流量净额(元)')),
                    )
                    db.add(financial)
                    count += 1

            db.commit()

            if (i + 1) % 50 == 0:
                print(f"  进度: {i+1}/{len(codes)}, 已入库 {count} 条")

        except Exception as e:
            db.rollback()
            if (i + 1) % 50 == 0:
                print(f"  {ts_code}: 失败 - {str(e)[:40]}")
            # 限速
            time.sleep(0.1)

    db.close()
    print(f"  财务数据总计: {count} 条")


def sync_industry_classification():
    """同步行业分类"""
    print("\n[5] 同步行业分类...")
    db = SessionLocal()
    count = 0

    try:
        from app.models.market import StockIndustry

        # 获取同花顺行业列表
        industries = ak.stock_board_industry_name_ths()
        print(f"  行业数: {len(industries)}")

        for _, ind_row in industries.iterrows():
            industry_name = ind_row['name']
            industry_code = ind_row['code']

            try:
                # 获取该行业成分股
                members = ak.stock_board_industry_cons_ths(symbol=industry_name)
                if members.empty:
                    continue

                for _, mem_row in members.iterrows():
                    code = str(mem_row.get('代码', mem_row.get('code', '')))
                    if not code:
                        continue

                    if code.startswith('6'):
                        ts_code = code + '.SH'
                    elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
                        ts_code = code + '.SZ'
                    else:
                        continue

                    existing = db.query(StockIndustry).filter(
                        StockIndustry.ts_code == ts_code,
                    ).first()

                    if not existing:
                        si = StockIndustry(
                            ts_code=ts_code,
                            industry=industry_name,
                            industry_code=industry_code,
                        )
                        db.add(si)
                        count += 1

                db.commit()
                if count > 0 and count % 500 == 0:
                    print(f"  已入库 {count} 条行业分类")

            except Exception:
                db.rollback()
                time.sleep(0.5)
                continue

        print(f"  行业分类总计: {count} 条")
    except Exception as e:
        print(f"  失败: {str(e)[:60]}")
        db.rollback()

    db.close()


def sync_stock_daily_extended():
    """扩展股票日线到2年"""
    print("\n[6] 扩展股票日线到2年...")
    db = SessionLocal()

    # 检查当前日期范围
    r = db.execute(text("SELECT MIN(trade_date), MAX(trade_date) FROM stock_daily")).fetchone()
    current_min, current_max = r[0], r[1]
    target_start = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')

    if str(current_min) <= target_start:
        print(f"  日期范围已满足: {current_min} ~ {current_max}")
        db.close()
        return

    print(f"  当前: {current_min} ~ {current_max}, 目标起始: {target_start}")

    codes = [r[0] for r in db.execute(text("SELECT DISTINCT ts_code FROM stock_daily")).fetchall()]
    print(f"  需扩展 {len(codes)} 只股票")

    from app.models.market import StockDaily
    from app.data_sources import get_data_source
    from app.data_sources.normalizer import DataNormalizer
    from app.data_sources.cleaner import DataCleaner

    normalizer = DataNormalizer()
    cleaner = DataCleaner()

    # 使用AKShare
    source = ak
    total_count = 0

    for i, ts_code in enumerate(codes):
        try:
            symbol = ts_code.split('.')[0]
            # AKShare获取日线
            df = ak.stock_zh_a_hist(symbol=symbol, period='daily',
                                     start_date='20240401', end_date='20260418', adjust='qfq')
            if df.empty:
                continue

            for _, row in df.iterrows():
                trade_date_str = str(row['日期'])
                trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d').date()

                # 只插入当前范围之前的数据
                if trade_date >= pd.Timestamp(current_min).date():
                    continue

                existing = db.query(StockDaily).filter(
                    StockDaily.ts_code == ts_code,
                    StockDaily.trade_date == trade_date
                ).first()

                if not existing:
                    daily = StockDaily(
                        ts_code=ts_code,
                        trade_date=trade_date,
                        open=float(row.get('开盘', 0)),
                        high=float(row.get('最高', 0)),
                        low=float(row.get('最低', 0)),
                        close=float(row.get('收盘', 0)),
                        pre_close=float(row.get('昨收', 0)) if '昨收' in row else 0,
                        change=float(row.get('涨跌额', 0)) if '涨跌额' in row else 0,
                        pct_chg=float(row.get('涨跌幅', 0)) if '涨跌幅' in row else 0,
                        vol=float(row.get('成交量', 0)),
                        amount=float(row.get('成交额', 0)),
                        data_source='akshare',
                    )
                    db.add(daily)
                    total_count += 1

            db.commit()

            if (i + 1) % 50 == 0:
                print(f"  进度: {i+1}/{len(codes)}, 新增 {total_count} 条")

        except Exception as e:
            db.rollback()
            if (i + 1) % 50 == 0:
                print(f"  {ts_code}: 失败 - {str(e)[:40]}")
            time.sleep(0.1)

    db.close()
    print(f"  扩展日线总计: {total_count} 条")


def main():
    print("=" * 60)
    print("补全数据库真实数据")
    print("=" * 60)

    t0 = time.time()

    sync_index_daily_extended()
    sync_trading_calendar_extended()
    sync_stock_basic_full()
    sync_financial_data()
    sync_industry_classification()
    sync_stock_daily_extended()

    print("\n" + "=" * 60)
    print(f"补全完成! 总耗时: {time.time()-t0:.1f}s")
    print("=" * 60)

    # 最终统计
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        print("\n最终数据统计:")
        for table in ['stock_daily', 'index_daily', 'trading_calendar', 'stock_basic', 'stock_financial', 'stock_industry']:
            try:
                n = conn.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()
                print(f"  {table}: {n} 条")
            except:
                pass
        r = conn.execute(text("SELECT MIN(trade_date), MAX(trade_date) FROM stock_daily")).fetchone()
        n = conn.execute(text("SELECT COUNT(DISTINCT ts_code) FROM stock_daily")).scalar()
        print(f"  股票日线: {n} 只, {r[0]} ~ {r[1]}")


if __name__ == "__main__":
    main()
