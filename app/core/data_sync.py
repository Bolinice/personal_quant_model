"""
高并发Tushare数据同步器
使用 ThreadPoolExecutor 并发从Tushare代理API获取数据并批量写入PostgreSQL

同步策略:
- Phase 1 基础数据串行执行（数据量小，后续Phase依赖这些表）
- Phase 2/3 批量数据按股票/日期并发（数据量大，IO密集，并发可大幅提速）
- 已有数据的股票只增量同步最近30天，缺失的股票做全量同步
- 每个worker持有独立DB session，避免多线程共享session的并发问题
"""

import time
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.core.config import settings
from app.data_sources.tushare_source import TushareDataSource
from app.db.base import SessionLocal

logger = logging.getLogger(__name__)


def safe_float(val):
    """安全转换为float — Tushare返回的数值可能含NaN/Inf/None，
    直接写入PostgreSQL的float列会报错，必须过滤为None"""
    try:
        if pd.isna(val):
            return None
        v = float(val)
        # np.inf/-inf出现在除零场景(如PE=价格/零eps)，PostgreSQL不接受Inf
        return v if np.isfinite(v) else None
    except (ValueError, TypeError):
        return None


class ConcurrentDataSyncer:
    """高并发Tushare数据同步器

    使用 Tushare 代理API (全接口权限) + ThreadPoolExecutor 并发写入
    """

    def __init__(
        self,
        token: Optional[str] = None,
        max_workers: int = 8,
        rate_limit: float = 0.35,  # Tushare代理API限流：每分钟约200次，0.35s间隔≈170次/分，留余量
    ):
        self.token = token or settings.TUSHARE_TOKEN
        self.max_workers = max_workers
        self.rate_limit = rate_limit

        self.source = TushareDataSource(self.token)
        self._connected = False

    def connect(self) -> bool:
        """连接Tushare"""
        self._connected = self.source.connect()
        return self._connected

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    def sync_all(
        self,
        trade_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        并发同步所有数据到数据库

        Args:
            trade_date: 当日交易日期 YYYYMMDD (用于当日快照)
            start_date: 历史数据起始日期 YYYYMMDD
            end_date: 历史数据结束日期 YYYYMMDD
        """
        if not self._connected:
            if not self.connect():
                logger.error("Tushare连接失败!")
                return {}

        now = datetime.now()
        if trade_date is None:
            trade_date = now.strftime("%Y%m%d")
        if start_date is None:
            start_date = (now - timedelta(days=365)).strftime("%Y%m%d")
        if end_date is None:
            end_date = trade_date

        logger.info("========== 开始全量数据同步 ==========")
        logger.info("  trade_date=%s, range=%s~%s", trade_date, start_date, end_date)

        results: Dict[str, int] = {}
        t0 = time.time()

        # Phase 1: 基础数据（串行，数据量小，后续Phase依赖这些数据）
        # stock_basic必须在最前面，后续Phase的_get_all_ts_codes()依赖它
        results["stock_basic"] = self._sync_stock_basic()
        results["trading_calendar"] = self._sync_trading_calendar(start_date, end_date)
        results["index_daily"] = self._sync_index_daily(start_date, end_date)
        results["index_components"] = self._sync_index_components(end_date)

        # Phase 2: 高并发批量数据（IO密集，适合线程池并发）
        # stock_daily/daily_basic数据量大，是同步耗时主力
        results["stock_daily"] = self._sync_stock_daily(start_date, end_date)
        results["daily_basic"] = self._sync_daily_basic(start_date, end_date)
        results["stock_financial"] = self._sync_stock_financial()

        # Phase 3: 资金流数据
        results["northbound"] = self._sync_northbound(start_date, end_date)
        results["money_flow"] = self._sync_money_flow(start_date, end_date)
        results["margin"] = self._sync_margin(start_date, end_date)

        elapsed = time.time() - t0
        total = sum(results.values())
        logger.info("========== 同步完成，共写入 %d 行，耗时 %.1fs ==========", total, elapsed)
        for k, v in results.items():
            logger.info("  %s: %d", k, v)

        return results

    # ------------------------------------------------------------------
    # Phase 1: 基础数据
    # ------------------------------------------------------------------

    def _sync_stock_basic(self) -> int:
        """同步全A股基础信息 (增量：新增+更新变更，不做全量删除重建)"""
        logger.info("[stock_basic] 开始同步...")
        from app.models.market import StockBasic

        db = SessionLocal()
        try:
            df = self.source.get_stock_basic()
            if df is None or df.empty:
                return 0

            # 查询所有已有记录 (不仅仅是ts_code, 还需要完整对象用于更新)
            existing_map: Dict[str, StockBasic] = {
                r.ts_code: r
                for r in db.query(StockBasic).all()
            }

            new_count = 0
            updated_count = 0

            for _, row in df.iterrows():
                ts_code = row.get("ts_code", "")
                if not ts_code:
                    continue

                # 提取API返回的字段值
                new_name = row.get("name", "")
                new_industry = row.get("industry", "")
                new_market = row.get("market", "")
                new_list_status = row.get("status", "L")

                if ts_code not in existing_map:
                    # 新增股票
                    db.add(StockBasic(
                        ts_code=ts_code,
                        symbol=row.get("symbol", ""),
                        name=new_name,
                        area=row.get("area", ""),
                        industry=new_industry,
                        market=new_market,
                        list_status=new_list_status,
                    ))
                    new_count += 1
                else:
                    # 已有股票: 检查关键字段是否有变更, 有则更新
                    # 股票更名/行业变更/退市(list_status变化)是常见场景，需及时同步
                    existing = existing_map[ts_code]
                    changed = False

                    if new_name and existing.name != new_name:
                        existing.name = new_name
                        changed = True
                    if new_industry and existing.industry != new_industry:
                        existing.industry = new_industry
                        changed = True
                    if new_market and existing.market != new_market:
                        existing.market = new_market
                        changed = True
                    if new_list_status and existing.list_status != new_list_status:
                        existing.list_status = new_list_status
                        changed = True

                    if changed:
                        updated_count += 1

            db.commit()

            logger.info(
                "[stock_basic] 新增 %d / 更新 %d / 已有 %d",
                new_count, updated_count, len(existing_map) - new_count - updated_count,
            )
            return new_count + updated_count
        except Exception as e:
            db.rollback()
            logger.error("[stock_basic] 失败: %s", e)
            return 0
        finally:
            db.close()

    def _sync_trading_calendar(self, start_date: str, end_date: str) -> int:
        """同步交易日历"""
        logger.info("[trading_calendar] 开始同步...")
        from app.models.market import TradingCalendar

        db = SessionLocal()
        try:
            df = self.source.get_trading_calendar(
                self._fmt(start_date), self._fmt(end_date)
            )
            if df is None or df.empty:
                return 0

            existing = set(
                r[0]
                for r in db.query(TradingCalendar.cal_date)
                .filter(TradingCalendar.exchange == "SSE")
                .all()
            )

            new_records = []
            for _, row in df.iterrows():
                td = pd.Timestamp(row.get("trade_date", ""))
                if not td or td.date() in existing:
                    continue
                new_records.append(
                    TradingCalendar(
                        exchange="SSE",
                        cal_date=td.date(),
                        is_open=bool(row.get("is_open", 1)),
                    )
                )

            if new_records:
                db.bulk_save_objects(new_records)
                db.commit()

            logger.info("[trading_calendar] 新增 %d", len(new_records))
            return len(new_records)
        except Exception as e:
            db.rollback()
            logger.error("[trading_calendar] 失败: %s", e)
            return 0
        finally:
            db.close()

    def _sync_index_daily(self, start_date: str, end_date: str) -> int:
        """同步主要指数日线"""
        logger.info("[index_daily] 开始同步...")
        from app.models.market import IndexDaily

        indices = [
            "000001.SH", "399001.SZ", "000300.SH",
            "000905.SH", "000852.SH",
        ]  # 上证/深证/沪深300/中证500/中证1000 — 覆盖主要宽基指数，择时和benchmark依赖
        total = 0
        db = SessionLocal()
        try:
            for index_code in indices:
                try:
                    df = self.source.get_index_daily(
                        index_code, start_date, end_date
                    )
                    if df is None or df.empty:
                        continue

                    existing = set(
                        r[0]
                        for r in db.query(IndexDaily.trade_date)
                        .filter(IndexDaily.index_code == index_code)
                        .all()
                    )

                    new_records = []
                    for _, row in df.iterrows():
                        td = pd.Timestamp(row.get("trade_date", ""))
                        if not td or td.date() in existing:
                            continue
                        new_records.append(
                            IndexDaily(
                                index_code=index_code,
                                trade_date=td.date(),
                                open=safe_float(row.get("open")),
                                high=safe_float(row.get("high")),
                                low=safe_float(row.get("low")),
                                close=safe_float(row.get("close")),
                                pre_close=safe_float(row.get("pre_close", 0)),
                                pct_chg=safe_float(row.get("pct_chg", 0)),
                                vol=safe_float(row.get("volume", 0)),
                                amount=safe_float(row.get("amount", 0)),
                                data_source="tushare",
                            )
                        )

                    if new_records:
                        db.bulk_save_objects(new_records)
                        db.commit()
                        total += len(new_records)

                    time.sleep(self.rate_limit)
                except Exception as e:
                    logger.warning("[index_daily] %s 失败: %s", index_code, e)
                    db.rollback()
        finally:
            db.close()

        logger.info("[index_daily] 新增 %d", total)
        return total

    def _sync_index_components(self, end_date: str) -> int:
        """同步指数成分股"""
        logger.info("[index_components] 开始同步...")
        from app.models.market import IndexComponent

        indices = ["000300.SH", "000905.SH", "000852.SH"]  # 只同步选股池相关的宽基指数成分，非全量指数
        total = 0
        db = SessionLocal()
        try:
            for index_code in indices:
                try:
                    codes = self.source.get_index_components(index_code, end_date)
                    if not codes:
                        continue

                    existing = set(
                        r[0]
                        for r in db.query(IndexComponent.ts_code)
                        .filter(IndexComponent.index_code == index_code)
                        .all()
                    )

                    new_records = []
                    td = pd.Timestamp(end_date).date() if len(end_date) == 8 else date.today()
                    for ts_code in codes:
                        if ts_code in existing:
                            continue
                        new_records.append(
                            IndexComponent(
                                index_code=index_code,
                                trade_date=td,
                                ts_code=ts_code,
                            )
                        )

                    if new_records:
                        db.bulk_save_objects(new_records)
                        db.commit()
                        total += len(new_records)

                    time.sleep(self.rate_limit)
                except Exception as e:
                    logger.warning("[index_components] %s 失败: %s", index_code, e)
                    db.rollback()
        finally:
            db.close()

        logger.info("[index_components] 新增 %d", total)
        return total

    # ------------------------------------------------------------------
    # Phase 2: 高并发批量数据
    # ------------------------------------------------------------------

    def _sync_stock_daily(self, start_date: str, end_date: str) -> int:
        """按股票并发同步全A股日线"""
        logger.info("[stock_daily] 开始并发同步...")
        from app.models.market import StockDaily

        ts_codes = self._get_all_ts_codes()
        if not ts_codes:
            return 0

        # 获取已有记录（按股票代码）
        db = SessionLocal()
        existing_codes = set(
            r[0]
            for r in db.execute(
                text("SELECT DISTINCT ts_code FROM stock_daily")
            ).fetchall()
        )
        db.close()

        # 优先同步还没有数据的股票（全量拉取）
        missing = [c for c in ts_codes if c not in existing_codes]
        # 已有数据的股票只同步增量（最近30天），避免重复拉取历史数据
        # 30天窗口覆盖最长节假日(春节7天+缓冲)，确保不遗漏交易日
        recent_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        logger.info(
            "[stock_daily] 全量:%d 增量:%d", len(missing), len(existing_codes)
        )

        total = 0
        completed = 0
        t0 = time.time()

        def fetch_one(ts_code: str, sd: str, ed: str) -> int:
            # 每个线程独立DB session，避免SQLAlchemy session跨线程共享问题
            db2 = SessionLocal()
            try:
                df = self.source.get_stock_daily(ts_code, sd, ed)
                if df is None or df.empty:
                    return 0

                # 批量检查已有日期
                dates_in_df = [pd.Timestamp(r).date() for r in df["trade_date"]]
                existing_dates = set(
                    r[0]
                    for r in db2.query(StockDaily.trade_date)
                    .filter(StockDaily.ts_code == ts_code)
                    .all()
                )

                new_records = []
                for _, row in df.iterrows():
                    td = pd.Timestamp(row.get("trade_date", "")).date()
                    if td in existing_dates:
                        continue
                    new_records.append(
                        StockDaily(
                            ts_code=ts_code,
                            trade_date=td,
                            open=safe_float(row.get("open")),
                            high=safe_float(row.get("high")),
                            low=safe_float(row.get("low")),
                            close=safe_float(row.get("close")),
                            pre_close=safe_float(row.get("pre_close", 0)),
                            pct_chg=safe_float(row.get("pct_chg", 0)),
                            vol=safe_float(row.get("volume", 0)),
                            amount=safe_float(row.get("amount", 0)),
                            data_source="tushare",
                        )
                    )

                if new_records:
                    db2.bulk_save_objects(new_records)
                    db2.commit()
                return len(new_records)
            except Exception:
                db2.rollback()
                return -1
            finally:
                db2.close()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            # 全量同步（缺失的股票）
            for ts_code in missing:
                future = executor.submit(
                    fetch_one, ts_code, start_date, end_date
                )
                futures[future] = ts_code
                time.sleep(self.rate_limit)

            # 增量同步（已有数据的股票）
            for ts_code in existing_codes.intersection(set(ts_codes)):
                future = executor.submit(
                    fetch_one, ts_code, recent_start, end_date
                )
                futures[future] = ts_code
                time.sleep(self.rate_limit * 0.5)

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
                    rate = completed / elapsed if elapsed > 0 else 0
                    logger.info(
                        "[stock_daily] 进度:%d/%d 新增:%d 速度:%.1f/s",
                        completed, len(futures), total, rate,
                    )

        logger.info("[stock_daily] 完成，新增 %d 行", total)
        return total

    def _sync_daily_basic(self, start_date: str, end_date: str) -> int:
        """按交易日并发同步全市场每日指标"""
        logger.info("[daily_basic] 开始并发同步...")
        from app.models.market import StockDailyBasic

        # 获取交易日历
        trade_dates = self._get_trade_dates(start_date, end_date)
        if not trade_dates:
            return 0

        # 获取已有日期
        db = SessionLocal()
        existing_dates = set(
            r[0]
            for r in db.execute(
                text("SELECT DISTINCT trade_date FROM stock_daily_basic")
            ).fetchall()
        )
        db.close()

        missing_dates = [d for d in trade_dates if d not in existing_dates]
        logger.info(
            "[daily_basic] 需同步 %d 个交易日 (已有 %d)",
            len(missing_dates), len(existing_dates),
        )

        total = 0

        def fetch_one(td: str) -> int:
            db2 = SessionLocal()
            try:
                df = self.source.get_daily_basic(trade_date=td)
                if df is None or df.empty:
                    return 0

                new_records = []
                for _, row in df.iterrows():
                    ts_code = row.get("ts_code", "")
                    if not ts_code:
                        continue
                    new_records.append(
                        StockDailyBasic(
                            ts_code=ts_code,
                            trade_date=td,
                            close=safe_float(row.get("close")),
                            turnover_rate=safe_float(row.get("turnover_rate")),
                            turnover_rate_f=safe_float(row.get("turnover_rate_f")),
                            volume_ratio=safe_float(row.get("volume_ratio")),
                            pe=safe_float(row.get("pe")),
                            pe_ttm=safe_float(row.get("pe_ttm")),
                            pb=safe_float(row.get("pb")),
                            ps=safe_float(row.get("ps")),
                            ps_ttm=safe_float(row.get("ps_ttm")),
                            dv_ratio=safe_float(row.get("dv_ratio")),
                            dv_ttm=safe_float(row.get("dv_ttm")),
                            total_mv=safe_float(row.get("total_mv")),
                            circ_mv=safe_float(row.get("circ_mv")),
                        )
                    )

                if new_records:
                    db2.bulk_save_objects(new_records)
                    db2.commit()
                return len(new_records)
            except Exception:
                db2.rollback()
                return 0
            finally:
                db2.close()

        # daily_basic按交易日拉全市场快照，单次数据量大(~4000行/天)，
        # 并发数限制为4，避免同时写入过多导致DB锁竞争
        with ThreadPoolExecutor(max_workers=min(self.max_workers, 4)) as executor:
            futures = {}
            for td in missing_dates:
                future = executor.submit(fetch_one, td)
                futures[future] = td
                time.sleep(self.rate_limit)

            for future in as_completed(futures):
                try:
                    total += future.result()
                except Exception:
                    pass

        logger.info("[daily_basic] 完成，新增 %d 行", total)
        return total

    def _sync_stock_financial(self) -> int:
        """按股票并发同步财务数据 — 财务数据按报告期去重，同股票不同报告期独立写入"""
        logger.info("[stock_financial] 开始并发同步...")
        from app.models.market import StockFinancial

        ts_codes = self._get_all_ts_codes()
        if not ts_codes:
            return 0

        # 获取已有财务数据的股票
        db = SessionLocal()
        existing_codes = set(
            r[0]
            for r in db.execute(
                text("SELECT DISTINCT ts_code FROM stock_financial")
            ).fetchall()
        )
        db.close()

        missing = [c for c in ts_codes if c not in existing_codes]
        logger.info(
            "[stock_financial] 需同步 %d 只 (已有 %d)",
            len(missing), len(existing_codes),
        )

        total = 0
        completed = 0
        t0 = time.time()

        def fetch_one(ts_code: str) -> int:
            db2 = SessionLocal()
            try:
                df = self.source.get_financial_indicator(
                    ts_code, "20200101", "20261231"
                )
                if df is None or df.empty:
                    return 0

                # 批量检查已有end_date
                end_dates = []
                for _, row in df.iterrows():
                    ed = str(row.get("end_date", ""))
                    if ed:
                        end_dates.append(ed)

                existing_dates = set(
                    r[0]
                    for r in db2.query(StockFinancial.end_date)
                    .filter(StockFinancial.ts_code == ts_code)
                    .all()
                )

                new_records = []
                for _, row in df.iterrows():
                    ed = str(row.get("end_date", ""))
                    if not ed or ed in existing_dates:
                        continue
                    new_records.append(
                        StockFinancial(
                            ts_code=ts_code,
                            end_date=ed,
                            ann_date=str(row.get("ann_date", ""))[:8] if pd.notna(row.get("ann_date")) else None,
                            roe=safe_float(row.get("roe")),
                            roa=safe_float(row.get("roa")),
                            gross_profit_margin=safe_float(row.get("grossprofit_margin")),
                            net_profit_margin=safe_float(row.get("netprofit_margin")),
                            current_ratio=safe_float(row.get("current_ratio")),
                            debt_to_assets=safe_float(row.get("debt_to_assets")),
                            eps=safe_float(row.get("eps")),
                            bvps=safe_float(row.get("bps")),
                        )
                    )

                if new_records:
                    db2.bulk_save_objects(new_records)
                    db2.commit()
                return len(new_records)
            except Exception:
                db2.rollback()
                return -1
            finally:
                db2.close()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for ts_code in missing:
                future = executor.submit(fetch_one, ts_code)
                futures[future] = ts_code
                time.sleep(self.rate_limit)

            for future in as_completed(futures):
                completed += 1
                try:
                    n = future.result()
                    if n > 0:
                        total += n
                except Exception:
                    pass

                if completed % 100 == 0:
                    elapsed = time.time() - t0
                    rate = completed / elapsed if elapsed > 0 else 0
                    logger.info(
                        "[stock_financial] 进度:%d/%d 新增:%d 速度:%.1f/s",
                        completed, len(futures), total, rate,
                    )

        logger.info("[stock_financial] 完成，新增 %d 行", total)
        return total

    # ------------------------------------------------------------------
    # Phase 3: 资金流数据
    # ------------------------------------------------------------------

    def _sync_northbound(self, start_date: str, end_date: str) -> int:
        """同步北向资金（按日期并发）— 补充持股数据"""
        logger.info("[northbound] 开始同步...")
        from app.models.market import StockNorthbound

        trade_dates = self._get_trade_dates(start_date, end_date)
        if not trade_dates:
            return 0

        total = 0

        def fetch_one(td: str) -> int:
            db2 = SessionLocal()
            try:
                df = self.source.get_hsgt_top10(td)
                if df is None or df.empty:
                    return 0

                existing = set(
                    r[0]
                    for r in db2.execute(
                        text(
                            "SELECT ts_code FROM stock_northbound WHERE trade_date = :d"
                        ),
                        {"d": td},
                    ).fetchall()
                )

                new_records = []
                for _, row in df.iterrows():
                    ts_code = row.get("ts_code", "")
                    if not ts_code or ts_code in existing:
                        continue
                    new_records.append(
                        StockNorthbound(
                            ts_code=ts_code,
                            trade_date=td,
                            north_net_buy=safe_float(row.get("net_amount")),
                            north_buy=safe_float(row.get("buy")),
                            north_sell=safe_float(row.get("sell")),
                            north_holding=safe_float(row.get("vol")),
                            north_holding_pct=safe_float(row.get("vol_ratio")),
                        )
                    )

                if new_records:
                    db2.bulk_save_objects(new_records)
                    db2.commit()
                return len(new_records)
            except Exception:
                db2.rollback()
                return 0
            finally:
                db2.close()

        # daily_basic按交易日拉全市场快照，单次数据量大(~4000行/天)，
        # 并发数限制为4，避免同时写入过多导致DB锁竞争
        with ThreadPoolExecutor(max_workers=min(self.max_workers, 4)) as executor:
            futures = {}
            for td in trade_dates:
                future = executor.submit(fetch_one, td)
                futures[future] = td
                time.sleep(self.rate_limit)

            for future in as_completed(futures):
                try:
                    total += future.result()
                except Exception:
                    pass

        logger.info("[northbound] 完成，新增 %d 行", total)
        return total

    def _sync_money_flow(self, start_date: str, end_date: str) -> int:
        """按股票并发同步资金流向"""
        logger.info("[money_flow] 开始并发同步...")
        from app.models.market import StockMoneyFlow

        ts_codes = self._get_all_ts_codes()
        if not ts_codes:
            return 0

        # 只同步最近30天的资金流
        recent_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        total = 0

        def fetch_one(ts_code: str) -> int:
            db2 = SessionLocal()
            try:
                df = self.source.get_money_flow(
                    ts_code, recent_start, end_date
                )
                if df is None or df.empty:
                    return 0

                existing = set(
                    r[0]
                    for r in db2.execute(
                        text(
                            "SELECT trade_date FROM stock_money_flow WHERE ts_code = :c"
                        ),
                        {"c": ts_code},
                    ).fetchall()
                )

                new_records = []
                for _, row in df.iterrows():
                    td = str(row.get("trade_date", ""))
                    if td in existing:
                        continue
                    # Tushare moneyflow接口返回买入/卖出分开的成交量/额，
                    # 需做差得到净流入；超大/大/中/小单按金额阈值划分
                    new_records.append(
                        StockMoneyFlow(
                            ts_code=ts_code,
                            trade_date=td,
                            smart_net_inflow=safe_float(row.get("net_mf_vol")),
                            smart_net_pct=safe_float(row.get("net_mf_amount")),
                            super_large_net_inflow=safe_float(row.get("buy_elg_vol", 0)) - safe_float(row.get("sell_elg_vol", 0)),
                            super_large_net_pct=safe_float(row.get("buy_elg_amount", 0)) - safe_float(row.get("sell_elg_amount", 0)),
                            large_net_inflow=safe_float(row.get("buy_lg_vol", 0)) - safe_float(row.get("sell_lg_vol", 0)),
                            large_net_pct=safe_float(row.get("buy_lg_amount", 0)) - safe_float(row.get("sell_lg_amount", 0)),
                            medium_net_inflow=safe_float(row.get("buy_md_vol", 0)) - safe_float(row.get("sell_md_vol", 0)),
                            medium_net_pct=safe_float(row.get("buy_md_amount", 0)) - safe_float(row.get("sell_md_amount", 0)),
                            small_net_inflow=safe_float(row.get("buy_sm_vol", 0)) - safe_float(row.get("sell_sm_vol", 0)),
                            small_net_pct=safe_float(row.get("buy_sm_amount", 0)) - safe_float(row.get("sell_sm_amount", 0)),
                        )
                    )

                if new_records:
                    db2.bulk_save_objects(new_records)
                    db2.commit()
                return len(new_records)
            except Exception:
                db2.rollback()
                return 0
            finally:
                db2.close()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for ts_code in ts_codes[:500]:  # 限制前500只：资金流API单只耗时长，全量5000+只耗时超8小时
                future = executor.submit(fetch_one, ts_code)
                futures[future] = ts_code
                time.sleep(self.rate_limit)

            for future in as_completed(futures):
                try:
                    total += future.result()
                except Exception:
                    pass

        logger.info("[money_flow] 完成，新增 %d 行", total)
        return total

    def _sync_margin(self, start_date: str, end_date: str) -> int:
        """同步融资融券数据"""
        logger.info("[margin] 开始同步...")
        from app.models.market import StockMargin

        if not self._connected:
            return 0

        try:
            # Tushare margin接口
            df = self.source._pro.margin(
                start_date=self._fmt(start_date),
                end_date=self._fmt(end_date),
            )
            if df is None or df.empty:
                return 0

            db = SessionLocal()
            try:
                existing = set(
                    r[0]
                    for r in db.execute(
                        text("SELECT DISTINCT trade_date FROM stock_margin")
                    ).fetchall()
                )

                new_records = []
                for _, row in df.iterrows():
                    td = str(row.get("trade_date", ""))
                    if td in existing:
                        continue
                    new_records.append(
                        StockMargin(
                            ts_code=row.get("ts_code", ""),
                            trade_date=td,
                            margin_buy=safe_float(row.get("rzye")),
                            margin_balance=safe_float(row.get("rzrqye")),
                        )
                    )

                if new_records:
                    db.bulk_save_objects(new_records)
                    db.commit()

                logger.info("[margin] 新增 %d 行", len(new_records))
                return len(new_records)
            except Exception as e:
                db.rollback()
                logger.error("[margin] 写入失败: %s", e)
                return 0
            finally:
                db.close()
        except Exception as e:
            logger.warning("[margin] 获取失败: %s", e)
            return 0

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _get_all_ts_codes(self) -> List[str]:
        """从DB获取全A股代码列表"""
        db = SessionLocal()
        try:
            codes = [
                r[0]
                for r in db.execute(
                    text(
                        "SELECT ts_code FROM stock_basic WHERE list_status='L' ORDER BY ts_code"
                    )
                ).fetchall()
            ]
            return codes
        finally:
            db.close()

    def _get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """从DB获取交易日历"""
        db = SessionLocal()
        try:
            dates = [
                r[0].strftime("%Y%m%d") if isinstance(r[0], date) else str(r[0])
                for r in db.execute(
                    text(
                        "SELECT cal_date FROM trading_calendar WHERE is_open = 1 "
                        "AND cal_date >= :s AND cal_date <= :e ORDER BY cal_date"
                    ),
                    {"s": start_date, "e": end_date},
                ).fetchall()
            ]
            return dates
        finally:
            db.close()

    @staticmethod
    def _fmt(date_str: str) -> str:
        """YYYY-MM-DD → YYYYMMDD"""
        return date_str.replace("-", "") if date_str else ""
