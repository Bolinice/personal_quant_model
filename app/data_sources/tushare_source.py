"""
Tushare 数据源适配器
专业金融数据接口
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
from app.data_sources.base import BaseDataSource
from app.core.logging import logger


class TushareDataSource(BaseDataSource):
    """Tushare 数据源"""

    def __init__(self, token: str = None):
        super().__init__("tushare")
        self.token = token
        self._pro = None

    def connect(self) -> bool:
        """连接 Tushare"""
        try:
            import tushare as ts
            if self.token:
                ts.set_token(self.token)
            self._pro = ts.pro_api()
            # 测试连接 - 使用股票基础信息接口（免费账户可用）
            df = self._pro.stock_basic(exchange='', list_status='L', fields='ts_code')
            self._connected = not df.empty
            if self._connected:
                logger.info("Tushare connected successfully (limited API access)")
            return self._connected
        except Exception as e:
            logger.error(f"Failed to connect Tushare: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected

    def _format_date(self, date_str: str) -> str:
        """将 YYYY-MM-DD 转换为 YYYYMMDD"""
        if not date_str:
            return None
        return date_str.replace('-', '')

    def _format_date_back(self, date_str: str) -> str:
        """将 YYYYMMDD 转换为 YYYY-MM-DD"""
        if not date_str or len(date_str) != 8:
            return date_str
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    # ==================== 行情数据 ====================

    def get_stock_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票日线行情"""
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.daily(
                ts_code=ts_code,
                start_date=self._format_date(start_date),
                end_date=self._format_date(end_date)
            )

            if df.empty:
                return pd.DataFrame()

            df = df.rename(columns={
                'vol': 'volume',
                'pct_chg': 'pct_chg'
            })
            df['trade_date'] = df['trade_date'].apply(self._format_date_back)

            return df[['trade_date', 'open', 'high', 'low', 'close',
                      'volume', 'amount', 'pct_chg', 'pre_close']]

        except Exception as e:
            logger.error(f"Error getting stock daily: {e}")
            return pd.DataFrame()

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数日线行情"""
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.index_daily(
                ts_code=index_code,
                start_date=self._format_date(start_date),
                end_date=self._format_date(end_date)
            )

            if df.empty:
                return pd.DataFrame()

            df = df.rename(columns={'vol': 'volume'})
            df['trade_date'] = df['trade_date'].apply(self._format_date_back)

            return df[['trade_date', 'open', 'high', 'low', 'close',
                      'volume', 'amount', 'pct_chg', 'pre_close']]

        except Exception as e:
            logger.error(f"Error getting index daily: {e}")
            return pd.DataFrame()

    def get_stock_daily_batch(self, ts_codes: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """批量获取多只股票日线行情"""
        if not self._connected:
            return pd.DataFrame()

        all_data = []
        for ts_code in ts_codes:
            df = self.get_stock_daily(ts_code, start_date, end_date)
            if not df.empty:
                df['ts_code'] = ts_code
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        return pd.concat(all_data, ignore_index=True)

    # ==================== 基础数据 ====================

    def get_stock_basic(self) -> pd.DataFrame:
        """获取股票基础信息"""
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,market,list_date,delist_date,is_hs')

            if df.empty:
                return pd.DataFrame()

            df['status'] = 'L'
            return df[['ts_code', 'symbol', 'name', 'industry', 'market', 'list_date', 'status']]

        except Exception as e:
            logger.error(f"Error getting stock basic: {e}")
            return pd.DataFrame()

    def get_index_components(self, index_code: str, date: str = None) -> List[str]:
        """获取指数成分股"""
        if not self._connected:
            return []

        try:
            date_str = self._format_date(date) if date else None

            df = self._pro.index_weight(
                index_code=index_code,
                start_date=date_str,
                end_date=date_str
            )

            if df.empty:
                return []

            return df['con_code'].tolist()

        except Exception as e:
            logger.error(f"Error getting index components: {e}")
            return []

    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取交易日历"""
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.trade_cal(
                exchange='SSE',
                start_date=self._format_date(start_date),
                end_date=self._format_date(end_date)
            )

            if df.empty:
                return pd.DataFrame()

            df = df.rename(columns={'cal_date': 'trade_date', 'pretrade_date': 'pretrade_date'})
            df['trade_date'] = df['trade_date'].apply(self._format_date_back)
            if 'pretrade_date' in df.columns:
                df['pretrade_date'] = df['pretrade_date'].apply(self._format_date_back)

            return df[['trade_date', 'is_open', 'pretrade_date']]

        except Exception as e:
            logger.error(f"Error getting trading calendar: {e}")
            return pd.DataFrame()

    # ==================== 财务数据 ====================

    def get_financial_indicator(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取财务指标"""
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.fina_indicator(
                ts_code=ts_code,
                start_date=self._format_date(start_date) if start_date else None,
                end_date=self._format_date(end_date) if end_date else None
            )

            if df.empty:
                return pd.DataFrame()

            df['end_date'] = df['end_date'].apply(self._format_date_back)

            # 选择常用指标
            columns = ['ts_code', 'end_date', 'ann_date', 'roe', 'roa',
                      'grossprofit_margin', 'netprofit_margin', 'debt_to_assets',
                      'current_ratio', 'quick_ratio', 'ocfps', 'eps', 'bps']

            available_cols = [col for col in columns if col in df.columns]
            return df[available_cols]

        except Exception as e:
            logger.error(f"Error getting financial indicator: {e}")
            return pd.DataFrame()

    def get_financial_data(self, ts_code: str = None, start_date: str = None,
                           end_date: str = None, **kwargs) -> pd.DataFrame:
        """获取财务数据（兼容基类接口）"""
        if ts_code:
            return self.get_financial_indicator(ts_code, start_date, end_date)
        return pd.DataFrame()

    def get_income_statement(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取利润表"""
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.income(
                ts_code=ts_code,
                start_date=self._format_date(start_date) if start_date else None,
                end_date=self._format_date(end_date) if end_date else None
            )

            if df.empty:
                return pd.DataFrame()

            df['end_date'] = df['end_date'].apply(self._format_date_back)
            return df

        except Exception as e:
            logger.error(f"Error getting income statement: {e}")
            return pd.DataFrame()

    def get_balance_sheet(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取资产负债表"""
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.balancesheet(
                ts_code=ts_code,
                start_date=self._format_date(start_date) if start_date else None,
                end_date=self._format_date(end_date) if end_date else None
            )

            if df.empty:
                return pd.DataFrame()

            df['end_date'] = df['end_date'].apply(self._format_date_back)
            return df

        except Exception as e:
            logger.error(f"Error getting balance sheet: {e}")
            return pd.DataFrame()

    # ==================== 行业数据 ====================

    def get_industry_classification(self, ts_code: str = None) -> pd.DataFrame:
        """获取行业分类"""
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.index_classify(level='L1', src='SW')

            if df.empty:
                return pd.DataFrame()

            return df[['index_code', 'industry_name']]

        except Exception as e:
            logger.error(f"Error getting industry classification: {e}")
            return pd.DataFrame()

    # ==================== 复权数据 ====================

    def get_adj_factor(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取复权因子"""
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.adj_factor(
                ts_code=ts_code,
                start_date=self._format_date(start_date),
                end_date=self._format_date(end_date)
            )

            if df.empty:
                return pd.DataFrame()

            df['trade_date'] = df['trade_date'].apply(self._format_date_back)
            return df[['trade_date', 'adj_factor']]

        except Exception as e:
            logger.error(f"Error getting adj factor: {e}")
            return pd.DataFrame()

    # ==================== 特色功能 ====================

    def get_daily_basic(self, trade_date: str) -> pd.DataFrame:
        """
        获取每日基本面数据（PE、PB、市值等）

        Args:
            trade_date: 交易日期

        Returns:
            DataFrame with PE, PB, total_mv, circ_mv etc.
        """
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.daily_basic(
                trade_date=self._format_date(trade_date),
                fields='ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,total_mv,circ_mv'
            )

            if df.empty:
                return pd.DataFrame()

            df['trade_date'] = df['trade_date'].apply(self._format_date_back)
            return df

        except Exception as e:
            logger.error(f"Error getting daily basic: {e}")
            return pd.DataFrame()

    def get_money_flow(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取资金流向数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame with money flow data
        """
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.moneyflow(
                ts_code=ts_code,
                start_date=self._format_date(start_date),
                end_date=self._format_date(end_date)
            )

            if df.empty:
                return pd.DataFrame()

            df['trade_date'] = df['trade_date'].apply(self._format_date_back)
            return df

        except Exception as e:
            logger.error(f"Error getting money flow: {e}")
            return pd.DataFrame()

    def get_limit_price(self, trade_date: str) -> pd.DataFrame:
        """
        获取涨跌停价格

        Args:
            trade_date: 交易日期

        Returns:
            DataFrame with limit up/down prices
        """
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.stk_limit(
                trade_date=self._format_date(trade_date)
            )

            if df.empty:
                return pd.DataFrame()

            df['trade_date'] = df['trade_date'].apply(self._format_date_back)
            return df

        except Exception as e:
            logger.error(f"Error getting limit price: {e}")
            return pd.DataFrame()
