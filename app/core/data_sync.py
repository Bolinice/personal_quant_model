"""
数据同步模块 — 高性能增量数据同步引擎

优化点:
  - 向量化批量写入替代逐行iterrows
  - PostgreSQL ON CONFLICT DO UPDATE (upsert)
  - 增量同步: 只查询最近N天已有记录
  - 同步进度持久化: 中断后可续传
  - 数据校验: 价格非负、日期合法、无重复
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import re
from sqlalchemy import text, inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# SQL安全: 合法表名/列名白名单
# ──────────────────────────────────────────────
_SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$", re.IGNORECASE)

VALIDATED_TABLES: dict[str, set[str]] = {}


def _validate_table_columns(session: Session, table_name: str, columns: list[str]) -> None:
    """校验表名和列名合法性, 防止SQL注入"""
    if not _SAFE_IDENTIFIER.match(table_name):
        raise ValueError(f"非法表名: {table_name}")
    for col in columns:
        if not _SAFE_IDENTIFIER.match(col):
            raise ValueError(f"非法列名: {col}")
    # 验证表存在且列属于该表 (首次时缓存)
    if table_name not in VALIDATED_TABLES:
        try:
            insp = sa_inspect(session.get_bind())
            if table_name not in insp.get_table_names():
                raise ValueError(f"表不存在: {table_name}")
            VALIDATED_TABLES[table_name] = {
                c["name"] for c in insp.get_columns(table_name)
            }
        except Exception:
            VALIDATED_TABLES[table_name] = set(columns)
    valid_cols = VALIDATED_TABLES[table_name]
    invalid = set(columns) - valid_cols
    if invalid:
        raise ValueError(f"列不存在于{table_name}: {invalid}")

# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def safe_float(val):
    """安全转换为float — Tushare返回的数值可能含NaN/Inf/None，
    直接写入PostgreSQL的float列会报错，必须过滤为None"""
    try:
        if pd.isna(val):
            return None
        v = float(val)
        return v if np.isfinite(v) else None
    except (ValueError, TypeError):
        return None


def _str_to_date(s: str) -> date:
    """将 YYYYMMDD 或 YYYY-MM-DD 字符串转换为 date 对象"""
    if isinstance(s, date):
        return s
    s = str(s).replace("-", "")
    return datetime.strptime(s, "%Y%m%d").date()


def _validate_price_data(df: pd.DataFrame) -> pd.DataFrame:
    """校验行情数据: 价格非负、日期合法、去重"""
    if df.empty:
        return df

    price_cols = [c for c in ("open", "high", "low", "close", "pre_close", "change", "vol", "amount")
                  if c in df.columns]
    for col in price_cols:
        mask = df[col] < 0
        if mask.any():
            logger.warning("数据校验: %s 有 %d 条负值已置NaN", col, mask.sum())
            df.loc[mask, col] = np.nan

    # 去重: 同一股票同一日期只保留最新
    if "ts_code" in df.columns and "trade_date" in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
        after = len(df)
        if before != after:
            logger.warning("数据校验: 去重 %d → %d (删除 %d 条)", before, after, before - after)

    return df


# ──────────────────────────────────────────────
# 同步进度持久化
# ──────────────────────────────────────────────

class SyncProgress:
    """同步进度管理 — 记录已同步的日期范围，支持断点续传"""

    PROGRESS_FILE = Path("data/sync_progress.json")

    def __init__(self):
        self.PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._progress = self._load()

    def _load(self) -> dict:
        if self.PROGRESS_FILE.exists():
            try:
                return json.loads(self.PROGRESS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self) -> None:
        self.PROGRESS_FILE.write_text(
            json.dumps(self._progress, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def get_last_sync_date(self, table_name: str) -> date | None:
        """获取某表最后同步日期"""
        val = self._progress.get(table_name, {}).get("last_date")
        return _str_to_date(val) if val else None

    def update(self, table_name: str, last_date: date, count: int = 0) -> None:
        """更新同步进度"""
        if table_name not in self._progress:
            self._progress[table_name] = {}
        self._progress[table_name]["last_date"] = str(last_date)
        self._progress[table_name]["total_count"] = self._progress[table_name].get("total_count", 0) + count
        self._save()


# ──────────────────────────────────────────────
# 批量 Upsert 引擎
# ──────────────────────────────────────────────

class BulkUpsert:
    """PostgreSQL ON CONFLICT DO UPDATE 批量写入"""

    @staticmethod
    def upsert_dataframe(
        session: Session,
        table_name: str,
        df: pd.DataFrame,
        conflict_columns: list[str],
        batch_size: int = 5000,
    ) -> int:
        """向量化批量upsert — 替代逐行iterrows

        Args:
            session: SQLAlchemy Session
            table_name: 目标表名
            df: 待写入数据
            conflict_columns: 冲突检测列 (ON CONFLICT)
            batch_size: 每批写入行数

        Returns:
            写入总行数
        """
        if df.empty:
            return 0

        total = 0
        columns = list(df.columns)

        # SQL注入防护: 校验表名和列名合法性
        _validate_table_columns(session, table_name, columns)

        conflict_clause = ", ".join(conflict_columns)

        # 构建 UPDATE SET 子句 (排除冲突列本身)
        update_cols = [c for c in columns if c not in conflict_columns]
        update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)

        for start in range(0, len(df), batch_size):
            batch = df.iloc[start : start + batch_size]
            rows = batch.where(batch.notna(), None).values.tolist()

            # 构建参数化SQL
            placeholders = ", ".join([f":{i}" for i in range(len(columns))])
            sql = text(
                f"INSERT INTO {table_name} ({', '.join(columns)}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_clause}"
            )

            # 批量执行
            params_list = [
                {str(i): row[i] for i in range(len(columns))}
                for row in rows
            ]
            session.execute(sql, params_list)
            total += len(batch)

        session.commit()
        return total


# ──────────────────────────────────────────────
# 数据同步主引擎
# ──────────────────────────────────────────────

class DataSyncEngine:
    """高性能数据同步引擎"""

    def __init__(self, session: Session, progress: SyncProgress | None = None):
        self.session = session
        self.progress = progress or SyncProgress()
        self.upserter = BulkUpsert()

    def sync_stock_daily(
        self,
        df: pd.DataFrame,
        batch_size: int = 5000,
    ) -> int:
        """同步日线行情数据"""
        if df.empty:
            return 0

        df = _validate_price_data(df)
        df = self._prepare_df(df, date_col="trade_date")

        # 转换数值列
        float_cols = ["open", "high", "low", "close", "pre_close", "change",
                       "pct_chg", "vol", "amount"]
        for col in float_cols:
            if col in df.columns:
                df[col] = df[col].apply(safe_float)

        count = self.upserter.upsert_dataframe(
            session=self.session,
            table_name="stock_daily",
            df=df,
            conflict_columns=["ts_code", "trade_date"],
            batch_size=batch_size,
        )

        if not df.empty and "trade_date" in df.columns:
            last_date = df["trade_date"].max()
            self.progress.update("stock_daily", last_date, count)

        logger.info("sync_stock_daily: %d 条写入", count)
        return count

    def sync_stock_daily_basic(
        self,
        df: pd.DataFrame,
        batch_size: int = 5000,
    ) -> int:
        """同步日线指标数据"""
        if df.empty:
            return 0

        df = self._prepare_df(df, date_col="trade_date")

        # 转换所有数值列
        skip_cols = {"ts_code", "trade_date", "name"}
        for col in df.columns:
            if col not in skip_cols:
                df[col] = df[col].apply(safe_float)

        count = self.upserter.upsert_dataframe(
            session=self.session,
            table_name="stock_daily_basic",
            df=df,
            conflict_columns=["ts_code", "trade_date"],
            batch_size=batch_size,
        )

        if not df.empty and "trade_date" in df.columns:
            last_date = df["trade_date"].max()
            self.progress.update("stock_daily_basic", last_date, count)

        logger.info("sync_stock_daily_basic: %d 条写入", count)
        return count

    def sync_stock_financial(
        self,
        df: pd.DataFrame,
        batch_size: int = 5000,
    ) -> int:
        """同步财务数据"""
        if df.empty:
            return 0

        df = self._prepare_df(df, date_col="end_date")

        skip_cols = {"ts_code", "end_date", "ann_date", "report_type"}
        for col in df.columns:
            if col not in skip_cols:
                df[col] = df[col].apply(safe_float)

        count = self.upserter.upsert_dataframe(
            session=self.session,
            table_name="stock_financial",
            df=df,
            conflict_columns=["ts_code", "end_date", "ann_date"],
            batch_size=batch_size,
        )

        if not df.empty and "ann_date" in df.columns:
            last_date = df["ann_date"].max()
            self.progress.update("stock_financial", last_date, count)

        logger.info("sync_stock_financial: %d 条写入", count)
        return count

    def sync_index_daily(
        self,
        df: pd.DataFrame,
        batch_size: int = 5000,
    ) -> int:
        """同步指数日线数据"""
        if df.empty:
            return 0

        df = _validate_price_data(df)
        df = self._prepare_df(df, date_col="trade_date")

        float_cols = ["open", "high", "low", "close", "pre_close", "change",
                       "pct_chg", "vol", "amount"]
        for col in float_cols:
            if col in df.columns:
                df[col] = df[col].apply(safe_float)

        count = self.upserter.upsert_dataframe(
            session=self.session,
            table_name="index_daily",
            df=df,
            conflict_columns=["ts_code", "trade_date"],
            batch_size=batch_size,
        )

        if not df.empty and "trade_date" in df.columns:
            last_date = df["trade_date"].max()
            self.progress.update("index_daily", last_date, count)

        logger.info("sync_index_daily: %d 条写入", count)
        return count

    def sync_moneyflow(
        self,
        df: pd.DataFrame,
        batch_size: int = 5000,
    ) -> int:
        """同步资金流数据"""
        if df.empty:
            return 0

        df = self._prepare_df(df, date_col="trade_date")

        skip_cols = {"ts_code", "trade_date", "name"}
        for col in df.columns:
            if col not in skip_cols:
                df[col] = df[col].apply(safe_float)

        count = self.upserter.upsert_dataframe(
            session=self.session,
            table_name="stock_moneyflow",
            df=df,
            conflict_columns=["ts_code", "trade_date"],
            batch_size=batch_size,
        )

        if not df.empty and "trade_date" in df.columns:
            last_date = df["trade_date"].max()
            self.progress.update("stock_moneyflow", last_date, count)

        logger.info("sync_moneyflow: %d 条写入", count)
        return count

    def sync_margin(
        self,
        df: pd.DataFrame,
        batch_size: int = 5000,
    ) -> int:
        """同步融资融券数据"""
        if df.empty:
            return 0

        df = self._prepare_df(df, date_col="trade_date")

        skip_cols = {"ts_code", "trade_date"}
        for col in df.columns:
            if col not in skip_cols:
                df[col] = df[col].apply(safe_float)

        count = self.upserter.upsert_dataframe(
            session=self.session,
            table_name="stock_margin",
            df=df,
            conflict_columns=["ts_code", "trade_date"],
            batch_size=batch_size,
        )

        if not df.empty and "trade_date" in df.columns:
            last_date = df["trade_date"].max()
            self.progress.update("stock_margin", last_date, count)

        logger.info("sync_margin: %d 条写入", count)
        return count

    def sync_northflow(
        self,
        df: pd.DataFrame,
        batch_size: int = 5000,
    ) -> int:
        """同步北向资金数据"""
        if df.empty:
            return 0

        df = self._prepare_df(df, date_col="trade_date")

        skip_cols = {"ts_code", "trade_date"}
        for col in df.columns:
            if col not in skip_cols:
                df[col] = df[col].apply(safe_float)

        count = self.upserter.upsert_dataframe(
            session=self.session,
            table_name="north_flow",
            df=df,
            conflict_columns=["ts_code", "trade_date"],
            batch_size=batch_size,
        )

        if not df.empty and "trade_date" in df.columns:
            last_date = df["trade_date"].max()
            self.progress.update("north_flow", last_date, count)

        logger.info("sync_northflow: %d 条写入", count)
        return count

    # ──────────────────────────────────────────────
    # 内部工具
    # ──────────────────────────────────────────────

    def _prepare_df(self, df: pd.DataFrame, date_col: str = "trade_date") -> pd.DataFrame:
        """预处理DataFrame: 日期转换、列名标准化"""
        df = df.copy()

        # 日期列转换
        if date_col in df.columns:
            df[date_col] = df[date_col].apply(_str_to_date)

        if "ann_date" in df.columns:
            df["ann_date"] = df["ann_date"].apply(_str_to_date)

        # 删除全空列
        df = df.dropna(axis=1, how="all")

        return df

    def get_incremental_start(self, table_name: str, default_days: int = 30) -> date:
        """获取增量同步起始日期 — 基于上次同步进度"""
        last = self.progress.get_last_sync_date(table_name)
        if last:
            return last + timedelta(days=1)
        return date.today() - timedelta(days=default_days)
