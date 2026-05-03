"""
Tushare数据源适配器 - 使用统一异常处理和重试机制

示例用法:
    from app.data_sources.tushare_source_enhanced import TushareSourceEnhanced

    source = TushareSourceEnhanced(token="your_token")

    # 自动重试网络错误
    daily_data = source.get_stock_daily("000001.SZ", "20240101", "20241231")
"""

import time
from datetime import date
from typing import Any

import pandas as pd
import tushare as ts

from app.core.exceptions import TushareException, DataNotAvailableException
from app.core.retry import retry_on_network_error
from app.core.logging import logger


class TushareSourceEnhanced:
    """
    Tushare数据源增强版

    特性:
    - 自动重试网络错误
    - 统一异常处理
    - 速率限制保护
    - 详细错误上下文
    """

    def __init__(
        self,
        token: str,
        proxy_url: str | None = None,
        rate_limit_delay: float = 0.2,  # 每次请求间隔200ms，避免触发限流
    ):
        """
        Args:
            token: Tushare API token
            proxy_url: 代理服务器URL（可选）
            rate_limit_delay: 请求间隔（秒）
        """
        if not token:
            raise TushareException(
                message="Tushare token未设置",
                context={"hint": "请在.env中设置TUSHARE_TOKEN"}
            )

        self.token = token
        self.proxy_url = proxy_url
        self.rate_limit_delay = rate_limit_delay
        self.api = ts.pro_api(token)
        self._last_request_time = 0.0

    def _rate_limit(self):
        """速率限制：确保请求间隔不小于rate_limit_delay"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    @retry_on_network_error(max_attempts=3, min_wait=2, max_wait=10)
    def get_stock_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        获取股票日线数据（自动重试）

        Args:
            ts_code: 股票代码（例如：000001.SZ）
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）

        Returns:
            日线数据DataFrame

        Raises:
            TushareException: 数据获取失败
            DataNotAvailableException: 数据不可用（停牌/退市）
        """
        self._rate_limit()

        try:
            df = self.api.daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )

            if df is None or df.empty:
                raise DataNotAvailableException(
                    message=f"股票 {ts_code} 在 {start_date}-{end_date} 期间无数据",
                    context={
                        "ts_code": ts_code,
                        "start_date": start_date,
                        "end_date": end_date,
                        "reason": "可能已退市或停牌"
                    }
                )

            logger.info(f"获取 {ts_code} 日线数据成功: {len(df)} 条")
            return df

        except DataNotAvailableException:
            raise
        except Exception as e:
            raise TushareException(
                message=f"获取股票日线数据失败: {ts_code}",
                context={
                    "ts_code": ts_code,
                    "start_date": start_date,
                    "end_date": end_date,
                    "error": str(e),
                }
            ) from e

    @retry_on_network_error(max_attempts=3, min_wait=2, max_wait=10)
    def get_financial_data(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        report_type: str = "1",  # 1:合并报表 2:单季度
    ) -> pd.DataFrame:
        """
        获取财务数据（自动重试）

        Args:
            ts_code: 股票代码
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
            report_type: 报表类型

        Returns:
            财务数据DataFrame

        Raises:
            TushareException: 数据获取失败
        """
        self._rate_limit()

        try:
            df = self.api.income(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                report_type=report_type,
            )

            if df is None or df.empty:
                logger.warning(f"股票 {ts_code} 在 {start_date}-{end_date} 期间无财务数据")
                return pd.DataFrame()

            logger.info(f"获取 {ts_code} 财务数据成功: {len(df)} 条")
            return df

        except Exception as e:
            raise TushareException(
                message=f"获取财务数据失败: {ts_code}",
                context={
                    "ts_code": ts_code,
                    "start_date": start_date,
                    "end_date": end_date,
                    "report_type": report_type,
                    "error": str(e),
                }
            ) from e

    @retry_on_network_error(max_attempts=3, min_wait=2, max_wait=10)
    def get_stock_basic(self, list_status: str = "L") -> pd.DataFrame:
        """
        获取股票基础信息（自动重试）

        Args:
            list_status: 上市状态（L:上市 D:退市 P:暂停上市）

        Returns:
            股票基础信息DataFrame

        Raises:
            TushareException: 数据获取失败
        """
        self._rate_limit()

        try:
            df = self.api.stock_basic(list_status=list_status)

            if df is None or df.empty:
                raise TushareException(
                    message="获取股票基础信息失败: 返回空数据",
                    context={"list_status": list_status}
                )

            logger.info(f"获取股票基础信息成功: {len(df)} 只股票")
            return df

        except TushareException:
            raise
        except Exception as e:
            raise TushareException(
                message="获取股票基础信息失败",
                context={
                    "list_status": list_status,
                    "error": str(e),
                }
            ) from e

    @retry_on_network_error(max_attempts=3, min_wait=2, max_wait=10)
    def get_trade_calendar(self, start_date: str, end_date: str, exchange: str = "SSE") -> pd.DataFrame:
        """
        获取交易日历（自动重试）

        Args:
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
            exchange: 交易所（SSE:上交所 SZSE:深交所）

        Returns:
            交易日历DataFrame

        Raises:
            TushareException: 数据获取失败
        """
        self._rate_limit()

        try:
            df = self.api.trade_cal(
                start_date=start_date,
                end_date=end_date,
                exchange=exchange,
            )

            if df is None or df.empty:
                raise TushareException(
                    message="获取交易日历失败: 返回空数据",
                    context={
                        "start_date": start_date,
                        "end_date": end_date,
                        "exchange": exchange,
                    }
                )

            logger.info(f"获取交易日历成功: {len(df)} 天")
            return df

        except TushareException:
            raise
        except Exception as e:
            raise TushareException(
                message="获取交易日历失败",
                context={
                    "start_date": start_date,
                    "end_date": end_date,
                    "exchange": exchange,
                    "error": str(e),
                }
            ) from e
