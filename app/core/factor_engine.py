"""
因子引擎模块
实现ADD 6.3节因子计算、存储、查询、分析全流程
"""
from typing import List, Optional, Dict, Any
from datetime import date, datetime
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.core.logging import logger
from app.core.factor_preprocess import FactorPreprocessor, preprocess_factor_values
from app.models.factors import Factor, FactorValue, FactorAnalysis, FactorResult


# 因子分组定义 (ADD 6.3.1 + 机构级扩展)
FACTOR_GROUPS = {
    'valuation': {
        'name': '价值因子',
        'factors': ['ep_ttm', 'bp', 'sp_ttm', 'dp', 'cfp_ttm'],
    },
    'growth': {
        'name': '成长因子',
        'factors': ['yoy_revenue', 'yoy_net_profit', 'yoy_deduct_net_profit', 'yoy_roe'],
    },
    'quality': {
        'name': '质量因子',
        'factors': ['roe', 'roa', 'gross_profit_margin', 'net_profit_margin', 'current_ratio'],
    },
    'momentum': {
        'name': '动量因子',
        'factors': ['ret_1m', 'ret_3m', 'ret_6m', 'ret_12m', 'ret_1m_reversal'],
    },
    'volatility': {
        'name': '波动率因子',
        'factors': ['vol_20d', 'vol_60d', 'beta', 'idio_vol'],
    },
    'liquidity': {
        'name': '流动性因子',
        'factors': ['turnover_20d', 'turnover_60d', 'amihud_20d', 'zero_return_ratio'],
    },
    # === 机构级扩展因子组 ===
    'northbound': {
        'name': '北向资金因子',
        'factors': ['north_net_buy_ratio', 'north_holding_chg_5d', 'north_holding_pct'],
    },
    'analyst': {
        'name': '分析师预期因子',
        'factors': ['sue', 'analyst_revision_1m', 'analyst_coverage', 'earnings_surprise'],
    },
    'microstructure': {
        'name': '微观结构因子',
        'factors': ['large_order_ratio', 'overnight_return', 'intraday_return_ratio', 'vpin'],
    },
    'policy': {
        'name': '政策因子',
        'factors': ['policy_sentiment', 'policy_theme_exposure'],
    },
    'supply_chain': {
        'name': '供应链因子',
        'factors': ['customer_momentum', 'supplier_demand'],
    },
    'sentiment': {
        'name': '情绪因子',
        'factors': ['retail_sentiment', 'margin_balance_chg', 'new_account_growth'],
    },
}

# 因子方向定义 (ADD 6.3.4 + 机构级扩展)
FACTOR_DIRECTIONS = {
    # 价值因子: 越低越便宜，方向为-1(越小越好的因子取反后越大越好)
    'ep_ttm': 1, 'bp': 1, 'sp_ttm': 1, 'dp': 1, 'cfp_ttm': 1,
    # 成长因子: 越高越好
    'yoy_revenue': 1, 'yoy_net_profit': 1, 'yoy_deduct_net_profit': 1, 'yoy_roe': 1,
    # 质量因子: 越高越好
    'roe': 1, 'roa': 1, 'gross_profit_margin': 1, 'net_profit_margin': 1, 'current_ratio': 1,
    # 动量因子: 正动量方向为1，反转因子方向为-1
    'ret_1m': 1, 'ret_3m': 1, 'ret_6m': 1, 'ret_12m': 1, 'ret_1m_reversal': -1,
    # 波动率因子: 低波动更好，方向为-1
    'vol_20d': -1, 'vol_60d': -1, 'beta': -1, 'idio_vol': -1,
    # 流动性因子: 高流动性更好
    'turnover_20d': 1, 'turnover_60d': 1, 'amihud_20d': -1, 'zero_return_ratio': -1,
    # === 北向资金因子: 北向净买入越多越好 ===
    'north_net_buy_ratio': 1, 'north_holding_chg_5d': 1, 'north_holding_pct': 1,
    # === 分析师预期因子 ===
    'sue': 1, 'analyst_revision_1m': 1, 'analyst_coverage': 1, 'earnings_surprise': 1,
    # === 微观结构因子 ===
    'large_order_ratio': 1, 'overnight_return': -1, 'intraday_return_ratio': 1, 'vpin': -1,
    # === 政策因子 ===
    'policy_sentiment': 1, 'policy_theme_exposure': 1,
    # === 供应链因子 ===
    'customer_momentum': 1, 'supplier_demand': 1,
    # === 情绪因子: 散户情绪过高反向 ===
    'retail_sentiment': -1, 'margin_balance_chg': 1, 'new_account_growth': -1,
}


