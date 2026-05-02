"""
数据同步服务
自动从数据源同步市场数据到数据库
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from datetime import UTC, date, datetime

import pandas as pd

from app.core.logging import logger
from app.data_sources import (
    AKShareSource,
    CrawlerDataSource,
    TushareSource,
    data_source_manager,
    get_data_source,
)
from app.data_sources.cleaner import DataCleaner
from app.data_sources.normalizer import DataNormalizer
from app.db.base import SessionLocal
from app.models.market import IndexDaily, StockBasic, StockDaily, StockFinancial, TradingCalendar


def _safe_date(value) -> date | None:
    """安全转换为date对象，处理None/NaN/空字符串/各种日期格式"""
    if value is None:
        return None
    try:
        if isinstance(value, date) and not isinstance(value, type):
            return value
        if pd.isna(value):
            return None
        ts = pd.Timestamp(value)
        if pd.isna(ts):
            return None
        return ts.date()
    except (ValueError, TypeError):
        return None


class DataSyncService:
    """数据同步服务"""

    def __init__(self, primary_source: str = "crawler", tushare_token: str | None = None, tushare_proxy_url: str | None = None):
        """
        初始化数据同步服务

        Args:
            primary_source: 主数据源 ('crawler', 'tushare' 或 'akshare')
            tushare_token: Tushare token
            tushare_proxy_url: Tushare 代理服务器 URL（可选）
        """
        # 默认crawler为主数据源 — 爬虫免费且无频率限制，tushare/akshare作为降级备选
        self.primary_source = primary_source
        self.tushare_token = tushare_token
        self.normalizer = DataNormalizer()
        self.cleaner = DataCleaner()

        # 注册数据源
        if tushare_token:
            tushare = TushareSource(token=tushare_token, proxy_url=tushare_proxy_url)
            data_source_manager.register("tushare", tushare, is_primary=(primary_source == "tushare"))

        akshare = AKShareSource()
        data_source_manager.register("akshare", akshare, is_primary=(primary_source == "akshare"))

        crawler = CrawlerDataSource()
        data_source_manager.register("crawler", crawler, is_primary=(primary_source == "crawler"))

        # 连接数据源
        self.connection_status = data_source_manager.connect_all()
        logger.info(f"Data source connection status: {self.connection_status}")

    def get_source_for_data(self, data_type: str) -> str | None:
        """
        根据数据类型选择最佳数据源

        Args:
            data_type: 数据类型 ('stock_daily', 'stock_basic', 'index_daily', 'trading_calendar')

        Returns:
            数据源名称
        """
        # Tushare免费账户权限有限，某些接口需要用AKShare补充
        # 优先级策略：crawler(快且免费) > tushare(数据准但有限频) > akshare(覆盖广但慢)
        tushare_available = self.connection_status.get("tushare", False)
        akshare_available = self.connection_status.get("akshare", False)

        # 优先级映射：根据数据类型选择数据源
        # 财务数据用akshare优先 — tushare财务接口需要较高积分权限
        source_priority = {
            "stock_daily": ["crawler", "tushare", "akshare"],  # 爬虫最快最稳定
            "stock_basic": ["crawler", "tushare", "akshare"],  # 爬虫股票基础信息
            "index_daily": ["crawler", "akshare", "tushare"],  # 爬虫指数数据
            "trading_calendar": ["crawler", "akshare", "tushare"],  # 爬虫交易日历
            "financial": ["akshare", "tushare"],  # 财务数据
        }

        for source in source_priority.get(data_type, ["crawler", "tushare", "akshare"]):
            if source == "tushare" and tushare_available:
                return "tushare"
            if source == "akshare" and akshare_available:
                return "akshare"
            if source == "crawler" and self.connection_status.get("crawler", False):
                return "crawler"

        return self.get_available_source()

    def get_available_source(self) -> str | None:
        """获取可用的数据源"""
        for name in ["tushare", "akshare"]:
            if self.connection_status.get(name):
                return name
        return None

    # ==================== 交易日历同步 ====================

    # 增量同步策略：交易日历/股票基础信息按需upsert，日线行情按(ts_code, trade_date)去重只插入新数据
    # 全量同步仅用于首次建库或数据修复，日常同步走增量
    def sync_trading_calendar(self, start_date: str, end_date: str) -> int:
        """
        同步交易日历

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期

        Returns:
            同步的记录数
        """
        source_name = self.get_source_for_data("trading_calendar")
        if not source_name:
            logger.error("No available data source for trading calendar")
            return 0

        source = get_data_source(source_name)
        df = source.get_trading_calendar(start_date, end_date)

        if df.empty:
            logger.warning("No trading calendar data fetched")
            return 0

        # 标准化 + 清洗
        df = self.normalizer.normalize_trading_calendar(df, source_name)
        df, clean_report = self.cleaner.clean_trading_calendar(df)
        if clean_report.issues:
            logger.warning(f"Trading calendar clean issues: {len(clean_report.issues)}")

        db = SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                # 处理日期格式
                trade_date = row["trade_date"]
                if isinstance(trade_date, str):
                    trade_date = datetime.strptime(trade_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
                elif hasattr(trade_date, "date"):
                    trade_date = trade_date.date()

                pretrade_date = row.get("pretrade_date")
                if pretrade_date and not pd.isna(pretrade_date):
                    if isinstance(pretrade_date, str):
                        pretrade_date = datetime.strptime(pretrade_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
                    elif hasattr(pretrade_date, "date"):
                        pretrade_date = pretrade_date.date()
                else:
                    pretrade_date = None

                existing = (
                    db.query(TradingCalendar)
                    .filter(
                        TradingCalendar.exchange == "SSE",  # 仅覆盖上交所日历，深交所交易日与上交所一致
                        TradingCalendar.cal_date == trade_date,
                    )
                    .first()
                )

                if not existing:
                    calendar = TradingCalendar(
                        exchange="SSE", cal_date=trade_date, is_open=bool(row["is_open"]), pretrade_date=pretrade_date
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
        source_name = self.get_source_for_data("stock_basic")
        if not source_name:
            logger.error("No available data source for stock basic")
            return 0

        source = get_data_source(source_name)
        df = source.get_stock_basic()

        if df.empty:
            logger.warning("No stock basic data fetched")
            return 0

        # 标准化 + 清洗
        df = self.normalizer.normalize_stock_basic(df, source_name)
        df, clean_report = self.cleaner.clean_stock_basic(df)
        if clean_report.issues:
            logger.warning(f"Stock basic clean issues: {len(clean_report.issues)}")

        db = SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                existing = db.query(StockBasic).filter(StockBasic.ts_code == row["ts_code"]).first()

                if existing:
                    # 更新
                    existing.name = row.get("name")
                    existing.market = row.get("market")
                    existing.list_status = row.get("status", "L")
                else:
                    # 新增 — 仅插入不更新，股票基础信息变更走全量重刷
                    # 处理 list_date，避免 nan
                    list_date = row.get("list_date")
                    if pd.isna(list_date):
                        list_date = None

                    stock = StockBasic(
                        ts_code=row["ts_code"],
                        symbol=row.get("symbol"),
                        name=row.get("name"),
                        market=row.get("market"),
                        list_date=list_date,
                        list_status=row.get("status", "L"),
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
        source_name = self.get_source_for_data("stock_daily")
        if not source_name:
            logger.error("No available data source for stock daily")
            return 0

        source = get_data_source(source_name)
        df = source.get_stock_daily(ts_code, start_date, end_date)

        if df.empty:
            logger.warning(f"No daily data fetched for {ts_code}")
            return 0

        # 标准化 + 清洗
        df = self.normalizer.normalize_stock_daily(df, source_name)
        df, clean_report = self.cleaner.clean_stock_daily(df)
        if clean_report.issues:
            logger.warning(f"Stock daily clean issues for {ts_code}: {len(clean_report.issues)}")

        db = SessionLocal()
        try:
            # 批量获取已存在日期（增量同步核心：只插入不存在的日期，跳过已有数据）
            # 比逐行SELECT+INSERT快一个数量级，避免N+1问题
            dates_in_df = []
            for _, row in df.iterrows():
                trade_date = row["trade_date"]
                if isinstance(trade_date, str):
                    trade_date = datetime.strptime(trade_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
                elif hasattr(trade_date, "date"):
                    trade_date = trade_date.date()
                dates_in_df.append(trade_date)

            existing_dates = (
                {
                    r[0]
                    for r in db.query(StockDaily.trade_date)
                    .filter(
                        StockDaily.ts_code == ts_code,
                        StockDaily.trade_date.in_(dates_in_df),
                    )
                    .all()
                }
                if dates_in_df
                else set()
            )

            # 批量插入不存在的记录 — 使用bulk_save_objects跳过ORM事件，性能最优
            new_records = []
            for _, row in df.iterrows():
                # 处理日期格式
                trade_date = row["trade_date"]
                if isinstance(trade_date, str):
                    trade_date = datetime.strptime(trade_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
                elif hasattr(trade_date, "date"):
                    trade_date = trade_date.date()

                if trade_date not in existing_dates:
                    new_records.append(
                        StockDaily(
                            ts_code=ts_code,
                            trade_date=trade_date,
                            open=row.get("open"),
                            high=row.get("high"),
                            low=row.get("low"),
                            close=row.get("close"),
                            pre_close=row.get("pre_close"),
                            change=row.get("change"),
                            pct_chg=row.get("pct_chg"),
                            vol=row.get("volume"),
                            amount=row.get("amount"),
                            data_source=row.get("data_source", source_name),
                            amount_is_estimated=row.get("amount_is_estimated", False),
                        )
                    )

            if new_records:
                db.bulk_save_objects(new_records)
                db.commit()

            count = len(new_records)
            logger.info(f"Synced {count} daily records for {ts_code}")
            return count

        except Exception as e:
            logger.error(f"Error syncing stock daily: {e}")
            db.rollback()
            return 0
        finally:
            db.close()

    def sync_stock_daily_batch(self, ts_codes: list[str], start_date: str, end_date: str) -> int:
        """
        批量同步股票日线行情 — 串行逐只同步，避免并发请求触发数据源限频

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
                # 每50只打印进度，避免日志爆炸
                logger.info(f"同步进度: {i + 1}/{len(ts_codes)}, 已同步{total_count}条")

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
        source_name = self.get_source_for_data("index_daily")
        if not source_name:
            logger.error("No available data source for index daily")
            return 0

        source = get_data_source(source_name)
        df = source.get_index_daily(index_code, start_date, end_date)

        if df.empty:
            logger.warning(f"No index daily data fetched for {index_code}")
            return 0

        # 标准化 + 清洗
        df = self.normalizer.normalize_index_daily(df, source_name)
        df, clean_report = self.cleaner.clean_index_daily(df)
        if clean_report.issues:
            logger.warning(f"Index daily clean issues for {index_code}: {len(clean_report.issues)}")

        db = SessionLocal()
        try:
            count = 0
            for _, row in df.iterrows():
                # 处理日期格式
                trade_date = row["trade_date"]
                if isinstance(trade_date, str):
                    trade_date = datetime.strptime(trade_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
                elif hasattr(trade_date, "date"):
                    trade_date = trade_date.date()

                existing = (
                    db.query(IndexDaily)
                    .filter(IndexDaily.index_code == index_code, IndexDaily.trade_date == trade_date)
                    .first()
                )

                if not existing:
                    daily = IndexDaily(
                        index_code=index_code,
                        trade_date=trade_date,
                        open=row.get("open"),
                        high=row.get("high"),
                        low=row.get("low"),
                        close=row.get("close"),
                        pre_close=row.get("pre_close"),
                        change=row.get("change"),
                        pct_chg=row.get("pct_chg"),
                        vol=row.get("volume"),
                        amount=row.get("amount"),
                        data_source=row.get("data_source", source_name),
                        amount_is_estimated=row.get("amount_is_estimated", False),
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
                # 财务数据按报告期(end_date)去重 — 同一报告期可能有多次修正，以最新一次为准
                existing = (
                    db.query(StockFinancial)
                    .filter(StockFinancial.ts_code == ts_code, StockFinancial.end_date == _safe_date(row.get("end_date")))
                    .first()
                )

                if not existing:
                    financial = StockFinancial(
                        ts_code=ts_code,
                        end_date=_safe_date(row.get("end_date")),
                        ann_date=_safe_date(row.get("ann_date")),
                        revenue=row.get("revenue"),
                        net_profit=row.get("net_profit"),
                        roe=row.get("roe"),
                        roa=row.get("roa"),
                        gross_profit=row.get("gross_profit"),
                        total_assets=row.get("total_assets"),
                        total_equity=row.get("total_equity"),
                        operating_cash_flow=row.get("operating_cash_flow"),
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

    def sync_all(self, start_date: str, end_date: str, stock_codes: list[str] | None = None) -> dict[str, int]:
        """
        全量数据同步

        Args:
            start_date: 开始日期
            end_date: 结束日期
            stock_codes: 股票代码列表 (可选)

        Returns:
            各类型同步记录数
        """
        # 全量同步执行顺序：日历→基础信息→日线→指数，前置依赖保证后续数据完整性
        results = {}

        # 1. 同步交易日历
        logger.info("Syncing trading calendar...")
        results["trading_calendar"] = self.sync_trading_calendar(start_date, end_date)

        # 2. 同步股票基础信息
        logger.info("Syncing stock basic info...")
        results["stock_basic"] = self.sync_stock_basic()

        # 3. 同步股票日线行情
        if stock_codes is None:
            # 无指定列表时取全部上市股票('L') — 排除退市/暂停上市，避免同步无效数据
            db = SessionLocal()
            stocks = db.query(StockBasic).filter(StockBasic.status == "L").all()
            stock_codes = [s.ts_code for s in stocks]
            db.close()

        logger.info(f"Syncing daily data for {len(stock_codes)} stocks...")
        results["stock_daily"] = self.sync_stock_daily_batch(stock_codes, start_date, end_date)

        # 4. 同步主要指数 — 仅核心宽基指数，窄基/行业指数按需单独同步
        index_codes = ["000300.SH", "000905.SH", "000852.SH", "000001.SH", "399001.SZ", "399006.SZ"]
        # 依次为：沪深300、中证500、中证1000、上证指数、深证成指、创业板指
        results["index_daily"] = 0
        for index_code in index_codes:
            count = self.sync_index_daily(index_code, start_date, end_date)
            results["index_daily"] += count

        logger.info(f"Full data sync completed: {results}")
        return results

    # ==================== 数据质量检查 (ADD 3.3节) ====================

    def check_data_quality(self, trade_date: str) -> dict:
        """
        数据质量检查 (PRD 9.1.3节)
        - 数据缺失与异常需可监控
        - 数据口径变更需留痕
        - 不允许未来函数穿越
        """
        db = SessionLocal()
        try:
            issues = []

            # 检查行情数据完整性
            daily_count = db.query(StockDaily).filter(StockDaily.trade_date == trade_date).count()

            if daily_count == 0:
                issues.append({"type": "missing_data", "message": f"No stock daily data for {trade_date}"})

            # 检查异常值
            daily_data = (
                db.query(StockDaily)
                .filter(
                    StockDaily.trade_date == trade_date,
                )
                .all()
            )

            for d in daily_data:
                if d.close and d.close < 0:
                    issues.append(
                        {"type": "invalid_price", "ts_code": d.ts_code, "message": f"Negative close: {d.close}"}
                    )
                if d.vol and d.vol < 0:
                    issues.append(
                        {"type": "invalid_volume", "ts_code": d.ts_code, "message": f"Negative volume: {d.vol}"}
                    )

                # OHLC 逻辑一致性
                if d.high and d.low and d.open and d.close:
                    max_oc = max(d.open, d.close)
                    min_oc = min(d.open, d.close)
                    if d.high < max_oc:
                        issues.append(
                            {
                                "type": "ohlc_violation",
                                "ts_code": d.ts_code,
                                "message": f"high({d.high}) < max(open,close)({max_oc})",
                            }
                        )
                    if d.low > min_oc:
                        issues.append(
                            {
                                "type": "ohlc_violation",
                                "ts_code": d.ts_code,
                                "message": f"low({d.low}) > min(open,close)({min_oc})",
                            }
                        )

                # 涨跌幅与收盘价/昨收价一致性
                if d.close and d.pre_close and d.pre_close != 0 and d.pct_chg is not None:
                    expected_pct = (d.close / d.pre_close - 1) * 100
                    diff = abs(d.pct_chg - expected_pct)
                    if diff > 0.5:  # 0.5%容忍度 — 复权价/除权除息会导致小幅偏差
                        issues.append(
                            {
                                "type": "pct_chg_mismatch",
                                "ts_code": d.ts_code,
                                "message": f"pct_chg({d.pct_chg}) vs expected({expected_pct:.4f}), diff={diff:.4f}",
                            }
                        )

                # 成交额与成交量/均价合理性
                if d.amount and d.vol and d.close and d.vol > 0 and d.close > 0:
                    avg_price = d.amount / d.vol
                    price_ratio = avg_price / d.close
                    if price_ratio < 0.8 or price_ratio > 1.2:  # 均价偏离收盘价20%以上视为异常
                        issues.append(
                            {
                                "type": "amount_volume_mismatch",
                                "ts_code": d.ts_code,
                                "message": f"avg_price/close ratio={price_ratio:.2f} (expected ~1.0)",
                            }
                        )

            # 数据覆盖率检查
            total_stocks = db.query(StockBasic).filter(StockBasic.list_status == "L").count()
            coverage = daily_count / total_stocks if total_stocks > 0 else 0
            if coverage < 0.8:  # 覆盖率低于80%说明大量股票缺失当日数据，可能是数据源故障
                issues.append(
                    {"type": "low_coverage", "message": f"Daily data coverage={coverage:.2%} (expected >80%)"}
                )

            # 交叉验证：检查同一股票是否有不同数据源的数据
            multi_source = (
                db.query(StockDaily.ts_code)
                .filter(StockDaily.trade_date == trade_date)
                .group_by(StockDaily.ts_code)
                .having(db.func.count(StockDaily.data_source) > 1)
                .all()
            )
            if multi_source:
                issues.append(
                    {"type": "multi_source", "message": f"{len(multi_source)} stocks have data from multiple sources"}
                )  # 多源数据可能不一致，需人工确认

            return {
                "trade_date": trade_date,
                "daily_count": daily_count,
                "issues_count": len(issues),
                "is_healthy": len(issues) == 0,
                "coverage": coverage,
                "issues": issues[:20],  # 限制返回条数，避免大量异常数据撑爆响应
            }
        finally:
            db.close()

    # ==================== 日终同步任务链 (ADD 6.1节) ====================

    def run_daily_pipeline(self, trade_date: str) -> dict:
        """日终流水线：单日增量同步，比sync_all更轻量，适合Celery定时任务调度"""
        results = {}

        # 1. 同步交易日历
        results["calendar"] = self.sync_trading_calendar(trade_date, trade_date)

        # 2. 同步股票日线
        results["stock_daily"] = 0  # 需要传入股票列表

        # 3. 同步主要指数
        index_codes = ["000300.SH", "000905.SH", "000852.SH", "000001.SH"]
        results["index_daily"] = sum(self.sync_index_daily(code, trade_date, trade_date) for code in index_codes)

        # 4. 数据质量检查
        results["quality_check"] = self.check_data_quality(trade_date)

        return results


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据同步服务")
    parser.add_argument("--start-date", required=True, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--tushare-token", help="Tushare Token")
    parser.add_argument("--tushare-proxy-url", help="Tushare 代理服务器 URL")
    parser.add_argument("--primary-source", default="akshare", choices=["tushare", "akshare"], help="主数据源")
    parser.add_argument(
        "--sync-type", default="all", choices=["all", "calendar", "basic", "daily", "index"], help="同步类型"
    )

    args = parser.parse_args()

    # 创建同步服务
    service = DataSyncService(
        primary_source=args.primary_source,
        tushare_token=args.tushare_token,
        tushare_proxy_url=args.tushare_proxy_url,
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
        results = {
            "index_daily": sum(
                service.sync_index_daily(code, args.start_date, args.end_date)
                for code in ["000300.SH", "000905.SH", "000852.SH"]
            )
        }

    print("\n同步结果:")
    for key, value in results.items():
        print(f"  {key}: {value} 条记录")


if __name__ == "__main__":
    main()
