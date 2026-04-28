"""
AKShare 数据源适配器
免费开源金融数据接口

与Tushare的核心差异:
1. 无PIT公告日字段，财务数据无法做精确PIT对齐，因子计算需注意未来函数风险
2. 无TTM指标（需本地滚动计算），无pe_ttm/ps_ttm等预计算字段
3. 没有统一字段命名规范，不同接口返回中文/英文列名混杂
4. 无全市场每日快照接口(daily_basic)，需逐只获取或用实时行情替代
5. 成交额需本地估算（成交价*成交量），精度低于Tushare的实际成交额
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.logging import logger
from app.data_sources.base import BaseDataSource


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
            # 测试连接 - 使用腾讯接口（更稳定），新浪源频繁限流不稳定
            df = ak.stock_zh_a_hist_tx(symbol="sh600000", start_date="2024-01-01", end_date="2024-01-10")
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
        """将 ts_code 转换为 AKShare 格式 — AKShare不用'市场后缀'，只用6位代码"""
        # 600000.SH -> 600000
        if "." in ts_code:
            return ts_code.split(".")[0]
        return ts_code

    def _format_code_back(self, code: str, market: str = "SH") -> str:
        """将 AKShare 格式转回 ts_code"""
        # 600000 -> 600000.SH
        if "." not in code:
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
            symbol = f"sh{code}" if ts_code.endswith(".SH") else f"sz{code}"

            # 使用腾讯数据源（更稳定）
            df = self._ak.stock_zh_a_hist_tx(symbol=symbol, start_date=start_date, end_date=end_date)

            if df.empty:
                return pd.DataFrame()

            # 重命名列
            df = df.rename(
                columns={
                    "date": "trade_date",
                    "amount": "volume",  # 腾讯接口的'amount'实际是成交量(手)，不是成交额，必须重命名避免混淆
                }
            )

            # 格式化日期
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")

            # 计算涨跌幅和昨收
            df["pre_close"] = df["close"].shift(1)
            df["pct_chg"] = (df["close"] / df["pre_close"] - 1) * 100
            df["amount"] = df["volume"] * df["close"]  # 估算成交额=成交量*收盘价，仅为近似值（Tushare返回真实成交额）

            # 选择需要的列
            result_cols = ["trade_date", "open", "high", "low", "close", "volume", "amount", "pct_chg", "pre_close"]
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
                "000300": "sh000300",  # 沪深300
                "000905": "sh000905",  # 中证500
                "000852": "sh000852",  # 中证1000
                "000001": "sh000001",  # 上证指数
                "399001": "sz399001",  # 深证成指
                "399006": "sz399006",  # 创业板指
            }

            ak_code = index_map.get(code, f"sh{code}")

            df = self._ak.stock_zh_index_daily(symbol=ak_code)

            if df.empty:
                return pd.DataFrame()

            # 筛选日期范围
            df["trade_date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]

            # 重命名列
            df = df.rename(columns={"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"})

            # 计算涨跌幅
            df["pct_chg"] = df["close"].pct_change() * 100
            df["pre_close"] = df["close"].shift(1)
            df["amount"] = df["volume"] * df["close"]  # 估算成交额=成交量*收盘价，仅为近似值

            return df[["trade_date", "open", "high", "low", "close", "volume", "amount", "pct_chg", "pre_close"]]

        except Exception as e:
            logger.error(f"Error getting index daily: {e}")
            return pd.DataFrame()

    def get_stock_daily_batch(self, ts_codes: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        """批量获取多只股票日线行情"""
        all_data = []
        for ts_code in ts_codes:
            df = self.get_stock_daily(ts_code, start_date, end_date)
            if not df.empty:
                df["ts_code"] = ts_code
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

            # 重命名列 (AKShare 返回中文列名，Tushare返回英文，这里统一映射为英文)
            df = df.rename(
                columns={
                    "代码": "symbol",
                    "名称": "name",
                }
            )

            # 过滤掉北交所股票 (bj开头) 和非主板股票 — 北交所流动性差，不在选股池内
            df = df[~df["symbol"].str.startswith("bj")]

            # 移除 symbol 中的 sh/sz 前缀
            df["symbol"] = df["symbol"].str.replace("^(sh|sz)", "", regex=True)

            # 构建 ts_code: 6开头为沪市，其他为深市
            # AKShare的新浪源不带上市日期和行业信息，设为None后续通过其他接口补全
            df["market"] = df["symbol"].apply(lambda x: "SH" if x.startswith("6") else "SZ")
            df["ts_code"] = df["symbol"] + "." + df["market"]
            df["status"] = "L"
            df["list_date"] = None
            df["industry"] = None

            return df[["ts_code", "symbol", "name", "industry", "market", "list_date", "status"]]

        except Exception as e:
            logger.error(f"Error getting stock basic: {e}")
            return pd.DataFrame()

    def get_index_components(self, index_code: str, date: str | None = None) -> list[str]:
        """获取指数成分股"""
        if not self._connected:
            return []

        try:
            code = self._format_code(index_code)

            # 指数成分股映射
            if code == "000300":
                df = self._ak.index_stock_cons_weight_csindex(symbol="000300")
            elif code == "000905":
                df = self._ak.index_stock_cons_weight_csindex(symbol="000905")
            elif code == "000852":
                df = self._ak.index_stock_cons_weight_csindex(symbol="000852")
            else:
                df = self._ak.index_stock_cons_weight_csindex(symbol=code)

            if df.empty:
                return []

            # 获取成分股代码
            # AKShare中证指数接口返回的列名为中文'成分券代码'，不同接口列名不同
            codes = df["成分券代码"].tolist() if "成分券代码" in df.columns else df.iloc[:, 0].tolist()

            # 转换为 ts_code 格式
            result = []
            for c in codes:
                c = str(c).zfill(6)
                if c.startswith("6"):
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

            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")

            # 筛选日期范围
            df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]

            df["is_open"] = 1  # AKShare交易日历只有交易日列表，非交易日不存在记录，故is_open恒为1
            df["pretrade_date"] = df["trade_date"].shift(1)  # 近似前一交易日，未精确跳过节假日

            return df[["trade_date", "is_open", "pretrade_date"]]

        except Exception as e:
            logger.error(f"Error getting trading calendar: {e}")
            return pd.DataFrame()

    # ==================== 财务数据 ====================

    def get_financial_indicator(
        self, ts_code: str, start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        """获取财务指标"""
        if not self._connected:
            return pd.DataFrame()

        try:
            code = self._format_code(ts_code)

            # 获取财务指标数据
            df = self._ak.stock_financial_analysis_indicator(symbol=code)

            if df.empty:
                return pd.DataFrame()

            # 重命名列 — AKShare的财务指标接口返回中文列名，映射到Tushare兼容的英文字段
            # 注意: AKShare缺少ann_date(公告日)字段，无法做PIT对齐，用于回测可能引入未来函数
            column_map = {
                "日期": "end_date",
                "净资产收益率": "roe",
                "总资产净利率": "roa",
                "销售毛利率": "grossprofit_margin",
                "销售净利率": "netprofit_margin",
                "资产负债率": "debt_to_assets",
                "流动比率": "current_ratio",
                "速动比率": "quick_ratio",
            }

            df = df.rename(columns=column_map)

            if "end_date" in df.columns:
                df["end_date"] = pd.to_datetime(df["end_date"]).dt.strftime("%Y-%m-%d")

                # 筛选日期范围
                if start_date:
                    df = df[df["end_date"] >= start_date]
                if end_date:
                    df = df[df["end_date"] <= end_date]

            df["ts_code"] = ts_code

            return df

        except Exception as e:
            logger.error(f"Error getting financial indicator: {e}")
            return pd.DataFrame()

    def get_financial_data(
        self, ts_code: str | None = None, start_date: str | None = None, end_date: str | None = None, **kwargs
    ) -> pd.DataFrame:
        """获取财务数据（兼容基类接口）"""
        if ts_code:
            return self.get_financial_indicator(ts_code, start_date, end_date)
        return pd.DataFrame()

    def get_income_statement(
        self, ts_code: str, start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        """获取利润表"""
        if not self._connected:
            return pd.DataFrame()

        try:
            code = self._format_code(ts_code)

            df = self._ak.stock_financial_report_sina(stock=code, symbol="利润表")

            if df.empty:
                return pd.DataFrame()

            df["ts_code"] = ts_code
            return df

        except Exception as e:
            logger.error(f"Error getting income statement: {e}")
            return pd.DataFrame()

    def get_balance_sheet(
        self, ts_code: str, start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        """获取资产负债表"""
        if not self._connected:
            return pd.DataFrame()

        try:
            code = self._format_code(ts_code)

            df = self._ak.stock_financial_report_sina(stock=code, symbol="资产负债表")

            if df.empty:
                return pd.DataFrame()

            df["ts_code"] = ts_code
            return df

        except Exception as e:
            logger.error(f"Error getting balance sheet: {e}")
            return pd.DataFrame()

    # ==================== 行业数据 ====================

    def get_industry_classification(self, ts_code: str | None = None) -> pd.DataFrame:
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
        """获取复权因子 — AKShare无直接复权因子接口，需用前复权价/不复权价反算"""
        if not self._connected:
            return pd.DataFrame()

        try:
            code = self._format_code(ts_code)

            # 获取前复权数据
            df_qfq = self._ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq",  # 前复权
            )

            # 获取不复权数据
            df_raw = self._ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="",
            )

            if df_qfq.empty or df_raw.empty:
                return pd.DataFrame()

            # 计算复权因子
            df_qfq["trade_date"] = pd.to_datetime(df_qfq["日期"]).dt.strftime("%Y-%m-%d")
            df_raw["trade_date"] = pd.to_datetime(df_raw["日期"]).dt.strftime("%Y-%m-%d")

            merged = df_qfq[["trade_date", "收盘"]].merge(
                df_raw[["trade_date", "收盘"]], on="trade_date", suffixes=("_qfq", "_raw")
            )

            # adj_factor = 前复权价 / 不复权价，首日应为1.0，受除权除息影响后续偏离
            merged["adj_factor"] = merged["收盘_qfq"] / merged["收盘_raw"]

            return merged[["trade_date", "adj_factor"]]

        except Exception as e:
            logger.error(f"Error getting adj factor: {e}")
            return pd.DataFrame()

    # ==================== 特色功能 ====================

    def get_realtime_quotes(self) -> pd.DataFrame:
        """获取实时行情"""
        if not self._connected:
            return pd.DataFrame()

        try:
            return self._ak.stock_zh_a_spot_em()

        except Exception as e:
            logger.error(f"Error getting realtime quotes: {e}")
            return pd.DataFrame()

    def get_northbound_hold(self) -> pd.DataFrame:
        """获取北向持股数据（东方财富）"""
        try:
            df = self._ak.stock_hsgt_hold_stock_em(market="北向")
            if df is not None and not df.empty:
                logger.info(f"获取北向持股数据: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取北向持股数据失败: {e}")
            return pd.DataFrame()

    def get_money_flow(self, ts_code: str) -> pd.DataFrame:
        """获取个股资金流向（东方财富）"""
        try:
            code = ts_code.split(".")[0]
            market = "sz" if ts_code.endswith(".SZ") else "sh"
            df = self._ak.stock_individual_fund_flow(stock=code, market=market)
            if df is not None and not df.empty:
                logger.info(f"获取资金流向 {ts_code}: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取资金流向 {ts_code} 失败: {e}")
            return pd.DataFrame()

    def get_daily_basic_em(self) -> pd.DataFrame:
        """获取全市场每日基本面快照（东方财富实时行情）"""
        try:
            df = self._ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                logger.info(f"获取全市场每日基本面: {len(df)} 条")
            return df
        except Exception as e:
            logger.error(f"获取全市场每日基本面失败: {e}")
            return pd.DataFrame()

    def get_margin_detail(self, trade_date: str) -> pd.DataFrame:
        """获取融资融券明细"""
        # AKShare将沪深两融分成了不同接口，需依次尝试；
        # Tushare的margin接口统一返回沪深数据，无需此处理
        # 尝试上交所
        try:
            df = self._ak.stock_margin_detail_sse(date=trade_date)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
        # 尝试深交所
        try:
            df = self._ak.stock_margin_detail_szse(date=trade_date)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass
        return pd.DataFrame()

    def get_financial_abstract(self, ts_code: str) -> pd.DataFrame:
        """获取同花顺财务摘要（资产负债表关键数据）"""
        try:
            code = ts_code.split(".")[0]
            return self._ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        except Exception as e:
            logger.error(f"获取财务摘要 {ts_code} 失败: {e}")
            return pd.DataFrame()

    def get_financial_analysis_indicator(self, ts_code: str) -> pd.DataFrame:
        """获取财务分析指标"""
        try:
            code = ts_code.split(".")[0]
            return self._ak.stock_financial_analysis_indicator(symbol=code, start_year="2020")
        except Exception as e:
            logger.error(f"获取财务分析指标 {ts_code} 失败: {e}")
            return pd.DataFrame()

    def get_stock_info(self, ts_code: str) -> dict[str, Any]:
        """获取股票详细信息"""
        if not self._connected:
            return {}

        try:
            code = self._format_code(ts_code)
            df = self._ak.stock_individual_info_em(symbol=code)

            if df.empty:
                return {}

            return dict(zip(df["item"], df["value"]))

        except Exception as e:
            logger.error(f"Error getting stock info: {e}")
            return {}

    # ==================== 股权质押 ====================

    def get_share_pledge(self, ts_code: str | None = None) -> pd.DataFrame:
        """获取股权质押数据 (东方财富)"""
        try:
            if ts_code:
                code = ts_code.split(".")[0]
                df = self._ak.stock_gpzy_individual_pledge_ratio_detail_em(symbol=code)
            else:
                df = self._ak.stock_gpzy_pledge_ratio_em()
            if df is not None and not df.empty:
                logger.info(f"获取股权质押数据: {len(df)} 条")
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"获取股权质押数据失败: {e}")
            return pd.DataFrame()

    # ==================== 前十大股东 ====================

    def get_top10_holders(self, ts_code: str, date: str | None = None) -> pd.DataFrame:
        """获取前十大股东数据 (东方财富)"""
        try:
            code = ts_code.split(".")[0]
            df = self._ak.stock_gdfx_top_10_em(symbol=code, date=date)
            if df is not None and not df.empty:
                logger.info(f"获取前十大股东 {ts_code}: {len(df)} 条")
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"获取前十大股东 {ts_code} 失败: {e}")
            return pd.DataFrame()

    # ==================== 机构持仓 ====================

    def get_institutional_holding(self, ts_code: str, quarter: str | None = None) -> pd.DataFrame:
        """获取机构持仓数据 (东方财富)"""
        try:
            code = ts_code.split(".")[0]
            df = self._ak.stock_institute_hold_detail(stock=code, quarter=quarter)
            if df is not None and not df.empty:
                logger.info(f"获取机构持仓 {ts_code}: {len(df)} 条")
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"获取机构持仓 {ts_code} 失败: {e}")
            return pd.DataFrame()

    # ==================== 分析师一致预期 ====================

    def get_analyst_consensus(self, ts_code: str | None = None) -> pd.DataFrame:
        """获取分析师一致预期数据 (新浪财经)"""
        try:
            df = self._ak.stock_institute_recommend(symbol="一致预期选股")
            if df is not None and not df.empty:
                logger.info(f"获取分析师一致预期: {len(df)} 条")
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"获取分析师一致预期失败: {e}")
            return pd.DataFrame()
