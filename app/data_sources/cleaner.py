"""
数据清洗器
行情数据质量保障：异常值过滤、停牌处理、OHLC校验、缺失值处理、去重
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import pandas as pd
import numpy as np
from app.core.logging import logger


@dataclass
class CleanReport:
    """清洗报告"""
    original_count: int = 0
    cleaned_count: int = 0
    removed_count: int = 0
    flagged_count: int = 0
    issues: List[Dict] = field(default_factory=list)

    def add_issue(self, issue_type: str, message: str,
                  code: str = None, trade_date: str = None):
        self.issues.append({
            'type': issue_type,
            'ts_code': code,
            'trade_date': trade_date,
            'message': message,
        })

    def summary(self) -> str:
        return (f"CleanReport: {self.original_count} → {self.cleaned_count} "
                f"(removed={self.removed_count}, flagged={self.flagged_count}, "
                f"issues={len(self.issues)})")


class DataCleaner:
    """数据清洗器 — 行情数据质量保障"""

    # A股涨跌停阈值
    NORMAL_LIMIT_PCT = 10.0    # 主板 ±10%
    ST_LIMIT_PCT = 5.0         # ST ±5%
    GEM_LIMIT_PCT = 20.0       # 创业板/科创板 ±20%

    def clean_stock_daily(self, df: pd.DataFrame,
                          code_col: str = 'ts_code') -> Tuple[pd.DataFrame, CleanReport]:
        """
        清洗股票日线行情

        Args:
            df: 标准化后的 DataFrame
            code_col: 股票代码列名

        Returns:
            (清洗后 DataFrame, CleanReport)
        """
        report = CleanReport(original_count=len(df))

        if df.empty:
            return df, report

        df = df.copy()

        # 1. 关键列缺失 → 移除
        df, removed = self._remove_missing_critical(df, ['close', 'volume'], code_col, report)
        report.removed_count += removed

        # 2. 负值过滤
        df, removed = self._remove_negative_values(df, code_col, report)
        report.removed_count += removed

        # 3. OHLC 逻辑校验
        df = self._flag_ohlc_violations(df, code_col, report)

        # 4. 涨跌停异常标记
        df = self._flag_limit_violations(df, code_col, report)

        # 5. 停牌数据标记
        df = self._mark_suspended(df, code_col, report)

        # 6. 非关键列缺失值 → 前值填充
        df = self._fill_non_critical(df, code_col, report)

        # 7. 去重
        df, removed = self._deduplicate(df, code_col, report)
        report.removed_count += removed

        report.cleaned_count = len(df)
        logger.info(report.summary())
        return df, report

    def clean_index_daily(self, df: pd.DataFrame,
                          code_col: str = 'index_code') -> Tuple[pd.DataFrame, CleanReport]:
        """清洗指数日线行情"""
        report = CleanReport(original_count=len(df))

        if df.empty:
            return df, report

        df = df.copy()

        # 1. 关键列缺失 → 移除
        df, removed = self._remove_missing_critical(df, ['close', 'volume'], code_col, report)
        report.removed_count += removed

        # 2. 负值过滤
        df, removed = self._remove_negative_values(df, code_col, report)
        report.removed_count += removed

        # 3. OHLC 逻辑校验
        df = self._flag_ohlc_violations(df, code_col, report)

        # 4. 非关键列缺失值 → 前值填充
        df = self._fill_non_critical(df, code_col, report)

        # 5. 去重
        df, removed = self._deduplicate(df, code_col, report)
        report.removed_count += removed

        report.cleaned_count = len(df)
        logger.info(report.summary())
        return df, report

    def clean_stock_basic(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, CleanReport]:
        """清洗股票基础信息"""
        report = CleanReport(original_count=len(df))

        if df.empty:
            return df, report

        df = df.copy()

        # 1. ts_code 格式校验
        if 'ts_code' in df.columns:
            valid_mask = df['ts_code'].str.match(r'^\d{6}\.(SH|SZ)$', na=False)
            invalid_count = (~valid_mask).sum()
            if invalid_count > 0:
                report.add_issue('invalid_ts_code',
                                 f'Removed {invalid_count} rows with invalid ts_code format')
                df = df[valid_mask]

        # 2. 北交所过滤
        if 'ts_code' in df.columns:
            bj_mask = df['ts_code'].str.startswith('8') | df['ts_code'].str.startswith('4')
            bj_count = bj_mask.sum()
            if bj_count > 0:
                report.add_issue('bj_filtered',
                                 f'Removed {bj_count} Beijing Stock Exchange stocks')
                df = df[~bj_mask]

        # 3. industry 缺失填充
        if 'industry' in df.columns:
            missing = df['industry'].isna().sum()
            if missing > 0:
                df['industry'] = df['industry'].fillna('未知')
                report.add_issue('industry_filled',
                                 f'Filled {missing} missing industry values')

        # 4. 去重
        if 'ts_code' in df.columns:
            before = len(df)
            df = df.drop_duplicates(subset='ts_code', keep='last')
            dup = before - len(df)
            if dup > 0:
                report.add_issue('duplicate_removed',
                                 f'Removed {dup} duplicate ts_code entries')

        report.cleaned_count = len(df)
        report.removed_count = report.original_count - len(df)
        logger.info(report.summary())
        return df, report

    def clean_trading_calendar(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, CleanReport]:
        """清洗交易日历"""
        report = CleanReport(original_count=len(df))

        if df.empty:
            return df, report

        df = df.copy()

        # 1. 关键列缺失 → 移除
        df, removed = self._remove_missing_critical(df, ['trade_date', 'is_open'], None, report)
        report.removed_count += removed

        # 2. 去重
        df, removed = self._deduplicate_by_date(df, report)
        report.removed_count += removed

        report.cleaned_count = len(df)
        logger.info(report.summary())
        return df, report

    # ==================== 内部清洗方法 ====================

    def _remove_missing_critical(self, df: pd.DataFrame, critical_cols: List[str],
                                  code_col: Optional[str],
                                  report: CleanReport) -> Tuple[pd.DataFrame, int]:
        """移除关键列缺失的行"""
        existing_cols = [c for c in critical_cols if c in df.columns]
        if not existing_cols:
            return df, 0

        mask = df[existing_cols].isna().any(axis=1)
        removed = mask.sum()
        if removed > 0:
            for idx in df[mask].index[:10]:  # 最多记录10条
                code = df.loc[idx, code_col] if code_col and code_col in df.columns else None
                trade_date = df.loc[idx, 'trade_date'] if 'trade_date' in df.columns else None
                report.add_issue('missing_critical',
                                 f'Missing critical column value',
                                 code=code, trade_date=trade_date)
            if removed > 10:
                report.add_issue('missing_critical',
                                 f'... and {removed - 10} more rows with missing critical values')
            df = df[~mask].reset_index(drop=True)

        return df, removed

    def _remove_negative_values(self, df: pd.DataFrame,
                                 code_col: Optional[str],
                                 report: CleanReport) -> Tuple[pd.DataFrame, int]:
        """移除价格/成交量为负的行"""
        price_cols = [c for c in ['open', 'high', 'low', 'close', 'pre_close', 'volume']
                      if c in df.columns]
        if not price_cols:
            return df, 0

        mask = (df[price_cols] < 0).any(axis=1)
        removed = mask.sum()
        if removed > 0:
            for idx in df[mask].index[:10]:
                code = df.loc[idx, code_col] if code_col and code_col in df.columns else None
                trade_date = df.loc[idx, 'trade_date'] if 'trade_date' in df.columns else None
                neg_cols = [c for c in price_cols if df.loc[idx, c] < 0]
                report.add_issue('negative_value',
                                 f'Negative values in: {neg_cols}',
                                 code=code, trade_date=trade_date)
            df = df[~mask].reset_index(drop=True)

        return df, removed

    def _flag_ohlc_violations(self, df: pd.DataFrame,
                               code_col: Optional[str],
                               report: CleanReport) -> pd.DataFrame:
        """标记 OHLC 逻辑不一致的行"""
        required = {'open', 'high', 'low', 'close'}
        if not required.issubset(df.columns):
            return df

        # high >= max(open, close)
        # low <= min(open, close)
        max_oc = df[['open', 'close']].max(axis=1)
        min_oc = df[['open', 'close']].min(axis=1)

        high_violation = df['high'] < max_oc
        low_violation = df['low'] > min_oc
        violation = high_violation | low_violation

        if violation.any():
            df['ohlc_flag'] = False
            df.loc[violation, 'ohlc_flag'] = True
            count = violation.sum()
            report.flagged_count += count
            report.add_issue('ohlc_violation',
                             f'Flagged {count} rows with OHLC logic violations')

        return df

    def _flag_limit_violations(self, df: pd.DataFrame,
                                code_col: Optional[str],
                                report: CleanReport) -> pd.DataFrame:
        """标记涨跌停异常（超出正常涨跌幅范围）"""
        if 'pct_chg' not in df.columns:
            return df

        # 判断板块：688开头=科创板，30开头=创业板，其他=主板
        if code_col and code_col in df.columns:
            code = df[code_col].astype(str)
            is_gem = code.str.startswith('688') | code.str.startswith('30')
            limit_pct = pd.Series(self.NORMAL_LIMIT_PCT, index=df.index)
            limit_pct[is_gem] = self.GEM_LIMIT_PCT
        else:
            limit_pct = self.NORMAL_LIMIT_PCT

        # 允许一定误差（浮点精度 + 涨停可能略超）
        tolerance = 0.5
        over_limit = df['pct_chg'].abs() > (limit_pct + tolerance)

        if over_limit.any():
            df['limit_flag'] = False
            df.loc[over_limit, 'limit_flag'] = True
            count = over_limit.sum()
            report.flagged_count += count
            report.add_issue('limit_violation',
                             f'Flagged {count} rows exceeding daily limit')

        return df

    def _mark_suspended(self, df: pd.DataFrame,
                         code_col: Optional[str],
                         report: CleanReport) -> pd.DataFrame:
        """标记停牌数据"""
        if 'volume' not in df.columns or 'close' not in df.columns:
            return df

        # volume == 0 且 close == pre_close 视为停牌
        is_suspended = (df['volume'] == 0)
        if 'pre_close' in df.columns:
            is_suspended = is_suspended & (df['close'] == df['pre_close'])

        df['is_suspended'] = is_suspended
        suspended_count = is_suspended.sum()
        if suspended_count > 0:
            report.add_issue('suspended',
                             f'Marked {suspended_count} suspended trading rows')

        return df

    def _fill_non_critical(self, df: pd.DataFrame,
                            code_col: Optional[str],
                            report: CleanReport) -> pd.DataFrame:
        """非关键列缺失值用前值填充"""
        non_critical = ['open', 'high', 'low', 'pre_close', 'change', 'pct_chg', 'amount']
        fill_cols = [c for c in non_critical if c in df.columns]

        if not fill_cols:
            return df

        missing_before = df[fill_cols].isna().sum().sum()
        if missing_before == 0:
            return df

        # 按股票分组前值填充
        group_col = code_col if code_col and code_col in df.columns else None
        if group_col:
            df[fill_cols] = df.groupby(group_col)[fill_cols].ffill()
        else:
            df[fill_cols] = df[fill_cols].ffill()

        missing_after = df[fill_cols].isna().sum().sum()
        filled = missing_before - missing_after
        if filled > 0:
            report.add_issue('filled_non_critical',
                             f'Forward-filled {filled} non-critical missing values')

        return df

    def _deduplicate(self, df: pd.DataFrame,
                      code_col: Optional[str],
                      report: CleanReport) -> Tuple[pd.DataFrame, int]:
        """按 (code, trade_date) 去重"""
        subset = []
        if code_col and code_col in df.columns:
            subset.append(code_col)
        if 'trade_date' in df.columns:
            subset.append('trade_date')

        if not subset:
            return df, 0

        before = len(df)
        df = df.drop_duplicates(subset=subset, keep='last').reset_index(drop=True)
        removed = before - len(df)
        if removed > 0:
            report.add_issue('duplicate_removed',
                             f'Removed {removed} duplicate rows')

        return df, removed

    def _deduplicate_by_date(self, df: pd.DataFrame,
                              report: CleanReport) -> Tuple[pd.DataFrame, int]:
        """按 trade_date 去重（交易日历）"""
        if 'trade_date' not in df.columns:
            return df, 0

        before = len(df)
        df = df.drop_duplicates(subset='trade_date', keep='last').reset_index(drop=True)
        removed = before - len(df)
        if removed > 0:
            report.add_issue('duplicate_removed',
                             f'Removed {removed} duplicate dates')

        return df, removed
