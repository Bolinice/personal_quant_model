"""
因子引擎模块 - 因子定义管理、因子值存储/查询、IC分析、因子衰减、分组回测
实现ADD 6.3节因子计算、存储、查询、分析全流程
重构: 计算逻辑委托给FactorCalculator，本模块专注DB交互+因子分析
"""
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.logging import logger
from app.core.factor_preprocess import FactorPreprocessor, preprocess_factor_values
from app.core.factor_calculator import FactorCalculator, FACTOR_GROUPS, FACTOR_DIRECTIONS
from app.models.factors import Factor, FactorValue, FactorAnalysis, FactorResult


class FactorEngine:
    """因子引擎 - 因子定义管理 + 因子值存储/查询 + 因子分析"""

    def __init__(self, db: Session):
        self.db = db
        self.preprocessor = FactorPreprocessor()
        self.calculator = FactorCalculator()

    # ==================== 因子定义管理 ====================

    def create_factor(self, factor_code: str, factor_name: str, category: str,
                      direction: int = 1, formula_desc: str = None,
                      calc_expression: str = None, description: str = None,
                      created_by: int = None) -> Factor:
        """创建因子定义"""
        factor = Factor(
            factor_code=factor_code,
            factor_name=factor_name,
            category=category,
            direction=direction,
            formula_desc=formula_desc,
            calc_expression=calc_expression,
            description=description,
            created_by=created_by,
        )
        self.db.add(factor)
        self.db.commit()
        self.db.refresh(factor)
        return factor

    def get_factor(self, factor_id: int) -> Optional[Factor]:
        """获取因子定义"""
        return self.db.query(Factor).filter(Factor.id == factor_id).first()

    def get_factor_by_code(self, factor_code: str) -> Optional[Factor]:
        """根据代码获取因子"""
        return self.db.query(Factor).filter(Factor.factor_code == factor_code).first()

    def list_factors(self, category: str = None, is_active: bool = True) -> List[Factor]:
        """列出因子"""
        query = self.db.query(Factor)
        if category:
            query = query.filter(Factor.category == category)
        if is_active is not None:
            query = query.filter(Factor.is_active == is_active)
        return query.all()

    # ==================== 因子值存储 ====================

    def save_factor_values(self, factor_id: int, trade_date: date,
                           values: pd.DataFrame, run_id: str = None) -> int:
        """批量保存因子值 (优化: to_dict替代iterrows)"""
        records = []
        for row in values.to_dict('records'):
            record = FactorValue(
                factor_id=factor_id,
                trade_date=trade_date,
                security_id=row['security_id'],
                raw_value=row.get('raw_value'),
                processed_value=row.get('processed_value'),
                neutralized_value=row.get('neutralized_value'),
                zscore_value=row.get('zscore_value'),
                value=row.get('zscore_value', row.get('processed_value')),
                run_id=run_id,
            )
            records.append(record)

        self.db.bulk_save_objects(records)
        self.db.commit()
        return len(records)

    def get_factor_values(self, factor_id: int, trade_date: date) -> pd.DataFrame:
        """获取因子值 - 带缓存"""
        from app.core.cache import factor_cache
        cache_key = f"fv:{factor_id}:{trade_date}"
        cached = factor_cache.get(cache_key)
        if cached is not None:
            return cached

        query = self.db.query(FactorValue).filter(
            and_(FactorValue.factor_id == factor_id, FactorValue.trade_date == trade_date)
        )
        results = query.all()
        if not results:
            return pd.DataFrame()
        df = pd.DataFrame([{
            'security_id': r.security_id,
            'raw_value': r.raw_value,
            'processed_value': r.processed_value,
            'neutralized_value': r.neutralized_value,
            'zscore_value': r.zscore_value,
            'value': r.value,
        } for r in results])
        factor_cache.set(cache_key, df)
        return df

    def get_factor_values_range(self, factor_id: int, start_date: date,
                                end_date: date) -> pd.DataFrame:
        """获取因子值时间序列 - 带范围缓存"""
        from app.core.cache import factor_cache
        cache_key = f"fvr:{factor_id}:{start_date}:{end_date}"
        cached = factor_cache.get(cache_key)
        if cached is not None:
            return cached

        query = self.db.query(FactorValue).filter(
            and_(
                FactorValue.factor_id == factor_id,
                FactorValue.trade_date >= start_date,
                FactorValue.trade_date <= end_date,
            )
        )
        results = query.all()
        if not results:
            return pd.DataFrame()
        df = pd.DataFrame([{
            'trade_date': r.trade_date,
            'security_id': r.security_id,
            'value': r.value,
            'zscore_value': r.zscore_value,
        } for r in results])
        factor_cache.set(cache_key, df)
        return df

    # ==================== 因子分析 (合并自FactorAnalyzer) ====================

    def calc_ic(self, factor_values: pd.Series, forward_returns: pd.Series) -> Dict[str, float]:
        """计算因子IC (Pearson + Spearman Rank IC)"""
        valid = ~(factor_values.isna() | forward_returns.isna())
        if valid.sum() < 10:
            return {'ic': np.nan, 'rank_ic': np.nan}

        fv = factor_values[valid]
        fr = forward_returns[valid]

        ic = fv.corr(fr)
        rank_ic = fv.rank().corr(fr.rank())

        return {
            'ic': round(ic, 4) if not np.isnan(ic) else 0,
            'rank_ic': round(rank_ic, 4) if not np.isnan(rank_ic) else 0,
        }

    def calc_ic_series(self, factor_id: int, start_date: date, end_date: date,
                       forward_period: int = 20) -> pd.DataFrame:
        """计算IC时间序列 (向量化: groupby替代逐日期filter)"""
        factor_data = self.get_factor_values_range(factor_id, start_date, end_date)
        if factor_data.empty:
            return pd.DataFrame()

        security_ids = factor_data['security_id'].unique().tolist()
        forward_returns = self._get_forward_returns(
            security_ids, start_date, end_date, forward_period
        )
        if forward_returns.empty:
            return pd.DataFrame()

        fr_long = forward_returns.reset_index().melt(
            id_vars='security_id', var_name='trade_date', value_name='forward_return'
        ).dropna(subset=['forward_return'])

        merged = pd.merge(
            factor_data[['trade_date', 'security_id', 'value']],
            fr_long,
            on=['trade_date', 'security_id'],
            how='inner',
        )
        if merged.empty:
            return pd.DataFrame()

        ic_records = []
        for trade_date, group in merged.groupby('trade_date'):
            if len(group) < 10:
                continue
            fv = group['value']
            fr = group['forward_return']
            valid = ~(fv.isna() | fr.isna())
            if valid.sum() < 10:
                continue
            fv_valid = fv[valid]
            fr_valid = fr[valid]
            ic = fv_valid.corr(fr_valid)
            rank_ic = fv_valid.rank().corr(fr_valid.rank())
            ic_records.append({
                'trade_date': trade_date,
                'factor_id': factor_id,
                'ic': round(ic, 4) if not np.isnan(ic) else 0,
                'rank_ic': round(rank_ic, 4) if not np.isnan(rank_ic) else 0,
                'n_stocks': valid.sum(),
            })

        return pd.DataFrame(ic_records)

    def calc_ic_statistics(self, ic_series: pd.Series) -> Dict[str, Any]:
        """计算IC统计指标 (含Newey-West调整t统计量)"""
        ic_series = ic_series.dropna()
        if len(ic_series) < 2:
            return {'ic_mean': np.nan, 'icir': np.nan}

        naive_t = sp_stats.ttest_1samp(ic_series, 0)[0]
        naive_p = sp_stats.ttest_1samp(ic_series, 0)[1]

        try:
            from app.core.risk_model import newey_west_tstat, newey_west_se
            nw_t = newey_west_tstat(ic_series)
            nw_se = newey_west_se(ic_series)
        except ImportError:
            nw_t = naive_t
            nw_se = ic_series.std() / np.sqrt(len(ic_series))

        return {
            'ic_mean': ic_series.mean(),
            'ic_std': ic_series.std(),
            'icir': ic_series.mean() / ic_series.std() if ic_series.std() > 0 else 0,
            'ic_positive_ratio': (ic_series > 0).mean(),
            'ic_t_stat': naive_t,
            'ic_p_value': naive_p,
            'ic_nw_t_stat': round(nw_t, 4),
            'ic_nw_se': round(nw_se, 6) if not np.isnan(nw_se) else np.nan,
        }

    def calc_factor_decay(self, factor_id: int, trade_date: date,
                          max_lag: int = 20) -> Dict:
        """计算因子衰减 - 一次查询计算所有lag"""
        factor_data = self.get_factor_values(factor_id, trade_date)
        if factor_data.empty:
            return {'factor_id': factor_id, 'trade_date': trade_date, 'decay_values': []}

        fv = factor_data.set_index('security_id')['value']
        security_ids = fv.index.tolist()

        try:
            from app.models.market import StockDaily
            from datetime import timedelta
            query_end = trade_date + timedelta(days=max_lag + 60)

            stocks = self.db.query(StockDaily).filter(
                StockDaily.ts_code.in_(security_ids),
                StockDaily.trade_date >= trade_date,
                StockDaily.trade_date <= query_end,
            ).all()

            if not stocks:
                return {'factor_id': factor_id, 'trade_date': trade_date,
                        'decay_values': [{'lag': lag, 'ic': 0, 'rank_ic': 0} for lag in range(1, max_lag + 1)]}

            price_df = pd.DataFrame([{
                'trade_date': s.trade_date,
                'security_id': s.ts_code,
                'close': float(s.close) if s.close else np.nan,
            } for s in stocks])
            price_df = price_df.dropna(subset=['close']).sort_values(['security_id', 'trade_date'])

        except (ImportError, Exception):
            return {'factor_id': factor_id, 'trade_date': trade_date,
                    'decay_values': [{'lag': lag, 'ic': 0, 'rank_ic': 0} for lag in range(1, max_lag + 1)]}

        decay_values = []
        for lag in range(1, max_lag + 1):
            price_df_lag = price_df.copy()
            price_df_lag['fwd_close'] = price_df_lag.groupby('security_id')['close'].shift(-lag)
            price_df_lag['forward_return'] = price_df_lag['fwd_close'] / price_df_lag['close'] - 1

            day_data = price_df_lag[price_df_lag['trade_date'] == trade_date].dropna(subset=['forward_return'])
            if day_data.empty:
                decay_values.append({'lag': lag, 'ic': 0, 'rank_ic': 0})
                continue

            fr = day_data.set_index('security_id')['forward_return']
            common = fv.index.intersection(fr.index)
            if len(common) < 10:
                decay_values.append({'lag': lag, 'ic': 0, 'rank_ic': 0})
                continue

            fv_common = fv.loc[common]
            fr_common = fr.loc[common]
            valid = ~(fv_common.isna() | fr_common.isna())
            if valid.sum() < 10:
                decay_values.append({'lag': lag, 'ic': 0, 'rank_ic': 0})
                continue

            ic = fv_common[valid].corr(fr_common[valid])
            rank_ic = fv_common[valid].rank().corr(fr_common[valid].rank())

            decay_values.append({
                'lag': lag,
                'ic': round(ic, 4) if not np.isnan(ic) else 0,
                'rank_ic': round(rank_ic, 4) if not np.isnan(rank_ic) else 0,
            })

        return {'factor_id': factor_id, 'trade_date': trade_date, 'decay_values': decay_values}

    def calc_factor_correlation(self, factor_id_a: int, factor_id_b: int,
                                start_date: date, end_date: date) -> Dict:
        """计算两个因子的相关性"""
        values_a = self.get_factor_values_range(factor_id_a, start_date, end_date)
        values_b = self.get_factor_values_range(factor_id_b, start_date, end_date)

        if values_a.empty or values_b.empty:
            return {'correlation': np.nan}

        merged = pd.merge(
            values_a[['trade_date', 'security_id', 'value']],
            values_b[['trade_date', 'security_id', 'value']],
            on=['trade_date', 'security_id'],
            suffixes=('_a', '_b'),
        )

        if merged.empty:
            return {'correlation': np.nan}

        corr = merged['value_a'].corr(merged['value_b'])
        rank_corr = merged['value_a'].rank().corr(merged['value_b'].rank())

        return {
            'correlation': round(corr, 4) if not np.isnan(corr) else 0,
            'rank_correlation': round(rank_corr, 4) if not np.isnan(rank_corr) else 0,
        }

    def group_backtest(self, factor_id: int, start_date: date, end_date: date,
                       n_groups: int = 5, forward_period: int = 20) -> Dict:
        """因子分组回测 (计算各组实际收益 + 多空Sharpe)"""
        factor_data = self.get_factor_values_range(factor_id, start_date, end_date)
        if factor_data.empty:
            return {}

        security_ids = factor_data['security_id'].unique().tolist()
        forward_returns = self._get_forward_returns(
            security_ids, start_date, end_date, forward_period
        )
        if forward_returns.empty:
            return {'factor_id': factor_id, 'n_groups': n_groups, 'group_results': {}}

        group_returns_by_date = {}

        for trade_date in sorted(factor_data['trade_date'].unique()):
            day_data = factor_data[factor_data['trade_date'] == trade_date].copy()
            if trade_date not in forward_returns.columns:
                continue

            day_return = forward_returns[trade_date].dropna()
            day_data = day_data[day_data['security_id'].isin(day_return.index)]

            if len(day_data) < n_groups * 2:
                continue

            day_data = day_data.sort_values('value')
            group_labels = pd.qcut(day_data['value'], n_groups, labels=False, duplicates='drop')
            day_data['group'] = group_labels

            group_returns = {}
            for group_num in range(n_groups):
                group_stocks = day_data[day_data['group'] == group_num]['security_id']
                group_ret = day_return.reindex(group_stocks).mean()
                if not np.isnan(group_ret):
                    group_returns[group_num] = group_ret

            if group_returns:
                group_returns_by_date[trade_date] = group_returns

        if not group_returns_by_date:
            return {'factor_id': factor_id, 'n_groups': n_groups, 'group_results': {}}

        dates = sorted(group_returns_by_date.keys())
        group_cumulative = {g: [1.0] for g in range(n_groups)}
        group_returns_series = {g: [] for g in range(n_groups)}

        for dt in dates:
            for g in range(n_groups):
                ret = group_returns_by_date[dt].get(g, 0)
                group_returns_series[g].append(ret)
                group_cumulative[g].append(group_cumulative[g][-1] * (1 + ret))

        long_short_returns = []
        for dt in dates:
            top_ret = group_returns_by_date[dt].get(n_groups - 1, 0)
            bottom_ret = group_returns_by_date[dt].get(0, 0)
            long_short_returns.append(top_ret - bottom_ret)

        ls_series = pd.Series(long_short_returns)
        ls_sharpe = ls_series.mean() / ls_series.std() * np.sqrt(252 / forward_period) if ls_series.std() > 0 else 0
        ls_cummax = (1 + ls_series).cumprod().cummax()
        ls_dd = ((1 + ls_series).cumprod() - ls_cummax) / ls_cummax
        ls_max_dd = ls_dd.min() if len(ls_dd) > 0 else 0

        group_stats = {}
        for g in range(n_groups):
            rets = pd.Series(group_returns_series[g])
            group_stats[g] = {
                'mean_return': round(rets.mean(), 6) if len(rets) > 0 else 0,
                'cum_return': round(group_cumulative[g][-1] - 1, 4),
                'n_periods': len(rets),
            }

        return {
            'factor_id': factor_id,
            'n_groups': n_groups,
            'group_stats': group_stats,
            'group_returns_series': {g: group_returns_series[g] for g in range(n_groups)},
            'group_cumulative_returns': {g: group_cumulative[g] for g in range(n_groups)},
            'dates': dates,
            'long_short_sharpe': round(ls_sharpe, 2),
            'long_short_max_drawdown': round(ls_max_dd, 4),
            'long_short_mean_return': round(ls_series.mean(), 6) if len(ls_series) > 0 else 0,
        }

    def analyze_factor(self, factor_id: int, start_date: date, end_date: date,
                       forward_period: int = 20) -> Dict:
        """执行完整因子分析 (IC + 分组回测 + 覆盖率)"""
        factor_data = self.get_factor_values_range(factor_id, start_date, end_date)
        if factor_data.empty:
            return {'error': 'No factor values found'}

        # IC分析
        ic_df = self.calc_ic_series(factor_id, start_date, end_date, forward_period)
        ic_stats = {}
        if not ic_df.empty and 'ic' in ic_df.columns:
            ic_stats = self.calc_ic_statistics(ic_df['ic'])

        # 分组回测
        group_result = self.group_backtest(factor_id, start_date, end_date, forward_period=forward_period)

        # 覆盖率
        security_ids = factor_data['security_id'].unique()
        coverage = len(security_ids)

        return {
            'factor_id': factor_id,
            'ic_stats': ic_stats,
            'group_backtest': group_result,
            'coverage': coverage,
            'n_dates': len(factor_data['trade_date'].unique()),
        }

    # ==================== 因子计算 (委托给FactorCalculator) ====================

    def calc_all_factors(self, financial_df: pd.DataFrame, price_df: pd.DataFrame,
                         industry_col: str = None, cap_col: str = None,
                         neutralize: bool = True,
                         northbound_df: pd.DataFrame = None,
                         analyst_df: pd.DataFrame = None,
                         policy_df: pd.DataFrame = None,
                         supply_chain_df: pd.DataFrame = None,
                         sentiment_df: pd.DataFrame = None,
                         stock_basic_df: pd.DataFrame = None,
                         stock_status_df: pd.DataFrame = None) -> pd.DataFrame:
        """计算所有因子并预处理 (委托给FactorCalculator)"""
        return self.calculator.calc_all_factors(
            financial_df, price_df,
            industry_col=industry_col, cap_col=cap_col,
            neutralize=neutralize,
            northbound_df=northbound_df, analyst_df=analyst_df,
            policy_df=policy_df, supply_chain_df=supply_chain_df,
            sentiment_df=sentiment_df,
            stock_basic_df=stock_basic_df, stock_status_df=stock_status_df,
        )

    # ==================== 无数据库便捷函数 ====================

    @staticmethod
    def calc_factors_from_data(price_df: pd.DataFrame,
                               financial_df: pd.DataFrame = None,
                               neutralize: bool = False,
                               industry_col: str = None,
                               cap_col: str = None) -> pd.DataFrame:
        """不依赖数据库的因子计算便捷函数 (委托给FactorCalculator)"""
        return FactorCalculator.calc_factors_from_data(
            price_df, financial_df,
            neutralize=neutralize,
            industry_col=industry_col,
            cap_col=cap_col,
        )

    # ==================== 辅助方法 ====================

    def _get_forward_returns(self, security_ids: List[str],
                              start_date: date, end_date: date,
                              forward_period: int) -> pd.DataFrame:
        """获取前瞻收益 (向量化计算, 仅使用公告日之后数据)"""
        try:
            from app.models.market import StockDaily
        except ImportError:
            return pd.DataFrame()

        if self.db is None:
            return pd.DataFrame()

        from datetime import timedelta
        query_end = end_date + timedelta(days=forward_period + 30)

        stocks = self.db.query(StockDaily).filter(
            StockDaily.ts_code.in_(security_ids),
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= query_end,
        ).all()

        if not stocks:
            return pd.DataFrame()

        price_df = pd.DataFrame([{
            'trade_date': s.trade_date,
            'security_id': s.ts_code,
            'close': float(s.close) if s.close else np.nan,
        } for s in stocks])

        if price_df.empty:
            return pd.DataFrame()

        price_df = price_df.dropna(subset=['close']).sort_values(['security_id', 'trade_date'])
        price_df['fwd_close'] = price_df.groupby('security_id')['close'].shift(-forward_period)
        price_df['forward_return'] = price_df['fwd_close'] / price_df['close'] - 1

        valid = price_df.dropna(subset=['forward_return'])
        if valid.empty:
            return pd.DataFrame()

        pivot = valid.pivot(index='security_id', columns='trade_date', values='forward_return')
        return pivot

    def close(self) -> None:
        if self.db:
            self.db.close()


# 向后兼容: 保留模块级常量
__all__ = ['FactorEngine', 'FactorCalculator', 'FACTOR_GROUPS', 'FACTOR_DIRECTIONS']
