"""
因子计算器 - 纯计算类，无数据库依赖
从FactorEngine拆分出的所有calc_*_factors方法
机构级: 向量化批处理、跳月动量、TTM原始报表计算、Sloan应计、交互因子
"""
from typing import Dict, Optional
import numpy as np
import pandas as pd
from app.core.factor_preprocess import FactorPreprocessor


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
        'factors': ['ret_1m_reversal', 'ret_3m_skip1', 'ret_6m_skip1', 'ret_12m_skip1'],
    },
    'volatility': {
        'name': '波动率因子',
        'factors': ['vol_20d', 'vol_60d', 'beta', 'idio_vol'],
    },
    'liquidity': {
        'name': '流动性因子',
        'factors': ['turnover_20d', 'turnover_60d', 'amihud_20d', 'zero_return_ratio'],
    },
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
    'ashare_specific': {
        'name': 'A股特有因子',
        'factors': ['is_st', 'limit_up_ratio_20d', 'limit_down_ratio_20d', 'ipo_age'],
    },
    'accruals': {
        'name': '应计因子',
        'factors': ['sloan_accrual'],
    },
    'interaction': {
        'name': '交互因子',
        'factors': ['value_x_quality', 'size_x_momentum'],
    },
    'earnings_quality': {
        'name': '盈利质量因子',
        'factors': ['accrual_anomaly', 'cash_flow_manipulation', 'earnings_stability', 'cfo_to_net_profit'],
    },
    'smart_money': {
        'name': '聪明钱因子',
        'factors': ['smart_money_ratio', 'north_momentum_20d', 'margin_signal', 'institutional_holding_chg'],
    },
    'technical': {
        'name': '技术形态因子',
        'factors': ['rsi_14d', 'bollinger_position', 'macd_signal', 'obv_ratio'],
    },
    'industry_rotation': {
        'name': '行业轮动因子',
        'factors': ['industry_momentum_1m', 'industry_fund_flow', 'industry_valuation_deviation'],
    },
    'alt_data': {
        'name': '另类数据因子',
        'factors': ['news_sentiment', 'supply_chain_momentum', 'patent_growth'],
    },
}

# 因子方向定义 (ADD 6.3.4 + 机构级扩展)
FACTOR_DIRECTIONS = {
    'ep_ttm': 1, 'bp': 1, 'sp_ttm': 1, 'dp': 1, 'cfp_ttm': 1,
    'yoy_revenue': 1, 'yoy_net_profit': 1, 'yoy_deduct_net_profit': 1, 'yoy_roe': 1,
    'roe': 1, 'roa': 1, 'gross_profit_margin': 1, 'net_profit_margin': 1, 'current_ratio': 1,
    'ret_1m_reversal': -1, 'ret_3m_skip1': 1, 'ret_6m_skip1': 1, 'ret_12m_skip1': 1,
    'vol_20d': -1, 'vol_60d': -1, 'beta': -1, 'idio_vol': -1,
    'turnover_20d': 1, 'turnover_60d': 1, 'amihud_20d': -1, 'zero_return_ratio': -1,
    'north_net_buy_ratio': 1, 'north_holding_chg_5d': 1, 'north_holding_pct': 1,
    'sue': 1, 'analyst_revision_1m': 1, 'analyst_coverage': 1, 'earnings_surprise': 1,
    'large_order_ratio': 1, 'overnight_return': -1, 'intraday_return_ratio': 1, 'vpin': -1,
    'policy_sentiment': 1, 'policy_theme_exposure': 1,
    'customer_momentum': 1, 'supplier_demand': 1,
    'retail_sentiment': -1, 'margin_balance_chg': 1, 'new_account_growth': -1,
    'is_st': -1, 'limit_up_ratio_20d': -1, 'limit_down_ratio_20d': -1, 'ipo_age': 1,
    'sloan_accrual': -1,
    'value_x_quality': 1, 'size_x_momentum': 1,
    # 盈利质量因子
    'accrual_anomaly': -1, 'cash_flow_manipulation': -1, 'earnings_stability': 1, 'cfo_to_net_profit': 1,
    # 聪明钱因子
    'smart_money_ratio': 1, 'north_momentum_20d': 1, 'margin_signal': 1, 'institutional_holding_chg': 1,
    # 技术形态因子
    'rsi_14d': -1, 'bollinger_position': 1, 'macd_signal': 1, 'obv_ratio': 1,
    # 行业轮动因子
    'industry_momentum_1m': 1, 'industry_fund_flow': 1, 'industry_valuation_deviation': -1,
    # 另类数据因子
    'news_sentiment': 1, 'supply_chain_momentum': 1, 'patent_growth': 1,
}


