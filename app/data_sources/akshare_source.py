"""
AKShare 数据源适配器
免费开源金融数据接口
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from app.data_sources.base import BaseDataSource
from app.core.logging import logger


class AKShareDataSource(BaseDataSource):
    """AKShare 数据源"""

    def __init__(self):
        super().__init__("akshare")
        self._ak = None

    def connect(self) -> bool:
        """连接 AKShare"""
        try:
            import akshare as ak
            self._ak = ak
            # 测试连接 - 使用腾讯接口（更稳定）
            df = ak.stock_zh_a_hist_tx(symbol='sh600000', start_date='2024-01-01', end_date='2024-01-10')
            self._connected = not df.empty
            if self._connected:
                logger.info("AKShare connected successfully (using Tencent source)")
            return self._connected
        except Exception as e:
            logger.error(f"Failed to connect AKShare: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected

    def _format_code(self, ts_code: str) -> str:
        """将 ts_code 转换为 AKShare 格式"""
        # 600000.SH -> 600000
        if '.' in ts_code:
            return ts_code.split('.')[0]
        return ts_code

    def _format_code_back(self, code: str, market: str = 'SH') -> str:
        """将 AKShare 格式转回 ts_code"""
        # 600000 -> 600000.SH
        if '.' not in code:
            return f"{code}.{market}"
        return code

    # ==================== 行情数据 ====================

    def get_stock_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票日线行情"""
        if not self._connected:
            return pd.DataFrame()

        try:
            code = self._format_code(ts_code)

            # 确定市场前缀
            if ts_code.endswith('.SH'):
                symbol = f'sh{code}'
            else:
                symbol = f'sz{code}'

            # 使用腾讯数据源（更稳定）
            df = self._ak.stock_zh_a_hist_tx(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )

            if df.empty:
                return pd.DataFrame()

            # 重命名列
            df = df.rename(columns={
                'date': 'trade_date',
                'amount': 'volume',  # 腾讯的 amount 是成交量
            })

            # 格式化日期
            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')

            # 计算涨跌幅和昨收
            df['pre_close'] = df['close'].shift(1)
            df['pct_chg'] = (df['close'] / df['pre_close'] - 1) * 100
            df['amount'] = df['volume'] * df['close']  # 估算成交额

            # 选择需要的列
            result_cols = ['trade_date', 'open', 'high', 'low', 'close',
                          'volume', 'amount', 'pct_chg', 'pre_close']
            available_cols = [col for col in result_cols if col in df.columns]

            return df[available_cols]

        except Exception as e:
            logger.error(f"Error getting stock daily: {e}")
            return pd.DataFrame()

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数日线行情"""
        if not self._connected:
            return pd.DataFrame()

        try:
            code = self._format_code(index_code)

            # 指数代码映射
            index_map = {
                '000300': 'sh000300',  # 沪深300
                '000905': 'sh000905',  # 中证500
                '000852': 'sh000852',  # 中证1000
                '000001': 'sh000001',  # 上证指数
                '399001': 'sz399001',  # 深证成指
                '399006': 'sz399006',  # 创业板指
            }

            ak_code = index_map.get(code, f'sh{code}')

            df = self._ak.stock_zh_index_daily(symbol=ak_code)

            if df.empty:
                return pd.DataFrame()

            # 筛选日期范围
            df['trade_date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]

            # 重命名列
            df = df.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })

            # 计算涨跌幅
            df['pct_chg'] = df['close'].pct_change() * 100
            df['pre_close'] = df['close'].shift(1)
            df['amount'] = df['volume'] * df['close']  # 估算成交额

            return df[['trade_date', 'open', 'high', 'low', 'close',
                      'volume', 'amount', 'pct_chg', 'pre_close']]

        except Exception as e:
            logger.error(f"Error getting index daily: {e}")
            return pd.DataFrame()

    def get_stock_daily_batch(self, ts_codes: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """批量获取多只股票日线行情"""
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
            # 使用新浪实时行情获取股票列表
            df = self._ak.stock_zh_a_spot()

            if df.empty:
                return pd.DataFrame()

            # 重命名列 (AKShare 返回中文列名)
            df = df.rename(columns={
                '代码': 'symbol',
                '名称': 'name',
            })

            # 过滤掉北交所股票 (bj开头) 和非主板股票
            df = df[~df['symbol'].str.startswith('bj')]

            # 移除 symbol 中的 sh/sz 前缀
            df['symbol'] = df['symbol'].str.replace('^(sh|sz)', '', regex=True)

            # 构建 ts_code: 6开头为沪市，其他为深市
            df['market'] = df['symbol'].apply(lambda x: 'SH' if x.startswith('6') else 'SZ')
            df['ts_code'] = df['symbol'] + '.' + df['market']
            df['status'] = 'L'
            df['list_date'] = None
            df['industry'] = None

            return df[['ts_code', 'symbol', 'name', 'industry', 'market', 'list_date', 'status']]

        except Exception as e:
            logger.error(f"Error getting stock basic: {e}")
            return pd.DataFrame()

    def get_index_components(self, index_code: str, date: str = None) -> List[str]:
        """获取指数成分股"""
        if not self._connected:
            return []

        try:
            code = self._format_code(index_code)

            # 指数成分股映射
            if code == '000300':
                df = self._ak.index_stock_cons_weight_csindex(symbol="000300")
            elif code == '000905':
                df = self._ak.index_stock_cons_weight_csindex(symbol="000905")
            elif code == '000852':
                df = self._ak.index_stock_cons_weight_csindex(symbol="000852")
            else:
                df = self._ak.index_stock_cons_weight_csindex(symbol=code)

            if df.empty:
                return []

            # 获取成分股代码
            codes = df['成分券代码'].tolist() if '成分券代码' in df.columns else df.iloc[:, 0].tolist()

            # 转换为 ts_code 格式
            result = []
            for c in codes:
                c = str(c).zfill(6)
                if c.startswith('6'):
                    result.append(f"{c}.SH")
                else:
                    result.append(f"{c}.SZ")

            return result

        except Exception as e:
            logger.error(f"Error getting index components: {e}")
            return []

    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取交易日历"""
        if not self._connected:
            return pd.DataFrame()

        try:
            # 获取交易日历
            df = self._ak.tool_trade_date_hist_sina()

            if df.empty:
                return pd.DataFrame()

            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')

            # 筛选日期范围
            df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]

            df['is_open'] = 1
            df['pretrade_date'] = df['trade_date'].shift(1)

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
            code = self._format_code(ts_code)

            # 获取财务指标数据
            df = self._ak.stock_financial_analysis_indicator(symbol=code)

            if df.empty:
                return pd.DataFrame()

            # 重命名列
            column_map = {
                '日期': 'end_date',
                '净资产收益率': 'roe',
                '总资产净利率': 'roa',
                '销售毛利率': 'grossprofit_margin',
                '销售净利率': 'netprofit_margin',
                '资产负债率': 'debt_to_assets',
                '流动比率': 'current_ratio',
                '速动比率': 'quick_ratio',
            }

            df = df.rename(columns=column_map)

            if 'end_date' in df.columns:
                df['end_date'] = pd.to_datetime(df['end_date']).dt.strftime('%Y-%m-%d')

                # 筛选日期范围
                if start_date:
                    df = df[df['end_date'] >= start_date]
                if end_date:
                    df = df[df['end_date'] <= end_date]

            df['ts_code'] = ts_code

            return df

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
            code = self._format_code(ts_code)

            df = self._ak.stock_financial_report_sina(stock=code, symbol="利润表")

            if df.empty:
                return pd.DataFrame()

            df['ts_code'] = ts_code
            return df

        except Exception as e:
            logger.error(f"Error getting income statement: {e}")
            return pd.DataFrame()

    def get_balance_sheet(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取资产负债表"""
        if not self._connected:
            return pd.DataFrame()

        try:
            code = self._format_code(ts_code)

            df = self._ak.stock_financial_report_sina(stock=code, symbol="资产负债表")

            if df.empty:
                return pd.DataFrame()

            df['ts_code'] = ts_code
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
            # 获取行业板块
            df = self._ak.stock_board_industry_name_em()

            if df.empty:
                return pd.DataFrame()

            return df

        except Exception as e:
            logger.error(f"Error getting industry classification: {e}")
            return pd.DataFrame()

    # ==================== 复权数据 ====================

    def get_adj_factor(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取复权因子"""
        if not self._connected:
            return pd.DataFrame()

        try:
            code = self._format_code(ts_code)

            # 获取前复权数据
            df_qfq = self._ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust="qfq"  # 前复权
            )

            # 获取不复权数据
            df_raw = self._ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                adjust=""
            )

            if df_qfq.empty or df_raw.empty:
                return pd.DataFrame()

            # 计算复权因子
            df_qfq['trade_date'] = pd.to_datetime(df_qfq['日期']).dt.strftime('%Y-%m-%d')
            df_raw['trade_date'] = pd.to_datetime(df_raw['日期']).dt.strftime('%Y-%m-%d')

            merged = df_qfq[['trade_date', '收盘']].merge(
                df_raw[['trade_date', '收盘']],
                on='trade_date',
                suffixes=('_qfq', '_raw')
            )

            merged['adj_factor'] = merged['收盘_qfq'] / merged['收盘_raw']

            return merged[['trade_date', 'adj_factor']]

        except Exception as e:
            logger.error(f"Error getting adj factor: {e}")
            return pd.DataFrame()

    # ==================== 特色功能 ====================

    def get_realtime_quotes(self) -> pd.DataFrame:
        """获取实时行情"""
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._ak.stock_zh_a_spot_em()
            return df

        except Exception as e:
            logger.error(f"Error getting realtime quotes: {e}")
            return pd.DataFrame()

    def get_stock_info(self, ts_code: str) -> Dict[str, Any]:
        """获取股票详细信息"""
        if not self._connected:
            return {}

        try:
            code = self._format_code(ts_code)
            df = self._ak.stock_individual_info_em(symbol=code)

            if df.empty:
                return {}

            return dict(zip(df['item'], df['value']))

        except Exception as e:
            logger.error(f"Error getting stock info: {e}")
            return {}
