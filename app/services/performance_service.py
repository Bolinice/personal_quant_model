from sqlalchemy.orm import Session
from app.db.base import with_db
from app.models.backtests import BacktestResult, BacktestTrade
from app.models.simulated_portfolios import SimulatedPortfolio, SimulatedPortfolioNav, SimulatedPortfolioPosition
from app.models.securities import Security
from app.schemas.performance import PerformanceCreate
import pandas as pd
import numpy as np
from datetime import datetime

@with_db
def get_performance_analysis(backtest_id: int, start_date: str = None, end_date: str = None, db: Session = None):
    """获取绩效分析结果"""
    # 获取回测结果
    result = db.query(BacktestResult).filter(BacktestResult.backtest_id == backtest_id).first()
    if not result:
        return None

    # 获取交易记录
    trades = db.query(BacktestTrade).filter(BacktestTrade.backtest_id == backtest_id).all()

    # 获取净值历史
    navs = db.query(SimulatedPortfolioNav).filter(
        SimulatedPortfolioNav.portfolio_id == backtest_id,
        SimulatedPortfolioNav.trade_date >= start_date if start_date else "1900-01-01",
        SimulatedPortfolioNav.trade_date <= end_date if end_date else datetime.now().strftime("%Y-%m-%d")
    ).all()

    # 转换为DataFrame
    nav_df = pd.DataFrame([(n.trade_date, n.nav) for n in navs], columns=['date', 'nav'])

    # 计算绩效指标
    analysis = calculate_performance_metrics(nav_df, result)

    return analysis

def calculate_performance_metrics(nav_df, result):
    """计算绩效指标"""
    if nav_df.empty:
        return None

    # 计算收益率
    nav_df['return'] = nav_df['nav'].pct_change()

    # 计算累计收益率
    nav_df['cum_return'] = (nav_df['nav'] / nav_df['nav'].iloc[0] - 1)

    # 计算年化收益率
    total_days = (nav_df['date'].max() - nav_df['date'].min()).days
    annual_return = (nav_df['nav'].iloc[-1] / nav_df['nav'].iloc[0]) ** (252 / total_days) - 1

    # 计算最大回撤
    nav_df['drawdown'] = nav_df['nav'] / nav_df['nav'].cummax() - 1
    max_drawdown = nav_df['drawdown'].min()

    # 计算夏普比率
    sharpe = nav_df['return'].mean() / nav_df['return'].std() * np.sqrt(252)

    # 计算卡玛比率
    calmar = annual_return / abs(max_drawdown)

    # 计算信息比率
    information_ratio = result.information_ratio if result.information_ratio else 0.0

    # 计算换手率
    turnover_rate = result.turnover_rate if result.turnover_rate else 0.0

    # 计算月度收益率
    nav_df['month'] = nav_df['date'].dt.to_period('M')
    monthly_returns = nav_df.groupby('month')['nav'].last().pct_change()

    # 计算胜率
    positive_returns = nav_df[nav_df['return'] > 0].shape[0]
    total_returns = nav_df['return'].count()
    win_rate = positive_returns / total_returns if total_returns > 0 else 0

    return PerformanceAnalysis(
        metrics=PerformanceMetrics(
            total_return=result.total_return,
            annual_return=annual_return,
            benchmark_return=result.benchmark_return,
            excess_return=result.excess_return,
            max_drawdown=max_drawdown,
            sharpe=sharpe,
            calmar=calmar,
            information_ratio=information_ratio,
            turnover_rate=turnover_rate,
            win_rate=win_rate
        ),
        monthly_returns=monthly_returns.to_dict(),
        performance_chart=PerformanceChart(
            dates=[d.strftime('%Y-%m-%d') for d in nav_df['date']],
            nav=nav_df['nav'].tolist(),
            cum_return=nav_df['cum_return'].tolist(),
            drawdown=nav_df['drawdown'].tolist()
        ),
        industry_exposure=[],
        style_exposure=StyleExposure(
            market_cap=0.0,
            value=0.0,
            growth=0.0
        )
    )

@with_db
def get_industry_exposure(portfolio_id: int, date: str, db: Session = None):
    """获取行业暴露分析"""
    # 获取持仓
    positions = db.query(SimulatedPortfolioPosition).filter(
        SimulatedPortfolioPosition.portfolio_id == portfolio_id,
        SimulatedPortfolioPosition.trade_date == date
    ).all()

    if not positions:
        return None

    # 获取行业数据
    industry_exposure = {}
    for position in positions:
        # 获取股票基本信息
        security = db.query(Security).filter(
            Security.id == position.security_id,
            Security.list_date <= date
        ).first()

        if security:
            industry_name = security.industry_name
            weight = position.weight
            industry_exposure[industry_name] = industry_exposure.get(industry_name, 0) + weight

    return industry_exposure

@with_db
def get_style_exposure(portfolio_id: int, date: str, db: Session = None):
    """获取风格暴露分析"""
    # 获取持仓
    positions = db.query(SimulatedPortfolioPosition).filter(
        SimulatedPortfolioPosition.portfolio_id == portfolio_id,
        SimulatedPortfolioPosition.trade_date == date
    ).all()

    if not positions:
        return None

    # 计算市值暴露
    market_cap_exposure = 0
    for position in positions:
        # 获取股票基本信息
        security = db.query(Security).filter(
            Security.id == position.security_id
        ).first()

        if security:
            # 简单的市值分类
            if security.board == "主板":
                market_cap_exposure += position.weight * 0.3
            elif security.board == "创业板":
                market_cap_exposure += position.weight * 0.5
            elif security.board == "科创板":
                market_cap_exposure += position.weight * 0.7

    return {
        'market_cap': market_cap_exposure,
        'value': 0.0,  # 估值暴露
        'growth': 0.0   # 成长暴露
    }

def generate_performance_report(analysis: PerformanceAnalysis):
    """生成绩效报告"""
    report = PerformanceReport(
        summary={
            'total_return': f"{analysis.metrics.total_return:.2%}",
            'annual_return': f"{analysis.metrics.annual_return:.2%}",
            'max_drawdown': f"{analysis.metrics.max_drawdown:.2%}",
            'sharpe': f"{analysis.metrics.sharpe:.2f}",
            'calmar': f"{analysis.metrics.calmar:.2f}"
        },
        charts=analysis.performance_chart,
        monthly_returns={k: f"{v:.2%}" for k, v in analysis.monthly_returns.items()},
        industry_exposure=analysis.industry_exposure,
        style_exposure=analysis.style_exposure
    )

    return report