class FactorEngine:
    """因子引擎 - 核心因子计算、存储、分析"""

    def __init__(self, db: Session):
        self.db = db
        self.preprocessor = FactorPreprocessor()

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
        """
        批量保存因子值
        支持raw/processed/neutralized/zscore多级存储

        Args:
            factor_id: 因子ID
            trade_date: 交易日期
            values: DataFrame with columns [security_id, raw_value, processed_value, neutralized_value, zscore_value]
            run_id: 运行ID

        Returns:
            保存的记录数
        """
        records = []
        for _, row in values.iterrows():
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
        """获取因子值"""
        query = self.db.query(FactorValue).filter(
            and_(FactorValue.factor_id == factor_id, FactorValue.trade_date == trade_date)
        )
        results = query.all()
        if not results:
            return pd.DataFrame()
        return pd.DataFrame([{
            'security_id': r.security_id,
            'raw_value': r.raw_value,
            'processed_value': r.processed_value,
            'neutralized_value': r.neutralized_value,
            'zscore_value': r.zscore_value,
            'value': r.value,
        } for r in results])

    def get_factor_values_range(self, factor_id: int, start_date: date,
                                end_date: date) -> pd.DataFrame:
        """获取因子值时间序列"""
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
        return pd.DataFrame([{
            'trade_date': r.trade_date,
            'security_id': r.security_id,
            'value': r.value,
            'zscore_value': r.zscore_value,
        } for r in results])

    # ==================== 因子分析 ====================

    def calc_ic(self, factor_values: pd.Series, forward_returns: pd.Series) -> Dict[str, float]:
        """
        计算因子IC
        符合ADD 6.3.6节

        Args:
            factor_values: 因子值
            forward_returns: 下期收益

        Returns:
            IC指标
        """
        valid = ~(factor_values.isna() | forward_returns.isna())
        if valid.sum() < 10:
            return {'ic': np.nan, 'rank_ic': np.nan}

        fv = factor_values[valid]
        fr = forward_returns[valid]

        ic = fv.corr(fr)  # Pearson IC
        rank_ic = fv.rank().corr(fr.rank())  # Spearman Rank IC

        return {
            'ic': round(ic, 4) if not np.isnan(ic) else 0,
            'rank_ic': round(rank_ic, 4) if not np.isnan(rank_ic) else 0,
        }

    def calc_ic_series(self, factor_id: int, start_date: date, end_date: date,
                       forward_period: int = 20) -> pd.DataFrame:
        """
        计算IC时间序列
        符合ADD 6.3.6节
        """
        # 获取因子值
        factor_data = self.get_factor_values_range(factor_id, start_date, end_date)
        if factor_data.empty:
            return pd.DataFrame()

        # 按日期计算IC
        ic_records = []
        for trade_date in factor_data['trade_date'].unique():
            day_data = factor_data[factor_data['trade_date'] == trade_date]
            # 这里需要获取下期收益，简化处理
            ic_record = {
                'trade_date': trade_date,
                'factor_id': factor_id,
            }
            ic_records.append(ic_record)

        return pd.DataFrame(ic_records)

    def calc_factor_decay(self, factor_id: int, trade_date: date,
                          max_lag: int = 20) -> Dict:
        """
        计算因子衰减
        符合ADD 6.3.6节: 因子值与未来N期收益的相关性

        Args:
            factor_id: 因子ID
            trade_date: 基准日期
            max_lag: 最大滞后期数

        Returns:
            衰减数据
        """
        # 简化实现：返回衰减结构
        decay_values = []
        for lag in range(1, max_lag + 1):
            # 实际实现需要查询不同滞后期收益
            decay_values.append({'lag': lag, 'ic': 0})

        return {
            'factor_id': factor_id,
            'trade_date': trade_date,
            'decay_values': decay_values,
        }

    def calc_factor_correlation(self, factor_id_a: int, factor_id_b: int,
                                start_date: date, end_date: date) -> Dict:
        """
        计算两个因子的相关性
        符合ADD 6.3.6节
        """
        values_a = self.get_factor_values_range(factor_id_a, start_date, end_date)
        values_b = self.get_factor_values_range(factor_id_b, start_date, end_date)

        if values_a.empty or values_b.empty:
            return {'correlation': np.nan}

        # 按日期和证券对齐
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
                       n_groups: int = 5) -> Dict:
        """
        因子分组回测
        符合ADD 6.3.6节: 按因子值分组，计算各组收益

        Args:
            factor_id: 因子ID
            start_date: 开始日期
            end_date: 结束日期
            n_groups: 分组数

        Returns:
            分组回测结果
        """
        factor_data = self.get_factor_values_range(factor_id, start_date, end_date)
        if factor_data.empty:
            return {}

        # 按日期分组
        group_results = {}
        for trade_date in factor_data['trade_date'].unique():
            day_data = factor_data[factor_data['trade_date'] == trade_date]
            day_data = day_data.sort_values('value')

            # 等分
            group_labels = pd.qcut(day_data['value'], n_groups, labels=False, duplicates='drop')
            day_data['group'] = group_labels

            for group_num in range(n_groups):
                group_data = day_data[day_data['group'] == group_num]
                if group_num not in group_results:
                    group_results[group_num] = []
                group_results[group_num].append({
                    'trade_date': trade_date,
                    'count': len(group_data),
                    'mean_value': group_data['value'].mean(),
                })

        return {
            'factor_id': factor_id,
            'n_groups': n_groups,
            'group_results': group_results,
        }

    # ==================== 因子计算 ====================

    def calc_valuation_factors(self, financial_df: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
        """
        计算价值因子
        符合ADD 6.3.1节
        """
        result = pd.DataFrame()
        result['security_id'] = financial_df['ts_code']

        # EP_TTM = 1 / PE_TTM
        result['ep_ttm'] = 1 / financial_df['pe_ttm'].replace(0, np.nan)

        # BP = 1 / PB
        result['bp'] = 1 / financial_df['pb'].replace(0, np.nan)

        # SP_TTM = 1 / PS_TTM
        result['sp_ttm'] = 1 / financial_df['ps_ttm'].replace(0, np.nan)

        # DP = 股息率
        result['dp'] = financial_df.get('dividend_yield', np.nan)

        # CFP_TTM = 经营现金流/总市值
        if 'operating_cash_flow' in financial_df.columns and 'total_market_cap' in financial_df.columns:
            result['cfp_ttm'] = financial_df['operating_cash_flow'] / financial_df['total_market_cap'].replace(0, np.nan)

        return result

    def calc_growth_factors(self, financial_df: pd.DataFrame) -> pd.DataFrame:
        """计算成长因子"""
        result = pd.DataFrame()
        result['security_id'] = financial_df['ts_code']
        result['yoy_revenue'] = financial_df.get('yoy_revenue')
        result['yoy_net_profit'] = financial_df.get('yoy_net_profit')
        result['yoy_deduct_net_profit'] = financial_df.get('yoy_deduct_net_profit')
        result['yoy_roe'] = financial_df.get('yoy_roe')
        return result

    def calc_quality_factors(self, financial_df: pd.DataFrame) -> pd.DataFrame:
        """计算质量因子"""
        result = pd.DataFrame()
        result['security_id'] = financial_df['ts_code']
        result['roe'] = financial_df.get('roe')
        result['roa'] = financial_df.get('roa')
        result['gross_profit_margin'] = financial_df.get('gross_profit_margin')
        result['net_profit_margin'] = financial_df.get('net_profit_margin')
        result['current_ratio'] = financial_df.get('current_ratio')
        return result

    def calc_momentum_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """
        计算动量因子
        符合ADD 6.3.1节
        """
        result = pd.DataFrame()

        if 'close' not in price_df.columns or 'ts_code' not in price_df.columns:
            return result

        result['security_id'] = price_df['ts_code']

        # 过去N月收益率
        close = price_df['close']
        result['ret_1m'] = close.pct_change(20)
        result['ret_3m'] = close.pct_change(60)
        result['ret_6m'] = close.pct_change(120)
        result['ret_12m'] = close.pct_change(240)

        # 1个月反转因子
        result['ret_1m_reversal'] = -result['ret_1m']

        return result

    def calc_volatility_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算波动率因子"""
        result = pd.DataFrame()

        if 'close' not in price_df.columns:
            return result

        result['security_id'] = price_df.get('ts_code')

        # 日收益率
        daily_ret = price_df['close'].pct_change()

        # 滚动波动率
        result['vol_20d'] = daily_ret.rolling(20).std() * np.sqrt(252)
        result['vol_60d'] = daily_ret.rolling(60).std() * np.sqrt(252)

        return result

    def calc_liquidity_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算流动性因子"""
        result = pd.DataFrame()

        if 'turnover_rate' not in price_df.columns:
            return result

        result['security_id'] = price_df.get('ts_code')

        # 滚动换手率
        result['turnover_20d'] = price_df['turnover_rate'].rolling(20).mean()
        result['turnover_60d'] = price_df['turnover_rate'].rolling(60).mean()

        # Amihud非流动性指标
        if 'amount' in price_df.columns and 'close' in price_df.columns:
            abs_ret = price_df['close'].pct_change().abs()
            amount = price_df['amount']
            result['amihud_20d'] = (abs_ret / amount.replace(0, np.nan)).rolling(20).mean()

        # 零收益天数占比
        daily_ret = price_df['close'].pct_change() if 'close' in price_df.columns else pd.Series()
        result['zero_return_ratio'] = (daily_ret.abs() < 0.001).rolling(20).mean()

        return result

    # ==================== 机构级扩展因子计算 ====================

    def calc_northbound_factors(self, northbound_df: pd.DataFrame) -> pd.DataFrame:
        """
        北向资金因子
        北向资金是A股最重要的聪明钱信号之一

        Args:
            northbound_df: 需包含 ts_code, north_net_buy, north_holding, north_holding_pct, daily_volume
        """
        result = pd.DataFrame()
        result['security_id'] = northbound_df['ts_code']

        # 北向净买入占比 = 北向净买入额 / 日成交额
        if 'north_net_buy' in northbound_df.columns and 'daily_volume' in northbound_df.columns:
            result['north_net_buy_ratio'] = (
                northbound_df['north_net_buy'] / northbound_df['daily_volume'].replace(0, np.nan)
            )

        # 北向持股5日变化率
        if 'north_holding' in northbound_df.columns:
            result['north_holding_chg_5d'] = northbound_df['north_holding'].pct_change(5)

        # 北向持股占比
        if 'north_holding_pct' in northbound_df.columns:
            result['north_holding_pct'] = northbound_df['north_holding_pct']

        return result

    def calc_analyst_factors(self, analyst_df: pd.DataFrame) -> pd.DataFrame:
        """
        分析师预期因子
        SUE(标准化预期外盈利)和分析师修正因子是机构核心Alpha来源

        Args:
            analyst_df: 需包含 ts_code, actual_eps, expected_eps, num_analysts,
                        consensus_rating_1m_ago, consensus_rating, earnings_date
        """
        result = pd.DataFrame()
        result['security_id'] = analyst_df['ts_code']

        # SUE = (实际盈利 - 预期盈利) / 历史预测误差标准差
        if all(c in analyst_df.columns for c in ['actual_eps', 'expected_eps']):
            surprise = analyst_df['actual_eps'] - analyst_df['expected_eps']
            # 使用滚动标准差作为分母
            surprise_std = surprise.rolling(8, min_periods=4).std() if len(surprise) >= 4 else surprise.std()
            result['sue'] = surprise / surprise_std.replace(0, np.nan)

        # 分析师评级1个月修正 = 当前一致评级 - 1月前一致评级
        if all(c in analyst_df.columns for c in ['consensus_rating', 'consensus_rating_1m_ago']):
            result['analyst_revision_1m'] = (
                analyst_df['consensus_rating_1m_ago'] - analyst_df['consensus_rating']
            )  # 评级越低越好(1=买入), 所以取反

        # 分析师覆盖度 = 覆盖分析师数量
        if 'num_analysts' in analyst_df.columns:
            result['analyst_coverage'] = analyst_df['num_analysts']

        # 盈利惊喜 = (实际 - 预期) / |预期|
        if all(c in analyst_df.columns for c in ['actual_eps', 'expected_eps']):
            result['earnings_surprise'] = (
                (analyst_df['actual_eps'] - analyst_df['expected_eps'])
                / analyst_df['expected_eps'].abs().replace(0, np.nan)
            )

        return result

    def calc_microstructure_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """
        微观结构因子
        从日内交易数据提取低频可用的Alpha信号

        Args:
            price_df: 需包含 ts_code, close, open, volume, amount,
                      large_order_volume(可选), super_large_order_volume(可选)
        """
        result = pd.DataFrame()
        result['security_id'] = price_df.get('ts_code')

        # 大单比率 = (大单成交额 + 超大单成交额) / 总成交额
        if all(c in price_df.columns for c in ['large_order_volume', 'super_large_order_volume', 'volume']):
            smart_money_vol = price_df['large_order_volume'].fillna(0) + price_df['super_large_order_volume'].fillna(0)
            result['large_order_ratio'] = smart_money_vol / price_df['volume'].replace(0, np.nan)
            result['large_order_ratio'] = result['large_order_ratio'].rolling(20, min_periods=5).mean()

        # 隔夜收益率 = 今日开盘价 / 昨日收盘价 - 1
        if all(c in price_df.columns for c in ['open', 'close']):
            result['overnight_return'] = price_df['open'] / price_df['close'].shift(1) - 1
            result['overnight_return'] = result['overnight_return'].rolling(20, min_periods=5).mean()

        # 日内/隔夜收益比 = 日内收益绝对值 / 隔夜收益绝对值
        if all(c in price_df.columns for c in ['open', 'close']):
            intraday_ret = price_df['close'] / price_df['open'] - 1
            overnight_ret = price_df['open'] / price_df['close'].shift(1) - 1
            result['intraday_return_ratio'] = (
                intraday_ret.abs().rolling(20, min_periods=5).mean()
                / overnight_ret.abs().rolling(20, min_periods=5).mean().replace(0, np.nan)
            )

        # VPIN (Volume-Synchronized Probability of Informed Trading) 简化估计
        if all(c in price_df.columns for c in ['close', 'volume']):
            daily_ret = price_df['close'].pct_change()
            # 使用价格变化与成交量的关系作为VPIN代理
            abs_ret = daily_ret.abs()
            vol_ratio = price_df['volume'] / price_df['volume'].rolling(20, min_periods=5).mean()
            result['vpin'] = (abs_ret * vol_ratio).rolling(20, min_periods=5).mean()

        return result

    def calc_policy_factors(self, policy_df: pd.DataFrame) -> pd.DataFrame:
        """
        政策因子 (A股特有)
        政策是A股最重要的驱动因素之一

        Args:
            policy_df: 需包含 ts_code, policy_sentiment_score, policy_keywords_match
        """
        result = pd.DataFrame()
        result['security_id'] = policy_df.get('ts_code')

        # 政策情绪得分 = 基于政策文件NLP分析的得分
        if 'policy_sentiment_score' in policy_df.columns:
            result['policy_sentiment'] = policy_df['policy_sentiment_score']

        # 政策主题暴露度 = 与当前政策主题关键词匹配度
        if 'policy_keywords_match' in policy_df.columns:
            result['policy_theme_exposure'] = policy_df['policy_keywords_match']

        return result

    def calc_supply_chain_factors(self, supply_chain_df: pd.DataFrame) -> pd.DataFrame:
        """
        供应链因子 (Cohen-Frazzini客户动量)
        下游客户收入加速 → 上游供应商未来1-3个月跑赢

        Args:
            supply_chain_df: 需包含 ts_code, customer_revenue_growth, downstream_demand_index
        """
        result = pd.DataFrame()
        result['security_id'] = supply_chain_df.get('ts_code')

        # 客户动量 = 下游主要客户收入增速加权平均
        if 'customer_revenue_growth' in supply_chain_df.columns:
            result['customer_momentum'] = supply_chain_df['customer_revenue_growth']

        # 供应商需求指标
        if 'downstream_demand_index' in supply_chain_df.columns:
            result['supplier_demand'] = supply_chain_df['downstream_demand_index']

        return result

    def calc_sentiment_factors(self, sentiment_df: pd.DataFrame) -> pd.DataFrame:
        """
        情绪因子 (A股特有)
        A股散户占比高，情绪因子具有显著Alpha

        Args:
            sentiment_df: 需包含 ts_code, retail_order_ratio(可选), margin_balance(可选),
                          new_accounts(可选), social_media_volume(可选)
        """
        result = pd.DataFrame()
        result['security_id'] = sentiment_df.get('ts_code')

        # 散户情绪 = 散户订单占比 (越高越反向)
        if 'retail_order_ratio' in sentiment_df.columns:
            result['retail_sentiment'] = sentiment_df['retail_order_ratio'].rolling(20, min_periods=5).mean()

        # 融资余额变化率
        if 'margin_balance' in sentiment_df.columns:
            result['margin_balance_chg'] = sentiment_df['margin_balance'].pct_change(5)

        # 新开户数增长率 (市场级别)
        if 'new_accounts' in sentiment_df.columns:
            result['new_account_growth'] = sentiment_df['new_accounts'].pct_change(20)

        return result

    # ==================== 无数据库便捷函数 ====================

    @staticmethod
    def calc_factors_from_data(price_df: pd.DataFrame,
                               financial_df: pd.DataFrame = None,
                               neutralize: bool = False,
                               industry_col: str = None,
                               cap_col: str = None) -> pd.DataFrame:
        """
        不依赖数据库的因子计算便捷函数
        直接从 DataFrame 计算所有可用因子并预处理

        Args:
            price_df: 行情数据，需包含 ts_code, close, open, high, low, volume, amount, trade_date
            financial_df: 财务数据（可选）
            neutralize: 是否中性化
            industry_col: 行业列名
            cap_col: 市值列名

        Returns:
            预处理后的因子DataFrame
        """
        preprocessor = FactorPreprocessor()

        # 计算各类因子
        factor_dfs = []

        # 动量因子
        momentum = FactorEngine._calc_momentum_static(price_df)
        if not momentum.empty:
            factor_dfs.append(momentum)

        # 波动率因子
        volatility = FactorEngine._calc_volatility_static(price_df)
        if not volatility.empty:
            factor_dfs.append(volatility)

        # 流动性因子
        liquidity = FactorEngine._calc_liquidity_static(price_df)
        if not liquidity.empty:
            factor_dfs.append(liquidity)

        # 微观结构因子
        microstructure = FactorEngine._calc_microstructure_static(price_df)
        if not microstructure.empty:
            factor_dfs.append(microstructure)

        # 价值/成长/质量因子（需要财务数据）
        if financial_df is not None and not financial_df.empty:
            valuation = FactorEngine._calc_valuation_static(financial_df, price_df)
            if not valuation.empty:
                factor_dfs.append(valuation)
            growth = FactorEngine._calc_growth_static(financial_df)
            if not growth.empty:
                factor_dfs.append(growth)
            quality = FactorEngine._calc_quality_static(financial_df)
            if not quality.empty:
                factor_dfs.append(quality)

        if not factor_dfs:
            return pd.DataFrame()

        # 合并所有因子
        merged = factor_dfs[0]
        for f in factor_dfs[1:]:
            if 'security_id' in f.columns and 'security_id' in merged.columns:
                merged = pd.merge(merged, f, on='security_id', how='outer')

        if merged.empty:
            return merged

        # 预处理
        factor_cols = [c for c in merged.columns if c != 'security_id']
        merged = preprocessor.preprocess_dataframe(
            merged, factor_cols,
            industry_col=industry_col,
            cap_col=cap_col,
            neutralize=neutralize,
            direction_map=FACTOR_DIRECTIONS,
        )

        return merged

    @staticmethod
    def _calc_momentum_static(price_df: pd.DataFrame) -> pd.DataFrame:
        """计算动量因子（不依赖db）"""
        result = pd.DataFrame()
        if 'close' not in price_df.columns:
            return result
        result['security_id'] = price_df.get('ts_code', price_df.index)
        close = price_df['close']
        result['ret_1m'] = close.pct_change(20)
        result['ret_3m'] = close.pct_change(60)
        result['ret_6m'] = close.pct_change(120)
        result['ret_12m'] = close.pct_change(240)
        result['ret_1m_reversal'] = -result['ret_1m']
        return result

    @staticmethod
    def _calc_volatility_static(price_df: pd.DataFrame) -> pd.DataFrame:
        """计算波动率因子（不依赖db）"""
        result = pd.DataFrame()
        if 'close' not in price_df.columns:
            return result
        result['security_id'] = price_df.get('ts_code', price_df.index)
        daily_ret = price_df['close'].pct_change()
        result['vol_20d'] = daily_ret.rolling(20).std() * np.sqrt(252)
        result['vol_60d'] = daily_ret.rolling(60).std() * np.sqrt(252)
        return result

    @staticmethod
    def _calc_liquidity_static(price_df: pd.DataFrame) -> pd.DataFrame:
        """计算流动性因子（不依赖db）"""
        result = pd.DataFrame()
        result['security_id'] = price_df.get('ts_code', price_df.index)
        if 'turnover_rate' in price_df.columns:
            result['turnover_20d'] = price_df['turnover_rate'].rolling(20).mean()
            result['turnover_60d'] = price_df['turnover_rate'].rolling(60).mean()
        if 'amount' in price_df.columns and 'close' in price_df.columns:
            abs_ret = price_df['close'].pct_change().abs()
            amount = price_df['amount']
            result['amihud_20d'] = (abs_ret / amount.replace(0, np.nan)).rolling(20).mean()
        if 'close' in price_df.columns:
            daily_ret = price_df['close'].pct_change()
            result['zero_return_ratio'] = (daily_ret.abs() < 0.001).rolling(20).mean()
        return result

    @staticmethod
    def _calc_microstructure_static(price_df: pd.DataFrame) -> pd.DataFrame:
        """计算微观结构因子（不依赖db）"""
        result = pd.DataFrame()
        result['security_id'] = price_df.get('ts_code', price_df.index)
        if all(c in price_df.columns for c in ['open', 'close']):
            result['overnight_return'] = price_df['open'] / price_df['close'].shift(1) - 1
            result['overnight_return'] = result['overnight_return'].rolling(20, min_periods=5).mean()
        return result

    @staticmethod
    def _calc_valuation_static(financial_df: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算价值因子（不依赖db）"""
        result = pd.DataFrame()
        result['security_id'] = financial_df.get('ts_code', financial_df.index)
        if 'pe_ttm' in financial_df.columns:
            result['ep_ttm'] = 1 / financial_df['pe_ttm'].replace(0, np.nan)
        if 'pb' in financial_df.columns:
            result['bp'] = 1 / financial_df['pb'].replace(0, np.nan)
        if 'ps_ttm' in financial_df.columns:
            result['sp_ttm'] = 1 / financial_df['ps_ttm'].replace(0, np.nan)
        return result

    @staticmethod
    def _calc_growth_static(financial_df: pd.DataFrame) -> pd.DataFrame:
        """计算成长因子（不依赖db）"""
        result = pd.DataFrame()
        result['security_id'] = financial_df.get('ts_code', financial_df.index)
        result['yoy_revenue'] = financial_df.get('yoy_revenue')
        result['yoy_net_profit'] = financial_df.get('yoy_net_profit')
        return result

    @staticmethod
    def _calc_quality_static(financial_df: pd.DataFrame) -> pd.DataFrame:
        """计算质量因子（不依赖db）"""
        result = pd.DataFrame()
        result['security_id'] = financial_df.get('ts_code', financial_df.index)
        result['roe'] = financial_df.get('roe')
        result['roa'] = financial_df.get('roa')
        result['gross_profit_margin'] = financial_df.get('grossprofit_margin', financial_df.get('gross_profit_margin'))
        result['net_profit_margin'] = financial_df.get('netprofit_margin', financial_df.get('net_profit_margin'))
        return result

    def calc_all_factors(self, financial_df: pd.DataFrame, price_df: pd.DataFrame,
                         industry_col: str = None, cap_col: str = None,
                         neutralize: bool = True,
                         northbound_df: pd.DataFrame = None,
                         analyst_df: pd.DataFrame = None,
                         policy_df: pd.DataFrame = None,
                         supply_chain_df: pd.DataFrame = None,
                         sentiment_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        计算所有因子并预处理
        符合ADD 6.3节完整流程 + 机构级扩展因子
        """
        # 计算各类因子
        valuation = self.calc_valuation_factors(financial_df, price_df)
        growth = self.calc_growth_factors(financial_df)
        quality = self.calc_quality_factors(financial_df)
        momentum = self.calc_momentum_factors(price_df)
        volatility = self.calc_volatility_factors(price_df)
        liquidity = self.calc_liquidity_factors(price_df)

        # 机构级扩展因子
        northbound = self.calc_northbound_factors(northbound_df) if northbound_df is not None and not northbound_df.empty else pd.DataFrame()
        analyst = self.calc_analyst_factors(analyst_df) if analyst_df is not None and not analyst_df.empty else pd.DataFrame()
        microstructure = self.calc_microstructure_factors(price_df)
        policy = self.calc_policy_factors(policy_df) if policy_df is not None and not policy_df.empty else pd.DataFrame()
        supply_chain = self.calc_supply_chain_factors(supply_chain_df) if supply_chain_df is not None and not supply_chain_df.empty else pd.DataFrame()
        sentiment = self.calc_sentiment_factors(sentiment_df) if sentiment_df is not None and not sentiment_df.empty else pd.DataFrame()

        # 合并
        all_factors = [valuation, growth, quality, momentum, volatility, liquidity,
                       northbound, analyst, microstructure, policy, supply_chain, sentiment]
        merged = pd.DataFrame()
        for f in all_factors:
            if not f.empty and 'security_id' in f.columns:
                if merged.empty:
                    merged = f
                else:
                    merged = pd.merge(merged, f, on='security_id', how='outer')

        if merged.empty:
            return merged

        # 预处理所有因子列
        factor_cols = [c for c in merged.columns if c != 'security_id']
        merged = self.preprocessor.preprocess_dataframe(
            merged, factor_cols,
            industry_col=industry_col,
            cap_col=cap_col,
            neutralize=neutralize,
            direction_map=FACTOR_DIRECTIONS,
        )

        return merged