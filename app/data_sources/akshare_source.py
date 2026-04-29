"""
AKShare 数据源适配器 — Tushare 的 fallback

当Tushare接口不可用或触发频率限制时，自动切换到AKShare获取数据。
AKShare免费无限制，但数据字段和精度可能略有差异。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

logger = logging.getLogger(__name__)


class AKShareSource:
    """AKShare数据源 — Tushare fallback"""

    def fetch(self, data_type: str, **kwargs) -> pd.DataFrame:
        """统一数据获取入口 — 根据data_type路由到对应方法"""
        handlers = {
            "price": self._fetch_stock_daily,
            "basic": self._fetch_stock_daily_basic,
            "financial": self._fetch_financial,
            "index": self._fetch_index_daily,
            "moneyflow": self._fetch_moneyflow,
            "margin": self._fetch_margin,
            "northflow": self._fetch_northflow,
        }
        handler = handlers.get(data_type)
        if handler is None:
            raise ValueError(f"AKShare不支持数据类型: {data_type}")
        return handler(**kwargs)

    def _fetch_stock_daily(self, **kwargs) -> pd.DataFrame:
        """获取股票日线行情"""
        try:
            import akshare as ak

            ts_code = kwargs.get("ts_code")
            kwargs.get("trade_date")
            start_date = kwargs.get("start_date")
            end_date = kwargs.get("end_date")

            if ts_code:
                # AKShare使用6位代码
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date.strftime("%Y%m%d") if start_date else "20200101",
                    end_date=end_date.strftime("%Y%m%d") if end_date else datetime.now(tz=timezone.utc).strftime("%Y%m%d"),
                    adjust="qfq",
                )
                # 列名映射到Tushare格式
                col_map = {
                    "日期": "trade_date",
                    "开盘": "open",
                    "收盘": "close",
                    "最高": "high",
                    "最低": "low",
                    "成交量": "vol",
                    "成交额": "amount",
                    "涨跌幅": "pct_chg",
                    "涨跌额": "change",
                    "换手率": "turnover_rate",
                }
                df = df.rename(columns=col_map)
                if "trade_date" in df.columns:
                    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y%m%d")
                df["ts_code"] = ts_code
                return df

            return pd.DataFrame()

        except ImportError:
            raise ImportError("请安装akshare: pip install akshare") from None
        except Exception as e:
            logger.error("AKShare获取stock_daily失败: %s", e)
            return pd.DataFrame()

    def _fetch_stock_daily_basic(self, **kwargs) -> pd.DataFrame:
        """获取每日指标 — AKShare字段较少，返回基础指标"""
        try:
            import akshare as ak

            trade_date = kwargs.get("trade_date")
            if trade_date:
                df = ak.stock_a_indicator_lg(trade_date.strftime("%Y%m%d"))
                # 列名映射
                col_map = {
                    "trade_date": "trade_date",
                    "code": "ts_code",
                    "pe": "pe",
                    "pe_ttm": "pe_ttm",
                    "pb": "pb",
                    "dv_ratio": "dv_ratio",
                    "total_mv": "total_mv",
                    "circ_mv": "circ_mv",
                }
                existing = {k: v for k, v in col_map.items() if k in df.columns}
                df = df.rename(columns=existing)
                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error("AKShare获取stock_daily_basic失败: %s", e)
            return pd.DataFrame()

    def _fetch_financial(self, **kwargs) -> pd.DataFrame:
        """获取财务数据 — AKShare返回格式与Tushare不同，仅作基础fallback"""
        try:
            import akshare as ak

            ts_code = kwargs.get("ts_code")
            if ts_code:
                symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
                return ak.stock_financial_analysis_indicator(symbol=symbol)

            return pd.DataFrame()

        except Exception as e:
            logger.error("AKShare获取financial失败: %s", e)
            return pd.DataFrame()

    def _fetch_index_daily(self, **kwargs) -> pd.DataFrame:
        """获取指数日线"""
        try:
            import akshare as ak

            ts_code = kwargs.get("ts_code", "000001.SH")
            kwargs.get("start_date")
            kwargs.get("end_date")

            # 映射Tushare指数代码到AKShare
            index_map = {
                "000001.SH": "sh000001",  # 上证指数
                "399001.SZ": "sz399001",  # 深证成指
                "399006.SZ": "sz399006",  # 创业板指
                "000300.SH": "sh000300",  # 沪深300
                "000905.SH": "sh000905",  # 中证500
                "000852.SH": "sh000852",  # 中证1000
            }
            symbol = index_map.get(ts_code, f"sh{ts_code.split('.')[0]}")

            df = ak.stock_zh_index_daily(symbol=symbol)
            col_map = {
                "date": "trade_date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "vol",
            }
            existing = {k: v for k, v in col_map.items() if k in df.columns}
            df = df.rename(columns=existing)
            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y%m%d")
            df["ts_code"] = ts_code
            return df

        except Exception as e:
            logger.error("AKShare获取index_daily失败: %s", e)
            return pd.DataFrame()

    def _fetch_moneyflow(self, **kwargs) -> pd.DataFrame:
        """获取资金流数据"""
        try:
            import akshare as ak

            trade_date = kwargs.get("trade_date")
            if trade_date:
                return ak.stock_individual_fund_flow_rank(indicator="今日")

            return pd.DataFrame()

        except Exception as e:
            logger.error("AKShare获取moneyflow失败: %s", e)
            return pd.DataFrame()

    def _fetch_margin(self, **kwargs) -> pd.DataFrame:
        """获取融资融券数据"""
        try:
            import akshare as ak

            trade_date = kwargs.get("trade_date")
            start_date = kwargs.get("start_date")

            return ak.stock_margin_detail_sse(
                start_date=start_date.strftime("%Y%m%d") if start_date else "20230101",
                end_date=trade_date.strftime("%Y%m%d") if trade_date else datetime.now(tz=timezone.utc).strftime("%Y%m%d"),
            )

        except Exception as e:
            logger.error("AKShare获取margin失败: %s", e)
            return pd.DataFrame()

    def _fetch_northflow(self, **kwargs) -> pd.DataFrame:
        """获取北向资金数据"""
        try:
            import akshare as ak

            return ak.stock_hsgt_north_net_flow_in_em(indicator="北向")

        except Exception as e:
            logger.error("AKShare获取northflow失败: %s", e)
            return pd.DataFrame()
