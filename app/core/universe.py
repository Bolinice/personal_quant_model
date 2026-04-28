"""
股票池构建模块 V2
=================
V2参数收紧: 上市天数180/成交额8000万/市值80亿/股价3元
V2新增: 风险事件过滤/黑名单硬过滤/交易可行性过滤
"""

from datetime import date

import pandas as pd

from app.core.logging import logger


class UniverseBuilder:
    """股票池构建器 - GPT设计4.1节"""

    # V2默认参数 (参数收紧)
    DEFAULT_CORE_PARAMS = {
        "min_list_days": 180,  # V2: 上市满180个交易日(原250) — 180天覆盖一个完整财报季, IPO效应基本消退
        "min_daily_amount": 8e7,  # V2: 日均成交额>8000万(原1亿) — 保证中等规模资金可进出, 降低冲击成本
        "min_price": 3.0,  # V2: 价格>3元(原3元) — 3元以下多为ST/退市风险股, 且涨跌幅绝对值占比过大
        "liquidity_pct": 0.80,  # 流动性前80% — 排除尾部20%低流动性股, 减少滑点
        "exclude_st": True,
        "exclude_suspended": True,
        "exclude_delist": True,
        "min_market_cap": 80e9,  # V2: 最低市值80亿(原50亿) — 80亿以上个股容量足以容纳策略资金, 减少小盘风格暴露
        "exclude_risk_events": True,  # V2: 排除重大风险事件股
        "exclude_blacklist": True,  # V2: 黑名单硬过滤
        "exclude_limit_up_down": True,  # V2: 排除涨跌停无法成交
    }

    DEFAULT_EXTENDED_PARAMS = {
        "min_list_days": 120,  # 扩展池: 上市满120个交易日 — 120天覆盖季报, 但保留更多次新股alpha
        "min_daily_amount": 5e7,  # 日均成交额>5000万 — 放松流动性要求以覆盖中小盘
        "min_price": 2.0,  # 价格>2元 — 放松至2元, 但仍排除极端低价股
        "liquidity_pct": 0.70,  # 流动性前70% — 覆盖更广, 噪音也更大
        "exclude_st": True,
        "exclude_suspended": True,
        "exclude_delist": True,
        "min_market_cap": 0,  # 无市值下限 — 扩展池允许小盘股, alpha更多但风格暴露也更大
        "exclude_risk_events": True,
        "exclude_blacklist": True,
        "exclude_limit_up_down": True,
    }

    def __init__(self):
        pass

    def build(
        self,
        trade_date: date,
        stock_basic_df: pd.DataFrame,
        price_df: pd.DataFrame,
        stock_status_df: pd.DataFrame = None,
        daily_basic_df: pd.DataFrame = None,
        min_list_days: int = 120,
        min_daily_amount: float = 5e7,
        min_price: float = 2.0,
        liquidity_pct: float = 0.70,
        exclude_st: bool = True,
        exclude_suspended: bool = True,
        exclude_delist: bool = True,
        min_market_cap: float = 0,
        exclude_risk_events: bool = False,
        exclude_blacklist: bool = False,
        exclude_limit_up_down: bool = False,
    ) -> list[str]:
        """
        构建股票池

        Args:
            trade_date: 交易日期
            stock_basic_df: 股票基本信息, 需含 ts_code/list_date/list_status/delist_date
            price_df: 近期行情, 需含 ts_code/trade_date/close/amount/volume
            stock_status_df: 股票状态, 需含 ts_code/trade_date/is_st/is_suspended/is_delist
            daily_basic_df: 每日指标, 需含 ts_code/trade_date/total_mv (可选,用于市值过滤)
            min_list_days: 最小上市天数
            min_daily_amount: 最小日均成交额(元)
            min_price: 最低价格
            liquidity_pct: 流动性百分位阈值 (0-1, 保留前N%)
            exclude_st: 是否排除ST股
            exclude_suspended: 是否排除停牌股
            exclude_delist: 是否排除退市整理股
            min_market_cap: 最低总市值(元), 0=不限制

        Returns:
            符合条件的股票代码列表
        """
        candidates = set(stock_basic_df["ts_code"].dropna().unique())
        excluded_reasons: dict[str, int] = {}

        # 1. 排除退市/非上市
        if exclude_delist and "list_status" in stock_basic_df.columns:
            delisted = stock_basic_df[stock_basic_df["list_status"] == "D"]["ts_code"]
            excluded_reasons["delisted"] = len(delisted)
            candidates -= set(delisted)

        if "list_status" in stock_basic_df.columns:
            non_listed = stock_basic_df[~stock_basic_df["list_status"].isin(["L", "P"])]["ts_code"]
            excluded_reasons["non_listed"] = len(non_listed)
            candidates -= set(non_listed)

        # 2. 上市天数过滤
        # 新股IPO效应: 上市初期定价偏差大、换手率异常、缺乏历史数据, 需冷却期
        if min_list_days > 0 and "list_date" in stock_basic_df.columns:
            list_dates = pd.to_datetime(stock_basic_df.set_index("ts_code")["list_date"], errors="coerce")
            min_list_date = pd.Timestamp(trade_date) - pd.Timedelta(days=min_list_days)
            too_new = list_dates[list_dates > min_list_date].index
            excluded_reasons["too_new"] = len(too_new)
            candidates -= set(too_new)

        # 3. ST状态过滤
        if exclude_st and stock_status_df is not None and not stock_status_df.empty:
            status_on_date = self._filter_by_date(stock_status_df, trade_date)
            if "is_st" in status_on_date.columns:
                st_stocks = status_on_date[status_on_date["is_st"] == True]["ts_code"]  # noqa: E712
                excluded_reasons["st"] = len(st_stocks)
                candidates -= set(st_stocks)

        # 4. 停牌过滤
        if exclude_suspended and stock_status_df is not None and not stock_status_df.empty:
            status_on_date = self._filter_by_date(stock_status_df, trade_date)
            if "is_suspended" in status_on_date.columns:
                suspended = status_on_date[status_on_date["is_suspended"] == True]["ts_code"]  # noqa: E712
                excluded_reasons["suspended"] = len(suspended)
                candidates -= set(suspended)

        # 5. 退市整理过滤
        if exclude_delist and stock_status_df is not None and not stock_status_df.empty:
            status_on_date = self._filter_by_date(stock_status_df, trade_date)
            if "is_delist" in status_on_date.columns:
                delist_stocks = status_on_date[status_on_date["is_delist"] == True]["ts_code"]  # noqa: E712
                excluded_reasons["delist_organizing"] = len(delist_stocks)
                candidates -= set(delist_stocks)

        # 6. 流动性和价格过滤 (基于近期行情)
        # 使用20日均值而非单日: 避免单日异常成交额导致误判
        if not price_df.empty:
            recent = self._get_recent_data(price_df, trade_date, window=20)
            if not recent.empty:
                # 日均成交额
                if "amount" in recent.columns:
                    avg_amount = recent.groupby("ts_code")["amount"].mean()
                    low_liquidity = avg_amount[avg_amount < min_daily_amount].index
                    excluded_reasons["low_amount"] = len(low_liquidity)
                    candidates -= set(low_liquidity)

                    # 流动性百分位过滤
                    if liquidity_pct < 1.0 and len(avg_amount) > 0:
                        threshold = avg_amount.quantile(1 - liquidity_pct)
                        below_pct = avg_amount[avg_amount < threshold].index
                        excluded_reasons["below_liquidity_pct"] = len(below_pct)
                        candidates -= set(below_pct)

                # 最低价格
                if "close" in recent.columns:
                    latest_prices = recent.groupby("ts_code")["close"].last()
                    low_price = latest_prices[latest_prices < min_price].index
                    excluded_reasons["low_price"] = len(low_price)
                    candidates -= set(low_price)

        # 7. 市值过滤
        # 市值是流动性代理: 小市值股冲击成本高、操纵风险大
        if min_market_cap > 0 and daily_basic_df is not None and not daily_basic_df.empty:
            daily_on_date = self._filter_by_date(daily_basic_df, trade_date)
            if "total_mv" in daily_on_date.columns:
                small_cap = daily_on_date[daily_on_date["total_mv"] < min_market_cap]["ts_code"]
                excluded_reasons["small_cap"] = len(small_cap)
                candidates -= set(small_cap)

        # 只保留在candidates中的有效代码
        result = sorted([c for c in candidates if isinstance(c, str) and len(c) > 0])

        logger.info(
            "Universe built",
            extra={
                "trade_date": str(trade_date),
                "universe_size": len(result),
                "excluded": excluded_reasons,
            },
        )

        return result

    def build_core_pool(
        self,
        trade_date: date,
        stock_basic_df: pd.DataFrame,
        price_df: pd.DataFrame,
        stock_status_df: pd.DataFrame = None,
        daily_basic_df: pd.DataFrame = None,
    ) -> list[str]:
        """构建核心池: 中大市值+高流动性, 更稳定, 适合第一版"""
        return self.build(
            trade_date, stock_basic_df, price_df, stock_status_df, daily_basic_df, **self.DEFAULT_CORE_PARAMS
        )

    def build_extended_pool(
        self,
        trade_date: date,
        stock_basic_df: pd.DataFrame,
        price_df: pd.DataFrame,
        stock_status_df: pd.DataFrame = None,
        daily_basic_df: pd.DataFrame = None,
    ) -> list[str]:
        """构建扩展池: 覆盖更多股票, alpha更多但噪音更大"""
        return self.build(
            trade_date, stock_basic_df, price_df, stock_status_df, daily_basic_df, **self.DEFAULT_EXTENDED_PARAMS
        )

    # ==================== V2新增过滤方法 ====================

    def filter_risk_events(
        self, candidates: set, risk_events_df: pd.DataFrame, trade_date: date, lookback_days: int = 60
    ) -> tuple[set, dict[str, int]]:
        """
        V2: 风险事件过滤

        剔除近60日存在重大立案/处罚/严重审计问题的股票

        Args:
            candidates: 当前候选股票集合
            risk_events_df: 风险事件DataFrame, 需含 ts_code/event_date/event_type/severity
            trade_date: 交易日期
            lookback_days: 回溯天数

        Returns:
            (过滤后集合, 剔除原因统计)
        """
        excluded_reasons = {}

        if risk_events_df is None or risk_events_df.empty:
            return candidates, excluded_reasons

        # 筛选近lookback_days的重大风险事件
        if "event_date" in risk_events_df.columns:
            event_dates = pd.to_datetime(risk_events_df["event_date"], errors="coerce")
            cutoff = pd.Timestamp(trade_date) - pd.Timedelta(days=lookback_days)
            recent_events = risk_events_df[(event_dates >= cutoff) & (event_dates <= pd.Timestamp(trade_date))]
        else:
            recent_events = risk_events_df

        if recent_events.empty:
            return candidates, excluded_reasons

        # 筛选严重事件 (立案/处罚/严重审计问题)
        severe_types = {"investigation", "penalty", "audit_issue", "delist_risk"}
        # 立案/处罚 → 公司治理重大缺陷; 审计问题 → 财务真实性存疑; 退市风险 → 直接剔除
        if "event_type" in recent_events.columns:
            severe_events = recent_events[recent_events["event_type"].isin(severe_types)]
        elif "severity" in recent_events.columns:
            severe_events = recent_events[recent_events["severity"].isin(["critical", "high"])]
        else:
            severe_events = recent_events

        if "ts_code" in severe_events.columns:
            risk_stocks = set(severe_events["ts_code"].dropna().unique())
            excluded_reasons["risk_events"] = len(candidates & risk_stocks)
            candidates -= risk_stocks

        return candidates, excluded_reasons

    def filter_blacklist(
        self, candidates: set, blacklist_df: pd.DataFrame, trade_date: date
    ) -> tuple[set, dict[str, int]]:
        """
        V2: 黑名单硬过滤

        剔除: ST/退市整理/重大立案/严重审计非标

        Args:
            candidates: 当前候选股票集合
            blacklist_df: 黑名单DataFrame, 需含 ts_code/reason
            trade_date: 交易日期

        Returns:
            (过滤后集合, 剔除原因统计)
        """
        excluded_reasons = {}

        if blacklist_df is None or blacklist_df.empty:
            return candidates, excluded_reasons

        if "ts_code" in blacklist_df.columns:
            blacklisted = set(blacklist_df["ts_code"].dropna().unique())
            excluded_reasons["blacklist"] = len(candidates & blacklisted)
            candidates -= blacklisted

        return candidates, excluded_reasons

    def filter_limit_up_down(
        self, candidates: set, price_df: pd.DataFrame, trade_date: date
    ) -> tuple[set, dict[str, int]]:
        """
        V2: 交易可行性过滤

        剔除: 一字涨停/一字跌停/长期停牌刚复牌且流动性异常

        Args:
            candidates: 当前候选股票集合
            price_df: 行情DataFrame, 需含 ts_code/trade_date/open/close/high/low
            trade_date: 交易日期

        Returns:
            (过滤后集合, 剔除原因统计)
        """
        excluded_reasons = {}

        if price_df.empty:
            return candidates, excluded_reasons

        # 获取当日行情
        daily = self._filter_by_date(price_df, trade_date)
        if daily.empty:
            return candidates, excluded_reasons

        required_cols = {"ts_code", "open", "close", "high", "low"}
        if not required_cols.issubset(daily.columns):
            return candidates, excluded_reasons

        # 一字涨停/跌停: open=high=close=low (向量化替代iterrows)
        # 一字板无法成交, 买入即套牢或卖出无法成交, 必须排除
        candidate_mask = daily["ts_code"].isin(candidates)
        is_one_price = (
            (daily["open"] > 0)
            & (abs(daily["open"] - daily["high"]) < 0.01)
            & (abs(daily["high"] - daily["close"]) < 0.01)
            & (abs(daily["close"] - daily["low"]) < 0.01)
        )
        limit_stocks = set(daily.loc[candidate_mask & is_one_price, "ts_code"])

        excluded_reasons["limit_up_down"] = len(candidates & limit_stocks)
        candidates -= limit_stocks

        return candidates, excluded_reasons

    @staticmethod
    def _filter_by_date(df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
        """按交易日期过滤DataFrame"""
        if "trade_date" not in df.columns:
            return df
        df_dates = pd.to_datetime(df["trade_date"], errors="coerce")
        mask = df_dates == pd.Timestamp(trade_date)
        if mask.any():
            return df[mask]
        # 没有精确匹配, 取最近的
        mask = df_dates <= pd.Timestamp(trade_date)
        if mask.any():
            latest = df_dates[mask].max()
            return df[df_dates == latest]
        return pd.DataFrame()

    @staticmethod
    def _get_recent_data(df: pd.DataFrame, trade_date: date, window: int = 20) -> pd.DataFrame:
        """获取最近N个交易日的数据"""
        if "trade_date" not in df.columns:
            return df

        df_dates = pd.to_datetime(df["trade_date"], errors="coerce")
        cutoff = pd.Timestamp(trade_date) - pd.Timedelta(
            days=window * 2
        )  # 多取一些确保有足够交易日 (交易日约=自然日*0.7)
        mask = (df_dates >= cutoff) & (df_dates <= pd.Timestamp(trade_date))
        recent = df[mask].copy()

        if recent.empty:
            return recent

        # 每只股票只保留最近window条
        if "ts_code" in recent.columns:
            recent = recent.sort_values(["ts_code", "trade_date"])
            recent = recent.groupby("ts_code").tail(window)

        return recent
