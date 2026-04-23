"""
因子计算器 - 纯计算类，无数据库依赖
从FactorEngine拆分出的所有calc_*_factors方法
机构级: 向量化批处理、跳月动量、TTM原始报表计算、Sloan应计、交互因子
PIT安全: 所有财务因子计算均遵守Point-in-Time原则，仅使用ann_date <= trade_date的数据
"""
from typing import Dict, Optional
from datetime import date
import numpy as np
import pandas as pd
from app.core.factor_preprocess import FactorPreprocessor


def _safe_divide(numerator, denominator, eps: float = 1e-8):
    """安全除法: 分母接近0时返回NaN，避免inf污染"""
    denom = np.where(np.abs(denominator) < eps, np.nan, denominator)
    return numerator / denom


def pit_filter(financial_df: pd.DataFrame, trade_date: date,
               ann_date_col: str = 'ann_date') -> pd.DataFrame:
    """
    PIT (Point-in-Time) 过滤: 仅使用公告日 <= 交易日的财务数据
    消除财务数据的前瞻偏差(在公告日前使用未公开财务数据)

    对于同一股票同一报告期有多条记录的情况，取ann_date <= trade_date中最新的一条

    Args:
        financial_df: 财务数据DataFrame，需包含 ann_date 列和 ts_code 列
        trade_date: 当前交易日期
        ann_date_col: 公告日期列名

    Returns:
        过滤后的DataFrame
    """
    if financial_df.empty:
        return financial_df

    if ann_date_col not in financial_df.columns:
        # 没有公告日期列，无法做PIT过滤，发出警告
        import warnings
        warnings.warn(
            f"Financial data missing '{ann_date_col}' column, "
            "PIT filtering cannot be applied. This may introduce look-ahead bias.",
            UserWarning,
        )
        return financial_df

    # 确保日期类型一致
    ann_dates = pd.to_datetime(financial_df[ann_date_col])
    trade_dt = pd.to_datetime(trade_date)

    # 仅保留公告日 <= 交易日的记录
    mask = ann_dates <= trade_dt
    filtered = financial_df.loc[mask].copy()

    if filtered.empty:
        return filtered

    # 对于同一股票同一报告期，取最新的公告记录
    # 如果有report_period列，按(ts_code, report_period)去重取最新ann_date
    if 'report_period' in filtered.columns:
        filtered = filtered.sort_values([ann_date_col], ascending=False)
        filtered = filtered.drop_duplicates(subset=['ts_code', 'report_period'], keep='first')
    elif 'end_date' in filtered.columns:
        filtered = filtered.sort_values([ann_date_col], ascending=False)
        filtered = filtered.drop_duplicates(subset=['ts_code', 'end_date'], keep='first')

    return filtered


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

    def calc_valuation_factors(self, financial_df: pd.DataFrame,
                               price_df: pd.DataFrame = None,
                               trade_date: Optional[date] = None) -> pd.DataFrame:
        """计算价值因子 (优先从原始财务数据计算TTM, 回退到预计算比率)
        PIT安全: 当trade_date提供时，仅使用ann_date <= trade_date的财务数据
        """
        # PIT过滤
        if trade_date is not None:
            financial_df = pit_filter(financial_df, trade_date)

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

    def calc_growth_factors(self, financial_df: pd.DataFrame,
                            trade_date: Optional[date] = None) -> pd.DataFrame:
        """
        计算成长因子 (优先从连续季报计算YoY)
        PIT安全: 当trade_date提供时，仅使用ann_date <= trade_date的财务数据
        """
        # PIT过滤
        if trade_date is not None:
            financial_df = pit_filter(financial_df, trade_date)

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

    def calc_quality_factors(self, financial_df: pd.DataFrame,
                             trade_date: Optional[date] = None) -> pd.DataFrame:
        """
        计算质量因子 (ROE/ROA用平均净资产/总资产)
        PIT安全: 当trade_date提供时，仅使用ann_date <= trade_date的财务数据
        注意: Sloan应计已移至calc_accruals_factor，此处不再重复计算
        """
        # PIT过滤
        if trade_date is not None:
            financial_df = pit_filter(financial_df, trade_date)

        result = pd.DataFrame()
        result['security_id'] = financial_df['ts_code']

        has_raw = all(c in financial_df.columns for c in ['net_profit', 'total_equity'])
        if has_raw:
            if 'total_equity_prev' in financial_df.columns:
                avg_equity = (financial_df['total_equity'] + financial_df['total_equity_prev']) / 2
                result['roe'] = financial_df['net_profit'] / avg_equity.replace(0, np.nan)
            else:
                # 无上期数据时用期末*0.9近似期初值，避免高估ROE
                avg_equity = (financial_df['total_equity'] + financial_df['total_equity'] * 0.9) / 2
                result['roe'] = financial_df['net_profit'] / avg_equity.replace(0, np.nan)

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

            # 注意: Sloan应计已移至calc_accruals_factor，避免重复计算
        else:
            result['roe'] = financial_df.get('roe')
            result['roa'] = financial_df.get('roa')
            result['gross_profit_margin'] = financial_df.get('gross_profit_margin')
            result['net_profit_margin'] = financial_df.get('net_profit_margin')
            result['current_ratio'] = financial_df.get('current_ratio')

        return result

    # ==================== 动量因子 ====================

    def calc_momentum_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算动量因子 (跳月处理: 跳过最近1月避免短期反转污染)
        面板数据安全: 使用groupby('ts_code')确保rolling/shift不跨股票边界
        """
        result = pd.DataFrame()
        if 'close' not in price_df.columns or 'ts_code' not in price_df.columns:
            return result

        # 关键: 面板数据必须先按(ts_code, trade_date)排序，否则shift会跨股票边界
        if 'trade_date' in price_df.columns:
            price_df = price_df.sort_values(['ts_code', 'trade_date'])

        # 面板数据: 按股票分组计算，避免跨股票边界
        grouped = price_df.groupby('ts_code')
        close = price_df['close']
        close_shift_20 = grouped['close'].shift(20)
        close_shift_60 = grouped['close'].shift(60)
        close_shift_120 = grouped['close'].shift(120)
        close_shift_240 = grouped['close'].shift(240)

        result['security_id'] = price_df['ts_code']
        result['ret_1m_reversal'] = close / close_shift_20 - 1
        result['ret_3m_skip1'] = _safe_divide(close_shift_20, close_shift_60) - 1
        result['ret_6m_skip1'] = _safe_divide(close_shift_20, close_shift_120) - 1
        result['ret_12m_skip1'] = _safe_divide(close_shift_20, close_shift_240) - 1
        return result

    # ==================== 波动率因子 ====================

    def calc_volatility_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算波动率因子
        面板数据安全: 使用groupby('ts_code')确保rolling不跨股票边界
        """
        result = pd.DataFrame()
        if 'close' not in price_df.columns:
            return result

        result['security_id'] = price_df.get('ts_code')

        if 'ts_code' in price_df.columns:
            # 面板数据: 按股票分组rolling
            result['vol_20d'] = price_df.groupby('ts_code')['close'].transform(
                lambda s: s.pct_change().rolling(20, min_periods=10).std()
            ) * np.sqrt(252)
            result['vol_60d'] = price_df.groupby('ts_code')['close'].transform(
                lambda s: s.pct_change().rolling(60, min_periods=30).std()
            ) * np.sqrt(252)
        else:
            # 单股时间序列
            daily_ret = price_df['close'].pct_change()
            result['vol_20d'] = daily_ret.rolling(20).std() * np.sqrt(252)
            result['vol_60d'] = daily_ret.rolling(60).std() * np.sqrt(252)
        return result

    # ==================== 流动性因子 ====================

    def calc_liquidity_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算流动性因子
        面板数据安全: 使用groupby('ts_code')确保rolling不跨股票边界
        """
        result = pd.DataFrame()
        if 'turnover_rate' not in price_df.columns:
            return result

        result['security_id'] = price_df.get('ts_code')

        if 'ts_code' in price_df.columns:
            grouped = price_df.groupby('ts_code')
            result['turnover_20d'] = grouped['turnover_rate'].transform(
                lambda s: s.rolling(20, min_periods=10).mean()
            )
            result['turnover_60d'] = grouped['turnover_rate'].transform(
                lambda s: s.rolling(60, min_periods=30).mean()
            )

            if 'amount' in price_df.columns and 'close' in price_df.columns:
                daily_ret = price_df['close'] / grouped['close'].shift(1) - 1
                amihud_daily = daily_ret.abs() / price_df['amount'].replace(0, np.nan)
                result['amihud_20d'] = amihud_daily.groupby(price_df['ts_code']).transform(
                    lambda s: s.rolling(20, min_periods=10).mean()
                )

            if 'close' in price_df.columns:
                daily_ret = price_df['close'] / grouped['close'].shift(1) - 1
                result['zero_return_ratio'] = (daily_ret.abs() < 0.001).groupby(
                    price_df['ts_code']
                ).transform(lambda s: s.rolling(20, min_periods=10).mean())
        else:
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
        """微观结构因子
        面板数据安全: 使用groupby('ts_code')确保shift/rolling不跨股票边界
        """
        result = pd.DataFrame()
        result['security_id'] = price_df.get('ts_code')

        if 'ts_code' not in price_df.columns:
            # 单股时间序列模式
            if all(c in price_df.columns for c in ['large_order_volume', 'super_large_order_volume', 'volume']):
                smart_money_vol = price_df['large_order_volume'].fillna(0) + price_df['super_large_order_volume'].fillna(0)
                result['large_order_ratio'] = smart_money_vol / price_df['volume'].replace(0, np.nan)
                result['large_order_ratio'] = result['large_order_ratio'].rolling(20, min_periods=5).mean()

            if all(c in price_df.columns for c in ['open', 'close']):
                result['overnight_return'] = _safe_divide(price_df['open'], price_df['close'].shift(1)) - 1
                result['overnight_return'] = result['overnight_return'].rolling(20, min_periods=5).mean()

            if all(c in price_df.columns for c in ['open', 'close']):
                intraday_ret = _safe_divide(price_df['close'], price_df['open']) - 1
                overnight_ret = _safe_divide(price_df['open'], price_df['close'].shift(1)) - 1
                result['intraday_return_ratio'] = (
                    intraday_ret.abs().rolling(20, min_periods=5).mean()
                    / overnight_ret.abs().rolling(20, min_periods=5).mean().replace(0, np.nan)
                )

            if all(c in price_df.columns for c in ['close', 'volume']):
                daily_ret = price_df['close'].pct_change()
                abs_ret = daily_ret.abs()
                vol_ratio = _safe_divide(price_df['volume'], price_df['volume'].rolling(20, min_periods=5).mean())
                result['vpin'] = (abs_ret * vol_ratio).rolling(20, min_periods=5).mean()
            return result

        # 面板数据模式: 按股票分组
        grouped = price_df.groupby('ts_code')

        if all(c in price_df.columns for c in ['large_order_volume', 'super_large_order_volume', 'volume']):
            smart_money_vol = price_df['large_order_volume'].fillna(0) + price_df['super_large_order_volume'].fillna(0)
            result['large_order_ratio'] = smart_money_vol / price_df['volume'].replace(0, np.nan)
            result['large_order_ratio'] = result['large_order_ratio'].groupby(price_df['ts_code']).transform(
                lambda s: s.rolling(20, min_periods=5).mean()
            )

        if all(c in price_df.columns for c in ['open', 'close']):
            prev_close = grouped['close'].shift(1)
            result['overnight_return'] = _safe_divide(price_df['open'], prev_close) - 1
            result['overnight_return'] = result['overnight_return'].groupby(price_df['ts_code']).transform(
                lambda s: s.rolling(20, min_periods=5).mean()
            )

        if all(c in price_df.columns for c in ['open', 'close']):
            intraday_ret = _safe_divide(price_df['close'], price_df['open']) - 1
            overnight_ret = _safe_divide(price_df['open'], grouped['close'].shift(1)) - 1
            result['intraday_return_ratio'] = _safe_divide(
                intraday_ret.abs().groupby(price_df['ts_code']).transform(
                    lambda s: s.rolling(20, min_periods=5).mean()
                ),
                overnight_ret.abs().groupby(price_df['ts_code']).transform(
                    lambda s: s.rolling(20, min_periods=5).mean()
                )
            )

        if all(c in price_df.columns for c in ['close', 'volume']):
            daily_ret = price_df['close'] / grouped['close'].shift(1) - 1
            abs_ret = daily_ret.abs()
            vol_ratio = _safe_divide(
                price_df['volume'],
                price_df.groupby('ts_code')['volume'].transform(
                    lambda s: s.rolling(20, min_periods=5).mean()
                )
            )
            result['vpin'] = (abs_ret * vol_ratio).groupby(price_df['ts_code']).transform(
                lambda s: s.rolling(20, min_periods=5).mean()
            )

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
            # 涨跌停判断需区分板块: 主板10%, 创业板/科创板20%, 北交所30%, ST5%
            # pct_chg为百分比形式(如9.9表示9.9%)
            limit_pct = pd.Series(10.0, index=price_df.index)  # 默认主板10%

            if 'ts_code' in price_df.columns:
                ts = price_df['ts_code'].astype(str)
                # 创业板(300xxx.SZ)
                limit_pct[ts.str.startswith('3') & ts.str.endswith('.SZ')] = 20.0
                # 科创板(688xxx.SH)
                limit_pct[ts.str.startswith('688') & ts.str.endswith('.SH')] = 20.0
                # 北交所(8xxxxx.BJ / 4xxxxx.BJ)
                limit_pct[ts.str.endswith('.BJ')] = 30.0

            # ST股5%涨跌停
            if stock_status_df is not None and 'is_st' in stock_status_df.columns:
                st_map = stock_status_df.set_index('ts_code')['is_st']
                is_st = price_df['ts_code'].map(st_map).fillna(False) if 'ts_code' in price_df.columns else pd.Series(False, index=price_df.index)
                limit_pct[is_st] = 5.0

            is_limit_up = (price_df['pct_chg'] >= limit_pct - 0.01).astype(float)
            is_limit_down = (price_df['pct_chg'] <= -(limit_pct - 0.01)).astype(float)

            if 'ts_code' in price_df.columns:
                result['limit_up_ratio_20d'] = is_limit_up.groupby(price_df['ts_code']).transform(
                    lambda s: s.rolling(20, min_periods=10).mean())
                result['limit_down_ratio_20d'] = is_limit_down.groupby(price_df['ts_code']).transform(
                    lambda s: s.rolling(20, min_periods=10).mean())
            else:
                result['limit_up_ratio_20d'] = is_limit_up.rolling(20, min_periods=10).mean()
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

    def calc_accruals_factor(self, financial_df: pd.DataFrame,
                              trade_date: Optional[date] = None) -> pd.DataFrame:
        """Sloan应计因子
        PIT安全: 当trade_date提供时，仅使用ann_date <= trade_date的财务数据
        """
        if trade_date is not None:
            financial_df = pit_filter(financial_df, trade_date)

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
        """因子交互项 (在原始值层面计算，保留经济含义)
        重要: 交互项必须在标准化之前计算，两个z-score相乘不再具有原始经济含义
        """
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
                         stock_status_df: pd.DataFrame = None,
                         money_flow_df: pd.DataFrame = None,
                         margin_df: pd.DataFrame = None,
                         daily_basic_df: pd.DataFrame = None,
                         trade_date: Optional[date] = None) -> pd.DataFrame:
        """
        计算所有因子并预处理 (向量化批处理合并)
        PIT安全: 当trade_date提供时，财务因子仅使用ann_date <= trade_date的数据
        """
        factor_dfs = []

        # 基础因子 (财务因子传入trade_date做PIT过滤)
        factor_dfs.append(self.calc_valuation_factors(financial_df, price_df, trade_date=trade_date))
        factor_dfs.append(self.calc_growth_factors(financial_df, trade_date=trade_date))
        factor_dfs.append(self.calc_quality_factors(financial_df, trade_date=trade_date))
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
            factor_dfs.append(self.calc_accruals_factor(financial_df, trade_date=trade_date))
            factor_dfs.append(self.calc_earnings_quality_factors(financial_df, trade_date=trade_date))

        # 机构级增强因子
        factor_dfs.append(self.calc_technical_factors(price_df))
        factor_dfs.append(self.calc_smart_money_factors(price_df, northbound_df, margin_df))

        # 行业轮动因子
        factor_dfs.append(self.calc_industry_rotation_factors(price_df))

        # 另类数据因子 (已在supply_chain_df处理中调用，此处不再重复)
        # 注: calc_alt_data_factors已在上方supply_chain_df分支中调用

        # 从资金流向表补充微观结构数据
        if money_flow_df is not None and not money_flow_df.empty:
            mf_result = pd.DataFrame()
            mf_result['security_id'] = money_flow_df.get('ts_code', money_flow_df.index)
            if 'smart_net_pct' in money_flow_df.columns:
                mf_result['smart_money_ratio'] = money_flow_df['smart_net_pct'].rolling(20, min_periods=5).mean() / 100
            if 'large_net_pct' in money_flow_df.columns and 'super_large_net_pct' in money_flow_df.columns:
                mf_result['large_order_ratio'] = (
                    money_flow_df['large_net_pct'].fillna(0) + money_flow_df['super_large_net_pct'].fillna(0)
                ).rolling(20, min_periods=5).mean() / 100
            if not mf_result.empty:
                factor_dfs.append(mf_result)

        # 从融资融券表补充情绪数据
        if margin_df is not None and not margin_df.empty:
            mg_result = pd.DataFrame()
            mg_result['security_id'] = margin_df.get('ts_code', margin_df.index)
            if 'margin_balance' in margin_df.columns:
                mg_result['margin_signal'] = margin_df['margin_balance'].pct_change(5)
            if not mg_result.empty:
                factor_dfs.append(mg_result)

        # 向量化合并
        merged = self._merge_factor_dfs(factor_dfs)
        if merged.empty:
            return merged

        # 交互因子 (必须在标准化之前计算，保留原始经济含义)
        # 两个z-score相乘不再具有原始经济含义
        interaction = self.calc_interaction_factors(merged)
        if not interaction.empty and 'security_id' in interaction.columns:
            merged = pd.merge(merged, interaction, on='security_id', how='outer')

        # 预处理 (包含交互因子)
        factor_cols = [c for c in merged.columns if c != 'security_id']
        merged = self.preprocessor.preprocess_dataframe(
            merged, factor_cols,
            industry_col=industry_col,
            cap_col=cap_col,
            neutralize=neutralize,
            direction_map=FACTOR_DIRECTIONS,
        )

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

    def calc_earnings_quality_factors(self, financial_df: pd.DataFrame,
                                       trade_date: Optional[date] = None) -> pd.DataFrame:
        """
        盈利质量因子
        - accrual_anomaly: 改进Sloan应计异常 (区分经营性/投资性应计)
        - cash_flow_manipulation: 现金流操纵概率 (CFO与净利偏离度)
        - earnings_stability: 盈利稳定性 (近8季净利CV的倒数)
        - cfo_to_net_profit: CFO/净利 (现金流支撑度)
        PIT安全: 当trade_date提供时，仅使用ann_date <= trade_date的财务数据
        """
        if trade_date is not None:
            financial_df = pit_filter(financial_df, trade_date)

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

        # RSI(14) - Wilder平滑法 (标准定义)
        # 使用价格差而非收益率，Wilder EMA (alpha=1/14) 而非SMA
        if len(close) >= 15:
            price_diff = close.diff()  # 标准RSI使用价格差
            gain = price_diff.clip(lower=0)
            loss = (-price_diff).clip(lower=0)
            # Wilder平滑: EMA with alpha=1/period
            wilder_alpha = 1.0 / 14
            avg_gain = gain.ewm(alpha=wilder_alpha, adjust=False).mean()
            avg_loss = loss.ewm(alpha=wilder_alpha, adjust=False).mean()
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
