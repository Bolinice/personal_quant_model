"""
Tushare 数据源适配器
专业金融数据接口

注意: macOS 系统代理会导致 tushare 请求超时,
此处通过 monkey-patch DataApi.query 使用显式 no-proxy 的 Session 绕过系统代理。
"""
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import requests as _requests
from app.data_sources.base import BaseDataSource
from app.core.logging import logger

# 清除代理环境变量，防止 requests 通过 env 读取代理
for _k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
    os.environ.pop(_k, None)

# 全局 Session: trust_env=False + 显式 no-proxy，彻底绕过 macOS 系统代理
_NO_PROXY_SESSION = _requests.Session()
_NO_PROXY_SESSION.trust_env = False
_NO_PROXY_PROXIES = {'http': None, 'https': None}


def _patch_tushare_query():
    """Monkey-patch tushare DataApi.query, 使用显式 no-proxy 的 requests Session

    macOS 系统代理 (127.0.0.1:7897) 会导致 tushare 请求转发超时。
    requests 默认 trust_env=True，会通过 getproxies() 读取 macOS 系统偏好设置中的代理。
    patch 后改用 trust_env=False + proxies={http:None, https:None} 彻底绕过。
    """
    try:
        from tushare.pro.client import DataApi
        import json

        def patched_query(self, api_name, fields='', **kwargs):
            # 读取实例属性（connect() 设置的代理URL），fallback 到类属性
            http_url = getattr(self, '_DataApi__http_url', DataApi._DataApi__http_url)
            timeout = getattr(self, '_DataApi__timeout', 30)
            token = getattr(self, '_DataApi__token', '')

            kwargs.setdefault('ts_type_name', http_url)
            req_params = {
                'api_name': api_name,
                'token': token,
                'params': kwargs,
                'fields': fields,
            }

            url = f"{http_url}/{api_name}"
            res = _NO_PROXY_SESSION.post(
                url, json=req_params, timeout=timeout,
                proxies=_NO_PROXY_PROXIES,
            )
            if res and res.status_code == 200:
                result = json.loads(res.text)
                if result['code'] != 0:
                    raise Exception(result['msg'])
                data = result['data']
                columns = data['fields']
                items = data['items']
                return pd.DataFrame(items, columns=columns)
            else:
                return pd.DataFrame()

        DataApi.query = patched_query
        logger.info("Tushare DataApi.query patched with no-proxy session")
    except Exception as e:
        logger.warning(f"Failed to patch tushare DataApi: {e}")


# 启动时自动 patch
_patch_tushare_query()


