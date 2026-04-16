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
        计算IC时间序列

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
        ic_series = {}

        for i, date in enumerate(dates[:-1]):
            next_date = dates[i + 1]

            factor_today = factor_df[factor_df[date_col] == date].set_index(security_col)[factor_col]
            return_next = return_df[return_df[date_col] == next_date].set_index(security_col)[return_col]

            ic = self.calc_ic(factor_today, return_next)
            ic_series[date] = ic

        return pd.Series(ic_series)

    def calc_ic_statistics(self, ic_series: pd.Series) -> Dict:
        """
        计算IC统计指标

        Args:
            ic_series: IC时间序列

        Returns:
            IC统计指标字典
        """
        ic_series = ic_series.dropna()

        return {
            'ic_mean': ic_series.mean(),
            'ic_std': ic_series.std(),
            'icir': ic_series.mean() / ic_series.std() if ic_series.std() > 0 else 0,
            'ic_positive_ratio': (ic_series > 0).mean(),
            'ic_t_stat': stats.ttest_1samp(ic_series, 0)[0] if len(ic_series) > 1 else 0,
            'ic_p_value': stats.ttest_1samp(ic_series, 0)[1] if len(ic_series) > 1 else 1,
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
        计算分组收益时间序列

        Args:
            factor_df: 因子数据框
            return_df: 收益率数据框
            n_groups: 分组数量

        Returns:
            分组收益时间序列
        """
        dates = sorted(factor_df['trade_date'].unique())
        results = []

        for i, date in enumerate(dates[:-1]):
            next_date = dates[i + 1]

            factor_today = factor_df[factor_df['trade_date'] == date]
            return_next = return_df[return_df['trade_date'] == next_date]

            merged = factor_today.merge(return_next, on='ts_code', how='inner')

            if len(merged) < n_groups * 2:
                continue

            group_returns, _ = self.calc_group_returns(
                merged['value'], merged['pct_chg'], n_groups
            )

            group_returns.name = date
            results.append(group_returns)

        return pd.DataFrame(results)

    # ==================== 因子衰减分析 ====================

    def calc_ic_decay(self, factor_values: pd.Series, returns_df: pd.DataFrame,
                      max_lag: int = 20, date_col: str = 'trade_date',
                      security_col: str = 'ts_code', return_col: str = 'pct_chg') -> pd.Series:
        """
        计算IC衰减

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

        for lag in range(1, max_lag + 1):
            # 获取滞后期的收益率
            lag_returns = returns_df.groupby(security_col).apply(
                lambda x: x.sort_values(date_col)[return_col].shift(-lag)
            ).reset_index(level=0, drop=True)

            ic = self.calc_ic(factor_values, lag_returns)
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
