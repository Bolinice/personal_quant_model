"""
数据源基类
定义统一的数据源接口，支持增量同步、错误重试、限流控制
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field
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
    details: Dict = field(default_factory=dict)


class DataSourceManager:
    """数据源管理器 - 注册和切换数据源"""

    def __init__(self):
        self._sources: Dict[str, BaseDataSource] = {}
        self._primary: Optional[str] = None

    def register(self, name: str, source: BaseDataSource, is_primary: bool = False):
        self._sources[name] = source
        if is_primary:
            self._primary = name

    def get(self, name: str) -> Optional[BaseDataSource]:
        return self._sources.get(name)

    def get_primary(self) -> Optional[BaseDataSource]:
        if self._primary and self._primary in self._sources:
            return self._sources[self._primary]
        # fallback to first available
        if self._sources:
            return next(iter(self._sources.values()))
        return None

    def connect_all(self) -> Dict[str, bool]:
        """尝试连接所有数据源，返回状态"""
        status = {}
        for name, source in self._sources.items():
            try:
                # 简单验证：调用connect方法
                status[name] = source.connect()
            except Exception:
                status[name] = False
        return status


# 全局单例
data_source_manager = DataSourceManager()


def get_data_source(name: str) -> Optional[BaseDataSource]:
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
        pass

    @abstractmethod
    def get_stock_basic(self, **kwargs) -> pd.DataFrame:
        """获取股票基本信息"""
        pass

    @abstractmethod
    def get_stock_daily(self, ts_code: str = None, start_date: str = None,
                        end_date: str = None, **kwargs) -> pd.DataFrame:
        """获取日线行情"""
        pass

    @abstractmethod
    def get_index_daily(self, ts_code: str = None, start_date: str = None,
                        end_date: str = None, **kwargs) -> pd.DataFrame:
        """获取指数日线行情"""
        pass

    @abstractmethod
    def get_financial_data(self, ts_code: str = None, start_date: str = None,
                           end_date: str = None, **kwargs) -> pd.DataFrame:
        """获取财务数据"""
        pass

    @abstractmethod
    def get_trading_calendar(self, exchange: str = 'SSE',
                             start_date: str = None,
                             end_date: str = None) -> pd.DataFrame:
        """获取交易日历"""
        pass

    def get_index_components(self, index_code: str, trade_date: str = None) -> pd.DataFrame:
        """获取指数成分股"""
        return pd.DataFrame()

    def get_stock_status(self, ts_code: str = None, trade_date: str = None) -> pd.DataFrame:
        """获取股票状态（ST、停牌等）"""
        return pd.DataFrame()

    def get_adj_factor(self, ts_code: str = None, start_date: str = None,
                       end_date: str = None) -> pd.DataFrame:
        """获取复权因子"""
        return pd.DataFrame()

    def get_industry_classification(self, ts_code: str = None,
                                     standard: str = 'sw') -> pd.DataFrame:
        """获取行业分类"""
        return pd.DataFrame()

    # ==================== 增量同步 ====================

    def incremental_sync(self, data_type: str, last_sync_date: date,
                         end_date: date = None) -> SyncResult:
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
            return SyncResult(success=True, records_fetched=0, details={'message': 'Already up to date'})

        return self._sync_range(data_type, start, end_date)

    def _sync_range(self, data_type: str, start_date: date,
                    end_date: date) -> SyncResult:
        """同步指定日期范围的数据"""
        import time
        start_time = time.time()

        try:
            method_map = {
                'stock_daily': self.get_stock_daily,
                'index_daily': self.get_index_daily,
                'financial': self.get_financial_data,
                'stock_basic': self.get_stock_basic,
                'trading_calendar': self.get_trading_calendar,
            }

            method = method_map.get(data_type)
            if not method:
                return SyncResult(success=False, error_message=f"Unknown data type: {data_type}")

            df = method(start_date=start_date.strftime('%Y%m%d'),
                        end_date=end_date.strftime('%Y%m%d'))

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
                    wait = 2 ** attempt  # 指数退避
                    logger.warning(f"Retry {attempt + 1}/{self.max_retries} after {wait}s: {e}")
                    time.sleep(wait)
                else:
                    raise