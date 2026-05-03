"""
多因子选股模型
整合因子计算、预处理、合成、选股、组合构建的完整流程
"""

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.factor_calculator import FACTOR_DIRECTIONS, FACTOR_GROUPS, FactorCalculator
from app.core.factor_preprocess import FactorPreprocessor
from app.core.logging import logger
from app.core.portfolio_builder import PortfolioBuilder, PortfolioMode


class FactorWeightingMethod:
    """因子加权方法"""

    EQUAL = "equal"  # 等权重
    IC = "ic"  # IC加权
    IR = "ir"  # IR加权（IC/IC标准差）
    HISTORICAL_RETURN = "historical_return"  # 历史收益加权


class MultiFactorModel:
    """
    多因子选股模型

    完整流程：
    1. 因子计算 - 从数据库读取数据，计算所有因子
    2. 因子预处理 - 去极值、标准化、中性化
    3. 因子合成 - 多个因子加权合成为综合得分
    4. 股票选择 - 根据综合得分排序选股
    5. 组合构建 - 构建投资组合（分层赋权、风险控制）
    """

    def __init__(
        self,
        db: Session,
        factor_groups: list[str] | None = None,
        weighting_method: str = FactorWeightingMethod.EQUAL,
        neutralize_industry: bool = True,
        neutralize_market_cap: bool = True,
    ):
        """
        初始化多因子模型

        Args:
            db: 数据库会话
            factor_groups: 使用的因子组列表，None表示使用所有因子组
            weighting_method: 因子加权方法
            neutralize_industry: 是否进行行业中性化
            neutralize_market_cap: 是否进行市值中性化
        """
        self.db = db
        self.factor_groups = factor_groups or list(FACTOR_GROUPS.keys())
        self.weighting_method = weighting_method
        self.neutralize_industry = neutralize_industry
        self.neutralize_market_cap = neutralize_market_cap

        # 初始化组件
        self.calculator = FactorCalculator()
        self.preprocessor = FactorPreprocessor()
        self.portfolio_builder = PortfolioBuilder()

        logger.info(
            f"MultiFactorModel initialized with {len(self.factor_groups)} factor groups, "
            f"weighting={weighting_method}, "
            f"neutralize_industry={neutralize_industry}, "
            f"neutralize_market_cap={neutralize_market_cap}"
        )

    def calculate_factors(
        self, ts_codes: list[str], trade_date: date, lookback_days: int = 126, batch_size: int = 50
    ) -> pd.DataFrame:
        """
        计算因子值

        Args:
            ts_codes: 股票代码列表
            trade_date: 计算日期
            lookback_days: 回溯天数
            batch_size: 每批处理的股票数量，用于控制内存使用

        Returns:
            DataFrame with columns: ts_code, factor1, factor2, ...
        """
        logger.info(f"Calculating factors for {len(ts_codes)} stocks on {trade_date}")

        # 如果股票数量超过batch_size，分批处理
        if len(ts_codes) > batch_size:
            logger.info(f"Processing in batches of {batch_size} stocks to reduce memory usage")
            all_results = []
            for i in range(0, len(ts_codes), batch_size):
                batch = ts_codes[i:i+batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(ts_codes)-1)//batch_size + 1}: {len(batch)} stocks")
                batch_result = self._calculate_factors_batch(batch, trade_date, lookback_days)
                if not batch_result.empty:
                    all_results.append(batch_result)

            if all_results:
                return pd.concat(all_results, ignore_index=True)
            else:
                return pd.DataFrame()

        # 股票数量较少，直接处理
        return self._calculate_factors_batch(ts_codes, trade_date, lookback_days)

    def _calculate_factors_batch(
        self, ts_codes: list[str], trade_date: date, lookback_days: int = 126
    ) -> pd.DataFrame:
        """
        计算单批股票的因子值（内部方法）

        Args:
            ts_codes: 股票代码列表
            trade_date: 计算日期
            lookback_days: 回溯天数

        Returns:
            DataFrame with columns: ts_code, factor1, factor2, ...
        """

        # 获取所有需要的数据
        from sqlalchemy import text

        # 1. 获取价格数据
        price_query = text(
            """
            SELECT ts_code, trade_date, open, high, low, close, vol, amount,
                   pct_chg, turnover_rate
            FROM stock_daily
            WHERE ts_code = ANY(:ts_codes)
                AND trade_date <= :trade_date
                AND trade_date >= :start_date
            ORDER BY ts_code, trade_date DESC
        """
        )

        start_date = pd.to_datetime(trade_date) - pd.Timedelta(days=lookback_days)
        price_result = self.db.execute(
            price_query, {"ts_codes": ts_codes, "trade_date": trade_date, "start_date": start_date}
        )
        price_df = pd.DataFrame(price_result.fetchall(), columns=price_result.keys())

        # 转换Decimal类型为float
        for col in price_df.select_dtypes(include=['object']).columns:
            try:
                price_df[col] = pd.to_numeric(price_df[col], errors='ignore')
            except:
                pass

        # 2. 获取财务数据 - 只查询需要的字段，避免加载所有列
        financial_query = text(
            """
            SELECT ts_code, ann_date, end_date,
                   total_revenue, operating_revenue, operating_cost, gross_profit,
                   total_profit, net_profit, deduct_net_profit,
                   total_assets, total_liabilities, total_equity,
                   current_assets, current_liabilities,
                   operating_cash_flow, goodwill,
                   roe, roa, gross_profit_margin, net_profit_margin, debt_to_assets,
                   total_market_cap, circ_market_cap, pe_ttm, pb, ps_ttm,
                   revenue_ttm, net_profit_ttm, ocf_ttm,
                   revenue_yoy, net_profit_yoy
            FROM stock_financial
            WHERE ts_code = ANY(:ts_codes)
                AND ann_date <= :trade_date
                AND ann_date >= :start_date
            ORDER BY ts_code, ann_date DESC
        """
        )

        financial_result = self.db.execute(
            financial_query,
            {"ts_codes": ts_codes, "trade_date": trade_date, "start_date": start_date},
        )
        financial_df = pd.DataFrame(financial_result.fetchall(), columns=financial_result.keys())

        # 转换Decimal类型为float
        for col in financial_df.select_dtypes(include=['object']).columns:
            try:
                financial_df[col] = pd.to_numeric(financial_df[col], errors='ignore')
            except:
                pass

        # 过滤：只保留目标股票池的数据
        if not financial_df.empty and 'ts_code' in financial_df.columns:
            financial_df = financial_df[financial_df['ts_code'].isin(ts_codes)]

        # 3. 计算各组因子
        all_factors = []

        for group_key in self.factor_groups:
            if group_key not in FACTOR_GROUPS:
                logger.warning(f"Unknown factor group: {group_key}")
                continue

            try:
                if group_key in ["valuation", "quality", "growth"]:
                    # 财务因子
                    if not financial_df.empty:
                        method = getattr(self.calculator, f"calc_{group_key}_factors")
                        factors = method(financial_df, trade_date)
                        all_factors.append(factors)

                elif group_key in ["momentum", "volatility", "liquidity"]:
                    # 价格因子
                    if not price_df.empty:
                        method = getattr(self.calculator, f"calc_{group_key}_factors")
                        factors = method(price_df)
                        all_factors.append(factors)

                else:
                    # 其他因子组
                    if hasattr(self.calculator, f"calc_{group_key}_factors"):
                        method = getattr(self.calculator, f"calc_{group_key}_factors")
                        # 根据因子组类型传入不同的数据
                        # 这里需要根据具体因子组的需求来调整
                        pass

            except Exception as e:
                logger.error(f"Error calculating {group_key} factors: {e}", exc_info=True)

        # 4. 合并所有因子
        if not all_factors:
            logger.warning("No factors calculated")
            return pd.DataFrame()

        # 使用 security_id 作为合并键
        result_df = all_factors[0]
        for df in all_factors[1:]:
            result_df = result_df.merge(df, on="security_id", how="outer")

        # 重命名 security_id 为 ts_code
        result_df = result_df.rename(columns={"security_id": "ts_code"})

        # 过滤：只保留目标股票池的股票
        result_df = result_df[result_df['ts_code'].isin(ts_codes)]

        # 去重：每个股票只保留一条记录（取第一条，因为FactorCalculator已经按日期排序）
        result_df = result_df.drop_duplicates(subset=['ts_code'], keep='first')

        # 转换所有数值列为float类型，避免Decimal类型问题
        for col in result_df.columns:
            if col != 'ts_code':
                result_df[col] = pd.to_numeric(result_df[col], errors='coerce')

        logger.info(f"Calculated {len(result_df.columns)-1} factors for {len(result_df)} stocks")

        # 清理内存
        del price_df, financial_df, all_factors
        import gc
        gc.collect()

        return result_df

    def preprocess_factors(
        self, factor_df: pd.DataFrame, industry_df: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """
        因子预处理

        Args:
            factor_df: 因子数据，columns: ts_code, factor1, factor2, ...
            industry_df: 行业数据，columns: ts_code, industry

        Returns:
            预处理后的因子数据
        """
        logger.info(f"Preprocessing {len(factor_df.columns)-1} factors")

        result_df = factor_df.copy()
        factor_cols = [col for col in result_df.columns if col != "ts_code"]

        # 确保所有因子列都是float类型
        for col in factor_cols:
            result_df[col] = pd.to_numeric(result_df[col], errors='coerce')

        # 1. 去极值
        for col in factor_cols:
            result_df[col] = self.preprocessor.winsorize_mad(result_df[col], n_mad=3)

        # 2. 标准化
        for col in factor_cols:
            result_df[col] = self.preprocessor.standardize_zscore(result_df[col])

        # 3. 行业中性化
        if self.neutralize_industry and industry_df is not None:
            result_df = result_df.merge(industry_df, on="ts_code", how="left")
            for col in factor_cols:
                result_df[col] = self.preprocessor.neutralize_industry(
                    result_df, value_col=col, industry_col="industry"
                )
            result_df = result_df.drop(columns=["industry"])

        # 4. 市值中性化
        if self.neutralize_market_cap:
            # 需要获取市值数据
            pass

        logger.info("Factor preprocessing completed")
        return result_df

    def composite_factors(
        self, factor_df: pd.DataFrame, factor_weights: dict[str, float] | None = None
    ) -> pd.DataFrame:
        """
        因子合成

        Args:
            factor_df: 预处理后的因子数据
            factor_weights: 因子权重字典，None表示等权重

        Returns:
            DataFrame with columns: ts_code, composite_score
        """
        logger.info(f"Compositing factors using {self.weighting_method} method")

        factor_cols = [col for col in factor_df.columns if col != "ts_code"]

        if self.weighting_method == FactorWeightingMethod.EQUAL:
            # 等权重合成
            weights = {col: 1.0 / len(factor_cols) for col in factor_cols}

        elif self.weighting_method == FactorWeightingMethod.IC:
            # IC加权（需要历史IC数据）
            if factor_weights is None:
                logger.warning("IC weights not provided, using equal weights")
                weights = {col: 1.0 / len(factor_cols) for col in factor_cols}
            else:
                weights = factor_weights

        elif self.weighting_method == FactorWeightingMethod.IR:
            # IR加权（需要历史IR数据）
            if factor_weights is None:
                logger.warning("IR weights not provided, using equal weights")
                weights = {col: 1.0 / len(factor_cols) for col in factor_cols}
            else:
                weights = factor_weights

        else:
            # 默认等权重
            weights = {col: 1.0 / len(factor_cols) for col in factor_cols}

        # 应用因子方向
        for col in factor_cols:
            direction = FACTOR_DIRECTIONS.get(col, 1)
            factor_df[col] = factor_df[col] * direction

        # 计算综合得分
        composite_score = pd.Series(0.0, index=factor_df.index)
        for col, weight in weights.items():
            if col in factor_df.columns:
                composite_score += factor_df[col].fillna(0) * weight

        result_df = pd.DataFrame({"ts_code": factor_df["ts_code"], "composite_score": composite_score})

        logger.info(f"Composite score calculated for {len(result_df)} stocks")
        return result_df

    def select_stocks(
        self, composite_df: pd.DataFrame, top_n: int = 60, exclude_list: list[str] | None = None
    ) -> pd.DataFrame:
        """
        选股

        Args:
            composite_df: 综合得分数据
            top_n: 选择前N只股票
            exclude_list: 排除列表（ST、停牌等）

        Returns:
            DataFrame with columns: ts_code, composite_score, rank
        """
        logger.info(f"Selecting top {top_n} stocks")

        # 排除黑名单
        if exclude_list:
            composite_df = composite_df[~composite_df["ts_code"].isin(exclude_list)]

        # 按综合得分排序
        composite_df = composite_df.sort_values("composite_score", ascending=False)

        # 添加排名
        composite_df["rank"] = range(1, len(composite_df) + 1)

        # 选择前N只
        selected_df = composite_df.head(top_n).copy()

        logger.info(f"Selected {len(selected_df)} stocks")
        return selected_df

    def build_portfolio(
        self,
        selected_df: pd.DataFrame,
        total_value: float,
        trade_date: date,
        current_holdings: dict[str, float] | None = None,
        mode: PortfolioMode = PortfolioMode.PRODUCTION,
    ) -> dict[str, Any]:
        """
        构建投资组合

        Args:
            selected_df: 选中的股票及得分
            total_value: 总资产
            trade_date: 交易日期
            current_holdings: 当前持仓 {ts_code: shares}
            mode: 组合构建模式

        Returns:
            组合信息字典
        """
        logger.info(f"Building portfolio with mode={mode}, total_value={total_value}")

        # 获取价格数据
        from sqlalchemy import text

        ts_codes_list = selected_df["ts_code"].tolist()
        price_query = text("""
            SELECT DISTINCT ON (ts_code) ts_code, close as price
            FROM stock_daily
            WHERE ts_code = ANY(:ts_codes)
                AND trade_date <= :trade_date
            ORDER BY ts_code, trade_date DESC
        """)

        price_result = self.db.execute(
            price_query,
            {"ts_codes": ts_codes_list, "trade_date": trade_date}
        )
        price_data = {row[0]: float(row[1]) for row in price_result.fetchall()}
        prices = pd.Series(price_data)

        # 准备数据 - PortfolioBuilder.build() 需要 pd.Series
        scores = selected_df.set_index("ts_code")["composite_score"]

        # 使用 PortfolioBuilder 构建组合
        portfolio_df = self.portfolio_builder.build(
            scores=scores,
            mode=mode,
            total_capital=total_value,
            prices=prices,  # 传递价格数据
            current_holdings=None,
        )

        # 转换为原有格式 - 将权重转换为股数
        target_holdings = {}
        trades = []

        for _, row in portfolio_df.iterrows():
            ts_code = row["ts_code"]
            weight = row["weight"]
            price = prices.get(ts_code, 0)

            if price > 0:
                # 计算目标股数（100股整数倍）
                target_value = total_value * weight
                shares = int(target_value / price)
                shares = (shares // 100) * 100  # 向下取整到100股整数倍

                if shares > 0:
                    target_holdings[ts_code] = shares
                    trades.append({
                        "ts_code": ts_code,
                        "action": "buy",
                        "shares": shares,
                        "price": price,
                        "value": shares * price,
                    })

        portfolio = {
            "target_holdings": target_holdings,
            "trades": trades,
            "portfolio_df": portfolio_df,
        }

        logger.info(f"Portfolio built with {len(portfolio['target_holdings'])} positions")
        return portfolio

    def run(
        self,
        ts_codes: list[str],
        trade_date: date,
        total_value: float,
        current_holdings: dict[str, float] | None = None,
        top_n: int = 60,
        exclude_list: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        运行完整的多因子选股流程

        Args:
            ts_codes: 股票池
            trade_date: 交易日期
            total_value: 总资产
            current_holdings: 当前持仓
            top_n: 选择前N只股票
            exclude_list: 排除列表

        Returns:
            包含组合信息的字典
        """
        logger.info(f"Running multi-factor model on {trade_date} for {len(ts_codes)} stocks")

        # 1. 计算因子
        factor_df = self.calculate_factors(ts_codes, trade_date)

        if factor_df.empty:
            logger.warning("No factors calculated, returning empty portfolio")
            return {"target_holdings": {}, "trades": []}

        # 2. 预处理因子
        processed_df = self.preprocess_factors(factor_df)

        # 3. 合成因子
        composite_df = self.composite_factors(processed_df)

        # 4. 选股
        selected_df = self.select_stocks(composite_df, top_n=top_n, exclude_list=exclude_list)

        # 5. 构建组合
        portfolio = self.build_portfolio(selected_df, total_value, trade_date, current_holdings)

        logger.info("Multi-factor model run completed")
        return portfolio
