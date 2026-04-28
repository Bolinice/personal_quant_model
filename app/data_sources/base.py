from __future__ import annotations

"""
数据源基类
定义统一的数据源接口，支持增量同步、错误重试、限流控制、数据质量校验、主备切换
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from app.core.logging import logger


@dataclass
class SyncResult:
    """同步结果"""

    success: bool = True
    records_fetched: int = 0
    records_saved: int = 0
    records_updated: int = 0
    records_failed: int = 0
    error_message: str = None
    duration_seconds: float = 0.0
    details: dict = field(default_factory=dict)


@dataclass
class DataQualityReport:
    """数据质量报告"""

    data_type: str
    total_records: int = 0
    missing_rate: float = 0.0  # 缺失率
    outlier_rate: float = 0.0  # 异常值率
    date_continuity: float = 1.0  # 日期连续性 (1.0=完全连续)
    duplicate_rate: float = 0.0  # 重复率
    is_acceptable: bool = True
    issues: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"DataQuality[{self.data_type}]: records={self.total_records}, "
            f"missing={self.missing_rate:.2%}, outlier={self.outlier_rate:.2%}, "
            f"continuity={self.date_continuity:.2%}, dup={self.duplicate_rate:.2%}, "
            f"acceptable={self.is_acceptable}"
        )


class DataSourceManager:
    """数据源管理器 - 注册、主备切换、数据新鲜度检查"""

    def __init__(self):
        self._sources: dict[str, BaseDataSource] = {}
        self._primary: str | None = None
        self._fallback: str | None = None

    def register(self, name: str, source: BaseDataSource, is_primary: bool = False, is_fallback: bool = False):
        self._sources[name] = source
        if is_primary:
            self._primary = name
        if is_fallback:
            self._fallback = name

    def get(self, name: str) -> BaseDataSource | None:
        return self._sources.get(name)

    def get_primary(self) -> BaseDataSource | None:
        """获取主数据源，不可用时自动切换到备源"""
        if self._primary and self._primary in self._sources:
            source = self._sources[self._primary]
            try:
                if source.connect():
                    return source
            except Exception:
                pass

        # 主源不可用，切换到备源
        if self._fallback and self._fallback in self._sources:
            logger.warning(f"Primary source {self._primary} unavailable, falling back to {self._fallback}")
            return self._sources[self._fallback]

        # 最后尝试任意可用源
        for _name, source in self._sources.items():
            try:
                if source.connect():
                    return source
            except Exception:
                continue
        return None

    def check_data_freshness(self, data_type: str, max_age_days: int = 1) -> dict[str, bool]:
        """检查各数据源的数据新鲜度"""
        freshness = {}
        for name, source in self._sources.items():
            try:
                last_date = source.get_last_sync_date(data_type)
                if last_date is None:
                    freshness[name] = False
                else:
                    age = (date.today() - last_date).days
                    freshness[name] = age <= max_age_days
            except Exception:
                freshness[name] = False
        return freshness

    def connect_all(self) -> dict[str, bool]:
        """尝试连接所有数据源，返回状态"""
        status = {}
        for name, source in self._sources.items():
            try:
                status[name] = source.connect()
            except Exception:
                status[name] = False
        return status


# 全局单例
data_source_manager = DataSourceManager()


def get_data_source(name: str) -> BaseDataSource | None:
    """获取指定名称的数据源"""
    return data_source_manager.get(name)


class BaseDataSource(ABC):
    """数据源基类 - 统一接口"""

    def __init__(self, rate_limit: int = 200, max_retries: int = 3):
        """
        Args:
            rate_limit: 每分钟API调用次数限制
            max_retries: 最大重试次数
        """
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self._call_count = 0
        self._last_reset = datetime.now()

    @abstractmethod
    def connect(self) -> bool:
        """测试数据源连接是否可用"""

    @abstractmethod
    def get_stock_basic(self, **kwargs) -> pd.DataFrame:
        """获取股票基本信息"""

    @abstractmethod
    def get_stock_daily(
        self, ts_code: str | None = None, start_date: str | None = None, end_date: str | None = None, **kwargs
    ) -> pd.DataFrame:
        """获取日线行情"""

    @abstractmethod
    def get_index_daily(
        self, ts_code: str | None = None, start_date: str | None = None, end_date: str | None = None, **kwargs
    ) -> pd.DataFrame:
        """获取指数日线行情"""

    @abstractmethod
    def get_financial_data(
        self, ts_code: str | None = None, start_date: str | None = None, end_date: str | None = None, **kwargs
    ) -> pd.DataFrame:
        """获取财务数据"""

    @abstractmethod
    def get_trading_calendar(
        self, exchange: str = "SSE", start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        """获取交易日历"""

    def get_last_sync_date(self, data_type: str) -> date | None:
        """获取某类数据的最后同步日期 (用于新鲜度检查, 子类可覆写)"""
        return None

    def validate(
        self,
        df: pd.DataFrame,
        data_type: str,
        required_columns: list[str] | None = None,
        max_missing_rate: float = 0.1,
        max_outlier_rate: float = 0.05,
    ) -> DataQualityReport:
        """
        数据质量校验: 缺失率、异常值率、日期连续性、重复率
        """
        report = DataQualityReport(data_type=data_type)
        report.total_records = len(df)

        if df.empty:
            report.is_acceptable = False
            report.issues.append("Empty DataFrame")
            return report

        total_cells = df.size
        missing_cells = df.isna().sum().sum()
        report.missing_rate = missing_cells / total_cells if total_cells > 0 else 0

        if required_columns:
            missing_cols = [c for c in required_columns if c not in df.columns]
            if missing_cols:
                report.issues.append(f"Missing required columns: {missing_cols}")
                report.is_acceptable = False

        outlier_count = 0
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 10:
                continue
            median = series.median()
            mad = (series - median).abs().median()
            if mad > 0:
                outlier_mask = (series - median).abs() > 5 * mad
                outlier_count += outlier_mask.sum()

        total_numeric = sum(len(df[col].dropna()) for col in numeric_cols)
        report.outlier_rate = outlier_count / total_numeric if total_numeric > 0 else 0

        if "trade_date" in df.columns:
            dates = pd.to_datetime(df["trade_date"]).sort_values().dropna()
            if len(dates) > 1:
                expected_bdays = np.busday_count(dates.iloc[0].date(), dates.iloc[-1].date()) + 1
                actual_days = len(dates)
                report.date_continuity = actual_days / expected_bdays if expected_bdays > 0 else 1.0

        if "trade_date" in df.columns and "ts_code" in df.columns:
            total_rows = len(df)
            unique_rows = df.drop_duplicates(subset=["trade_date", "ts_code"]).shape[0]
            report.duplicate_rate = (total_rows - unique_rows) / total_rows if total_rows > 0 else 0

        if report.missing_rate > max_missing_rate:
            report.issues.append(f"Missing rate {report.missing_rate:.2%} > {max_missing_rate:.2%}")
            report.is_acceptable = False
        if report.outlier_rate > max_outlier_rate:
            report.issues.append(f"Outlier rate {report.outlier_rate:.2%} > {max_outlier_rate:.2%}")
            report.is_acceptable = False
        if report.duplicate_rate > 0.01:
            report.issues.append(f"Duplicate rate {report.duplicate_rate:.2%} > 1%")
            report.is_acceptable = False

        return report

    def get_index_components(self, index_code: str, trade_date: str | None = None) -> pd.DataFrame:
        """获取指数成分股"""
        return pd.DataFrame()

    def get_stock_status(self, ts_code: str | None = None, trade_date: str | None = None) -> pd.DataFrame:
        """获取股票状态（ST、停牌等）"""
        return pd.DataFrame()

    def get_adj_factor(
        self, ts_code: str | None = None, start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        """获取复权因子"""
        return pd.DataFrame()

    def get_industry_classification(self, ts_code: str | None = None, standard: str = "sw") -> pd.DataFrame:
        """获取行业分类"""
        return pd.DataFrame()

    # ==================== 增量同步 ====================

    def incremental_sync(self, data_type: str, last_sync_date: date, end_date: date | None = None) -> SyncResult:
        """
        增量同步数据
        只同步last_sync_date之后的数据

        Args:
            data_type: 数据类型
            last_sync_date: 上次同步日期
            end_date: 结束日期（默认今天）
        """
        if end_date is None:
            end_date = date.today()

        start = last_sync_date + timedelta(days=1)
        if start > end_date:
            return SyncResult(success=True, records_fetched=0, details={"message": "Already up to date"})

        return self._sync_range(data_type, start, end_date)

    def _sync_range(self, data_type: str, start_date: date, end_date: date) -> SyncResult:
        """同步指定日期范围的数据"""
        import time

        start_time = time.time()

        try:
            method_map = {
                "stock_daily": self.get_stock_daily,
                "index_daily": self.get_index_daily,
                "financial": self.get_financial_data,
                "stock_basic": self.get_stock_basic,
                "trading_calendar": self.get_trading_calendar,
            }

            method = method_map.get(data_type)
            if not method:
                return SyncResult(success=False, error_message=f"Unknown data type: {data_type}")

            df = method(start_date=start_date.strftime("%Y%m%d"), end_date=end_date.strftime("%Y%m%d"))

            duration = time.time() - start_time
            return SyncResult(
                success=True,
                records_fetched=len(df) if df is not None and not df.empty else 0,
                duration_seconds=round(duration, 2),
            )
        except Exception as e:
            logger.error(f"Sync failed for {data_type}: {e}")
            return SyncResult(success=False, error_message=str(e))

    # ==================== 限流控制 ====================

    def _rate_limit_check(self):
        """检查API调用频率"""
        now = datetime.now()
        if (now - self._last_reset).seconds >= 60:
            self._call_count = 0
            self._last_reset = now

        if self._call_count >= self.rate_limit:
            import time

            sleep_time = 60 - (now - self._last_reset).seconds
            logger.warning(f"Rate limit reached, sleeping {sleep_time}s")
            time.sleep(sleep_time)
            self._call_count = 0
            self._last_reset = datetime.now()

        self._call_count += 1

    # ==================== 重试机制 ====================

    def _retry_call(self, func, *args, **kwargs):
        """带重试的API调用"""
        import time

        for attempt in range(self.max_retries):
            try:
                self._rate_limit_check()
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait = 2**attempt  # 指数退避
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries} after {wait}s: {e}")
                    time.sleep(wait)
                else:
                    raise
