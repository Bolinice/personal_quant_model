"""
因子分析模块
实现IC分析、分层回测、因子相关性、因子衰减分析等功能
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, with_db
from app.models.factors import Factor, FactorValue, FactorAnalysis
from app.models.market import StockDaily
from app.core.logging import logger


class FactorAnalyzer:
    """因子分析器"""

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    # ==================== IC分析 ====================

    def calc_ic(self, factor_values: pd.Series, returns: pd.Series) -> float:
        """
        计算IC（Information Coefficient）
        IC = corr(因子值, 下期收益率)

        Args:
            factor_values: 因子值序列
            returns: 下期收益率序列

        Returns:
            IC值
        """
        # 对齐数据
        aligned = pd.DataFrame({
            'factor': factor_values,
            'return': returns
        }).dropna()

        if len(aligned) < 10:
            return np.nan

        return aligned['factor'].corr(aligned['return'], method='pearson')

    def calc_rank_ic(self, factor_values: pd.Series, returns: pd.Series) -> float:
        """
        计算Rank IC
        Rank IC = corr(rank(因子值), rank(下期收益率))

        Args:
            factor_values: 因子值序列
            returns: 下期收益率序列

        Returns:
            Rank IC值
        """
        aligned = pd.DataFrame({
            'factor': factor_values,
            'return': returns
        }).dropna()

        if len(aligned) < 10:
            return np.nan

        return aligned['factor'].rank().corr(aligned['return'].rank(), method='pearson')

    def calc_ic_series(self, factor_df: pd.DataFrame, return_df: pd.DataFrame,
                       date_col: str = 'trade_date', security_col: str = 'ts_code',
                       factor_col: str = 'value', return_col: str = 'pct_chg') -> pd.Series:
        """
        计算IC时间序列 (向量化: merge+groupby，避免逐日期filter)
        IC = corr(因子值_t, 收益率_{t+1})

        Args:
            factor_df: 因子数据框，包含日期、股票代码、因子值
            return_df: 收益率数据框，包含日期、股票代码、收益率
            date_col: 日期列名
            security_col: 股票代码列名
            factor_col: 因子值列名
            return_col: 收益率列名

        Returns:
            IC时间序列
        """
        dates = sorted(factor_df[date_col].unique())
        if len(dates) < 2:
            return pd.Series()

        # 构建日期映射: factor_date -> next_date (前瞻收益)
        date_to_next = {dates[i]: dates[i + 1] for i in range(len(dates) - 1)}

        # 给return_df标记对应的factor_date
        return_df_shifted = return_df.copy()
        # 反向映射: next_date -> factor_date
        next_to_date = {v: k for k, v in date_to_next.items()}
        return_df_shifted['_factor_date'] = return_df_shifted[date_col].map(next_to_date)
        return_df_shifted = return_df_shifted.dropna(subset=['_factor_date'])

        if return_df_shifted.empty:
            return pd.Series()

        # 向量化: merge factor at date with return at date+1
        merged = pd.merge(
            factor_df[[date_col, security_col, factor_col]],
            return_df_shifted[['_factor_date', security_col, return_col]],
            left_on=[date_col, security_col],
            right_on=['_factor_date', security_col],
            how='inner',
        ).drop(columns=['_factor_date'])

        if merged.empty:
            return pd.Series()

        # 按日期分组计算IC
        ic_series = {}
        for dt, group in merged.groupby(date_col):
            if len(group) < 10:
                continue
            ic = group[factor_col].corr(group[return_col], method='pearson')
            ic_series[dt] = ic

        return pd.Series(ic_series)

    def calc_ic_statistics(self, ic_series: pd.Series) -> Dict:
        """
        计算IC统计指标 (机构级: Newey-West调整t统计量)

        Args:
            ic_series: IC时间序列

        Returns:
            IC统计指标字典
        """
        ic_series = ic_series.dropna()

        # 朴素t统计量
        naive_t = stats.ttest_1samp(ic_series, 0)[0] if len(ic_series) > 1 else 0
        naive_p = stats.ttest_1samp(ic_series, 0)[1] if len(ic_series) > 1 else 1

        # Newey-West调整t统计量 (修正IC序列自相关)
        try:
            from app.core.risk_model import newey_west_tstat, newey_west_se
            nw_t = newey_west_tstat(ic_series)
            nw_se = newey_west_se(ic_series)
        except ImportError:
            nw_t = naive_t
            nw_se = ic_series.std() / np.sqrt(len(ic_series)) if len(ic_series) > 0 else np.nan

        return {
            'ic_mean': ic_series.mean(),
            'ic_std': ic_series.std(),
            'icir': ic_series.mean() / ic_series.std() if ic_series.std() > 0 else 0,
            'ic_positive_ratio': (ic_series > 0).mean(),
            'ic_t_stat': naive_t,
            'ic_p_value': naive_p,
            'ic_nw_t_stat': round(nw_t, 4),  # Newey-West调整t统计量
            'ic_nw_se': round(nw_se, 6) if not np.isnan(nw_se) else np.nan,
        }

    # ==================== 分层回测 ====================

    def calc_group_returns(self, factor_values: pd.Series, returns: pd.Series,
                           n_groups: int = 10) -> Tuple[pd.Series, float]:
        """
        分层回测（分组收益）

        Args:
            factor_values: 因子值序列
            returns: 下期收益率序列
            n_groups: 分组数量，默认10组

        Returns:
            (各组平均收益, 多空收益)
        """
        aligned = pd.DataFrame({
            'factor': factor_values,
            'return': returns
        }).dropna()

        if len(aligned) < n_groups * 2:
            return pd.Series(), np.nan

        # 按因子值分组
        aligned['group'] = pd.qcut(aligned['factor'], n_groups, labels=False, duplicates='drop')

        # 计算各组平均收益
        group_returns = aligned.groupby('group')['return'].mean()

        # 多空收益 = 最高组 - 最低组
        long_short = group_returns.iloc[-1] - group_returns.iloc[0]

        return group_returns, long_short

    def calc_group_returns_series(self, factor_df: pd.DataFrame, return_df: pd.DataFrame,
                                  n_groups: int = 10) -> pd.DataFrame:
        """
        计算分组收益时间序列 (向量化: merge+groupby，避免逐日期filter)
        因子值_t 与 收益率_{t+1} 分组

        Args:
            factor_df: 因子数据框
            return_df: 收益率数据框
            n_groups: 分组数量

        Returns:
            分组收益时间序列
        """
        dates = sorted(factor_df['trade_date'].unique())
        if len(dates) < 2:
            return pd.DataFrame()

        # 构建日期映射: factor_date -> next_date
        date_to_next = {dates[i]: dates[i + 1] for i in range(len(dates) - 1)}
        next_to_date = {v: k for k, v in date_to_next.items()}

        return_df_shifted = return_df.copy()
        return_df_shifted['_factor_date'] = return_df_shifted['trade_date'].map(next_to_date)
        return_df_shifted = return_df_shifted.dropna(subset=['_factor_date'])

        if return_df_shifted.empty:
            return pd.DataFrame()

        # 向量化: merge
        merged = factor_df[['trade_date', 'ts_code', 'value']].merge(
            return_df_shifted[['_factor_date', 'ts_code', 'pct_chg']],
            left_on=['trade_date', 'ts_code'],
            right_on=['_factor_date', 'ts_code'],
            how='inner',
        ).drop(columns=['_factor_date'])

        if merged.empty:
            return pd.DataFrame()

        # 按日期分组，每组内按因子值分位数分组
        def _qcut_group(s):
            if len(s) < n_groups * 2:
                return pd.Series(pd.NA, index=s.index)
            try:
                return pd.qcut(s, n_groups, labels=False, duplicates='drop')
            except ValueError:
                return pd.Series(pd.NA, index=s.index)

        merged['_group'] = merged.groupby('trade_date')['value'].transform(_qcut_group)
        merged = merged.dropna(subset=['_group'])
        merged['_group'] = merged['_group'].astype(int)

        # 按日期+分组计算平均收益
        group_returns = merged.groupby(['trade_date', '_group'])['pct_chg'].mean().unstack('_group')
        return group_returns

    # ==================== 因子衰减分析 ====================

    def calc_ic_decay(self, factor_values: pd.Series, returns_df: pd.DataFrame,
                      max_lag: int = 20, date_col: str = 'trade_date',
                      security_col: str = 'ts_code', return_col: str = 'pct_chg') -> pd.Series:
        """
        计算IC衰减 (向量化: 一次排序，逐lag仅shift+corr)

        Args:
            factor_values: 当期因子值
            returns_df: 收益率数据框（多期）
            max_lag: 最大滞后期
            date_col: 日期列名
            security_col: 股票代码列名
            return_col: 收益率列名

        Returns:
            各滞后期的IC值
        """
        ic_decay = {}
        # 预排序一次
        sorted_returns = returns_df.sort_values([security_col, date_col])

        for lag in range(1, max_lag + 1):
            # 向量化shift
            lag_returns = sorted_returns.groupby(security_col)[return_col].shift(-lag)
            # 对齐index
            aligned_idx = factor_values.index.intersection(lag_returns.dropna().index)
            if len(aligned_idx) < 10:
                ic_decay[f'lag_{lag}'] = np.nan
                continue
            ic = factor_values.loc[aligned_idx].corr(lag_returns.loc[aligned_idx])
            ic_decay[f'lag_{lag}'] = ic

        return pd.Series(ic_decay)

    # ==================== 因子相关性分析 ====================

    def calc_factor_correlation(self, factor_values_1: pd.Series, factor_values_2: pd.Series) -> float:
        """
        计算两个因子的相关性

        Args:
            factor_values_1: 因子1值
            factor_values_2: 因子2值

        Returns:
            相关系数
        """
        aligned = pd.DataFrame({
            'factor1': factor_values_1,
            'factor2': factor_values_2
        }).dropna()

        if len(aligned) < 10:
            return np.nan

        return aligned['factor1'].corr(aligned['factor2'])

    def calc_factor_correlation_matrix(self, factor_df: pd.DataFrame,
                                       factor_cols: List[str]) -> pd.DataFrame:
        """
        计算因子相关性矩阵

        Args:
            factor_df: 因子数据框
            factor_cols: 因子列名列表

        Returns:
            相关性矩阵
        """
        return factor_df[factor_cols].corr()

    # ==================== 因子覆盖率分析 ====================

    def calc_coverage(self, factor_values: pd.Series, total_stocks: int) -> float:
        """
        计算因子覆盖率

        Args:
            factor_values: 因子值序列
            total_stocks: 总股票数

        Returns:
            覆盖率
        """
        valid_count = factor_values.notna().sum()
        return valid_count / total_stocks if total_stocks > 0 else 0

    # ==================== 完整因子分析 ====================

    def analyze_factor(self, factor_id: int, start_date: str, end_date: str) -> Dict:
        """
        执行完整的因子分析

        Args:
            factor_id: 因子ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            分析结果字典
        """
        # 获取因子值
        factor_values = self.db.query(FactorValue).filter(
            FactorValue.factor_id == factor_id,
            FactorValue.trade_date >= start_date,
            FactorValue.trade_date <= end_date
        ).all()

        if not factor_values:
            return {'error': 'No factor values found'}

        # 转换为DataFrame
        factor_df = pd.DataFrame([{
            'trade_date': fv.trade_date,
            'ts_code': fv.security_id,
            'value': fv.value
        } for fv in factor_values])

        # 获取收益率数据
        ts_codes = factor_df['ts_code'].unique().tolist()
        returns = self.db.query(StockDaily).filter(
            StockDaily.ts_code.in_(ts_codes),
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date
        ).all()

        if not returns:
            return {'error': 'No return data found'}

        return_df = pd.DataFrame([{
            'trade_date': r.trade_date,
            'ts_code': r.ts_code,
            'pct_chg': float(r.pct_chg) / 100 if r.pct_chg else None
        } for r in returns])

        # 计算IC序列
        ic_series = self.calc_ic_series(factor_df, return_df)
        ic_stats = self.calc_ic_statistics(ic_series)

        # 计算分组收益
        group_returns = self.calc_group_returns_series(factor_df, return_df)

        # 计算多空收益
        long_short_returns = group_returns.iloc[:, -1] - group_returns.iloc[:, 0]

        return {
            'ic_mean': ic_stats['ic_mean'],
            'ic_std': ic_stats['ic_std'],
            'icir': ic_stats['icir'],
            'ic_positive_ratio': ic_stats['ic_positive_ratio'],
            'group_returns_mean': group_returns.mean().to_dict(),
            'long_short_mean': long_short_returns.mean(),
            'long_short_std': long_short_returns.std(),
            'coverage': self.calc_coverage(factor_df['value'], len(ts_codes)),
        }

    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()


# 便捷函数
def run_factor_analysis(factor_id: int, start_date: str, end_date: str,
                        analysis_type: str = 'ic') -> Dict:
    """
    运行因子分析

    Args:
        factor_id: 因子ID
        start_date: 开始日期
        end_date: 结束日期
        analysis_type: 分析类型 ('ic', 'group', 'decay', 'all')

    Returns:
        分析结果
    """
    analyzer = FactorAnalyzer()
    return analyzer.analyze_factor(factor_id, start_date, end_date)
