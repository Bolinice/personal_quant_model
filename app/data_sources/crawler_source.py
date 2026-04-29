"""
爬虫数据源
基于新浪财经公开接口
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import requests

from app.core.logging import logger
from app.data_sources.base import BaseDataSource


class CrawlerDataSource(BaseDataSource):
    """爬虫数据源 - 新浪财经"""

    def __init__(self):
        super().__init__("crawler")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Referer": "https://finance.sina.com.cn/",
            }
        )

    def connect(self) -> bool:
        """测试连接"""
        try:
            # 测试获取上证指数实时行情
            url = "https://hq.sinajs.cn/list=sh000001"
            resp = self.session.get(url, timeout=10)

            if resp.status_code == 200 and "var hq_str_sh000001" in resp.text:
                self._connected = True
                logger.info("Crawler data source connected successfully (Sina Finance)")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to connect crawler source: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected

    def _get_sina_code(self, ts_code: str) -> str:
        """将 ts_code 转换为新浪代码格式"""
        if "." in ts_code:
            code, market = ts_code.split(".")
        else:
            code = ts_code
            market = "SH" if code.startswith("6") else "SZ"

        # 新浪市场代码: sh=沪市, sz=深市
        prefix = "sh" if market == "SH" else "sz"
        return f"{prefix}{code}"

    def _parse_sina_quote(self, text: str, code: str) -> dict | None:
        """解析新浪行情数据"""
        try:
            pattern = rf'var hq_str_{code}="(.*)";'
            match = re.search(pattern, text)
            if not match:
                return None

            data = match.group(1).split(",")
            if len(data) < 32:
                return None

            return {
                "name": data[0],
                "open": float(data[1]) if data[1] else None,
                "pre_close": float(data[2]) if data[2] else None,
                "price": float(data[3]) if data[3] else None,
                "high": float(data[4]) if data[4] else None,
                "low": float(data[5]) if data[5] else None,
                "volume": float(data[8]) if data[8] else None,
                "amount": float(data[9]) if data[9] else None,
            }
        except Exception as e:
            logger.error(f"Error parsing sina quote: {e}")
            return None

    # ==================== 行情数据 ====================

    def get_stock_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票日线行情 - 使用新浪历史数据接口"""
        if not self._connected:
            return pd.DataFrame()

        try:
            sina_code = self._get_sina_code(ts_code)

            # 新浪历史K线接口
            url = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
            params = {
                "symbol": sina_code,
                "scale": "240",  # 日K
                "ma": "no",
                "datalen": "365",  # 获取一年数据
            }

            resp = self.session.get(url, params=params, timeout=30)
            text = resp.text

            # 解析JSON数据
            if text and text != "null":
                try:
                    data = json.loads(text)
                    if isinstance(data, list):
                        rows = []
                        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC)
                        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)

                        for item in data:
                            trade_date = datetime.strptime(item["day"], "%Y-%m-%d").replace(tzinfo=UTC)
                            if start_dt <= trade_date <= end_dt:
                                rows.append(
                                    {
                                        "trade_date": item["day"],
                                        "open": float(item["open"]),
                                        "high": float(item["high"]),
                                        "low": float(item["low"]),
                                        "close": float(item["close"]),
                                        "volume": float(item["volume"]),
                                    }
                                )

                        if rows:
                            df = pd.DataFrame(rows)
                            df["pct_chg"] = df["close"].pct_change() * 100
                            df["pre_close"] = df["close"].shift(1)
                            df["amount"] = df["volume"] * df["close"]
                            return df
                except json.JSONDecodeError:
                    pass

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting stock daily: {e}")
            return pd.DataFrame()

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取指数日线行情"""
        if not self._connected:
            return pd.DataFrame()

        try:
            sina_code = self._get_sina_code(index_code)

            url = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
            params = {
                "symbol": sina_code,
                "scale": "240",
                "ma": "no",
                "datalen": "365",
            }

            resp = self.session.get(url, params=params, timeout=30)
            text = resp.text

            if text and text != "null":
                try:
                    data = json.loads(text)
                    if isinstance(data, list):
                        rows = []
                        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC)
                        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)

                        for item in data:
                            trade_date = datetime.strptime(item["day"], "%Y-%m-%d").replace(tzinfo=UTC)
                            if start_dt <= trade_date <= end_dt:
                                rows.append(
                                    {
                                        "trade_date": item["day"],
                                        "open": float(item["open"]),
                                        "high": float(item["high"]),
                                        "low": float(item["low"]),
                                        "close": float(item["close"]),
                                        "volume": float(item["volume"]),
                                    }
                                )

                        if rows:
                            df = pd.DataFrame(rows)
                            df["pct_chg"] = df["close"].pct_change() * 100
                            df["pre_close"] = df["close"].shift(1)
                            df["amount"] = df["volume"] * df["close"]
                            return df
                except json.JSONDecodeError:
                    pass

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting index daily: {e}")
            return pd.DataFrame()

    def get_stock_daily_batch(self, ts_codes: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        """批量获取股票日线行情"""
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
            # 东方财富股票列表接口
            url = "https://push2.eastmoney.com/api/qt/clist/get"

            all_stocks = []

            # 沪市
            params = {
                "pn": 1,
                "pz": 5000,
                "po": 1,
                "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": "m:1+t:2,m:1+t:23",  # 沪市A股
                "fields": "f12,f14,f2,f3,f4,f5,f6",
            }
            resp = self.session.get(url, params=params, timeout=30)
            data = resp.json()

            if data.get("data") and data["data"].get("diff"):
                for item in data["data"]["diff"]:
                    code = item.get("f12", "")
                    name = item.get("f14", "")
                    if code and name:
                        all_stocks.append(
                            {
                                "ts_code": f"{code}.SH",
                                "symbol": code,
                                "name": name,
                                "market": "SH",
                                "list_date": None,
                                "industry": None,
                            }
                        )

            # 深市
            params["fs"] = "m:0+t:6,m:0+t:80"  # 深市A股
            resp = self.session.get(url, params=params, timeout=30)
            data = resp.json()

            if data.get("data") and data["data"].get("diff"):
                for item in data["data"]["diff"]:
                    code = item.get("f12", "")
                    name = item.get("f14", "")
                    if code and name:
                        all_stocks.append(
                            {
                                "ts_code": f"{code}.SZ",
                                "symbol": code,
                                "name": name,
                                "market": "SZ",
                                "list_date": None,
                                "industry": None,
                            }
                        )

            if all_stocks:
                df = pd.DataFrame(all_stocks)
                df["status"] = "L"
                logger.info(f"Fetched {len(df)} stocks from EastMoney")
                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting stock basic: {e}")
            return pd.DataFrame()

    def get_index_components(self, index_code: str, date: str | None = None) -> list[str]:
        """获取指数成分股"""
        if not self._connected:
            return []

        try:
            code = index_code.split(".")[0] if "." in index_code else index_code

            # 指数代码映射
            index_map = {
                "000300": "1.000300",  # 沪深300
                "000905": "1.000905",  # 中证500
                "000852": "1.000852",  # 中证1000
                "000001": "1.000001",  # 上证指数
                "399001": "0.399001",  # 深证成指
                "399006": "0.399006",  # 创业板指
            }

            secid = index_map.get(code, f"1.{code}")

            url = "https://push2.eastmoney.com/api/qt/clist/get"
            params = {
                "pn": 1,
                "pz": 500,
                "po": 1,
                "np": 1,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": f"b:{secid}",  # 指数成分股
                "fields": "f12",
            }

            resp = self.session.get(url, params=params, timeout=30)
            data = resp.json()

            if data.get("data") and data["data"].get("diff"):
                codes = []
                for item in data["data"]["diff"]:
                    c = str(item.get("f12", "")).zfill(6)
                    if c:
                        market = "SH" if c.startswith("6") else "SZ"
                        codes.append(f"{c}.{market}")
                return codes

            return []

        except Exception as e:
            logger.error(f"Error getting index components: {e}")
            return []

    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取交易日历"""
        if not self._connected:
            return pd.DataFrame()

        try:
            # 东方财富交易日历接口
            _url = "https://push2.eastmoney.com/api/qt/stock/get"
            _params = {
                "secid": "1.000001",  # 上证指数
                "fields": "f51,f52,f53,f54,f55,f56",
            }

            # 这个接口不直接提供交易日历，我们用另一种方式
            # 通过获取指数数据来推断交易日
            df = self.get_index_daily("000001.SH", start_date, end_date)

            if df.empty:
                return pd.DataFrame()

            df["is_open"] = 1
            df["pretrade_date"] = df["trade_date"].shift(1)

            return df[["trade_date", "is_open", "pretrade_date"]]

        except Exception as e:
            logger.error(f"Error getting trading calendar: {e}")
            return pd.DataFrame()

    # ==================== 财务数据 ====================

    def get_financial_indicator(
        self, ts_code: str, start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        """获取财务指标（简化版）"""
        # 东方财富财务数据接口较复杂，这里返回空
        # 可以后续扩展
        return pd.DataFrame()

    def get_financial_data(
        self, ts_code: str | None = None, start_date: str | None = None, end_date: str | None = None, **kwargs
    ) -> pd.DataFrame:
        """获取财务数据（兼容基类接口）"""
        return pd.DataFrame()

    def get_income_statement(
        self, ts_code: str, start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        """获取利润表"""
        return pd.DataFrame()

    def get_balance_sheet(
        self, ts_code: str, start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        """获取资产负债表"""
        return pd.DataFrame()

    # ==================== 复权数据 ====================

    def get_adj_factor(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取复权因子（爬虫源直接返回前复权数据，无需复权因子）"""
        return pd.DataFrame()

    # ==================== 行业数据 ====================

    def get_industry_classification(self, ts_code: str | None = None) -> pd.DataFrame:
        """获取行业分类"""
        return pd.DataFrame()

    # ==================== 特色功能 ====================

    def get_realtime_quotes(self, codes: list[str] | None = None) -> pd.DataFrame:
        """获取实时行情"""
        if not self._connected:
            return pd.DataFrame()

        try:
            # 使用新浪实时行情接口
            sina_codes = [self._get_sina_code(c) for c in (codes or ["600000.SH", "600036.SH", "000001.SZ"])]

            url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
            resp = self.session.get(url, timeout=10)
            text = resp.text

            rows = []
            for i, sina_code in enumerate(sina_codes):
                quote = self._parse_sina_quote(text, sina_code)
                if quote:
                    ts_code = codes[i] if codes else None
                    rows.append(
                        {
                            "symbol": ts_code.split(".")[0] if ts_code else sina_code[2:],
                            "name": quote["name"],
                            "price": quote["price"],
                            "open": quote["open"],
                            "high": quote["high"],
                            "low": quote["low"],
                            "pre_close": quote["pre_close"],
                            "volume": quote["volume"],
                            "amount": quote["amount"],
                        }
                    )

            if rows:
                return pd.DataFrame(rows)

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting realtime quotes: {e}")
            return pd.DataFrame()

    def get_stock_info(self, ts_code: str) -> dict[str, Any]:
        """获取股票详细信息"""
        if not self._connected:
            return {}

        try:
            sina_code = self._get_sina_code(ts_code)

            url = f"https://hq.sinajs.cn/list={sina_code}"
            resp = self.session.get(url, timeout=10)
            text = resp.text

            quote = self._parse_sina_quote(text, sina_code)
            if quote:
                return {
                    "code": ts_code,
                    "name": quote["name"],
                    "price": quote["price"],
                    "pre_close": quote["pre_close"],
                }

            return {}

        except Exception as e:
            logger.error(f"Error getting stock info: {e}")
            return {}
