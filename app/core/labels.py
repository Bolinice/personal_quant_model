"""
超额收益标签构建模块
实现GPT设计4.2-4.3节: 预测超额收益而非原始收益
避免模型押beta/行业/小盘/高波动等风格beta
支持: 超额收益(相对基准)、行业中性收益、多周期标签
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class LabelBuilder:
    """标签构建器 - GPT设计4.2-4.3节"""

    def __init__(self):
        pass

    # ==================== 标签1: 超额收益 ====================

    def excess_return(
        self,
        price_df: pd.DataFrame,
        benchmark_df: pd.DataFrame = None,
        benchmark_col: str = "close",
        horizon: int = 5,  # 默认5日: 与周度调仓周期对齐
        code_col: str = "ts_code",
        date_col: str = "trade_date",
        price_col: str = "close",
        exclude_codes: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        标签1: 未来k日超额收益 = r_stock - r_benchmark

        GPT设计4.2节: 预测超额收益而非原始收益，避免模型只是押指数beta

        Args:
            price_df: 股票行情, 需含 ts_code/trade_date/close
            benchmark_df: 基准行情(如沪深300), 需含 trade_date/close
            benchmark_col: 基准价格列名
            horizon: 预测周期(交易日数)
            code_col: 股票代码列名
            date_col: 日期列名
            price_col: 价格列名
            exclude_codes: 当无外部基准时, 计算全市场平均收益需排除的股票代码列表。
                用于避免循环依赖: 若被评估的股票自身也参与基准计算, 超额收益
                会被系统性拉低。典型用法: 传入当前持仓/待评估股票列表, 使基准
                仅由非持仓股票构成。

        Returns:
            DataFrame: [ts_code, trade_date, fwd_return, benchmark_return, excess_return]
        """
        # 计算股票前瞻收益
        stock_fwd = self._calc_forward_returns(price_df, horizon, code_col, date_col, price_col)

        if stock_fwd.empty:
            return pd.DataFrame()

        # 计算基准前瞻收益
        if benchmark_df is not None and not benchmark_df.empty:
            bench_fwd = self._calc_benchmark_forward_returns(benchmark_df, horizon, date_col, benchmark_col)
            # 合并: 每只股票的excess_return = stock_fwd - benchmark_fwd
            # 超额收益而非原始收益: 避免模型学习到市场beta而非选股alpha
            merged = pd.merge(stock_fwd, bench_fwd, on=date_col, how="left", suffixes=("", "_bench"))
            merged["excess_return"] = merged["fwd_return"] - merged["benchmark_fwd_return"]
            # 基准缺失时: 超额收益设为0而非原始收益
            # 原始收益包含市场beta, 用它回退会重新引入市场暴露偏差
            merged["benchmark_fwd_return"] = merged["benchmark_fwd_return"].fillna(0.0)
            merged["excess_return"] = merged["excess_return"].fillna(0.0)
        else:
            # 无基准时, 用全市场平均收益作为基准
            # 排除指定股票, 避免被评估股票自身参与基准计算导致循环依赖
            # 循环依赖: 若股票i也是基准成分, 则超额收益被自身拉低, 导致标签有偏
            merged = stock_fwd.copy()
            bench_pool = merged[~merged[code_col].isin(exclude_codes)] if exclude_codes else merged
            # 注意: 若排除后无可用股票, 退回全市场平均(并记录警告)
            if bench_pool.empty:
                from app.core.logging import logger as _logger

                _logger.warning(
                    "exclude_codes 排除了所有股票, 退回全市场平均作为基准; "
                    "这可能引入循环依赖, 建议提供 benchmark_df 或缩小 exclude_codes"
                )
                bench_pool = merged
            market_avg = bench_pool.groupby(date_col)["fwd_return"].mean()
            merged["benchmark_fwd_return"] = merged[date_col].map(market_avg)
            merged["excess_return"] = merged["fwd_return"] - merged["benchmark_fwd_return"]

        return merged

    # ==================== 标签2: 行业中性收益 ====================

    def industry_neutral_return(
        self,
        price_df: pd.DataFrame,
        industry_df: pd.DataFrame = None,
        horizon: int = 10,  # 默认10日: 行业轮动偏中期, 5日噪声太大
        code_col: str = "ts_code",
        date_col: str = "trade_date",
        price_col: str = "close",
        industry_col: str = "industry",
    ) -> pd.DataFrame:
        """
        标签2: 未来k日行业中性收益 = r_stock - r_industry

        GPT设计4.2节: 行业中性后，alpha才是真正的选股能力而非行业轮动

        Args:
            price_df: 股票行情
            industry_df: 行业映射, 需含 ts_code/industry
            horizon: 预测周期
            industry_col: 行业列名

        Returns:
            DataFrame: [ts_code, trade_date, fwd_return, industry_return, industry_neutral_return]
        """
        stock_fwd = self._calc_forward_returns(price_df, horizon, code_col, date_col, price_col)

        if stock_fwd.empty:
            return pd.DataFrame()

        if industry_df is None or industry_df.empty:
            # 无行业数据时, 用全市场平均 (退而求其次, 仍有beta对冲效果)
            merged = stock_fwd.copy()
            market_avg = merged.groupby(date_col)["fwd_return"].mean()
            merged["industry_return"] = merged[date_col].map(market_avg)
            merged["industry_neutral_return"] = merged["fwd_return"] - merged["industry_return"]
            return merged

        # 合并行业信息
        merged = pd.merge(stock_fwd, industry_df[[code_col, industry_col]], on=code_col, how="left")

        # 计算行业平均收益
        industry_avg = merged.groupby([date_col, industry_col])["fwd_return"].mean()
        industry_avg_df = industry_avg.reset_index()
        industry_avg_df.columns = [date_col, industry_col, "industry_return"]

        merged = pd.merge(merged, industry_avg_df, on=[date_col, industry_col], how="left")

        merged["industry_neutral_return"] = merged["fwd_return"] - merged["industry_return"]
        # 无行业归属的股票: 中性收益设为0而非原始收益
        # 原始收益包含行业beta, 用它回退会重新引入行业暴露偏差
        merged["industry_neutral_return"] = merged["industry_neutral_return"].fillna(0.0)

        return merged

    # ==================== 标签3: 风格调整后收益 ====================

    def style_adjusted_return(
        self,
        price_df: pd.DataFrame,
        style_exposures: pd.DataFrame = None,
        horizon: int = 20,  # 默认20日: 风格因子暴露衰减慢, 需更长周期才能观测纯alpha
        code_col: str = "ts_code",
        date_col: str = "trade_date",
        price_col: str = "close",
        style_cols: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        标签3: 未来k日风格调整后收益

        GPT设计4.2节: 适合更慢的基本面模块，去除size/beta/volatility等风格暴露

        Args:
            style_exposures: 风格暴露 DataFrame, 需含 ts_code + 风格列
            style_cols: 用于调整的风格列 (如 ['size', 'beta', 'residual_volatility'])

        Returns:
            DataFrame: [ts_code, trade_date, fwd_return, style_adjusted_return]
        """
        stock_fwd = self._calc_forward_returns(price_df, horizon, code_col, date_col, price_col)

        if stock_fwd.empty or style_exposures is None or style_exposures.empty:
            return stock_fwd

        if style_cols is None:
            style_cols = ["size", "beta", "residual_volatility"]
            # size: 去除小盘效应; beta: 去除市场暴露; residual_vol: 去除低波动异象

        available_cols = [c for c in style_cols if c in style_exposures.columns]
        if not available_cols:
            return stock_fwd

        # 截面回归: fwd_return = α + Σ β_k * style_k + ε
        merged = pd.merge(stock_fwd, style_exposures[[code_col, *available_cols]], on=code_col, how="left")

        # 对每个交易日做截面回归取残差
        # 残差即为剥离风格后的纯alpha, 截面回归而非时间序列: 每天独立回归避免未来函数
        result_parts = []
        for _dt, group in merged.groupby(date_col):
            group = group.copy()  # 避免SettingWithCopyWarning
            valid = group.dropna(subset=["fwd_return", *available_cols])
            # 样本量阈值: k个风格因子+1个截距, 至少需要3倍参数量+10个额外样本
            min_samples = max(3 * (len(available_cols) + 1), len(available_cols) + 11)
            if len(valid) < min_samples:
                # 样本不足时退回原始收益, 避免回归系数不稳定
                group["style_adjusted_return"] = group["fwd_return"]
                result_parts.append(group)
                continue

            y = valid["fwd_return"].values
            X = valid[available_cols].values
            X_with_const = np.column_stack([np.ones(len(y)), X])

            try:
                beta = np.linalg.lstsq(X_with_const, y, rcond=None)[0]
                predicted = X_with_const @ beta
                residuals = y - predicted
                valid_idx = valid.index
                group.loc[valid_idx, "style_adjusted_return"] = residuals
                # 无风格暴露的股票: 设为0而非原始收益, 避免重新引入风格暴露
                group["style_adjusted_return"] = group["style_adjusted_return"].fillna(0.0)
            except np.linalg.LinAlgError:
                group["style_adjusted_return"] = group["fwd_return"]

            result_parts.append(group)

        if not result_parts:
            return stock_fwd

        return pd.concat(result_parts, ignore_index=True)

    # ==================== 多周期标签 ====================

    def multi_horizon_labels(
        self,
        price_df: pd.DataFrame,
        benchmark_df: pd.DataFrame = None,
        horizons: list[int] | None = None,
        code_col: str = "ts_code",
        date_col: str = "trade_date",
        price_col: str = "close",
        exclude_codes: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        多周期标签 (GPT设计16.3节)

        同时计算5d/10d/20d三个周期的超额收益标签，
        后续可做horizon ensemble — 短周期捕捉快速反转, 长周期捕捉趋势持续

        Args:
            horizons: 预测周期列表
            exclude_codes: 当无外部基准时, 计算全市场平均收益需排除的股票代码列表

        Returns:
            DataFrame: [ts_code, trade_date, excess_5d, excess_10d, excess_20d, ...]
        """
        if horizons is None:
            horizons = [5, 10, 20]
        results = {}
        for h in horizons:
            label_df = self.excess_return(
                price_df,
                benchmark_df,
                horizon=h,
                code_col=code_col,
                date_col=date_col,
                price_col=price_col,
                exclude_codes=exclude_codes,
            )
            if not label_df.empty:
                # 只保留关键列
                key_cols = [code_col, date_col, "excess_return"]
                available = [c for c in key_cols if c in label_df.columns]
                results[h] = label_df[available].rename(
                    columns={"excess_return": f"excess_{h}d", "fwd_return": f"fwd_{h}d"}
                )

        if not results:
            return pd.DataFrame()

        # 合并各周期
        merged = None
        for df in results.values():
            merged = df if merged is None else pd.merge(merged, df, on=[code_col, date_col], how="outer")

        return merged

    # ==================== 辅助方法 ====================

    def _calc_forward_returns(
        self,
        price_df: pd.DataFrame,
        horizon: int,
        code_col: str = "ts_code",
        date_col: str = "trade_date",
        price_col: str = "close",
    ) -> pd.DataFrame:
        """
        计算前瞻收益 (向量化: groupby.shift替代逐股票循环)

        优先使用复权价格(adj_close/adj_price), 避免除权除息扭曲收益
        无复权价时回退到close, 但此时标签可能受除权除息影响

        fwd_return = price_{t+h} / price_t - 1

        PIT安全: 仅使用trade_date <= 当前日期的数据
        """
        if price_df.empty:
            return pd.DataFrame()

        # 优先使用复权价: 除权除息会导致原始收盘价跳空, 扭曲前瞻收益
        # 例如10送10后价格腰斩, 用原始close会显示-50%收益(纯除权, 非真实亏损)
        actual_price_col = price_col
        for adj_col in ["adj_close", "adj_price", "close_adj"]:
            if adj_col in price_df.columns:
                actual_price_col = adj_col
                break

        if actual_price_col not in price_df.columns:
            return pd.DataFrame()

        df = price_df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        # 去重: 同一 (ts_code, trade_date) 可能存在多条记录(数据质量问题),
        # 保留最后一条(通常为修正后的数据)
        df = df.drop_duplicates(subset=[code_col, date_col], keep="last")

        df = df.sort_values([code_col, date_col])

        # 向量化计算: 按股票分组shift
        grouped = df.groupby(code_col)
        fwd_price = grouped[actual_price_col].shift(-horizon)
        df["fwd_return"] = fwd_price / df[actual_price_col] - 1

        # 清理: 去掉最后horizon个交易日(没有完整前瞻数据)
        # 这是标签构造的关键边界: 未来数据不足的样本必须剔除, 否则引入存活偏差
        valid = df.dropna(subset=["fwd_return"])

        if valid.empty:
            return pd.DataFrame()

        return valid[[code_col, date_col, "fwd_return"]].reset_index(drop=True)

    def _calc_benchmark_forward_returns(
        self, benchmark_df: pd.DataFrame, horizon: int, date_col: str = "trade_date", price_col: str = "close"
    ) -> pd.DataFrame:
        """计算基准前瞻收益"""
        if benchmark_df.empty or price_col not in benchmark_df.columns:
            return pd.DataFrame()

        df = benchmark_df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.sort_values(date_col)

        fwd_price = df[price_col].shift(-horizon)
        df["benchmark_fwd_return"] = fwd_price / df[price_col] - 1

        valid = df.dropna(subset=["benchmark_fwd_return"])
        if valid.empty:
            return pd.DataFrame()

        return valid[[date_col, "benchmark_fwd_return"]].reset_index(drop=True)
