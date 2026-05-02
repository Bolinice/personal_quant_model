"""
Tushare 数据源适配器 — 带重试、断路器、数据校验

特性:
  - 指数退避重试 (3次)
  - 断路器保护 (连续5次失败后熔断30s)
  - 数据校验 (价格非负、日期合法、去重)
  - AKShare fallback
"""

from __future__ import annotations

import contextlib
import logging
import time
from functools import wraps
from typing import TYPE_CHECKING

import pandas as pd

from app.data_sources.base import CircuitBreaker, CircuitBreakerOpenError

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 重试装饰器
# ──────────────────────────────────────────────


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
):
    """指数退避重试装饰器"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2**attempt), max_delay)
                        logger.warning(
                            "重试 %s 第%d次 (等待%.1fs): %s",
                            func.__name__,
                            attempt + 1,
                            delay,
                            e,
                        )
                        time.sleep(delay)
            raise last_error

        return wrapper

    return decorator


# ──────────────────────────────────────────────
# 数据校验
# ──────────────────────────────────────────────


def _validate_dataframe(df: pd.DataFrame, data_type: str = "price") -> pd.DataFrame:
    """通用数据校验"""
    if df.empty:
        return df

    original_len = len(df)

    # 价格类数据校验
    if data_type == "price":
        price_cols = [c for c in ("open", "high", "low", "close", "pre_close") if c in df.columns]
        for col in price_cols:
            mask = df[col] < 0
            if mask.any():
                logger.warning("%s校验: %s 有 %d 条负值已置NaN", data_type, col, mask.sum())
                df.loc[mask, col] = pd.NA

    # 日期校验
    date_cols = [c for c in ("trade_date", "ann_date", "end_date") if c in df.columns]
    for col in date_cols:
        if df[col].dtype == object:
            with contextlib.suppress(Exception):
                df[col] = pd.to_datetime(df[col], format="mixed")

    # 去重
    dedup_cols = [c for c in ("ts_code", "trade_date") if c in df.columns]
    if len(dedup_cols) >= 2:
        df = df.drop_duplicates(subset=dedup_cols, keep="last")

    if len(df) != original_len:
        logger.info("%s校验: %d → %d (去重/清洗)", data_type, original_len, len(df))

    return df


# ──────────────────────────────────────────────
# Tushare 数据源
# ──────────────────────────────────────────────


class TushareSource:
    """Tushare数据源 — 带重试和断路器"""

    def __init__(self, token: str | None = None, proxy_url: str | None = None):
        self._token = token
        self._proxy_url = proxy_url
        self._pro = None
        self._breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30,
        )
        self._akshare_fallback = None

    @property
    def pro(self):
        """延迟初始化Tushare pro接口"""
        if self._pro is None:
            try:
                import tushare as ts
                from tushare.pro import client as _ts_client

                # 设置代理URL（如果提供）
                if self._proxy_url:
                    _ts_client.DataApi._DataApi__http_url = self._proxy_url
                    logger.info("Tushare代理URL已设置: %s", self._proxy_url)

                if self._token:
                    ts.set_token(self._token)
                self._pro = ts.pro_api()
                logger.info("Tushare pro接口初始化成功")
            except ImportError:
                raise ImportError("请安装tushare: pip install tushare") from None
        return self._pro

    @property
    def akshare_fallback(self):
        """AKShare fallback数据源"""
        if self._akshare_fallback is None:
            from app.data_sources.akshare_source import AKShareSource

            self._akshare_fallback = AKShareSource()
        return self._akshare_fallback

    @staticmethod
    def _build_params(
        ts_code: str | None = None,
        trade_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        period: date | None = None,
    ) -> dict[str, str]:
        """构建Tushare API参数 — 统一日期格式化"""
        params: dict[str, str] = {}
        if ts_code:
            params["ts_code"] = ts_code
        if trade_date:
            params["trade_date"] = trade_date.strftime("%Y%m%d")
        if start_date:
            params["start_date"] = start_date.strftime("%Y%m%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y%m%d")
        if period:
            params["period"] = period.strftime("%Y%m%d")
        return params

    def _call_with_fallback(self, func: Callable, data_type: str, **kwargs) -> pd.DataFrame:
        """带断路器和fallback的数据获取"""
        try:
            # 检查断路器状态
            if self._breaker.state == "OPEN":
                logger.warning("Tushare断路器开启，使用AKShare fallback")
                return self.akshare_fallback.fetch(data_type, **kwargs)

            # 通过断路器调用
            df = self._breaker.call(func, **kwargs)
            return _validate_dataframe(df, data_type)

        except CircuitBreakerOpenError:
            # 断路器开启，使用AKShare fallback
            logger.warning("Tushare断路器开启，使用AKShare fallback")
            try:
                df = self.akshare_fallback.fetch(data_type, **kwargs)
                logger.info("AKShare fallback成功: %s", data_type)
                return _validate_dataframe(df, data_type)
            except Exception as fallback_err:
                logger.error("AKShare fallback也失败: %s", fallback_err)
                raise

        except Exception as e:
            logger.error("Tushare请求失败: %s", e)
            # 尝试AKShare fallback
            try:
                df = self.akshare_fallback.fetch(data_type, **kwargs)
                logger.info("AKShare fallback成功: %s", data_type)
                return _validate_dataframe(df, data_type)
            except Exception as fallback_err:
                logger.error("AKShare fallback也失败: %s", fallback_err)
                raise

    # ──────────────────────────────────────────────
    # 行情数据
    # ──────────────────────────────────────────────

    @retry_with_backoff(max_retries=3)
    def get_stock_daily(self, ts_code=None, trade_date=None, start_date=None, end_date=None) -> pd.DataFrame:
        """获取股票日线行情"""
        return self._call_with_fallback(
            lambda **p: self.pro.daily(**p),
            "price",
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
        )

    @retry_with_backoff(max_retries=3)
    def get_stock_daily_basic(self, ts_code=None, trade_date=None, start_date=None, end_date=None) -> pd.DataFrame:
        """获取每日指标"""
        return self._call_with_fallback(
            lambda **p: self.pro.daily_basic(**p),
            "basic",
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
        )

    # ──────────────────────────────────────────────
    # 财务数据
    # ──────────────────────────────────────────────

    @retry_with_backoff(max_retries=3)
    def get_income(self, ts_code=None, period=None, start_date=None, end_date=None) -> pd.DataFrame:
        """获取利润表"""
        return self._call_with_fallback(
            lambda **p: self.pro.income(**p),
            "financial",
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

    @retry_with_backoff(max_retries=3)
    def get_balancesheet(self, ts_code=None, period=None, start_date=None, end_date=None) -> pd.DataFrame:
        """获取资产负债表"""
        return self._call_with_fallback(
            lambda **p: self.pro.balancesheet(**p),
            "financial",
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

    @retry_with_backoff(max_retries=3)
    def get_cashflow(self, ts_code=None, period=None, start_date=None, end_date=None) -> pd.DataFrame:
        """获取现金流量表"""
        return self._call_with_fallback(
            lambda **p: self.pro.cashflow(**p),
            "financial",
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

    @retry_with_backoff(max_retries=3)
    def get_financial_indicator(self, ts_code=None, period=None, start_date=None, end_date=None) -> pd.DataFrame:
        """获取财务指标"""
        return self._call_with_fallback(
            lambda **p: self.pro.fina_indicator(**p),
            "financial",
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

    # ──────────────────────────────────────────────
    # 指数数据
    # ──────────────────────────────────────────────

    @retry_with_backoff(max_retries=3)
    def get_index_daily(self, ts_code="000001.SH", start_date=None, end_date=None) -> pd.DataFrame:
        """获取指数日线"""
        return self._call_with_fallback(
            lambda **p: self.pro.index_daily(**p),
            "price",
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

    # ──────────────────────────────────────────────
    # 资金流数据
    # ──────────────────────────────────────────────

    @retry_with_backoff(max_retries=3)
    def get_moneyflow(self, ts_code=None, trade_date=None, start_date=None, end_date=None) -> pd.DataFrame:
        """获取个股资金流"""
        return self._call_with_fallback(
            lambda **p: self.pro.moneyflow(**p),
            "moneyflow",
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
        )

    # ──────────────────────────────────────────────
    # 融资融券
    # ──────────────────────────────────────────────

    @retry_with_backoff(max_retries=3)
    def get_margin(self, ts_code=None, trade_date=None, start_date=None, end_date=None) -> pd.DataFrame:
        """获取融资融券数据"""
        return self._call_with_fallback(
            lambda **p: self.pro.margin(**p),
            "margin",
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
        )

    # ──────────────────────────────────────────────
    # 北向资金
    # ──────────────────────────────────────────────

    @retry_with_backoff(max_retries=3)
    def get_north_flow(self, trade_date=None, start_date=None, end_date=None) -> pd.DataFrame:
        """获取北向资金数据"""
        return self._call_with_fallback(
            lambda **p: self.pro.hk_hold(**p),
            "northflow",
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
        )

    # ──────────────────────────────────────────────
    # 股票列表
    # ──────────────────────────────────────────────

    @retry_with_backoff(max_retries=3)
    def get_stock_basic(self, list_status="L") -> pd.DataFrame:
        """获取股票列表"""
        return self._call_with_fallback(
            lambda **p: self.pro.stock_basic(**p),
            "basic",
            list_status=list_status,
        )

    # ──────────────────────────────────────────────
    # 批量同步
    # ──────────────────────────────────────────────

    def fetch_all_for_date(self, trade_date: date) -> dict[str, pd.DataFrame]:
        """获取某日所有数据 — 用于日终流水线"""
        result = {}

        try:
            result["stock_daily"] = self.get_stock_daily(trade_date=trade_date)
        except Exception as e:
            logger.error("获取stock_daily失败: %s", e)

        try:
            result["stock_daily_basic"] = self.get_stock_daily_basic(trade_date=trade_date)
        except Exception as e:
            logger.error("获取stock_daily_basic失败: %s", e)

        try:
            result["moneyflow"] = self.get_moneyflow(trade_date=trade_date)
        except Exception as e:
            logger.error("获取moneyflow失败: %s", e)

        try:
            result["index_daily"] = self.get_index_daily(end_date=trade_date)
        except Exception as e:
            logger.error("获取index_daily失败: %s", e)

        try:
            result["margin"] = self.get_margin(trade_date=trade_date)
        except Exception as e:
            logger.error("获取margin失败: %s", e)

        try:
            result["northflow"] = self.get_north_flow(trade_date=trade_date)
        except Exception as e:
            logger.error("获取northflow失败: %s", e)

        success = [k for k, v in result.items() if not v.empty]
        logger.info("fetch_all_for_date %s: 成功 %d/%d 数据集", trade_date, len(success), len(result))

        return result
