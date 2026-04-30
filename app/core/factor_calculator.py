"""
因子计算器 - 纯计算类，无数据库依赖
从FactorEngine拆分出的所有calc_*_factors方法
机构级: 向量化批处理、跳月动量、TTM原始报表计算、Sloan应计、交互因子
PIT安全: 所有财务因子计算均遵守Point-in-Time原则，仅使用ann_date <= trade_date的数据
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from app.core.factor_preprocess import FactorPreprocessor
from app.core.performance import timer

if TYPE_CHECKING:
    from datetime import date


def _safe_divide(numerator, denominator, eps: float = 1e-8):
    """安全除法: 分母接近0时返回NaN，避免inf污染"""
    # 1e-8阈值过滤极小分母，防止除法结果爆炸为inf并污染后续向量化运算
    denom = np.where(np.abs(denominator) < eps, np.nan, denominator)
    return numerator / denom


def pit_filter(financial_df: pd.DataFrame, trade_date: date, ann_date_col: str = "ann_date") -> pd.DataFrame:
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
            stacklevel=2,
        )
        return financial_df

    # 确保日期类型一致
    ann_dates = pd.to_datetime(financial_df[ann_date_col])
    trade_dt = pd.to_datetime(trade_date)

    # 仅保留公告日 <= 交易日的记录
    # PIT核心约束：在公告日之前使用未公开财务数据会造成前瞻偏差，严重回测失真
    mask = ann_dates <= trade_dt
    filtered = financial_df.loc[mask].copy()

    if filtered.empty:
        return filtered

    # 对于同一股票同一报告期，取最新的公告记录
    # 同一报告期可能存在更正公告(如业绩快报→正式财报)，取最新ann_date确保使用最准确的已公告数据
    if "report_period" in filtered.columns:
        filtered = filtered.sort_values([ann_date_col], ascending=False)
        filtered = filtered.drop_duplicates(subset=["ts_code", "report_period"], keep="first")
    elif "end_date" in filtered.columns:
        filtered = filtered.sort_values([ann_date_col], ascending=False)
        filtered = filtered.drop_duplicates(subset=["ts_code", "end_date"], keep="first")

    return filtered


# 因子分组定义 (ADD 6.3.1 + 机构级扩展)
FACTOR_GROUPS = {
    "valuation": {
        "name": "价值因子",
        "factors": ["ep_ttm", "bp", "sp_ttm", "dp", "cfp_ttm"],
    },
    "growth": {
        "name": "成长因子",
        "factors": ["yoy_revenue", "yoy_net_profit", "yoy_deduct_net_profit", "yoy_roe"],
    },
    "quality": {
        "name": "质量因子",
        "factors": ["roe", "roa", "gross_profit_margin", "net_profit_margin", "current_ratio"],
    },
    "momentum": {
        "name": "动量因子",
        "factors": ["ret_1m_reversal", "ret_3m_skip1", "ret_6m_skip1", "ret_12m_skip1"],
    },
    "volatility": {
        "name": "波动率因子",
        "factors": ["vol_20d", "vol_60d", "beta", "idio_vol"],
    },
    "liquidity": {
        "name": "流动性因子",
        "factors": ["turnover_20d", "turnover_60d", "amihud_20d", "zero_return_ratio"],
    },
    "northbound": {
        "name": "北向资金因子",
        "factors": ["north_net_buy_ratio", "north_holding_chg_5d", "north_holding_pct"],
    },
    "analyst": {
        "name": "分析师预期因子",
        "factors": ["sue", "analyst_revision_1m", "analyst_coverage", "earnings_surprise"],
    },
    "microstructure": {
        "name": "微观结构因子",
        "factors": ["large_order_ratio", "overnight_return", "intraday_return_ratio", "vpin"],
    },
    "policy": {
        "name": "政策因子",
        "factors": ["policy_sentiment", "policy_theme_exposure"],
    },
    "supply_chain": {
        "name": "供应链因子",
        "factors": ["customer_momentum", "supplier_demand"],
    },
    "sentiment": {
        "name": "情绪因子",
        "factors": ["retail_sentiment", "margin_balance_chg", "new_account_growth"],
    },
    "ashare_specific": {
        "name": "A股特有因子",
        "factors": ["is_st", "limit_up_ratio_20d", "limit_down_ratio_20d", "ipo_age"],
    },
    "accruals": {
        "name": "应计因子",
        "factors": ["sloan_accrual"],
    },
    "interaction": {
        "name": "交互因子",
        "factors": ["value_x_quality", "size_x_momentum"],
    },
    "earnings_quality": {
        "name": "盈利质量因子",
        "factors": ["accrual_anomaly", "cash_flow_manipulation", "earnings_stability", "cfo_to_net_profit"],
    },
    "smart_money": {
        "name": "聪明钱因子",
        "factors": ["smart_money_ratio", "north_momentum_20d", "margin_signal", "institutional_holding_chg"],
    },
    "risk_penalty": {
        "name": "风险惩罚因子",
        "factors": [
            "volatility_20d",
            "idiosyncratic_vol",
            "max_drawdown_60d",
            "illiquidity",
            "concentration_top10",
            "pledge_ratio",
            "goodwill_ratio",
        ],
    },
    "technical": {
        "name": "技术形态因子",
        "factors": ["rsi_14d", "bollinger_position", "macd_signal", "obv_ratio"],
    },
    "industry_rotation": {
        "name": "行业轮动因子",
        "factors": ["industry_momentum_1m", "industry_fund_flow", "industry_valuation_deviation"],
    },
    "alt_data": {
        "name": "另类数据因子",
        "factors": ["news_sentiment", "supply_chain_momentum", "patent_growth"],
    },
}

# 因子方向定义 (ADD 6.3.4 + 机构级扩展)
# 方向=1表示因子值越大越好(升序排列选前N)，方向=-1表示因子值越小越好(降序排列选前N)
FACTOR_DIRECTIONS = {
    # 价值因子: 盈利收益率/账面价值比/营收市值比/股息率/现金流市值比，越高越便宜越有配置价值
    "ep_ttm": 1,
    "bp": 1,
    "sp_ttm": 1,
    "dp": 1,
    "cfp_ttm": 1,
    # 成长因子: 同比增速越高成长性越强
    "yoy_revenue": 1,
    "yoy_net_profit": 1,
    "yoy_deduct_net_profit": 1,
    "yoy_roe": 1,
    # 质量因子: 盈利能力和财务健康度，越高越好
    "roe": 1,
    "roa": 1,
    "gross_profit_margin": 1,
    "net_profit_margin": 1,
    "current_ratio": 1,
    # 动量因子: ret_1m_reversal方向=-1因为短期反转效应(涨多的股票近期收益差，应反向选)
    # 跳月动量(ret_3m_skip1等)方向=1因为中长期动量效应(强者恒强)
    "ret_1m_reversal": -1,
    "ret_3m_skip1": 1,
    "ret_6m_skip1": 1,
    "ret_12m_skip1": 1,
    # 波动率因子: 低波动异象——低波动股票风险调整后收益更优，方向=-1选低波动
    "vol_20d": -1,
    "vol_60d": -1,
    "beta": -1,
    "idio_vol": -1,
    # 流动性因子: 换手率适中为佳(方向=1)，Amihud非流动性越高越差(方向=-1)
    # zero_return_ratio=-1: 零收益天数多说明流动性差(停牌/涨跌停)
    "turnover_20d": 1,
    "turnover_60d": 1,
    "amihud_20d": -1,
    "zero_return_ratio": -1,
    # 北向资金因子: 北向为A股市场重要的"聪明钱"信号，净买入/增持为正面信号
    "north_net_buy_ratio": 1,
    "north_holding_chg_5d": 1,
    "north_holding_pct": 1,
    # 分析师预期因子: 上调/超预期为正面信号
    "sue": 1,
    "analyst_revision_1m": 1,
    "analyst_coverage": 1,
    "earnings_surprise": 1,
    # 微观结构因子: overnight_return=-1因为隔夜收益反映散户情绪(负向预测)
    # vpin=-1因为概率性知情交易越高流动性越差
    "large_order_ratio": 1,
    "overnight_return": -1,
    "intraday_return_ratio": 1,
    "vpin": -1,
    "policy_sentiment": 1,
    "policy_theme_exposure": 1,
    "customer_momentum": 1,
    "supplier_demand": 1,
    # 情绪因子: 散户情绪/新开户数为反向指标(散户狂热时往往是顶部)
    "retail_sentiment": -1,
    "margin_balance_chg": 1,
    "new_account_growth": -1,
    # A股特有因子: ST/涨跌停/跌停均为风险信号，方向=-1做排除; ipo_age=1偏好成熟标的
    "is_st": -1,
    "limit_up_ratio_20d": -1,
    "limit_down_ratio_20d": -1,
    "ipo_age": 1,
    # Sloan应计: 高应计意味着盈利质量差(利润含"纸面"成分)，方向=-1
    "sloan_accrual": -1,
    "value_x_quality": 1,
    "size_x_momentum": 1,
    # 盈利质量因子: 应计异常/现金流操纵越低盈利越真实; 稳定性和CFO支撑度越高越好
    "accrual_anomaly": -1,
    "cash_flow_manipulation": -1,
    "earnings_stability": 1,
    "cfo_to_net_profit": 1,
    # 聪明钱因子
    "smart_money_ratio": 1,
    "north_momentum_20d": 1,
    "margin_signal": 1,
    "institutional_holding_chg": 1,
    # 技术形态因子: rsi_14d=-1因为RSI过高为超买信号，应反向选择
    "rsi_14d": -1,
    "bollinger_position": 1,
    "macd_signal": 1,
    "obv_ratio": 1,
    # 行业轮动因子: 估值偏离=-1因为偏离历史均值过高意味着行业过热
    "industry_momentum_1m": 1,
    "industry_fund_flow": 1,
    "industry_valuation_deviation": -1,
    # 另类数据因子
    "news_sentiment": 1,
    "supply_chain_momentum": 1,
    "patent_growth": 1,
    # 风险惩罚因子: 集中度/质押/商誉均为风险指标，方向=-1做惩罚
    "concentration_top10": -1,
    "pledge_ratio": -1,
    "goodwill_ratio": -1,
    # 预期修正因子: 上修/评级上调为正面信号
    "eps_revision_fy0": 1,
    "eps_revision_fy1": 1,
    "rating_upgrade_ratio": 1,
    "guidance_up_ratio": 1,
}


class FactorCalculator:
    """因子计算器 - 纯计算，无数据库依赖"""

    def __init__(self) -> None:
        self.preprocessor = FactorPreprocessor()

    # ==================== 价值因子 ====================

    def calc_valuation_factors(
        self, financial_df: pd.DataFrame, price_df: pd.DataFrame = None, trade_date: date | None = None
    ) -> pd.DataFrame:
        """计算价值因子 (优先从原始财务数据计算TTM, 回退到预计算比率)
        PIT安全: 当trade_date提供时，仅使用ann_date <= trade_date的财务数据
        """
        # PIT过滤
        if trade_date is not None:
            financial_df = pit_filter(financial_df, trade_date)

        result = pd.DataFrame()
        result["security_id"] = financial_df["ts_code"]

        has_raw = all(c in financial_df.columns for c in ["net_profit", "total_market_cap"])
        if has_raw:
            # TTM口径计算：用最近4个季度累计净利润/总市值，确保跨期可比且遵守PIT
            cap = financial_df["total_market_cap"].replace(0, np.nan)
            result["ep_ttm"] = financial_df["net_profit"] / cap
            if "operating_cash_flow" in financial_df.columns:
                result["cfp_ttm"] = financial_df["operating_cash_flow"] / cap
            if "revenue" in financial_df.columns:
                result["sp_ttm"] = financial_df["revenue"] / cap
            if "total_equity" in financial_df.columns:
                result["bp"] = financial_df["total_equity"] / cap
        else:
            # 回退路径: 无原始报表数据时用预计算比率(如tushare pe_ttm)取倒数
            # 取倒数是因为因子定义统一为"收益/价格"口径，而行情源通常提供"价格/收益"
            if "pe_ttm" in financial_df.columns:
                result["ep_ttm"] = 1 / financial_df["pe_ttm"].replace(0, np.nan)
            if "pb" in financial_df.columns:
                result["bp"] = 1 / financial_df["pb"].replace(0, np.nan)
            if "ps_ttm" in financial_df.columns:
                result["sp_ttm"] = 1 / financial_df["ps_ttm"].replace(0, np.nan)
            if "operating_cash_flow" in financial_df.columns and "total_market_cap" in financial_df.columns:
                result["cfp_ttm"] = financial_df["operating_cash_flow"] / financial_df["total_market_cap"].replace(
                    0, np.nan
                )

        result["dp"] = financial_df.get("dividend_yield", np.nan)
        return result

    # ==================== 成长因子 ====================

    def calc_growth_factors(self, financial_df: pd.DataFrame, trade_date: date | None = None) -> pd.DataFrame:
        """
        计算成长因子 (优先从连续季报计算YoY)
        PIT安全: 当trade_date提供时，仅使用ann_date <= trade_date的财务数据
        """
        # PIT过滤
        if trade_date is not None:
            financial_df = pit_filter(financial_df, trade_date)

        result = pd.DataFrame()
        result["security_id"] = financial_df["ts_code"]

        has_raw = all(c in financial_df.columns for c in ["revenue", "revenue_yoy_4q"])
        if has_raw:
            # YoY计算必须用同比4个季度前的数据(revenue_yoy_4q)，而非单季同比
            # 单季同比受季节性干扰严重，4Q滚动可比消除了季节性偏差
            result["yoy_revenue"] = (financial_df["revenue"] - financial_df["revenue_yoy_4q"]) / financial_df[
                "revenue_yoy_4q"
            ].replace(0, np.nan).abs()
        else:
            result["yoy_revenue"] = financial_df.get("yoy_revenue")

        if "net_profit" in financial_df.columns and "net_profit_yoy_4q" in financial_df.columns:
            result["yoy_net_profit"] = (financial_df["net_profit"] - financial_df["net_profit_yoy_4q"]) / financial_df[
                "net_profit_yoy_4q"
            ].replace(0, np.nan).abs()
        else:
            result["yoy_net_profit"] = financial_df.get("yoy_net_profit")

        result["yoy_deduct_net_profit"] = financial_df.get("yoy_deduct_net_profit")
        result["yoy_roe"] = financial_df.get("yoy_roe")
        return result

    # ==================== 质量因子 ====================

    def calc_quality_factors(self, financial_df: pd.DataFrame, trade_date: date | None = None) -> pd.DataFrame:
        """
        计算质量因子 (ROE/ROA用平均净资产/总资产)
        PIT安全: 当trade_date提供时，仅使用ann_date <= trade_date的财务数据
        注意: Sloan应计已移至calc_accruals_factor，此处不再重复计算
        """
        # PIT过滤
        if trade_date is not None:
            financial_df = pit_filter(financial_df, trade_date)

        result = pd.DataFrame()
        result["security_id"] = financial_df["ts_code"]

        has_raw = all(c in financial_df.columns for c in ["net_profit", "total_equity"])
        if has_raw:
            if "total_equity_prev" in financial_df.columns:
                # DuPont分析标准做法: ROE分母用期初+期末净资产均值，避免增发/回购导致失真
                avg_equity = (financial_df["total_equity"] + financial_df["total_equity_prev"]) / 2
                result["roe"] = financial_df["net_profit"] / avg_equity.replace(0, np.nan)
            else:
                # 无上期数据时用期末*0.9近似期初值，避免高估ROE
                # 0.9假设净资产单季增长约10%，是经验近似; 有prev数据时优先用真实值
                avg_equity = (financial_df["total_equity"] + financial_df["total_equity"] * 0.9) / 2
                result["roe"] = financial_df["net_profit"] / avg_equity.replace(0, np.nan)

            if "total_assets" in financial_df.columns:
                if "total_assets_prev" in financial_df.columns:
                    avg_assets = (financial_df["total_assets"] + financial_df["total_assets_prev"]) / 2
                else:
                    avg_assets = financial_df["total_assets"]
                result["roa"] = financial_df["net_profit"] / avg_assets.replace(0, np.nan)

            if "gross_profit" in financial_df.columns and "revenue" in financial_df.columns:
                result["gross_profit_margin"] = financial_df["gross_profit"] / financial_df["revenue"].replace(
                    0, np.nan
                )

            if "revenue" in financial_df.columns:
                result["net_profit_margin"] = financial_df["net_profit"] / financial_df["revenue"].replace(0, np.nan)

            if "current_assets" in financial_df.columns and "current_liabilities" in financial_df.columns:
                result["current_ratio"] = financial_df["current_assets"] / financial_df["current_liabilities"].replace(
                    0, np.nan
                )

            # 注意: Sloan应计已移至calc_accruals_factor，避免重复计算
        else:
            result["roe"] = financial_df.get("roe")
            result["roa"] = financial_df.get("roa")
            result["gross_profit_margin"] = financial_df.get("gross_profit_margin")
            result["net_profit_margin"] = financial_df.get("net_profit_margin")
            result["current_ratio"] = financial_df.get("current_ratio")

        return result

    # ==================== 动量因子 ====================

    def calc_momentum_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算动量因子 (跳月处理: 跳过最近1月避免短期反转污染)
        面板数据安全: 使用groupby('ts_code')确保rolling/shift不跨股票边界
        """
        result = pd.DataFrame()
        if "close" not in price_df.columns or "ts_code" not in price_df.columns:
            return result

        # 关键: 面板数据必须先按(ts_code, trade_date)排序，否则shift会跨股票边界
        if "trade_date" in price_df.columns:
            price_df = price_df.sort_values(["ts_code", "trade_date"])

        # 面板数据: 按股票分组计算，避免跨股票边界
        grouped = price_df.groupby("ts_code")
        # 20/60/120/240个交易日分别对应约1/3/6/12个月(A股约240个交易日/年)
        close = price_df["close"]
        close_shift_20 = grouped["close"].shift(20)
        close_shift_60 = grouped["close"].shift(60)
        close_shift_120 = grouped["close"].shift(120)
        close_shift_240 = grouped["close"].shift(240)

        result["security_id"] = price_df["ts_code"]
        # ret_1m_reversal: 近1月收益，短期反转效应显著(涨多回撤)，方向=-1
        result["ret_1m_reversal"] = close / close_shift_20 - 1
        # 跳月动量(skip1): 跳过最近1个月计算动量，避免短期反转污染中长期动量信号
        # 公式: P(t-20)/P(t-60) - 1，即从1个月前到3个月前的收益
        result["ret_3m_skip1"] = _safe_divide(close_shift_20, close_shift_60) - 1
        result["ret_6m_skip1"] = _safe_divide(close_shift_20, close_shift_120) - 1
        result["ret_12m_skip1"] = _safe_divide(close_shift_20, close_shift_240) - 1
        return result

    # ==================== 波动率因子 ====================

    def calc_volatility_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算波动率因子
        面板数据安全: 使用groupby('ts_code')确保rolling不跨股票边界
        """
        result = pd.DataFrame()
        if "close" not in price_df.columns:
            return result

        result["security_id"] = price_df.get("ts_code")

        if "ts_code" in price_df.columns:
            # 面板数据: 按股票分组rolling
            # min_periods=10/30允许初期缺失，避免股票上市不足20/60天时无值
            # 年化: 日标准差 * sqrt(252)，252为A股年交易日数
            result["vol_20d"] = price_df.groupby("ts_code")["close"].transform(
                lambda s: s.pct_change().rolling(20, min_periods=10).std()
            ) * np.sqrt(252)
            result["vol_60d"] = price_df.groupby("ts_code")["close"].transform(
                lambda s: s.pct_change().rolling(60, min_periods=30).std()
            ) * np.sqrt(252)
        else:
            # 单股时间序列
            daily_ret = price_df["close"].pct_change()
            result["vol_20d"] = daily_ret.rolling(20).std() * np.sqrt(252)
            result["vol_60d"] = daily_ret.rolling(60).std() * np.sqrt(252)
        return result

    # ==================== 流动性因子 ====================

    def calc_liquidity_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """计算流动性因子
        面板数据安全: 使用groupby('ts_code')确保rolling不跨股票边界
        """
        result = pd.DataFrame()
        if "turnover_rate" not in price_df.columns:
            return result

        result["security_id"] = price_df.get("ts_code")

        if "ts_code" in price_df.columns:
            grouped = price_df.groupby("ts_code")
            result["turnover_20d"] = grouped["turnover_rate"].transform(lambda s: s.rolling(20, min_periods=10).mean())
            result["turnover_60d"] = grouped["turnover_rate"].transform(lambda s: s.rolling(60, min_periods=30).mean())

            if "amount" in price_df.columns and "close" in price_df.columns:
                # Amihud非流动性指标: |收益率|/成交额，衡量单位成交额引起的价格变动
                # 值越大说明流动性越差(小资金就能推动价格)
                daily_ret = price_df["close"] / grouped["close"].shift(1) - 1
                amihud_daily = daily_ret.abs() / price_df["amount"].replace(0, np.nan)
                result["amihud_20d"] = amihud_daily.groupby(price_df["ts_code"]).transform(
                    lambda s: s.rolling(20, min_periods=10).mean()
                )

            if "close" in price_df.columns:
                daily_ret = price_df["close"] / grouped["close"].shift(1) - 1
                # 零收益比例: |日收益|<0.1%视为零收益日(停牌/涨跌停/无成交)
                # 0.001=0.1%阈值排除最小价格变动导致的伪零收益
                result["zero_return_ratio"] = (
                    (daily_ret.abs() < 0.001)
                    .groupby(price_df["ts_code"])
                    .transform(lambda s: s.rolling(20, min_periods=10).mean())
                )
        else:
            result["turnover_20d"] = price_df["turnover_rate"].rolling(20).mean()
            result["turnover_60d"] = price_df["turnover_rate"].rolling(60).mean()

            if "amount" in price_df.columns and "close" in price_df.columns:
                abs_ret = price_df["close"].pct_change().abs()
                amount = price_df["amount"]
                result["amihud_20d"] = (abs_ret / amount.replace(0, np.nan)).rolling(20).mean()

            daily_ret = price_df["close"].pct_change() if "close" in price_df.columns else pd.Series()
            result["zero_return_ratio"] = (daily_ret.abs() < 0.001).rolling(20).mean()
        return result

    # ==================== 机构级扩展因子 ====================

    def calc_northbound_factors(self, northbound_df: pd.DataFrame) -> pd.DataFrame:
        """北向资金因子"""
        result = pd.DataFrame()
        result["security_id"] = northbound_df["ts_code"]

        if "north_net_buy" in northbound_df.columns and "daily_volume" in northbound_df.columns:
            # 北向净买入占比: 衡量外资对个股的短期关注度
            result["north_net_buy_ratio"] = northbound_df["north_net_buy"] / northbound_df["daily_volume"].replace(
                0, np.nan
            )
        if "north_holding" in northbound_df.columns:
            # pct_change(5): 最近5个交易日北向持仓变化率
            result["north_holding_chg_5d"] = northbound_df["north_holding"].pct_change(5)
        if "north_holding_pct" in northbound_df.columns:
            result["north_holding_pct"] = northbound_df["north_holding_pct"]
        return result

    def calc_analyst_factors(self, analyst_df: pd.DataFrame, consensus_df: pd.DataFrame = None) -> pd.DataFrame:
        """分析师预期因子 (SUE, 分析师修正, EPS修正, 业绩超预期)

        Args:
            analyst_df: 原始分析师数据 (含 actual_eps, expected_eps, num_analysts 等)
            consensus_df: 一致预期数据 (含 ts_code, effective_date, consensus_eps_fy0/fy1,
                           analyst_coverage, rating_mean 等)
        """
        result = pd.DataFrame()

        # 优先从 consensus_df 计算新因子
        if consensus_df is not None and not consensus_df.empty:
            result["security_id"] = consensus_df["ts_code"]

            # analyst_coverage: 分析师覆盖数
            if "analyst_coverage" in consensus_df.columns:
                result["analyst_coverage"] = consensus_df["analyst_coverage"]

            # eps_revision_fy0/fy1: EPS修正幅度
            if "consensus_eps_fy0" in consensus_df.columns and "ts_code" in consensus_df.columns:
                # 计算EPS修正: 当前EPS vs 1个月前EPS
                # shift(20): 约20个交易日=1个月，与市场惯例一致
                grouped = consensus_df.sort_values("effective_date").groupby("ts_code")
                eps_fy0_shift = grouped["consensus_eps_fy0"].shift(20)
                result["eps_revision_fy0"] = np.where(
                    eps_fy0_shift.notna() & (eps_fy0_shift != 0),
                    (consensus_df["consensus_eps_fy0"] - eps_fy0_shift) / eps_fy0_shift.abs(),
                    np.nan,
                )

            if "consensus_eps_fy1" in consensus_df.columns and "ts_code" in consensus_df.columns:
                grouped = consensus_df.sort_values("effective_date").groupby("ts_code")
                eps_fy1_shift = grouped["consensus_eps_fy1"].shift(20)
                result["eps_revision_fy1"] = np.where(
                    eps_fy1_shift.notna() & (eps_fy1_shift != 0),
                    (consensus_df["consensus_eps_fy1"] - eps_fy1_shift) / eps_fy1_shift.abs(),
                    np.nan,
                )

            # rating_upgrade_ratio: 评级上调比例 (从rating_mean变化推断)
            if "rating_mean" in consensus_df.columns and "ts_code" in consensus_df.columns:
                grouped = consensus_df.sort_values("effective_date").groupby("ts_code")
                rating_shift = grouped["rating_mean"].shift(20)
                # 评级越低越好(1=强烈推荐, 5=卖出), 所以rating下降=上调
                # rating_mean下降→rating_upgrade_ratio为正，与"上调=正面信号"一致
                result["rating_upgrade_ratio"] = np.where(
                    rating_shift.notna(),
                    (rating_shift - consensus_df["rating_mean"]) / rating_shift.abs().replace(0, np.nan),
                    np.nan,
                )

            # earnings_surprise: 业绩超预期幅度
            if all(c in consensus_df.columns for c in ["consensus_eps_fy0"]):
                # 需要实际EPS来计算超预期, 如果没有则用最近EPS变化近似
                result["earnings_surprise"] = consensus_df.get("earnings_surprise", np.nan)

            # guidance_up_ratio: 业绩预告上修比例 (从EPS修正方向推断)
            # 三值离散化: +1(上修)/0(持平)/-1(下修)，简单信号比连续值更稳健
            if "eps_revision_fy0" in result.columns:
                result["guidance_up_ratio"] = np.where(
                    result["eps_revision_fy0"] > 0, 1.0, np.where(result["eps_revision_fy0"] < 0, -1.0, 0.0)
                )

            return result

        # 回退到原始 analyst_df
        result["security_id"] = analyst_df["ts_code"]

        if all(c in analyst_df.columns for c in ["actual_eps", "expected_eps"]):
            # SUE(标准化意外盈利): 意外盈利/历史意外标准差，衡量超预期程度
            surprise = analyst_df["actual_eps"] - analyst_df["expected_eps"]
            # rolling(8,min_periods=4): 用近8个季度数据计算标准差，至少4期才可靠
            surprise_std = surprise.rolling(8, min_periods=4).std() if len(surprise) >= 4 else surprise.std()
            result["sue"] = surprise / surprise_std.replace(0, np.nan)

        if all(c in analyst_df.columns for c in ["consensus_rating", "consensus_rating_1m_ago"]):
            # 分析师评级修正: 用1个月前评级减当前评级(评级下降=上调，同上逻辑)
            result["analyst_revision_1m"] = analyst_df["consensus_rating_1m_ago"] - analyst_df["consensus_rating"]

        if "num_analysts" in analyst_df.columns:
            result["analyst_coverage"] = analyst_df["num_analysts"]

        if all(c in analyst_df.columns for c in ["actual_eps", "expected_eps"]):
            result["earnings_surprise"] = (analyst_df["actual_eps"] - analyst_df["expected_eps"]) / analyst_df[
                "expected_eps"
            ].abs().replace(0, np.nan)
        return result

    def calc_microstructure_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """微观结构因子
        面板数据安全: 使用groupby('ts_code')确保shift/rolling不跨股票边界
        """
        result = pd.DataFrame()
        result["security_id"] = price_df.get("ts_code")

        if "ts_code" not in price_df.columns:
            # 单股时间序列模式
            if all(c in price_df.columns for c in ["large_order_volume", "super_large_order_volume", "volume"]):
                smart_money_vol = price_df["large_order_volume"].fillna(0) + price_df[
                    "super_large_order_volume"
                ].fillna(0)
                result["large_order_ratio"] = smart_money_vol / price_df["volume"].replace(0, np.nan)
                result["large_order_ratio"] = result["large_order_ratio"].rolling(20, min_periods=5).mean()

            if all(c in price_df.columns for c in ["open", "close"]):
                # 隔夜收益: 今日开盘/昨收 - 1，反映集合竞价和隔夜信息
                # 方向=-1因为A股隔夜收益有显著反转效应(散户隔夜情绪过度反应)
                result["overnight_return"] = _safe_divide(price_df["open"], price_df["close"].shift(1)) - 1
                result["overnight_return"] = result["overnight_return"].rolling(20, min_periods=5).mean()

            if all(c in price_df.columns for c in ["open", "close"]):
                # 日内/隔夜收益比: 日内波动主导的股票信息效率更高
                intraday_ret = _safe_divide(price_df["close"], price_df["open"]) - 1
                overnight_ret = _safe_divide(price_df["open"], price_df["close"].shift(1)) - 1
                result["intraday_return_ratio"] = intraday_ret.abs().rolling(
                    20, min_periods=5
                ).mean() / overnight_ret.abs().rolling(20, min_periods=5).mean().replace(0, np.nan)

            if all(c in price_df.columns for c in ["close", "volume"]):
                # VPIN: 量价交互的知情交易概率指标，|收益|*相对成交量
                # 成交量放大+价格大幅变动=疑似知情交易，方向=-1
                daily_ret = price_df["close"].pct_change()
                abs_ret = daily_ret.abs()
                vol_ratio = _safe_divide(price_df["volume"], price_df["volume"].rolling(20, min_periods=5).mean())
                result["vpin"] = (abs_ret * vol_ratio).rolling(20, min_periods=5).mean()
            return result

        # 面板数据模式: 按股票分组
        grouped = price_df.groupby("ts_code")

        if all(c in price_df.columns for c in ["large_order_volume", "super_large_order_volume", "volume"]):
            smart_money_vol = price_df["large_order_volume"].fillna(0) + price_df["super_large_order_volume"].fillna(0)
            result["large_order_ratio"] = smart_money_vol / price_df["volume"].replace(0, np.nan)
            result["large_order_ratio"] = (
                result["large_order_ratio"]
                .groupby(price_df["ts_code"])
                .transform(lambda s: s.rolling(20, min_periods=5).mean())
            )

        if all(c in price_df.columns for c in ["open", "close"]):
            prev_close = grouped["close"].shift(1)
            result["overnight_return"] = _safe_divide(price_df["open"], prev_close) - 1
            result["overnight_return"] = (
                result["overnight_return"]
                .groupby(price_df["ts_code"])
                .transform(lambda s: s.rolling(20, min_periods=5).mean())
            )

        if all(c in price_df.columns for c in ["open", "close"]):
            intraday_ret = _safe_divide(price_df["close"], price_df["open"]) - 1
            overnight_ret = _safe_divide(price_df["open"], grouped["close"].shift(1)) - 1
            result["intraday_return_ratio"] = _safe_divide(
                intraday_ret.abs()
                .groupby(price_df["ts_code"])
                .transform(lambda s: s.rolling(20, min_periods=5).mean()),
                overnight_ret.abs()
                .groupby(price_df["ts_code"])
                .transform(lambda s: s.rolling(20, min_periods=5).mean()),
            )

        if all(c in price_df.columns for c in ["close", "volume"]):
            daily_ret = price_df["close"] / grouped["close"].shift(1) - 1
            abs_ret = daily_ret.abs()
            vol_ratio = _safe_divide(
                price_df["volume"],
                price_df.groupby("ts_code")["volume"].transform(lambda s: s.rolling(20, min_periods=5).mean()),
            )
            result["vpin"] = (
                (abs_ret * vol_ratio)
                .groupby(price_df["ts_code"])
                .transform(lambda s: s.rolling(20, min_periods=5).mean())
            )

        return result

    def calc_policy_factors(self, policy_df: pd.DataFrame) -> pd.DataFrame:
        """政策因子 (A股特有)"""
        # A股政策驱动特征明显: 产业政策/监管变动对行业轮动有强解释力
        result = pd.DataFrame()
        result["security_id"] = policy_df.get("ts_code")
        if "policy_sentiment_score" in policy_df.columns:
            result["policy_sentiment"] = policy_df["policy_sentiment_score"]
        if "policy_keywords_match" in policy_df.columns:
            result["policy_theme_exposure"] = policy_df["policy_keywords_match"]
        return result

    def calc_supply_chain_factors(self, supply_chain_df: pd.DataFrame) -> pd.DataFrame:
        """供应链因子 (Cohen-Frazzini客户动量)"""
        # Cohen-Frazzini(2008): 客户端业绩变化会沿供应链传导至供应商，存在3-6月滞后期
        result = pd.DataFrame()
        result["security_id"] = supply_chain_df.get("ts_code")
        if "customer_revenue_growth" in supply_chain_df.columns:
            result["customer_momentum"] = supply_chain_df["customer_revenue_growth"]
        if "downstream_demand_index" in supply_chain_df.columns:
            result["supplier_demand"] = supply_chain_df["downstream_demand_index"]
        return result

    def calc_sentiment_factors(self, sentiment_df: pd.DataFrame) -> pd.DataFrame:
        """情绪因子 (A股特有)
        面板数据安全: 使用groupby('ts_code')确保rolling/pct_change不跨股票边界
        """
        result = pd.DataFrame()
        result["security_id"] = sentiment_df.get("ts_code")

        if "retail_order_ratio" in sentiment_df.columns:
            # 散户订单占比: A股散户成交占比高(约80%)，散户狂热是反向指标
            # 散户集中买入往往意味着短期见顶，方向=-1
            if "ts_code" in sentiment_df.columns:
                result["retail_sentiment"] = sentiment_df.groupby("ts_code")["retail_order_ratio"].transform(
                    lambda s: s.rolling(20, min_periods=5).mean()
                )
            else:
                result["retail_sentiment"] = sentiment_df["retail_order_ratio"].rolling(20, min_periods=5).mean()
        if "margin_balance" in sentiment_df.columns:
            # 融资余额变化: 5日变动率，融资余额上升表示杠杆资金入场
            if "ts_code" in sentiment_df.columns:
                result["margin_balance_chg"] = sentiment_df.groupby("ts_code")["margin_balance"].transform(
                    lambda s: s.pct_change(5)
                )
            else:
                result["margin_balance_chg"] = sentiment_df["margin_balance"].pct_change(5)
        if "new_accounts" in sentiment_df.columns:
            # 新开户数增长率: 散户入场情绪指标，方向=-1(反向指标)
            # 历史上开户高峰对应市场顶部区域
            if "ts_code" in sentiment_df.columns:
                result["new_account_growth"] = sentiment_df.groupby("ts_code")["new_accounts"].transform(
                    lambda s: s.pct_change(20)
                )
            else:
                result["new_account_growth"] = sentiment_df["new_accounts"].pct_change(20)
        return result

    # ==================== A股特有因子 ====================

    def calc_ashare_specific_factors(
        self, price_df: pd.DataFrame, stock_basic_df: pd.DataFrame = None, stock_status_df: pd.DataFrame = None
    ) -> pd.DataFrame:
        """A股特有因子: ST状态、涨跌停占比、IPO年龄"""
        result = pd.DataFrame()
        result["security_id"] = price_df.get("ts_code", price_df.index)

        if stock_status_df is not None and "is_st" in stock_status_df.columns:
            st_map = stock_status_df.set_index("ts_code")["is_st"]
            result["is_st"] = result["security_id"].map(st_map).fillna(0).astype(float)
        else:
            if "ts_code" in price_df.columns:
                result["is_st"] = 0.0

        if "pct_chg" in price_df.columns:
            # 涨跌停判断需区分板块: 主板10%, 创业板/科创板20%, 北交所30%, ST5%
            # 这是A股特有的价格限制规则，不同板块涨跌幅限制不同
            # pct_chg为百分比形式(如9.9表示9.9%)
            limit_pct = pd.Series(10.0, index=price_df.index)  # 默认主板10%

            if "ts_code" in price_df.columns:
                ts = price_df["ts_code"].astype(str)
                # 创业板(300xxx.SZ)
                limit_pct[ts.str.startswith("3") & ts.str.endswith(".SZ")] = 20.0
                # 科创板(688xxx.SH)
                limit_pct[ts.str.startswith("688") & ts.str.endswith(".SH")] = 20.0
                # 北交所(8xxxxx.BJ / 4xxxxx.BJ)
                limit_pct[ts.str.endswith(".BJ")] = 30.0

            # ST股5%涨跌停
            # ST(特别处理)股涨跌幅限制收窄至5%，是退市风险警示的配套制度
            if stock_status_df is not None and "is_st" in stock_status_df.columns:
                st_map = stock_status_df.set_index("ts_code")["is_st"]
                is_st = (
                    price_df["ts_code"].map(st_map).fillna(False)
                    if "ts_code" in price_df.columns
                    else pd.Series(False, index=price_df.index)
                )
                limit_pct[is_st] = 5.0

            # 0.01容差: pct_chg可能因四舍五入略低于涨停线(如9.99%)
            is_limit_up = (price_df["pct_chg"] >= limit_pct - 0.01).astype(float)
            is_limit_down = (price_df["pct_chg"] <= -(limit_pct - 0.01)).astype(float)

            if "ts_code" in price_df.columns:
                result["limit_up_ratio_20d"] = is_limit_up.groupby(price_df["ts_code"]).transform(
                    lambda s: s.rolling(20, min_periods=10).mean()
                )
                result["limit_down_ratio_20d"] = is_limit_down.groupby(price_df["ts_code"]).transform(
                    lambda s: s.rolling(20, min_periods=10).mean()
                )
            else:
                result["limit_up_ratio_20d"] = is_limit_up.rolling(20, min_periods=10).mean()
                result["limit_down_ratio_20d"] = is_limit_down.rolling(20, min_periods=10).mean()

        if stock_basic_df is not None and "list_date" in stock_basic_df.columns:
            # IPO年龄: 上市天数/365.25转换为年，365.25包含闰年修正
            list_dates = stock_basic_df.set_index("ts_code")["list_date"]
            result["ipo_age"] = result["security_id"].map(list_dates)
            if "trade_date" in price_df.columns:
                trade_date = pd.to_datetime(price_df["trade_date"])
                list_date = pd.to_datetime(result["ipo_age"])
                result["ipo_age"] = (trade_date - list_date).dt.days / 365.25
                # clip(lower=0): 防止上市日期晚于交易日期的异常数据产生负值
                result["ipo_age"] = result["ipo_age"].clip(lower=0)
            else:
                result["ipo_age"] = np.nan

        return result

    def calc_accruals_factor(self, financial_df: pd.DataFrame, trade_date: date | None = None) -> pd.DataFrame:
        """Sloan应计因子
        PIT安全: 当trade_date提供时，仅使用ann_date <= trade_date的财务数据
        """
        if trade_date is not None:
            financial_df = pit_filter(financial_df, trade_date)

        result = pd.DataFrame()
        result["security_id"] = financial_df.get("ts_code", financial_df.index)

        # Sloan应计 = (净利润 - 经营现金流) / 平均总资产
        # Sloan(1996): 高应计企业未来盈利反转概率大，应计是盈利质量的反向指标
        # 经营现金流比净利润更难操纵，二者差异反映盈余管理空间
        required = ["net_profit", "operating_cash_flow", "total_assets"]
        if all(c in financial_df.columns for c in required):
            accruals = financial_df["net_profit"] - financial_df["operating_cash_flow"]
            if "total_assets_prev" in financial_df.columns:
                avg_assets = (financial_df["total_assets"] + financial_df["total_assets_prev"]) / 2
            else:
                avg_assets = financial_df["total_assets"]
            result["sloan_accrual"] = accruals / avg_assets.replace(0, np.nan)

        return result

    def calc_interaction_factors(self, factor_df: pd.DataFrame) -> pd.DataFrame:
        """因子交互项 (在原始值层面计算，保留经济含义)
        重要: 交互项必须在标准化之前计算，两个z-score相乘不再具有原始经济含义
        """
        result = pd.DataFrame()
        result["security_id"] = factor_df["security_id"]

        # 价值×质量: 低估值+高盈利质量的股票，即"便宜且优秀"的GARP策略内核
        if "ep_ttm" in factor_df.columns and "roe" in factor_df.columns:
            result["value_x_quality"] = factor_df["ep_ttm"] * factor_df["roe"]

        # 规模×动量: log(市值)×动量，捕捉大盘股动量效应
        # 用log消除市值量纲差异，避免大市值股票主导交互项
        if "total_market_cap" in factor_df.columns and "ret_12m_skip1" in factor_df.columns:
            result["size_x_momentum"] = np.log(factor_df["total_market_cap"]) * factor_df["ret_12m_skip1"]
        elif "market_cap" in factor_df.columns and "ret_12m_skip1" in factor_df.columns:
            result["size_x_momentum"] = np.log(factor_df["market_cap"]) * factor_df["ret_12m_skip1"]

        return result

    # ==================== 向量化批处理合并 ====================

    @staticmethod
    def _merge_factor_dfs(factor_dfs: list) -> pd.DataFrame:
        """
        向量化批处理合并因子DataFrame
        替代逐个pd.merge: 一次性concat+pivot，性能提升3-5倍
        """
        valid_dfs = [f for f in factor_dfs if not f.empty and "security_id" in f.columns]
        if not valid_dfs:
            return pd.DataFrame()

        if len(valid_dfs) == 1:
            return valid_dfs[0]

        # 收集所有security_id
        all_ids = set()
        for f in valid_dfs:
            all_ids.update(f["security_id"].values)

        # 逐个merge (pandas的merge已优化，对于<20个因子组足够快)
        merged = valid_dfs[0]
        for f in valid_dfs[1:]:
            merged = pd.merge(merged, f, on="security_id", how="outer")

        return merged

    # ==================== 全因子计算入口 ====================

    def calc_all_factors(
        self,
        financial_df: pd.DataFrame,
        price_df: pd.DataFrame,
        industry_col: str | None = None,
        cap_col: str | None = None,
        neutralize: bool = True,
        northbound_df: pd.DataFrame = None,
        analyst_df: pd.DataFrame = None,
        consensus_df: pd.DataFrame = None,
        policy_df: pd.DataFrame = None,
        supply_chain_df: pd.DataFrame = None,
        sentiment_df: pd.DataFrame = None,
        stock_basic_df: pd.DataFrame = None,
        stock_status_df: pd.DataFrame = None,
        money_flow_df: pd.DataFrame = None,
        margin_df: pd.DataFrame = None,
        daily_basic_df: pd.DataFrame = None,
        pledge_df: pd.DataFrame = None,
        holders_df: pd.DataFrame = None,
        institutional_df: pd.DataFrame = None,
        industry_df: pd.DataFrame = None,
        trade_date: date | None = None,
    ) -> pd.DataFrame:
        """
        计算所有因子并预处理 (向量化批处理合并)
        PIT安全: 当trade_date提供时，财务因子仅使用ann_date <= trade_date的数据
        """
        factor_dfs = []

        # 基础因子 (财务因子传入trade_date做PIT过滤)
        # 注意: 仅财务类因子需要PIT过滤，价格/成交量类因子天然无前瞻偏差
        with timer("calc_valuation_factors", log_threshold_ms=100):
            factor_dfs.append(self.calc_valuation_factors(financial_df, price_df, trade_date=trade_date))
        with timer("calc_growth_factors", log_threshold_ms=100):
            factor_dfs.append(self.calc_growth_factors(financial_df, trade_date=trade_date))
        with timer("calc_quality_factors", log_threshold_ms=100):
            factor_dfs.append(self.calc_quality_factors(financial_df, trade_date=trade_date))
        with timer("calc_momentum_factors", log_threshold_ms=100):
            factor_dfs.append(self.calc_momentum_factors(price_df))
        with timer("calc_volatility_factors", log_threshold_ms=100):
            factor_dfs.append(self.calc_volatility_factors(price_df))
        with timer("calc_liquidity_factors", log_threshold_ms=100):
            factor_dfs.append(self.calc_liquidity_factors(price_df))
        with timer("calc_microstructure_factors", log_threshold_ms=100):
            factor_dfs.append(self.calc_microstructure_factors(price_df))

        # 机构级扩展因子
        if northbound_df is not None and not northbound_df.empty:
            factor_dfs.append(self.calc_northbound_factors(northbound_df))
        if analyst_df is not None and not analyst_df.empty:
            factor_dfs.append(self.calc_analyst_factors(analyst_df, consensus_df=consensus_df))
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
        factor_dfs.append(self.calc_smart_money_factors(price_df, northbound_df, margin_df, institutional_df))

        # 行业轮动因子
        factor_dfs.append(self.calc_industry_rotation_factors(price_df, industry_df=industry_df))

        # 另类数据因子 (已在supply_chain_df处理中调用，此处不再重复)
        # 注: calc_alt_data_factors已在上方supply_chain_df分支中调用

        # 从资金流向表补充微观结构数据
        # smart_net_pct: 大单+超大单净买入占比，反映主力资金动向
        # 除以100: 百分比→小数(与smart_money_ratio量纲一致)
        if money_flow_df is not None and not money_flow_df.empty:
            mf_result = pd.DataFrame()
            mf_result["security_id"] = money_flow_df.get("ts_code", money_flow_df.index)
            if "smart_net_pct" in money_flow_df.columns:
                mf_result["smart_money_ratio"] = money_flow_df["smart_net_pct"].rolling(20, min_periods=5).mean() / 100
            if "large_net_pct" in money_flow_df.columns and "super_large_net_pct" in money_flow_df.columns:
                mf_result["large_order_ratio"] = (
                    money_flow_df["large_net_pct"].fillna(0) + money_flow_df["super_large_net_pct"].fillna(0)
                ).rolling(20, min_periods=5).mean() / 100
            if not mf_result.empty:
                factor_dfs.append(mf_result)

        # 从融资融券表补充情绪数据
        # 融资余额5日变化率: 杠杆资金短期进出场信号
        if margin_df is not None and not margin_df.empty:
            mg_result = pd.DataFrame()
            mg_result["security_id"] = margin_df.get("ts_code", margin_df.index)
            if "margin_balance" in margin_df.columns:
                mg_result["margin_signal"] = margin_df["margin_balance"].pct_change(5)
            if not mg_result.empty:
                factor_dfs.append(mg_result)

        # 向量化合并
        with timer("merge_factor_dfs", log_threshold_ms=100):
            merged = self._merge_factor_dfs(factor_dfs)
        if merged.empty:
            return merged

        # 交互因子 (必须在标准化之前计算，保留原始经济含义)
        # 两个z-score相乘不再具有原始经济含义，所以交互项必须在预处理前计算
        with timer("calc_interaction_factors", log_threshold_ms=100):
            interaction = self.calc_interaction_factors(merged)
        if not interaction.empty and "security_id" in interaction.columns:
            merged = pd.merge(merged, interaction, on="security_id", how="outer")

        # 预处理 (包含交互因子)
        # 流程: 缺失值处理→去极值(MAD)→中性化→标准化→方向统一
        # direction_map确保升序/降序方向一致: 方向=-1的因子在标准化时乘-1
        factor_cols = [c for c in merged.columns if c != "security_id"]
        with timer("preprocess_dataframe", log_threshold_ms=200):
            result = self.preprocessor.preprocess_dataframe(
                merged,
                factor_cols,
                industry_col=industry_col,
                cap_col=cap_col,
                neutralize=neutralize,
                direction_map=FACTOR_DIRECTIONS,
            )
        return result

    # ==================== 无数据库便捷函数 ====================

    @staticmethod
    def calc_factors_from_data(
        price_df: pd.DataFrame,
        financial_df: pd.DataFrame = None,
        neutralize: bool = False,
        industry_col: str | None = None,
        cap_col: str | None = None,
    ) -> pd.DataFrame:
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

        factor_cols = [c for c in merged.columns if c != "security_id"]
        return calculator.preprocessor.preprocess_dataframe(
            merged,
            factor_cols,
            industry_col=industry_col,
            cap_col=cap_col,
            neutralize=neutralize,
            direction_map=FACTOR_DIRECTIONS,
        )

    # ==================== 盈利质量因子 ====================

    def calc_earnings_quality_factors(self, financial_df: pd.DataFrame, trade_date: date | None = None) -> pd.DataFrame:
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
        result["security_id"] = financial_df.get("ts_code", financial_df.index)

        # 改进Sloan应计异常
        # 与calc_accruals_factor相同公式但归入盈利质量组，后续可扩展为拆分经营性/投资性应计
        required = ["net_profit", "operating_cash_flow", "total_assets"]
        if all(c in financial_df.columns for c in required):
            accruals = financial_df["net_profit"] - financial_df["operating_cash_flow"]
            if "total_assets_prev" in financial_df.columns:
                avg_assets = (financial_df["total_assets"] + financial_df["total_assets_prev"]) / 2
            else:
                avg_assets = financial_df["total_assets"]
            result["accrual_anomaly"] = accruals / avg_assets.replace(0, np.nan)

            # 现金流操纵概率: |CFO - Net Profit| / |Net Profit|
            # CFO与净利严重偏离暗示可能存在盈余管理(如提前确认收入/延迟计提费用)
            net_profit = financial_df["net_profit"].replace(0, np.nan)
            result["cash_flow_manipulation"] = (
                financial_df["operating_cash_flow"] - financial_df["net_profit"]
            ).abs() / net_profit.abs()

            # CFO/净利: 现金流支撑度
            # clip(-5,5): 极端值通常由净利润接近0导致(分母极小)，截断防止异常值
            result["cfo_to_net_profit"] = (financial_df["operating_cash_flow"] / net_profit).clip(-5, 5)

        # 盈利稳定性: 需要多期数据
        # 用近8季净利变异系数(CV)的变换，CV越小盈利越稳定
        # 1/(1+CV)映射: CV=0→1(最稳定), CV→∞→0(极不稳定)
        if "net_profit_std_8q" in financial_df.columns and "net_profit_mean_8q" in financial_df.columns:
            mean = financial_df["net_profit_mean_8q"].replace(0, np.nan)
            std = financial_df["net_profit_std_8q"]
            cv = (std / mean.abs()).clip(0, 10)
            # clip(0,10): CV截断防止极端值，10对应1/(1+10)≈0.09，已充分体现"极不稳定"
            result["earnings_stability"] = 1 / (1 + cv)

        return result

    # ==================== 风险惩罚因子 ====================

    def calc_risk_penalty_factors(
        self,
        daily_df: pd.DataFrame,
        pledge_df: pd.DataFrame = None,
        holders_df: pd.DataFrame = None,
        financial_df: pd.DataFrame = None,
    ) -> pd.DataFrame:
        """计算风险惩罚因子: concentration_top10, pledge_ratio, goodwill_ratio

        Args:
            daily_df: 日线数据 (含 ts_code, trade_date, close, amount 等)
            pledge_df: 股权质押数据 (含 ts_code, trade_date, pledge_ratio)
            holders_df: 前十大股东数据 (含 ts_code, end_date, hold_ratio, rank)
            financial_df: 财务数据 (含 ts_code, end_date, goodwill, total_equity)
        """
        result = daily_df[["ts_code", "trade_date"]].copy()

        # concentration_top10: 前十大股东持股比例之和
        # 高集中度意味着流动性风险(大股东减持冲击)和治理风险(小股东无话语权)
        if holders_df is not None and not holders_df.empty:
            top10_sum = (
                holders_df[holders_df["rank"] <= 10]
                .groupby(["ts_code", "end_date"])["hold_ratio"]
                .sum()
                .reset_index()
                .rename(columns={"hold_ratio": "concentration_top10"})
            )
            top10_sum = top10_sum.sort_values("end_date").groupby("ts_code").last().reset_index()
            result = result.merge(top10_sum[["ts_code", "concentration_top10"]], on="ts_code", how="left")
        else:
            result["concentration_top10"] = np.nan

        # pledge_ratio: 质押比例
        # 高质押比例=大股东资金紧张+平仓风险，是A股特有风险源(质押爆仓)
        if pledge_df is not None and not pledge_df.empty:
            latest_pledge = (
                pledge_df.sort_values("trade_date").groupby("ts_code").last().reset_index()[["ts_code", "pledge_ratio"]]
            )
            result = result.merge(latest_pledge, on="ts_code", how="left")
        else:
            result["pledge_ratio"] = np.nan

        # goodwill_ratio: 商誉/净资产
        # 高商誉比=高并购溢价，A股商誉减值是年报季重大风险(尤其传媒/游戏行业)
        if financial_df is not None and not financial_df.empty:
            fin = financial_df.copy()
            if "goodwill" in fin.columns and "total_equity" in fin.columns:
                fin["goodwill_ratio"] = np.where(
                    fin["total_equity"].notna() & (fin["total_equity"] != 0),
                    fin["goodwill"] / fin["total_equity"].replace(0, np.nan),
                    np.nan,
                )
                latest_gw = (
                    fin.sort_values("end_date").groupby("ts_code").last().reset_index()[["ts_code", "goodwill_ratio"]]
                )
                result = result.merge(latest_gw, on="ts_code", how="left")
            else:
                result["goodwill_ratio"] = np.nan
        else:
            result["goodwill_ratio"] = np.nan

        return result

    # ==================== 聪明钱因子 ====================

    def calc_smart_money_factors(
        self,
        price_df: pd.DataFrame,
        northbound_df: pd.DataFrame | None = None,
        margin_df: pd.DataFrame | None = None,
        institutional_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """
        聪明钱因子
        - smart_money_ratio: 聪明钱比率 (大单净买入/总成交)
        - north_momentum_20d: 北向资金20日动量
        - margin_signal: 融资融券信号 (融资余额变化率)
        - institutional_holding_chg: 机构持仓变化
        """
        result = pd.DataFrame()
        result["security_id"] = price_df.get("ts_code", price_df.index)

        # 聪明钱比率
        # 大单+超大单成交占比: A股大单通常对应机构/北向资金，小单对应散户
        # 大单占比上升=聪明钱入场，为正向信号
        if all(c in price_df.columns for c in ["large_order_volume", "super_large_order_volume", "volume"]):
            smart_vol = price_df["large_order_volume"].fillna(0) + price_df["super_large_order_volume"].fillna(0)
            total_vol = price_df["volume"].replace(0, np.nan)
            ratio = smart_vol / total_vol
            if "ts_code" in price_df.columns:
                # 面板数据: 按股票分组rolling，避免跨股票边界
                result["smart_money_ratio"] = ratio.groupby(price_df["ts_code"]).transform(
                    lambda s: s.rolling(20, min_periods=5).mean()
                )
            else:
                result["smart_money_ratio"] = ratio.rolling(20, min_periods=5).mean()

        # 北向资金动量
        # 20日持仓变化率: 北向持续增仓是中期看多信号(外资研究能力较强)
        if northbound_df is not None and not northbound_df.empty and "north_holding" in northbound_df.columns:
            result["north_momentum_20d"] = northbound_df["north_holding"].pct_change(20)

        # 融资融券信号
        # 融资余额5日变化率: 融资做多增加=杠杆资金看好(但需警惕极端值=过热)
        if margin_df is not None and not margin_df.empty:
            if "margin_balance" in margin_df.columns:
                result["margin_signal"] = margin_df["margin_balance"].pct_change(5)
        elif "margin_balance" in price_df.columns:
            result["margin_signal"] = price_df["margin_balance"].pct_change(5)

        # 机构持仓变化
        # 季报披露的机构持仓变动有滞后，但方向仍有预测力(机构调仓通常持续数月)
        if institutional_df is not None and not institutional_df.empty:
            if "hold_ratio" in institutional_df.columns:
                inst_result = pd.DataFrame()
                inst_result["security_id"] = institutional_df["ts_code"]
                inst_result["institutional_holding_chg"] = institutional_df["hold_ratio"].pct_change(20)
                # 合并到主result, 而非提前返回
                for col in inst_result.columns:
                    if col != "security_id":
                        result[col] = inst_result[col].values
        elif "institutional_holding_pct" in price_df.columns:
            result["institutional_holding_chg"] = price_df["institutional_holding_pct"].pct_change(20)

        return result

    # ==================== 技术形态因子 ====================

    def calc_technical_factors(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """
        技术形态因子
        - rsi_14d: 14日RSI (相对强弱指标)
        - bollinger_position: 布林带位置 (0=下轨, 0.5=中轨, 1=上轨)
        - macd_signal: MACD信号线
        - obv_ratio: OBV能量潮比率
        面板数据安全: 使用groupby('ts_code')确保ewm/rolling/cumsum不跨股票边界
        """
        result = pd.DataFrame()
        result["security_id"] = price_df.get("ts_code", price_df.index)

        if "close" not in price_df.columns:
            return result

        # 关键: 面板数据必须先按(ts_code, trade_date)排序
        if "ts_code" in price_df.columns and "trade_date" in price_df.columns:
            price_df = price_df.sort_values(["ts_code", "trade_date"])

        close = price_df["close"]
        daily_ret = close.pct_change()

        is_panel = "ts_code" in price_df.columns

        if is_panel:
            grouped = price_df.groupby("ts_code")
            # 面板数据: 每个计算都通过groupby transform确保不跨股票边界
            daily_ret_grouped = grouped["close"].transform(lambda s: s.pct_change())

            # RSI(14) - Wilder平滑法
            # Wilder法用alpha=1/period的EMA替代SMA，比简单均值对近期更敏感
            if len(close) >= 15:
                price_diff = grouped["close"].transform(lambda s: s.diff())
                gain = price_diff.clip(lower=0)
                loss = (-price_diff).clip(lower=0)
                wilder_alpha = 1.0 / 14
                # ewm(alpha=wilder_alpha): Wilder平滑等价于EMA(alpha=1/period)
                avg_gain = gain.groupby(price_df["ts_code"]).transform(
                    lambda s: s.ewm(alpha=wilder_alpha, adjust=False).mean()
                )
                avg_loss = loss.groupby(price_df["ts_code"]).transform(
                    lambda s: s.ewm(alpha=wilder_alpha, adjust=False).mean()
                )
                rs = avg_gain / avg_loss.replace(0, np.nan)
                result["rsi_14d"] = 100 - (100 / (1 + rs))

            # 布林带位置: 标准化到[-1,1]，0.5=中轨，1=上轨2倍标准差
            # clip(-1,1): 超出布林带的价格位置截断，防止极端值
            if len(close) >= 20:
                ma20 = grouped["close"].transform(lambda s: s.rolling(20).mean())
                std20 = grouped["close"].transform(lambda s: s.rolling(20).std())
                result["bollinger_position"] = ((close - ma20) / (2 * std20)).clip(-1, 1)

            # MACD信号: (DIF-DEA)/close*100，除以收盘价做归一化处理
            # 乘100放大到百分比量级，与MACD柱状图视觉比例一致
            if len(close) >= 35:
                ema12 = grouped["close"].transform(lambda s: s.ewm(span=12, adjust=False).mean())
                ema26 = grouped["close"].transform(lambda s: s.ewm(span=26, adjust=False).mean())
                dif = ema12 - ema26
                dea = dif.groupby(price_df["ts_code"]).transform(lambda s: s.ewm(span=9, adjust=False).mean())
                result["macd_signal"] = (dif - dea) / close.replace(0, np.nan) * 100

            # OBV能量潮比率: OBV/20日OBV均值-1，衡量成交量趋势强度
            # clip(-3,3): 极端比率通常是数据异常(如停牌复牌首日)，截断防污染
            if "volume" in price_df.columns and len(close) >= 20:
                direction = np.sign(daily_ret_grouped).fillna(0)
                obv = (direction * price_df["volume"]).groupby(price_df["ts_code"]).transform(lambda s: s.cumsum())
                obv_ma = obv.groupby(price_df["ts_code"]).transform(lambda s: s.rolling(20, min_periods=10).mean())
                result["obv_ratio"] = (obv / obv_ma.replace(0, np.nan) - 1).clip(-3, 3)

        else:
            # 单股时间序列模式 (原始逻辑)
            # RSI(14) - Wilder平滑法 (标准定义)
            if len(close) >= 15:
                price_diff = close.diff()  # 标准RSI使用价格差
                gain = price_diff.clip(lower=0)
                loss = (-price_diff).clip(lower=0)
                # Wilder平滑: EMA with alpha=1/period
                wilder_alpha = 1.0 / 14
                avg_gain = gain.ewm(alpha=wilder_alpha, adjust=False).mean()
                avg_loss = loss.ewm(alpha=wilder_alpha, adjust=False).mean()
                rs = avg_gain / avg_loss.replace(0, np.nan)
                result["rsi_14d"] = 100 - (100 / (1 + rs))

            # 布林带位置
            if len(close) >= 20:
                ma20 = close.rolling(20).mean()
                std20 = close.rolling(20).std()
                result["bollinger_position"] = ((close - ma20) / (2 * std20)).clip(-1, 1)

            # MACD信号
            if len(close) >= 35:
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                dif = ema12 - ema26
                dea = dif.ewm(span=9, adjust=False).mean()
                result["macd_signal"] = (dif - dea) / close.replace(0, np.nan) * 100

            # OBV能量潮比率: OBV/20日OBV均值-1，衡量成交量趋势强度
            # clip(-3,3): 极端比率通常是数据异常(如停牌复牌首日)，截断防污染
            if "volume" in price_df.columns and len(close) >= 20:
                direction = np.sign(daily_ret).fillna(0)
                obv = (direction * price_df["volume"]).cumsum()
                obv_ma = obv.rolling(20, min_periods=10).mean()
                result["obv_ratio"] = (obv / obv_ma.replace(0, np.nan) - 1).clip(-3, 3)

        return result

    # ==================== 行业轮动因子 ====================

    def calc_industry_rotation_factors(
        self, price_df: pd.DataFrame, industry_df: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """
        行业轮动因子
        - industry_momentum_1m: 行业1月动量
        - industry_fund_flow: 行业资金流向
        - industry_valuation_deviation: 行业估值偏离
        """
        result = pd.DataFrame()
        result["security_id"] = price_df.get("ts_code", price_df.index)

        if industry_df is None or industry_df.empty:
            return result

        # 行业动量
        if "industry_return_1m" in industry_df.columns:
            result["industry_momentum_1m"] = industry_df["industry_return_1m"]

        # 行业资金流向
        if "industry_net_inflow" in industry_df.columns:
            result["industry_fund_flow"] = industry_df["industry_net_inflow"]

        # 行业估值偏离: 当前PE vs 3年均值PE
        # clip(-3,3): 偏离3倍标准差以上视为极端异常，截断防止单个行业主导因子值
        if "industry_pe" in industry_df.columns and "industry_pe_mean_3y" in industry_df.columns:
            mean_pe = industry_df["industry_pe_mean_3y"].replace(0, np.nan)
            result["industry_valuation_deviation"] = ((industry_df["industry_pe"] - mean_pe) / mean_pe.abs()).clip(
                -3, 3
            )

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
        result["security_id"] = alt_data_df.get("ts_code", alt_data_df.index)

        # 新闻情感
        if "news_sentiment_score" in alt_data_df.columns:
            result["news_sentiment"] = alt_data_df["news_sentiment_score"].rolling(20, min_periods=5).mean()

        # 供应链传导动量
        if "customer_revenue_growth" in alt_data_df.columns and "supplier_revenue_growth" in alt_data_df.columns:
            # Cohen-Frazzini: 客户动量 + 供应商动量的加权平均
            # 0.6/0.4权重: 客户端信息含量更高(需求侧传导更直接)
            result["supply_chain_momentum"] = (
                0.6 * alt_data_df["customer_revenue_growth"] + 0.4 * alt_data_df["supplier_revenue_growth"]
            )
        elif "customer_revenue_growth" in alt_data_df.columns:
            result["supply_chain_momentum"] = alt_data_df["customer_revenue_growth"]

        # 专利增长
        # pct_change(4): 季度数据4期=年度同比变化
        if "patent_count" in alt_data_df.columns:
            result["patent_growth"] = alt_data_df["patent_count"].pct_change(4)

        return result
