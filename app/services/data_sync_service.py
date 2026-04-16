"""
数据同步服务
自动从数据源同步市场数据到数据库
"""
import sys
sys.path.insert(0, '.')

from typing import List, Optional, Dict
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy.orm import Session
from app.db.base import with_db, SessionLocal
from app.models.market import StockDaily, IndexDaily, TradingCalendar, StockBasic, StockFinancial
from app.data_sources import TushareDataSource, AKShareDataSource, CrawlerDataSource, data_source_manager, get_data_source
from app.core.logging import logger
from app.core.config import settings


class DataSyncService:
    """数据同步服务"""

    def __init__(self, primary_source: str = 'crawler', tushare_token: str = None):
        """
        初始化数据同步服务

        Args:
            primary_source: 主数据源 ('crawler', 'tushare' 或 'akshare')
            tushare_token: Tushare token
        """
        self.primary_source = primary_source
        self.tushare_token = tushare_token

        # 注册数据源
        if tushare_token:
            tushare = TushareDataSource(token=tushare_token)
            data_source_manager.register('tushare', tushare, is_primary=(primary_source == 'tushare'))

        akshare = AKShareDataSource()
        data_source_manager.register('akshare', akshare, is_primary=(primary_source == 'akshare'))

        crawler = CrawlerDataSource()
        data_source_manager.register('crawler', crawler, is_primary=(primary_source == 'crawler'))

        # 连接数据源
        self.connection_status = data_source_manager.connect_all()
        logger.info(f"Data source connection status: {self.connection_status}")

    def get_source_for_data(self, data_type: str) -> Optional[str]:
        """
        根据数据类型选择最佳数据源

        Args:
            data_type: 数据类型 ('stock_daily', 'stock_basic', 'index_daily', 'trading_calendar')

        Returns:
            数据源名称
        """
        # Tushare 免费账户权限有限，某些接口需要用 AKShare 补充
        tushare_available = self.connection_status.get('tushare', False)
        akshare_available = self.connection_status.get('akshare', False)

        # 优先级映射：根据数据类型选择数据源
        source_priority = {
            'stock_daily': ['crawler', 'tushare', 'akshare'],      # 爬虫最快最稳定
            'stock_basic': ['crawler', 'tushare', 'akshare'],      # 爬虫股票基础信息
            'index_daily': ['crawler', 'akshare', 'tushare'],      # 爬虫指数数据
            'trading_calendar': ['crawler', 'akshare', 'tushare'], # 爬虫交易日历
            'financial': ['akshare', 'tushare'],                   # 财务数据
        }

        for source in source_priority.get(data_type, ['crawler', 'tushare', 'akshare']):
            if source == 'tushare' and tushare_available:
                return 'tushare'
            elif source == 'akshare' and akshare_available:
                return 'akshare'
            elif source == 'crawler' and self.connection_status.get('crawler', False):
                return 'crawler'

        return self.get_available_source()

    def get_available_source(self) -> Optional[str]:
        """获取可用的数据源"""
        for name in ['tushare', 'akshare']:
            if self.connection_status.get(name):
                return name
        return None

    # ==================== 交易日历同步 ====================

    def sync_trading_calendar(self, start_date: str, end_date: str) -> int:
        """
        同步交易日历

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期

        Returns:
            同步的记录数
        """
        source_name = self.get_source_for_data('trading_calendar')
        if not source_name:
            logger.error("No available data source for trading calendar")
            return 0

        source = get_data_source(source_name)
        df = source.get_trading_calendar(start_date, end_date)

        if df.empty:
            logger.warning("No trading calendar data fetched")
            return 0

        db = SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                # 处理日期格式
                trade_date = row['trade_date']
                if isinstance(trade_date, str):
                    trade_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                elif hasattr(trade_date, 'date'):
                    trade_date = trade_date.date()

                pretrade_date = row.get('pretrade_date')
                if pretrade_date and not pd.isna(pretrade_date):
                    if isinstance(pretrade_date, str):
                        pretrade_date = datetime.strptime(pretrade_date, '%Y-%m-%d').date()
                    elif hasattr(pretrade_date, 'date'):
                        pretrade_date = pretrade_date.date()
                else:
                    pretrade_date = None

                existing = db.query(TradingCalendar).filter(
                    TradingCalendar.exchange == 'SSE',
                    TradingCalendar.cal_date == trade_date
                ).first()

                if not existing:
                    calendar = TradingCalendar(
                        exchange='SSE',
                        cal_date=trade_date,
                        is_open=bool(row['is_open']),
                        pretrade_date=pretrade_date
                    )
                    db.add(calendar)
                    count += 1

            db.commit()
            logger.info(f"Synced {count} trading calendar records")
            return count

        except Exception as e:
            logger.error(f"Error syncing trading calendar: {e}")
            db.rollback()
            return 0
        finally:
            db.close()

    # ==================== 股票基础信息同步 ====================

    def sync_stock_basic(self) -> int:
        """
        同步股票基础信息

        Returns:
            同步的记录数
        """
        source_name = self.get_source_for_data('stock_basic')
        if not source_name:
            logger.error("No available data source for stock basic")
            return 0

        source = get_data_source(source_name)
        df = source.get_stock_basic()

        if df.empty:
            logger.warning("No stock basic data fetched")
            return 0

        db = SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                existing = db.query(StockBasic).filter(
                    StockBasic.ts_code == row['ts_code']
                ).first()

                if existing:
                    # 更新
                    existing.name = row.get('name')
                    existing.market = row.get('market')
                    existing.list_status = row.get('status', 'L')
                else:
                    # 新增
                    # 处理 list_date，避免 nan
                    list_date = row.get('list_date')
                    if pd.isna(list_date):
                        list_date = None

                    stock = StockBasic(
                        ts_code=row['ts_code'],
                        symbol=row.get('symbol'),
                        name=row.get('name'),
                        market=row.get('market'),
                        list_date=list_date,
                        list_status=row.get('status', 'L')
                    )
                    db.add(stock)
                    count += 1

            db.commit()
            logger.info(f"Synced {count} stock basic records")
            return count

        except Exception as e:
            logger.error(f"Error syncing stock basic: {e}")
            db.rollback()
            return 0
        finally:
            db.close()

    # ==================== 股票日线行情同步 ====================

    def sync_stock_daily(self, ts_code: str, start_date: str, end_date: str) -> int:
        """
        同步单只股票日线行情

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            同步的记录数
        """
        source_name = self.get_source_for_data('stock_daily')
        if not source_name:
            logger.error("No available data source for stock daily")
            return 0

        source = get_data_source(source_name)
        df = source.get_stock_daily(ts_code, start_date, end_date)

        if df.empty:
            logger.warning(f"No daily data fetched for {ts_code}")
            return 0

        db = SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                # 处理日期格式
                trade_date = row['trade_date']
                if isinstance(trade_date, str):
                    trade_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                elif hasattr(trade_date, 'date'):
                    trade_date = trade_date.date()

                existing = db.query(StockDaily).filter(
                    StockDaily.ts_code == ts_code,
                    StockDaily.trade_date == trade_date
                ).first()

                if not existing:
                    daily = StockDaily(
                        ts_code=ts_code,
                        trade_date=trade_date,
                        open=row.get('open'),
                        high=row.get('high'),
                        low=row.get('low'),
                        close=row.get('close'),
                        pre_close=row.get('pre_close'),
                        change=row.get('change'),
                        pct_chg=row.get('pct_chg'),
                        vol=row.get('volume'),
                        amount=row.get('amount')
                    )
                    db.add(daily)
                    count += 1

            db.commit()
            logger.info(f"Synced {count} daily records for {ts_code}")
            return count

        except Exception as e:
            logger.error(f"Error syncing stock daily: {e}")
            db.rollback()
            return 0
        finally:
            db.close()

    def sync_stock_daily_batch(self, ts_codes: List[str], start_date: str, end_date: str) -> int:
        """
        批量同步股票日线行情

        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            总同步记录数
        """
        total_count = 0
        for i, ts_code in enumerate(ts_codes):
            count = self.sync_stock_daily(ts_code, start_date, end_date)
            total_count += count

            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i + 1}/{len(ts_codes)} stocks processed")

        return total_count

    # ==================== 指数日线行情同步 ====================

    def sync_index_daily(self, index_code: str, start_date: str, end_date: str) -> int:
        """
        同步指数日线行情

        Args:
            index_code: 指数代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            同步的记录数
        """
        source_name = self.get_source_for_data('index_daily')
        if not source_name:
            logger.error("No available data source for index daily")
            return 0

        source = get_data_source(source_name)
        df = source.get_index_daily(index_code, start_date, end_date)

        if df.empty:
            logger.warning(f"No index daily data fetched for {index_code}")
            return 0

        db = SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                # 处理日期格式
                trade_date = row['trade_date']
                if isinstance(trade_date, str):
                    trade_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                elif hasattr(trade_date, 'date'):
                    trade_date = trade_date.date()

                existing = db.query(IndexDaily).filter(
                    IndexDaily.index_code == index_code,
                    IndexDaily.trade_date == trade_date
                ).first()

                if not existing:
                    daily = IndexDaily(
                        index_code=index_code,
                        trade_date=trade_date,
                        open=row.get('open'),
                        high=row.get('high'),
                        low=row.get('low'),
                        close=row.get('close'),
                        pre_close=row.get('pre_close'),
                        change=row.get('change'),
                        pct_chg=row.get('pct_chg'),
                        vol=row.get('volume'),
                        amount=row.get('amount')
                    )
                    db.add(daily)
                    count += 1

            db.commit()
            logger.info(f"Synced {count} index daily records for {index_code}")
            return count

        except Exception as e:
            logger.error(f"Error syncing index daily: {e}")
            db.rollback()
            return 0
        finally:
            db.close()

    # ==================== 财务数据同步 ====================

    def sync_financial_data(self, ts_code: str) -> int:
        """
        同步财务数据

        Args:
            ts_code: 股票代码

        Returns:
            同步的记录数
        """
        source_name = self.get_available_source()
        if not source_name:
            logger.error("No available data source")
            return 0

        source = get_data_source(source_name)
        df = source.get_financial_indicator(ts_code)

        if df.empty:
            logger.warning(f"No financial data fetched for {ts_code}")
            return 0

        db = SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                existing = db.query(StockFinancial).filter(
                    StockFinancial.ts_code == ts_code,
                    StockFinancial.end_date == row.get('end_date')
                ).first()

                if not existing:
                    financial = StockFinancial(
                        ts_code=ts_code,
                        end_date=row.get('end_date'),
                        ann_date=row.get('ann_date'),
                        revenue=row.get('revenue'),
                        net_profit=row.get('net_profit'),
                        roe=row.get('roe'),
                        roa=row.get('roa'),
                        gross_profit=row.get('gross_profit'),
                        total_assets=row.get('total_assets'),
                        total_equity=row.get('total_equity'),
                        operating_cash_flow=row.get('operating_cash_flow')
                    )
                    db.add(financial)
                    count += 1

            db.commit()
            logger.info(f"Synced {count} financial records for {ts_code}")
            return count

        except Exception as e:
            logger.error(f"Error syncing financial data: {e}")
            db.rollback()
            return 0
        finally:
            db.close()

    # ==================== 全量同步 ====================

    def sync_all(self, start_date: str, end_date: str, stock_codes: List[str] = None) -> Dict[str, int]:
        """
        全量数据同步

        Args:
            start_date: 开始日期
            end_date: 结束日期
            stock_codes: 股票代码列表 (可选)

        Returns:
            各类型同步记录数
        """
        results = {}

        logger.info("Starting full data sync...")

        # 1. 同步交易日历
        logger.info("Syncing trading calendar...")
        results['trading_calendar'] = self.sync_trading_calendar(start_date, end_date)

        # 2. 同步股票基础信息
        logger.info("Syncing stock basic info...")
        results['stock_basic'] = self.sync_stock_basic()

        # 3. 同步股票日线行情
        if stock_codes is None:
            # 获取所有股票代码
            db = SessionLocal()
            stocks = db.query(StockBasic).filter(StockBasic.status == 'L').all()
            stock_codes = [s.ts_code for s in stocks]
            db.close()

        logger.info(f"Syncing daily data for {len(stock_codes)} stocks...")
        results['stock_daily'] = self.sync_stock_daily_batch(stock_codes, start_date, end_date)

        # 4. 同步主要指数
        index_codes = ['000300.SH', '000905.SH', '000852.SH', '000001.SH', '399001.SZ', '399006.SZ']
        results['index_daily'] = 0
        for index_code in index_codes:
            count = self.sync_index_daily(index_code, start_date, end_date)
            results['index_daily'] += count

        logger.info(f"Full data sync completed: {results}")
        return results


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据同步服务")
    parser.add_argument("--start-date", required=True, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--tushare-token", help="Tushare Token")
    parser.add_argument("--primary-source", default="akshare", choices=["tushare", "akshare"], help="主数据源")
    parser.add_argument("--sync-type", default="all", choices=["all", "calendar", "basic", "daily", "index"], help="同步类型")

    args = parser.parse_args()

    # 创建同步服务
    service = DataSyncService(
        primary_source=args.primary_source,
        tushare_token=args.tushare_token
    )

    # 执行同步
    if args.sync_type == "all":
        results = service.sync_all(args.start_date, args.end_date)
    elif args.sync_type == "calendar":
        results = {"trading_calendar": service.sync_trading_calendar(args.start_date, args.end_date)}
    elif args.sync_type == "basic":
        results = {"stock_basic": service.sync_stock_basic()}
    elif args.sync_type == "daily":
        results = {"stock_daily": service.sync_stock_daily_batch([], args.start_date, args.end_date)}
    elif args.sync_type == "index":
        results = {"index_daily": sum(
            service.sync_index_daily(code, args.start_date, args.end_date)
            for code in ['000300.SH', '000905.SH', '000852.SH']
        )}

    print("\n同步结果:")
    for key, value in results.items():
        print(f"  {key}: {value} 条记录")


if __name__ == "__main__":
    main()