class TushareDataSource(BaseDataSource):
    """Tushare 数据源"""

    def __init__(self, token: str = None):
        super().__init__("tushare")
        self.token = token
        self._pro = None

    def connect(self) -> bool:
        """连接 Tushare（优先代理API，fallback到官方API）"""
        try:
            import tushare as ts
            if self.token:
                ts.set_token(self.token)
            self._pro = ts.pro_api()

            # 优先尝试代理API（全接口权限，无需积分），
            # 官方API需较高积分才能调用fina_indicator/daily_basic等接口
            self._pro._DataApi__http_url = "http://tsy.xiaodefa.cn"
            try:
                df = self._pro.stock_basic(exchange='', list_status='L', fields='ts_code')
                if not df.empty:
                    self._connected = True
                    logger.info("Tushare connected successfully (proxy API, full access)")
                    return True
            except Exception:
                logger.warning("Proxy API unavailable, falling back to official API")

            # Fallback: 官方 API（部分接口可能权限不足）
            self._pro._DataApi__http_url = "https://api.tushare.pro"
            try:
                df = self._pro.stock_basic(exchange='', list_status='L', fields='ts_code')
                if not df.empty:
                    self._connected = True
                    logger.info("Tushare connected successfully (official API, limited access)")
                    return True
            except Exception as e2:
                logger.error(f"Both proxy and official API failed: {e2}")

            self._connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect Tushare: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected

    def _format_date(self, date_str: str) -> str:
        """将 YYYY-MM-DD 转换为 YYYYMMDD — Tushare API要求YYYYMMDD格式"""
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
                'vol': 'volume',  # Tushare用'vol'，统一为'volume'以兼容AKShare和下游逻辑
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
            # list_status='L'仅获取上市股票，已退市/暂停上市不纳入股票池
            # delist_date用于判断即将退市的股票

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
        """获取财务指标 — 注意: Tushare返回的是报告期(end_date)，非公告日，
        因子计算时必须按ann_date(公告日)对齐到PIT时点，否则引入未来函数"""
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
            # pe_ttm/ps_ttm等TTM指标由Tushare在服务端计算，使用最近4个季度滚动加总
            # 相比本地手算TTM，Tushare的TTM已处理亏损/空值等边界情况
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
            # 申万一级分类，因子中性化时按此行业分组
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

    def get_daily_basic(self, trade_date: str = None, ts_code: str = None,
                        start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        获取每日基本面数据（PE/PB/市值/换手率等）

        支持两种调用方式:
        1. 按交易日获取全市场: get_daily_basic(trade_date='2026-04-17')
        2. 按股票+日期范围: get_daily_basic(ts_code='000001.SZ', start_date='2026-01-01', end_date='2026-04-18')

        注意: total_mv/circ_mv单位为万元，使用时需*10000转为元
        pe_ttm为滚动市盈率（TTM），pb为静态市净率（最新报告期）

        Args:
            trade_date: 交易日期 YYYY-MM-DD（获取全市场快照）
            ts_code: 股票代码
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            DataFrame with PE, PB, total_mv, circ_mv etc.
        """
        if not self._connected:
            return pd.DataFrame()

        try:
            params = {
                'fields': 'ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_mv,circ_mv'
                # turnover_rate_f为自由流通股换手率，比turnover_rate(总股本换手率)更能反映真实交易活跃度
            }
            if trade_date:
                params['trade_date'] = self._format_date(trade_date)
            if ts_code:
                params['ts_code'] = ts_code
            if start_date:
                params['start_date'] = self._format_date(start_date)
            if end_date:
                params['end_date'] = self._format_date(end_date)

            df = self._pro.daily_basic(**params)

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

    def get_hsgt_top10(self, trade_date: str) -> pd.DataFrame:
        """
        获取沪深港通十大成交股

        Args:
            trade_date: 交易日期 YYYY-MM-DD

        Returns:
            DataFrame with north money flow data per stock
        """
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.hsgt_top10(trade_date=self._format_date(trade_date))

            if df.empty:
                return pd.DataFrame()

            df['trade_date'] = df['trade_date'].apply(self._format_date_back)
            return df

        except Exception as e:
            logger.error(f"Error getting hsgt_top10: {e}")
            return pd.DataFrame()

    def get_moneyflow_hsgt(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取北向资金净流入汇总

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            DataFrame with daily north/south money flow totals
        """
        if not self._connected:
            return pd.DataFrame()

        try:
            df = self._pro.moneyflow_hsgt(
                start_date=self._format_date(start_date),
                end_date=self._format_date(end_date)
            )

            if df.empty:
                return pd.DataFrame()

            df['trade_date'] = df['trade_date'].apply(self._format_date_back)
            return df

        except Exception as e:
            logger.error(f"Error getting moneyflow_hsgt: {e}")
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

    # ==================== 股权质押 ====================

    def get_share_pledge(self, ts_code: str = None, start_date: str = None,
                         end_date: str = None) -> pd.DataFrame:
        """获取股权质押数据"""
        if not self._connected:
            return pd.DataFrame()
        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if start_date:
                params['start_date'] = self._format_date(start_date)
            if end_date:
                params['end_date'] = self._format_date(end_date)
            df = self._pro.share_pledge(**params)
            if df is None or df.empty:
                return pd.DataFrame()
            if 'end_date' in df.columns:
                df['end_date'] = df['end_date'].apply(self._format_date_back)
            return df
        except Exception as e:
            logger.error(f"Error getting share pledge: {e}")
            return pd.DataFrame()

    # ==================== 前十大股东 ====================

    def get_top10_holders(self, ts_code: str, period: str = None) -> pd.DataFrame:
        """获取前十大股东数据"""
        if not self._connected:
            return pd.DataFrame()
        try:
            params = {'ts_code': ts_code}
            if period:
                params['period'] = self._format_date(period)
            df = self._pro.top10_holders(**params)
            if df is None or df.empty:
                return pd.DataFrame()
            if 'ann_date' in df.columns:
                df['ann_date'] = df['ann_date'].apply(self._format_date_back)
            if 'end_date' in df.columns:
                df['end_date'] = df['end_date'].apply(self._format_date_back)
            return df
        except Exception as e:
            logger.error(f"Error getting top10 holders: {e}")
            return pd.DataFrame()

    # ==================== 机构持仓 ====================

    def get_institutional_holding(self, ts_code: str, start_date: str = None,
                                   end_date: str = None) -> pd.DataFrame:
        """获取机构持仓数据 (stk_holdernumber)"""
        if not self._connected:
            return pd.DataFrame()
        try:
            params = {'ts_code': ts_code}
            if start_date:
                params['start_date'] = self._format_date(start_date)
            if end_date:
                params['end_date'] = self._format_date(end_date)
            df = self._pro.stk_holdernumber(**params)
            if df is None or df.empty:
                return pd.DataFrame()
            if 'ann_date' in df.columns:
                df['ann_date'] = df['ann_date'].apply(self._format_date_back)
            if 'end_date' in df.columns:
                df['end_date'] = df['end_date'].apply(self._format_date_back)
            return df
        except Exception as e:
            logger.error(f"Error getting institutional holding: {e}")
            return pd.DataFrame()

    # ==================== 分析师一致预期 ====================

    def get_analyst_consensus(self, ts_code: str = None, start_date: str = None,
                               end_date: str = None) -> pd.DataFrame:
        """获取分析师一致预期数据"""
        if not self._connected:
            return pd.DataFrame()
        try:
            params = {}
            if ts_code:
                params['ts_code'] = ts_code
            if start_date:
                params['start_date'] = self._format_date(start_date)
            if end_date:
                params['end_date'] = self._format_date(end_date)
            df = self._pro.consensus_data(**params)
            if df is None or df.empty:
                return pd.DataFrame()
            if 'ann_date' in df.columns:
                df['ann_date'] = df['ann_date'].apply(self._format_date_back)
            if 'end_date' in df.columns:
                df['end_date'] = df['end_date'].apply(self._format_date_back)
            return df
        except Exception as e:
            logger.error(f"Error getting analyst consensus: {e}")
            return pd.DataFrame()

    # ==================== 资产负债表(含商誉) ====================

    def get_balance_sheet_with_goodwill(self, ts_code: str, period: str = None) -> pd.DataFrame:
        """获取资产负债表关键字段(含商誉)
        f_ann_date为首次公告日，比ann_date更早，PIT对齐应优先使用f_ann_date"""
        if not self._connected:
            return pd.DataFrame()
        try:
            params = {'ts_code': ts_code}
            if period:
                params['period'] = self._format_date(period)
            # f_ann_date(首次公告日)比ann_date更精确，用于PIT对齐
            # goodwill/商誉是暴雷高发指标，需单独监控
            df = self._pro.balancesheet(
                fields='ts_code,ann_date,f_ann_date,end_date,goodwill,total_assets,total_hldr_eqy_exc_min_int',
                **params
            )
            if df is None or df.empty:
                return pd.DataFrame()
            if 'ann_date' in df.columns:
                df['ann_date'] = df['ann_date'].apply(self._format_date_back)
            if 'end_date' in df.columns:
                df['end_date'] = df['end_date'].apply(self._format_date_back)
            return df
        except Exception as e:
            logger.error(f"Error getting balance sheet with goodwill: {e}")
            return pd.DataFrame()
