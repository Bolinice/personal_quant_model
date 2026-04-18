"""
数据标准化器
统一多数据源输出格式，确保列名、日期、数值类型、口径标注一致
"""
from typing import Optional
import pandas as pd
import numpy as np
from app.core.logging import logger


class DataNormalizer:
    """数据标准化器 — 统一多数据源输出格式"""

    # 统一输出列定义
    STOCK_DAILY_COLUMNS = [
        'trade_date', 'open', 'high', 'low', 'close',
        'pre_close', 'change', 'pct_chg', 'volume', 'amount',
    ]
    INDEX_DAILY_COLUMNS = STOCK_DAILY_COLUMNS
    STOCK_BASIC_COLUMNS = [
        'ts_code', 'symbol', 'name', 'industry', 'market',
        'list_date', 'status',
    ]
    TRADING_CALENDAR_COLUMNS = ['trade_date', 'is_open', 'pretrade_date']

    # 成交额为估算值的数据源
    AMOUNT_ESTIMATED_SOURCES = {'akshare', 'crawler'}

    def normalize_stock_daily(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """
        标准化股票日线行情

        Args:
            df: 原始 DataFrame
            source: 数据源名称 ('tushare', 'akshare', 'crawler')
        """
        if df.empty:
            return df

        df = df.copy()

        # 1. 列名统一
        column_map = {'vol': 'volume'}
        df.rename(columns=column_map, inplace=True)

        # 2. 日期格式统一 → YYYY-MM-DD 字符串
        df['trade_date'] = self._normalize_date_column(df['trade_date'])

        # 3. 数值类型统一
        numeric_cols = ['open', 'high', 'low', 'close', 'pre_close',
                        'change', 'pct_chg', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 4. 计算 change（如果缺失）
        if 'change' not in df.columns or df['change'].isna().all():
            if 'close' in df.columns and 'pre_close' in df.columns:
                df['change'] = df['close'] - df['pre_close']

        # 5. 口径标注
        df['data_source'] = source
        df['amount_is_estimated'] = source in self.AMOUNT_ESTIMATED_SOURCES

        # 6. 只保留标准列 + 标注列
        keep_cols = [c for c in self.STOCK_DAILY_COLUMNS if c in df.columns]
        extra_cols = ['data_source', 'amount_is_estimated']
        # 保留 ts_code 如果存在（批量获取时）
        if 'ts_code' in df.columns:
            extra_cols.insert(0, 'ts_code')
        df = df[extra_cols + keep_cols]

        # 7. 排序
        if 'trade_date' in df.columns:
            df = df.sort_values('trade_date').reset_index(drop=True)

        return df

    def normalize_index_daily(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """标准化指数日线行情"""
        if df.empty:
            return df

        df = df.copy()

        # 列名统一
        column_map = {'vol': 'volume'}
        df.rename(columns=column_map, inplace=True)

        # 日期格式统一
        df['trade_date'] = self._normalize_date_column(df['trade_date'])

        # 数值类型统一
        numeric_cols = ['open', 'high', 'low', 'close', 'pre_close',
                        'change', 'pct_chg', 'volume', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 计算 change
        if 'change' not in df.columns or df['change'].isna().all():
            if 'close' in df.columns and 'pre_close' in df.columns:
                df['change'] = df['close'] - df['pre_close']

        # 口径标注
        df['data_source'] = source
        df['amount_is_estimated'] = source in self.AMOUNT_ESTIMATED_SOURCES

        # 只保留标准列 + 标注列
        keep_cols = [c for c in self.INDEX_DAILY_COLUMNS if c in df.columns]
        extra_cols = ['data_source', 'amount_is_estimated']
        if 'index_code' in df.columns:
            extra_cols.insert(0, 'index_code')
        df = df[extra_cols + keep_cols]

        # 排序
        if 'trade_date' in df.columns:
            df = df.sort_values('trade_date').reset_index(drop=True)

        return df

    def normalize_stock_basic(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """标准化股票基础信息"""
        if df.empty:
            return df

        df = df.copy()

        # 列名统一
        column_map = {'list_status': 'status'}
        df.rename(columns=column_map, inplace=True)

        # ts_code 格式校验与统一
        if 'ts_code' in df.columns:
            df['ts_code'] = df['ts_code'].str.upper().str.strip()

        # industry 缺失填充
        if 'industry' in df.columns:
            df['industry'] = df['industry'].fillna('未知')

        # list_date 格式统一
        if 'list_date' in df.columns:
            df['list_date'] = self._normalize_date_column(df['list_date'])

        # 只保留标准列
        keep_cols = [c for c in self.STOCK_BASIC_COLUMNS if c in df.columns]
        df = df[keep_cols]

        return df

    def normalize_trading_calendar(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """标准化交易日历"""
        if df.empty:
            return df

        df = df.copy()

        # 列名统一
        column_map = {'cal_date': 'trade_date'}
        df.rename(columns=column_map, inplace=True)

        # 日期格式统一
        df['trade_date'] = self._normalize_date_column(df['trade_date'])
        if 'pretrade_date' in df.columns:
            df['pretrade_date'] = self._normalize_date_column(df['pretrade_date'])

        # is_open 类型统一
        if 'is_open' in df.columns:
            df['is_open'] = df['is_open'].astype(int)

        # 只保留标准列
        keep_cols = [c for c in self.TRADING_CALENDAR_COLUMNS if c in df.columns]
        df = df[keep_cols]

        # 排序
        if 'trade_date' in df.columns:
            df = df.sort_values('trade_date').reset_index(drop=True)

        return df

    # ==================== 内部工具方法 ====================

    def _normalize_date_column(self, series: pd.Series) -> pd.Series:
        """将日期列统一为 YYYY-MM-DD 字符串格式"""
        if series.empty:
            return series

        # 尝试转为 datetime 再格式化
        try:
            dt = pd.to_datetime(series, format='mixed', errors='coerce')
            return dt.dt.strftime('%Y-%m-%d')
        except Exception:
            pass

        # 兜底：字符串处理 YYYYMMDD → YYYY-MM-DD
        def _format_date(val):
            if pd.isna(val):
                return None
            s = str(val).strip()
            if len(s) == 8 and s.isdigit():
                return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            return s

        return series.apply(_format_date)
