"""
数据源适配器基类
定义统一的数据接口规范
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import pandas as pd
from app.core.logging import logger


class BaseDataSource(ABC):
    """数据源基类"""

    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self._connected = False

    @abstractmethod
    def connect(self) -> bool:
        """连接数据源"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass

    # ==================== 行情数据 ====================

    @abstractmethod
    def get_stock_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取股票日线行情

        Args:
            ts_code: 股票代码 (如 '600000.SH')
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            DataFrame with columns: trade_date, open, high, low, close, volume, amount, pct_chg
        """
        pass

    @abstractmethod
    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取指数日线行情

        Args:
            index_code: 指数代码 (如 '000300.SH')
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with columns: trade_date, open, high, low, close, volume, amount, pct_chg
        """
        pass

    @abstractmethod
    def get_stock_daily_batch(self, ts_codes: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """
        批量获取多只股票日线行情

        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with columns: ts_code, trade_date, open, high, low, close, volume, amount, pct_chg
        """
        pass

    # ==================== 基础数据 ====================

    @abstractmethod
    def get_stock_basic(self) -> pd.DataFrame:
        """
        获取股票基础信息

        Returns:
            DataFrame with columns: ts_code, symbol, name, industry, market, list_date, status
        """
        pass

    @abstractmethod
    def get_index_components(self, index_code: str, date: str = None) -> List[str]:
        """
        获取指数成分股

        Args:
            index_code: 指数代码
            date: 日期 (可选，默认最新)

        Returns:
            成分股代码列表
        """
        pass

    @abstractmethod
    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取交易日历

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with columns: trade_date, is_open, pretrade_date
        """
        pass

    # ==================== 财务数据 ====================

    @abstractmethod
    def get_financial_indicator(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取财务指标

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with columns: end_date, roe, roa, grossprofit_margin, netprofit_margin, etc.
        """
        pass

    @abstractmethod
    def get_income_statement(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取利润表

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with income statement data
        """
        pass

    @abstractmethod
    def get_balance_sheet(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取资产负债表

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with balance sheet data
        """
        pass

    # ==================== 行业数据 ====================

    @abstractmethod
    def get_industry_classification(self, ts_code: str = None) -> pd.DataFrame:
        """
        获取行业分类

        Args:
            ts_code: 股票代码 (可选，不传则返回全部)

        Returns:
            DataFrame with columns: ts_code, industry, industry_name
        """
        pass

    # ==================== 复权数据 ====================

    @abstractmethod
    def get_adj_factor(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取复权因子

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with columns: trade_date, adj_factor
        """
        pass

    def get_stock_daily_adj(self, ts_code: str, start_date: str, end_date: str,
                            adj: str = 'qfq') -> pd.DataFrame:
        """
        获取复权后的股票日线行情

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            adj: 复权类型 ('qfq'-前复权, 'hfq'-后复权, None-不复权)

        Returns:
            复权后的行情数据
        """
        # 获取原始行情
        daily = self.get_stock_daily(ts_code, start_date, end_date)

        if daily.empty or adj is None:
            return daily

        # 获取复权因子
        adj_factor = self.get_adj_factor(ts_code, start_date, end_date)

        if adj_factor.empty:
            return daily

        # 合并复权因子
        daily = daily.merge(adj_factor, on='trade_date', how='left')

        # 应用复权
        if adj == 'qfq':  # 前复权
            # 使用最新的复权因子作为基准
            latest_factor = adj_factor['adj_factor'].iloc[-1]
            daily['adj_factor'] = daily['adj_factor'] / latest_factor
        # 后复权使用原始因子

        # 复权计算
        for col in ['open', 'high', 'low', 'close']:
            daily[col] = daily[col] * daily['adj_factor']

        return daily.drop(columns=['adj_factor'])


class DataSourceManager:
    """数据源管理器"""

    def __init__(self):
        self._sources: Dict[str, BaseDataSource] = {}
        self._primary_source: str = None

    def register(self, name: str, source: BaseDataSource, is_primary: bool = False):
        """注册数据源"""
        self._sources[name] = source
        if is_primary or self._primary_source is None:
            self._primary_source = name

    def get(self, name: str = None) -> BaseDataSource:
        """获取数据源"""
        if name:
            return self._sources.get(name)
        return self._sources.get(self._primary_source)

    def get_available_sources(self) -> List[str]:
        """获取可用数据源列表"""
        return list(self._sources.keys())

    def connect_all(self) -> Dict[str, bool]:
        """连接所有数据源"""
        results = {}
        for name, source in self._sources.items():
            try:
                results[name] = source.connect()
            except Exception as e:
                logger.error(f"Failed to connect {name}: {e}")
                results[name] = False
        return results


# 全局数据源管理器
data_source_manager = DataSourceManager()


def get_data_source(name: str = None) -> BaseDataSource:
    """获取数据源的便捷函数"""
    return data_source_manager.get(name)