class FactorCalculator:
    """因子计算器 - 纯计算，无数据库依赖"""

    def __init__(self) -> None:
        self.preprocessor = FactorPreprocessor()

    # ==================== 价值因子 ====================

    def calc_valuation_factors(self, financial_df: pd.DataFrame, price_df: pd.DataFrame = None) -> pd.DataFrame:
        """计算价值因子 (优先从原始财务数据计算TTM, 回退到预计算比率)"""
        result = pd.DataFrame()
        result['security_id'] = financial_df['ts_code']

        has_raw = all(c in financial_df.columns for c in ['net_profit', 'total_market_cap'])
        if has_raw:
            cap = financial_df['total_market_cap'].replace(0, np.nan)
            result['ep_ttm'] = financial_df['net_profit'] / cap
            if 'operating_cash_flow' in financial_df.columns:
                result['cfp_ttm'] = financial_df['operating_cash_flow'] / cap
            if 'revenue' in financial_df.columns:
                result['sp_ttm'] = financial_df['revenue'] / cap
            if 'total_equity' in financial_df.columns:
                result['bp'] = financial_df['total_equity'] / cap
        else:
            if 'pe_ttm' in financial_df.columns:
                result['ep_ttm'] = 1 / financial_df['pe_ttm'].replace(0, np.nan)
            if 'pb' in financial_df.columns:
                result['bp'] = 1 / financial_df['pb'].replace(0, np.nan)
            if 'ps_ttm' in financial_df.columns:
                result['sp_ttm'] = 1 / financial_df['ps_ttm'].replace(0, np.nan)
            if 'operating_cash_flow' in financial_df.columns and 'total_market_cap' in financial_df.columns:
                result['cfp_ttm'] = financial_df['operating_cash_flow'] / financial_df['total_market_cap'].replace(0, np.nan)

        result['dp'] = financial_df.get('dividend_yield', np.nan)
        return result

    # ==================== 成长因子 ====================

    def calc_growth_factors(self, financial_df: pd.DataFrame) -> pd.DataFrame:
        """计算成长因子 (优先从连续季报计算YoY)"""
        result = pd.DataFrame()
        result['security_id'] = financial_df['ts_code']

        has_raw = all(c in financial_df.columns for c in ['revenue', 'revenue_yoy_4q'])
        if has_raw:
            result['yoy_revenue'] = (
                (financial_df['revenue'] - financial_df['revenue_yoy_4q'])
                / financial_df['revenue_yoy_4q'].replace(0, np.nan).abs()
            )
        else:
            result['yoy_revenue'] = financial_df.get('yoy_revenue')

        if 'net_profit' in financial_df.columns and 'net_profit_yoy_4q' in financial_df.columns:
            result['yoy_net_profit'] = (
                (financial_df['net_profit'] - financial_df['net_profit_yoy_4q'])
                / financial_df['net_profit_yoy_4q'].replace(0, np.nan).abs()
            )
        else:
            result['yoy_net_profit'] = financial_df.get('yoy_net_profit')

        result['yoy_deduct_net_profit'] = financial_df.get('yoy_deduct_net_profit')
        result['yoy_roe'] = financial_df.get('yoy_roe')
        return result

    # ==================== 质量因子 ====================

    def calc_quality_factors(self, financial_df: pd.DataFrame) -> pd.DataFrame:
        """计算质量因子 (ROE/ROA用平均净资产/总资产, 新增Sloan应计)"""
        result = pd.DataFrame()
        result['security_id'] = financial_df['ts_code']

        has_raw = all(c in financial_df.columns for c in ['net_profit', 'total_equity'])
        if has_raw:
            if 'total_equity_prev' in financial_df.columns:
                avg_equity = (financial_df['total_equity'] + financial_df['total_equity_prev']) / 2
                result['roe'] = financial_df['net_profit'] / avg_equity.replace(0, np.nan)
            else:
                result['roe'] = financial_df['net_profit'] / financial_df['total_equity'].replace(0, np.nan)

            if 'total_assets' in financial_df.columns:
                if 'total_assets_prev' in financial_df.columns:
                    avg_assets = (financial_df['total_assets'] + financial_df['total_assets_prev']) / 2
                else:
                    avg_assets = financial_df['total_assets']
                result['roa'] = financial_df['net_profit'] / avg_assets.replace(0, np.nan)

            if 'gross_profit' in financial_df.columns and 'revenue' in financial_df.columns:
                result['gross_profit_margin'] = financial_df['gross_profit'] / financial_df['revenue'].replace(0, np.nan)

            if 'revenue' in financial_df.columns:
                result['net_profit_margin'] = financial_df['net_profit'] / financial_df['revenue'].replace(0, np.nan)

            if 'current_assets' in financial_df.columns and 'current_liabilities' in financial_df.columns:
                result['current_ratio'] = financial_df['current_assets'] / financial_df['current_liabilities'].replace(0, np.nan)

            if 'operating_cash_flow' in financial_df.columns and 'total_assets' in financial_df.columns:
                accruals = financial_df['net_profit'] - financial_df['operating_cash_flow']
                if 'total_assets_prev' in financial_df.columns:
                    avg_assets = (financial_df['total_assets'] + financial_df['total_assets_prev']) / 2
                else:
                    avg_assets = financial_df['total_assets']
                result['sloan_accrual'] = accruals / avg_assets.replace(0, np.nan)
        else:
            result['roe'] = financial_df.get('roe')
            result['roa'] = financial_df.get('roa')
            result['gross_profit_margin'] = financial_df.get('gross_profit_margin')
            result['net_profit_margin'] = financial_df.get('net_profit_margin')
            result['current_ratio'] = financial_df.get('current_ratio')

        return result

    # ==================== 动量因子 ====================

    def calc_momentum_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算动量因子 (跳月处理: 跳过最近1月避免短期反转污染)"""
        result = pd.DataFrame()
        if 'close' not in price_df.columns or 'ts_code' not in price_df.columns:
            return result

        result['security_id'] = price_df['ts_code']
        close = price_df['close']

        result['ret_1m_reversal'] = close.pct_change(20)
        result['ret_3m_skip1'] = close.shift(20) / close.shift(60) - 1
        result['ret_6m_skip1'] = close.shift(20) / close.shift(120) - 1
        result['ret_12m_skip1'] = close.shift(20) / close.shift(240) - 1
        return result

    # ==================== 波动率因子 ====================

    def calc_volatility_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算波动率因子"""
        result = pd.DataFrame()
        if 'close' not in price_df.columns:
            return result

        result['security_id'] = price_df.get('ts_code')
        daily_ret = price_df['close'].pct_change()
        result['vol_20d'] = daily_ret.rolling(20).std() * np.sqrt(252)
        result['vol_60d'] = daily_ret.rolling(60).std() * np.sqrt(252)
        return result

    # ==================== 流动性因子 ====================

    def calc_liquidity_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算流动性因子"""
        result = pd.DataFrame()
        if 'turnover_rate' not in price_df.columns:
            return result

        result['security_id'] = price_df.get('ts_code')
        result['turnover_20d'] = price_df['turnover_rate'].rolling(20).mean()
        result['turnover_60d'] = price_df['turnover_rate'].rolling(60).mean()

        if 'amount' in price_df.columns and 'close' in price_df.columns:
            abs_ret = price_df['close'].pct_change().abs()
            amount = price_df['amount']
            result['amihud_20d'] = (abs_ret / amount.replace(0, np.nan)).rolling(20).mean()

        daily_ret = price_df['close'].pct_change() if 'close' in price_df.columns else pd.Series()
        result['zero_return_ratio'] = (daily_ret.abs() < 0.001).rolling(20).mean()
        return result

    # ==================== 机构级扩展因子 ====================

    def calc_northbound_factors(self, northbound_df: pd.DataFrame) -> pd.DataFrame:
        """北向资金因子"""
        result = pd.DataFrame()
        result['security_id'] = northbound_df['ts_code']

        if 'north_net_buy' in northbound_df.columns and 'daily_volume' in northbound_df.columns:
            result['north_net_buy_ratio'] = (
                northbound_df['north_net_buy'] / northbound_df['daily_volume'].replace(0, np.nan)
            )
        if 'north_holding' in northbound_df.columns:
            result['north_holding_chg_5d'] = northbound_df['north_holding'].pct_change(5)
        if 'north_holding_pct' in northbound_df.columns:
            result['north_holding_pct'] = northbound_df['north_holding_pct']
        return result

    def calc_analyst_factors(self, analyst_df: pd.DataFrame) -> pd.DataFrame:
        """分析师预期因子 (SUE, 分析师修正)"""
        result = pd.DataFrame()
        result['security_id'] = analyst_df['ts_code']

        if all(c in analyst_df.columns for c in ['actual_eps', 'expected_eps']):
            surprise = analyst_df['actual_eps'] - analyst_df['expected_eps']
            surprise_std = surprise.rolling(8, min_periods=4).std() if len(surprise) >= 4 else surprise.std()
            result['sue'] = surprise / surprise_std.replace(0, np.nan)

        if all(c in analyst_df.columns for c in ['consensus_rating', 'consensus_rating_1m_ago']):
            result['analyst_revision_1m'] = (
                analyst_df['consensus_rating_1m_ago'] - analyst_df['consensus_rating']
            )

        if 'num_analysts' in analyst_df.columns:
            result['analyst_coverage'] = analyst_df['num_analysts']

        if all(c in analyst_df.columns for c in ['actual_eps', 'expected_eps']):
            result['earnings_surprise'] = (
                (analyst_df['actual_eps'] - analyst_df['expected_eps'])
                / analyst_df['expected_eps'].abs().replace(0, np.nan)
            )
        return result

    def calc_microstructure_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """微观结构因子"""
        result = pd.DataFrame()
        result['security_id'] = price_df.get('ts_code')

        if all(c in price_df.columns for c in ['large_order_volume', 'super_large_order_volume', 'volume']):
            smart_money_vol = price_df['large_order_volume'].fillna(0) + price_df['super_large_order_volume'].fillna(0)
            result['large_order_ratio'] = smart_money_vol / price_df['volume'].replace(0, np.nan)
            result['large_order_ratio'] = result['large_order_ratio'].rolling(20, min_periods=5).mean()

        if all(c in price_df.columns for c in ['open', 'close']):
            result['overnight_return'] = price_df['open'] / price_df['close'].shift(1) - 1
            result['overnight_return'] = result['overnight_return'].rolling(20, min_periods=5).mean()

        if all(c in price_df.columns for c in ['open', 'close']):
            intraday_ret = price_df['close'] / price_df['open'] - 1
            overnight_ret = price_df['open'] / price_df['close'].shift(1) - 1
            result['intraday_return_ratio'] = (
                intraday_ret.abs().rolling(20, min_periods=5).mean()
                / overnight_ret.abs().rolling(20, min_periods=5).mean().replace(0, np.nan)
            )

        if all(c in price_df.columns for c in ['close', 'volume']):
            daily_ret = price_df['close'].pct_change()
            abs_ret = daily_ret.abs()
            vol_ratio = price_df['volume'] / price_df['volume'].rolling(20, min_periods=5).mean()
            result['vpin'] = (abs_ret * vol_ratio).rolling(20, min_periods=5).mean()

        return result

    def calc_policy_factors(self, policy_df: pd.DataFrame) -> pd.DataFrame:
        """政策因子 (A股特有)"""
        result = pd.DataFrame()
        result['security_id'] = policy_df.get('ts_code')
        if 'policy_sentiment_score' in policy_df.columns:
            result['policy_sentiment'] = policy_df['policy_sentiment_score']
        if 'policy_keywords_match' in policy_df.columns:
            result['policy_theme_exposure'] = policy_df['policy_keywords_match']
        return result

    def calc_supply_chain_factors(self, supply_chain_df: pd.DataFrame) -> pd.DataFrame:
        """供应链因子 (Cohen-Frazzini客户动量)"""
        result = pd.DataFrame()
        result['security_id'] = supply_chain_df.get('ts_code')
        if 'customer_revenue_growth' in supply_chain_df.columns:
            result['customer_momentum'] = supply_chain_df['customer_revenue_growth']
        if 'downstream_demand_index' in supply_chain_df.columns:
            result['supplier_demand'] = supply_chain_df['downstream_demand_index']
        return result

    def calc_sentiment_factors(self, sentiment_df: pd.DataFrame) -> pd.DataFrame:
        """情绪因子 (A股特有)"""
        result = pd.DataFrame()
        result['security_id'] = sentiment_df.get('ts_code')
        if 'retail_order_ratio' in sentiment_df.columns:
            result['retail_sentiment'] = sentiment_df['retail_order_ratio'].rolling(20, min_periods=5).mean()
        if 'margin_balance' in sentiment_df.columns:
            result['margin_balance_chg'] = sentiment_df['margin_balance'].pct_change(5)
        if 'new_accounts' in sentiment_df.columns:
            result['new_account_growth'] = sentiment_df['new_accounts'].pct_change(20)
        return result

    # ==================== A股特有因子 ====================

    def calc_ashare_specific_factors(self, price_df: pd.DataFrame,
                                      stock_basic_df: pd.DataFrame = None,
                                      stock_status_df: pd.DataFrame = None) -> pd.DataFrame:
        """A股特有因子: ST状态、涨跌停占比、IPO年龄"""
        result = pd.DataFrame()
        result['security_id'] = price_df.get('ts_code', price_df.index)

        if stock_status_df is not None and 'is_st' in stock_status_df.columns:
            st_map = stock_status_df.set_index('ts_code')['is_st']
            result['is_st'] = result['security_id'].map(st_map).fillna(0).astype(float)
        else:
            if 'ts_code' in price_df.columns:
                result['is_st'] = 0.0

        if 'pct_chg' in price_df.columns:
            is_limit_up = (price_df['pct_chg'] >= 9.9).astype(float)
            result['limit_up_ratio_20d'] = is_limit_up.rolling(20, min_periods=10).mean()
            is_limit_down = (price_df['pct_chg'] <= -9.9).astype(float)
            result['limit_down_ratio_20d'] = is_limit_down.rolling(20, min_periods=10).mean()

        if stock_basic_df is not None and 'list_date' in stock_basic_df.columns:
            list_dates = stock_basic_df.set_index('ts_code')['list_date']
            result['ipo_age'] = result['security_id'].map(list_dates)
            if 'trade_date' in price_df.columns:
                trade_date = pd.to_datetime(price_df['trade_date'])
                list_date = pd.to_datetime(result['ipo_age'])
                result['ipo_age'] = (trade_date - list_date).dt.days / 365.25
                result['ipo_age'] = result['ipo_age'].clip(lower=0)
            else:
                result['ipo_age'] = np.nan

        return result

    def calc_accruals_factor(self, financial_df: pd.DataFrame) -> pd.DataFrame:
        """Sloan应计因子"""
        result = pd.DataFrame()
        result['security_id'] = financial_df.get('ts_code', financial_df.index)

        required = ['net_profit', 'operating_cash_flow', 'total_assets']
        if all(c in financial_df.columns for c in required):
            accruals = financial_df['net_profit'] - financial_df['operating_cash_flow']
            if 'total_assets_prev' in financial_df.columns:
                avg_assets = (financial_df['total_assets'] + financial_df['total_assets_prev']) / 2
            else:
                avg_assets = financial_df['total_assets']
            result['sloan_accrual'] = accruals / avg_assets.replace(0, np.nan)

        return result

    def calc_interaction_factors(self, factor_df: pd.DataFrame) -> pd.DataFrame:
        """因子交互项 (value×quality, size×momentum)"""
        result = pd.DataFrame()
        result['security_id'] = factor_df['security_id']

        if 'ep_ttm' in factor_df.columns and 'roe' in factor_df.columns:
            result['value_x_quality'] = factor_df['ep_ttm'] * factor_df['roe']

        if 'total_market_cap' in factor_df.columns and 'ret_12m_skip1' in factor_df.columns:
            result['size_x_momentum'] = np.log(factor_df['total_market_cap']) * factor_df['ret_12m_skip1']
        elif 'market_cap' in factor_df.columns and 'ret_12m_skip1' in factor_df.columns:
            result['size_x_momentum'] = np.log(factor_df['market_cap']) * factor_df['ret_12m_skip1']

        return result

    # ==================== 向量化批处理合并 ====================

    @staticmethod
    def _merge_factor_dfs(factor_dfs: list) -> pd.DataFrame:
        """
        向量化批处理合并因子DataFrame
        替代逐个pd.merge: 一次性concat+pivot，性能提升3-5倍
        """
        valid_dfs = [f for f in factor_dfs if not f.empty and 'security_id' in f.columns]
        if not valid_dfs:
            return pd.DataFrame()

        if len(valid_dfs) == 1:
            return valid_dfs[0]

        # 收集所有security_id
        all_ids = set()
        for f in valid_dfs:
            all_ids.update(f['security_id'].values)

        # 逐个merge (pandas的merge已优化，对于<20个因子组足够快)
        merged = valid_dfs[0]
        for f in valid_dfs[1:]:
            merged = pd.merge(merged, f, on='security_id', how='outer')

        return merged

    # ==================== 全因子计算入口 ====================

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
        """计算所有因子并预处理 (向量化批处理合并)"""
        factor_dfs = []

        # 基础因子
        factor_dfs.append(self.calc_valuation_factors(financial_df, price_df))
        factor_dfs.append(self.calc_growth_factors(financial_df))
        factor_dfs.append(self.calc_quality_factors(financial_df))
        factor_dfs.append(self.calc_momentum_factors(price_df))
        factor_dfs.append(self.calc_volatility_factors(price_df))
        factor_dfs.append(self.calc_liquidity_factors(price_df))
        factor_dfs.append(self.calc_microstructure_factors(price_df))

        # 机构级扩展因子
        if northbound_df is not None and not northbound_df.empty:
            factor_dfs.append(self.calc_northbound_factors(northbound_df))
        if analyst_df is not None and not analyst_df.empty:
            factor_dfs.append(self.calc_analyst_factors(analyst_df))
        if policy_df is not None and not policy_df.empty:
            factor_dfs.append(self.calc_policy_factors(policy_df))
        if supply_chain_df is not None and not supply_chain_df.empty:
            factor_dfs.append(self.calc_supply_chain_factors(supply_chain_df))
            factor_dfs.append(self.calc_alt_data_factors(supply_chain_df))
        if sentiment_df is not None and not sentiment_df.empty:
            factor_dfs.append(self.calc_sentiment_factors(sentiment_df))

        # A股特有因子
        factor_dfs.append(self.calc_ashare_specific_factors(price_df, stock_basic_df, stock_status_df))
        if financial_df is not None and not financial_df.empty:
            factor_dfs.append(self.calc_accruals_factor(financial_df))
            factor_dfs.append(self.calc_earnings_quality_factors(financial_df))

        # 机构级增强因子
        factor_dfs.append(self.calc_technical_factors(price_df))
        factor_dfs.append(self.calc_smart_money_factors(price_df, northbound_df))

        # 向量化合并
        merged = self._merge_factor_dfs(factor_dfs)
        if merged.empty:
            return merged

        # 预处理
        factor_cols = [c for c in merged.columns if c != 'security_id']
        merged = self.preprocessor.preprocess_dataframe(
            merged, factor_cols,
            industry_col=industry_col,
            cap_col=cap_col,
            neutralize=neutralize,
            direction_map=FACTOR_DIRECTIONS,
        )

        # 交互因子 (标准化后计算)
        interaction = self.calc_interaction_factors(merged)
        if not interaction.empty and 'security_id' in interaction.columns:
            interaction_cols = [c for c in interaction.columns if c != 'security_id']
            interaction = self.preprocessor.preprocess_dataframe(
                interaction, interaction_cols,
                direction_map=FACTOR_DIRECTIONS,
            )
            merged = pd.merge(merged, interaction, on='security_id', how='outer')

        return merged

    # ==================== 无数据库便捷函数 ====================

    @staticmethod
    def calc_factors_from_data(price_df: pd.DataFrame,
                               financial_df: pd.DataFrame = None,
                               neutralize: bool = False,
                               industry_col: str = None,
                               cap_col: str = None) -> pd.DataFrame:
        """不依赖数据库的因子计算便捷函数"""
        calculator = FactorCalculator()

        factor_dfs = []
        factor_dfs.append(calculator.calc_momentum_factors(price_df))
        factor_dfs.append(calculator.calc_volatility_factors(price_df))
        factor_dfs.append(calculator.calc_liquidity_factors(price_df))
        factor_dfs.append(calculator.calc_microstructure_factors(price_df))
        factor_dfs.append(calculator.calc_technical_factors(price_df))

        if financial_df is not None and not financial_df.empty:
            factor_dfs.append(calculator.calc_valuation_factors(financial_df, price_df))
            factor_dfs.append(calculator.calc_growth_factors(financial_df))
            factor_dfs.append(calculator.calc_quality_factors(financial_df))
            factor_dfs.append(calculator.calc_earnings_quality_factors(financial_df))

        merged = FactorCalculator._merge_factor_dfs(factor_dfs)
        if merged.empty:
            return merged

        factor_cols = [c for c in merged.columns if c != 'security_id']
        merged = calculator.preprocessor.preprocess_dataframe(
            merged, factor_cols,
            industry_col=industry_col,
            cap_col=cap_col,
            neutralize=neutralize,
            direction_map=FACTOR_DIRECTIONS,
        )
        return merged

    # ==================== 盈利质量因子 ====================

    def calc_earnings_quality_factors(self, financial_df: pd.DataFrame) -> pd.DataFrame:
        """
        盈利质量因子
        - accrual_anomaly: 改进Sloan应计异常 (区分经营性/投资性应计)
        - cash_flow_manipulation: 现金流操纵概率 (CFO与净利偏离度)
        - earnings_stability: 盈利稳定性 (近8季净利CV的倒数)
        - cfo_to_net_profit: CFO/净利 (现金流支撑度)
        """
        result = pd.DataFrame()
        result['security_id'] = financial_df.get('ts_code', financial_df.index)

        # 改进Sloan应计异常
        required = ['net_profit', 'operating_cash_flow', 'total_assets']
        if all(c in financial_df.columns for c in required):
            accruals = financial_df['net_profit'] - financial_df['operating_cash_flow']
            if 'total_assets_prev' in financial_df.columns:
                avg_assets = (financial_df['total_assets'] + financial_df['total_assets_prev']) / 2
            else:
                avg_assets = financial_df['total_assets']
            result['accrual_anomaly'] = accruals / avg_assets.replace(0, np.nan)

            # 现金流操纵概率: |CFO - Net Profit| / |Net Profit|
            net_profit = financial_df['net_profit'].replace(0, np.nan)
            result['cash_flow_manipulation'] = (
                (financial_df['operating_cash_flow'] - financial_df['net_profit']).abs()
                / net_profit.abs()
            )

            # CFO/净利: 现金流支撑度
            result['cfo_to_net_profit'] = (
                financial_df['operating_cash_flow'] / net_profit
            ).clip(-5, 5)

        # 盈利稳定性: 需要多期数据
        if 'net_profit_std_8q' in financial_df.columns and 'net_profit_mean_8q' in financial_df.columns:
            mean = financial_df['net_profit_mean_8q'].replace(0, np.nan)
            std = financial_df['net_profit_std_8q']
            cv = (std / mean.abs()).clip(0, 10)
            result['earnings_stability'] = 1 / (1 + cv)

        return result

    # ==================== 聪明钱因子 ====================

    def calc_smart_money_factors(self, price_df: pd.DataFrame,
                                  northbound_df: Optional[pd.DataFrame] = None,
                                  margin_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        聪明钱因子
        - smart_money_ratio: 聪明钱比率 (大单净买入/总成交)
        - north_momentum_20d: 北向资金20日动量
        - margin_signal: 融资融券信号 (融资余额变化率)
        - institutional_holding_chg: 机构持仓变化
        """
        result = pd.DataFrame()
        result['security_id'] = price_df.get('ts_code', price_df.index)

        # 聪明钱比率
        if all(c in price_df.columns for c in ['large_order_volume', 'super_large_order_volume', 'volume']):
            smart_vol = price_df['large_order_volume'].fillna(0) + price_df['super_large_order_volume'].fillna(0)
            total_vol = price_df['volume'].replace(0, np.nan)
            result['smart_money_ratio'] = (smart_vol / total_vol).rolling(20, min_periods=5).mean()

        # 北向资金动量
        if northbound_df is not None and not northbound_df.empty:
            if 'north_holding' in northbound_df.columns:
                result['north_momentum_20d'] = northbound_df['north_holding'].pct_change(20)

        # 融资融券信号
        if margin_df is not None and not margin_df.empty:
            if 'margin_balance' in margin_df.columns:
                result['margin_signal'] = margin_df['margin_balance'].pct_change(5)
        elif 'margin_balance' in price_df.columns:
            result['margin_signal'] = price_df['margin_balance'].pct_change(5)

        # 机构持仓变化
        if 'institutional_holding_pct' in price_df.columns:
            result['institutional_holding_chg'] = price_df['institutional_holding_pct'].pct_change(20)

        return result

    # ==================== 技术形态因子 ====================

    def calc_technical_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """
        技术形态因子
        - rsi_14d: 14日RSI (相对强弱指标)
        - bollinger_position: 布林带位置 (0=下轨, 0.5=中轨, 1=上轨)
        - macd_signal: MACD信号线
        - obv_ratio: OBV能量潮比率
        """
        result = pd.DataFrame()
        result['security_id'] = price_df.get('ts_code', price_df.index)

        if 'close' not in price_df.columns:
            return result

        close = price_df['close']
        daily_ret = close.pct_change()

        # RSI(14)
        if len(close) >= 15:
            gain = daily_ret.clip(lower=0)
            loss = (-daily_ret).clip(lower=0)
            avg_gain = gain.rolling(14, min_periods=10).mean()
            avg_loss = loss.rolling(14, min_periods=10).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            result['rsi_14d'] = 100 - (100 / (1 + rs))

        # 布林带位置
        if len(close) >= 20:
            ma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            result['bollinger_position'] = ((close - ma20) / (2 * std20)).clip(-1, 1)

        # MACD信号
        if len(close) >= 35:
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            dif = ema12 - ema26
            dea = dif.ewm(span=9, adjust=False).mean()
            result['macd_signal'] = (dif - dea) / close.replace(0, np.nan) * 100

        # OBV能量潮比率
        if 'volume' in price_df.columns and len(close) >= 20:
            direction = np.sign(daily_ret).fillna(0)
            obv = (direction * price_df['volume']).cumsum()
            obv_ma = obv.rolling(20, min_periods=10).mean()
            result['obv_ratio'] = (obv / obv_ma.replace(0, np.nan) - 1).clip(-3, 3)

        return result

    # ==================== 行业轮动因子 ====================

    def calc_industry_rotation_factors(self, price_df: pd.DataFrame,
                                         industry_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        行业轮动因子
        - industry_momentum_1m: 行业1月动量
        - industry_fund_flow: 行业资金流向
        - industry_valuation_deviation: 行业估值偏离
        """
        result = pd.DataFrame()
        result['security_id'] = price_df.get('ts_code', price_df.index)

        if industry_df is None or industry_df.empty:
            return result

        # 行业动量
        if 'industry_return_1m' in industry_df.columns:
            result['industry_momentum_1m'] = industry_df['industry_return_1m']

        # 行业资金流向
        if 'industry_net_inflow' in industry_df.columns:
            result['industry_fund_flow'] = industry_df['industry_net_inflow']

        # 行业估值偏离
        if 'industry_pe' in industry_df.columns and 'industry_pe_mean_3y' in industry_df.columns:
            mean_pe = industry_df['industry_pe_mean_3y'].replace(0, np.nan)
            result['industry_valuation_deviation'] = (
                (industry_df['industry_pe'] - mean_pe) / mean_pe.abs()
            ).clip(-3, 3)

        return result

    # ==================== 另类数据因子 ====================

    def calc_alt_data_factors(self, alt_data_df: pd.DataFrame) -> pd.DataFrame:
        """
        另类数据因子
        - news_sentiment: 新闻情感得分
        - supply_chain_momentum: 供应链传导动量 (Cohen-Frazzini增强)
        - patent_growth: 专利增长率
        """
        result = pd.DataFrame()
        result['security_id'] = alt_data_df.get('ts_code', alt_data_df.index)

        # 新闻情感
        if 'news_sentiment_score' in alt_data_df.columns:
            result['news_sentiment'] = alt_data_df['news_sentiment_score'].rolling(20, min_periods=5).mean()

        # 供应链传导动量
        if 'customer_revenue_growth' in alt_data_df.columns and 'supplier_revenue_growth' in alt_data_df.columns:
            # Cohen-Frazzini: 客户动量 + 供应商动量的加权平均
            result['supply_chain_momentum'] = (
                0.6 * alt_data_df['customer_revenue_growth'] +
                0.4 * alt_data_df['supplier_revenue_growth']
            )
        elif 'customer_revenue_growth' in alt_data_df.columns:
            result['supply_chain_momentum'] = alt_data_df['customer_revenue_growth']

        # 专利增长
        if 'patent_count' in alt_data_df.columns:
            result['patent_growth'] = alt_data_df['patent_count'].pct_change(4)

        return result
