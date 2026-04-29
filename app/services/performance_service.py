from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from app.db.base import with_db
from app.models.backtests import BacktestResult, BacktestTrade
from app.models.securities import Security
from app.models.simulated_portfolios import SimulatedPortfolioNav, SimulatedPortfolioPosition
from app.schemas.performance import PerformanceAnalysis, PerformanceReport

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@with_db
def get_performance_analysis(
    backtest_id: int, start_date: str | None = None, end_date: str | None = None, db: Session | None = None
):
    """获取绩效分析结果"""
    # 获取回测结果
    result = db.query(BacktestResult).filter(BacktestResult.backtest_id == backtest_id).first()
    if not result:
        return None

    # 获取交易记录（用于扩展分析）
    _ = db.query(BacktestTrade).filter(BacktestTrade.backtest_id == backtest_id).all()

    # 获取净值历史
    navs = (
        db.query(SimulatedPortfolioNav)
        .filter(
            SimulatedPortfolioNav.portfolio_id == backtest_id,
            SimulatedPortfolioNav.trade_date >= start_date if start_date else "1900-01-01",
            SimulatedPortfolioNav.trade_date <= end_date if end_date else datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
        )
        .all()
    )

    # 转换为DataFrame
    nav_df = pd.DataFrame([(n.trade_date, n.nav) for n in navs], columns=["date", "nav"])

    # 计算绩效指标
    return calculate_performance_metrics(nav_df, result)


def calculate_performance_metrics(nav_df, result):
    """计算绩效指标"""
    if nav_df.empty:
        return None

    # 计算收益率
    nav_df["return"] = nav_df["nav"].pct_change()

    # 计算累计收益率
    nav_df["cum_return"] = nav_df["nav"] / nav_df["nav"].iloc[0] - 1

    # 计算年化收益率
    total_days = (nav_df["date"].max() - nav_df["date"].min()).days
    annual_return = (nav_df["nav"].iloc[-1] / nav_df["nav"].iloc[0]) ** (252 / total_days) - 1

    # 计算最大回撤
    nav_df["drawdown"] = nav_df["nav"] / nav_df["nav"].cummax() - 1
    max_drawdown = nav_df["drawdown"].min()

    # 计算夏普比率
    sharpe = nav_df["return"].mean() / nav_df["return"].std() * np.sqrt(252)

    # 计算卡玛比率
    calmar = annual_return / abs(max_drawdown)

    # 计算信息比率
    information_ratio = result.information_ratio or 0.0

    # 计算换手率
    turnover_rate = result.turnover_rate or 0.0

    # 计算月度收益率
    nav_df["month"] = nav_df["date"].dt.to_period("M")
    _ = nav_df.groupby("month")["nav"].last().pct_change()

    # 计算胜率
    positive_returns = nav_df[nav_df["return"] > 0].shape[0]
    total_returns = nav_df["return"].count()
    win_rate = positive_returns / total_returns if total_returns > 0 else 0

    return PerformanceAnalysis(
        total_return=result.total_return,
        annual_return=annual_return,
        benchmark_return=result.benchmark_return,
        excess_return=result.excess_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe,
        calmar_ratio=calmar,
        information_ratio=information_ratio,
        turnover_rate=turnover_rate,
        win_rate=win_rate,
    )


@with_db
def get_industry_exposure(portfolio_id: int, date: str, db: Session = None):
    """获取行业暴露分析"""
    # 获取持仓
    positions = (
        db.query(SimulatedPortfolioPosition)
        .filter(SimulatedPortfolioPosition.portfolio_id == portfolio_id, SimulatedPortfolioPosition.trade_date == date)
        .all()
    )

    if not positions:
        return None

    # 获取行业数据
    industry_exposure = {}
    for position in positions:
        # 获取股票基本信息
        security = db.query(Security).filter(Security.id == position.security_id, Security.list_date <= date).first()

        if security:
            industry_name = security.industry_name
            weight = position.weight
            industry_exposure[industry_name] = industry_exposure.get(industry_name, 0) + weight

    return industry_exposure


@with_db
def get_style_exposure(portfolio_id: int, date: str, db: Session = None):
    """获取风格暴露分析 — 使用 RiskModel 计算真实暴露"""
    import numpy as np

    from app.core.risk_model import RiskModel

    # 获取持仓
    positions = (
        db.query(SimulatedPortfolioPosition)
        .filter(SimulatedPortfolioPosition.portfolio_id == portfolio_id, SimulatedPortfolioPosition.trade_date == date)
        .all()
    )

    if not positions:
        return None

    # 构建持仓数据用于 Barra 因子暴露计算
    stock_data = pd.DataFrame(
        [
            {
                "security_id": p.security_id,
                "weight": p.weight,
            }
            for p in positions
        ]
    )

    # 尝试从 Security 获取市值和基本面数据
    for idx, row in stock_data.iterrows():
        security = db.query(Security).filter(Security.id == row["security_id"]).first()
        if security:
            stock_data.loc[idx, "total_market_cap"] = getattr(security, "total_market_cap", None)
            stock_data.loc[idx, "market_cap"] = getattr(security, "market_cap", None)
            stock_data.loc[idx, "bp"] = getattr(security, "bp", None)
            stock_data.loc[idx, "ep_ttm"] = getattr(security, "ep_ttm", None)

    # 用 RiskModel 计算 Barra 因子暴露
    risk_model = RiskModel()
    exposures = risk_model.barra_factor_exposure(stock_data)

    # 加权计算组合暴露
    result = {}
    if not exposures.empty:
        weights = stock_data["weight"].values
        for col in exposures.columns:
            vals = exposures[col].values
            # 加权平均
            valid = ~np.isnan(vals)
            if valid.any():
                result[col] = float(np.average(vals[valid], weights=weights[valid]))
            else:
                result[col] = 0.0

    # 确保返回标准格式
    return {
        "market_cap": result.get("size", 0.0),
        "value": result.get("book_to_price", 0.0),
        "growth": result.get("growth", 0.0),
        "momentum": result.get("momentum", 0.0),
        "volatility": result.get("residual_volatility", 0.0),
    }


def generate_performance_report(analysis: PerformanceAnalysis):
    """生成绩效报告"""
    return PerformanceReport(
        analysis=analysis,
        generated_at=datetime.now(tz=timezone.utc),
    )
