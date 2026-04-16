"""
绩效分析引擎
实现收益计算、风险指标、归因分析、报告生成
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, with_db
from app.models.backtests import BacktestResult
from app.models.simulated_portfolios import SimulatedPortfolioNav
from app.models.market import IndexDaily
from app.core.logging import logger


class PerformanceAnalyzer:
    """绩效分析器"""

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    # ==================== 收益指标 ====================

    def calc_total_return(self, nav_series: pd.Series) -> float:
        """计算总收益率"""
        if len(nav_series) < 2:
            return 0
        return nav_series.iloc[-1] / nav_series.iloc[0] - 1

    def calc_annual_return(self, nav_series: pd.Series, trading_days: int = 252) -> float:
        """计算年化收益率"""
        if len(nav_series) < 2:
            return 0

        total_return = self.calc_total_return(nav_series)
        total_days = len(nav_series)

        return (1 + total_return) ** (trading_days / total_days) - 1

    def calc_period_returns(self, nav_series: pd.Series, freq: str = 'M') -> pd.Series:
        """
        计算周期收益率

        Args:
            nav_series: 净值序列
            freq: 频率 ('D', 'W', 'M', 'Q', 'Y')

        Returns:
            周期收益率序列
        """
        returns = nav_series.pct_change()

        if freq == 'D':
            return returns
        elif freq == 'W':
            return (1 + returns).resample('W').prod() - 1
        elif freq == 'M':
            return (1 + returns).resample('M').prod() - 1
        elif freq == 'Q':
            return (1 + returns).resample('Q').prod() - 1
        elif freq == 'Y':
            return (1 + returns).resample('Y').prod() - 1

        return returns

    def calc_excess_return(self, strategy_return: float, benchmark_return: float) -> float:
        """计算超额收益"""
        return strategy_return - benchmark_return

    # ==================== 风险指标 ====================

    def calc_volatility(self, returns: pd.Series, annualize: bool = True) -> float:
        """计算波动率"""
        vol = returns.std()

        if annualize:
            vol *= np.sqrt(252)

        return vol

    def calc_downside_volatility(self, returns: pd.Series, target: float = 0,
                                 annualize: bool = True) -> float:
        """计算下行波动率"""
        downside_returns = returns[returns < target]
        vol = downside_returns.std()

        if annualize:
            vol *= np.sqrt(252)

        return vol

    def calc_max_drawdown(self, nav_series: pd.Series) -> Tuple[float, datetime, datetime]:
        """
        计算最大回撤

        Returns:
            (最大回撤, 开始日期, 结束日期)
        """
        cummax = nav_series.cummax()
        drawdown = (nav_series - cummax) / cummax

        max_dd = drawdown.min()
        end_idx = drawdown.idxmin()

        # 找到回撤开始点
        start_idx = nav_series[:end_idx].idxmax()

        return max_dd, start_idx, end_idx

    def calc_var(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """计算VaR（Value at Risk）"""
        return np.percentile(returns, (1 - confidence) * 100)

    def calc_cvar(self, returns: pd.Series, confidence: float = 0.95) -> float:
        """计算CVaR（Conditional VaR）"""
        var = self.calc_var(returns, confidence)
        return returns[returns <= var].mean()

    # ==================== 风险调整收益指标 ====================

    def calc_sharpe_ratio(self, returns: pd.Series, risk_free_rate: float = 0.03) -> float:
        """计算夏普比率"""
        excess_returns = returns - risk_free_rate / 252

        if excess_returns.std() == 0:
            return 0

        return excess_returns.mean() / excess_returns.std() * np.sqrt(252)

    def calc_sortino_ratio(self, returns: pd.Series, risk_free_rate: float = 0.03) -> float:
        """计算索提诺比率"""
        excess_returns = returns - risk_free_rate / 252
        downside_vol = self.calc_downside_volatility(returns)

        if downside_vol == 0:
            return 0

        return excess_returns.mean() * 252 / downside_vol

    def calc_calmar_ratio(self, annual_return: float, max_drawdown: float) -> float:
        """计算卡玛比率"""
        if max_drawdown == 0:
            return 0
        return annual_return / abs(max_drawdown)

    def calc_information_ratio(self, strategy_returns: pd.Series,
                               benchmark_returns: pd.Series) -> float:
        """计算信息比率"""
        excess_returns = strategy_returns - benchmark_returns

        if excess_returns.std() == 0:
            return 0

        return excess_returns.mean() / excess_returns.std() * np.sqrt(252)

    def calc_treynor_ratio(self, returns: pd.Series, beta: float,
                          risk_free_rate: float = 0.03) -> float:
        """计算特雷诺比率"""
        if beta == 0:
            return 0

        excess_return = returns.mean() * 252 - risk_free_rate
        return excess_return / beta

    # ==================== 其他指标 ====================

    def calc_win_rate(self, returns: pd.Series) -> float:
        """计算胜率"""
        positive_days = (returns > 0).sum()
        total_days = len(returns[returns != 0])

        if total_days == 0:
            return 0

        return positive_days / total_days

    def calc_profit_loss_ratio(self, returns: pd.Series) -> float:
        """计算盈亏比"""
        profits = returns[returns > 0]
        losses = returns[returns < 0]

        if len(losses) == 0:
            return float('inf')
        if len(profits) == 0:
            return 0

        return profits.mean() / abs(losses.mean())

    def calc_beta(self, strategy_returns: pd.Series,
                  benchmark_returns: pd.Series) -> float:
        """计算Beta"""
        covariance = strategy_returns.cov(benchmark_returns)
        variance = benchmark_returns.var()

        if variance == 0:
            return 0

        return covariance / variance

    def calc_alpha(self, strategy_return: float, benchmark_return: float,
                   beta: float, risk_free_rate: float = 0.03) -> float:
        """计算Alpha"""
        return strategy_return - (risk_free_rate + beta * (benchmark_return - risk_free_rate))

    # ==================== 归因分析 ====================

    def calc_industry_attribution(self, portfolio_weights: pd.DataFrame,
                                  industry_returns: pd.DataFrame) -> pd.DataFrame:
        """
        行业归因分析

        Args:
            portfolio_weights: 组合权重 (日期 x 行业)
            industry_returns: 行业收益率 (日期 x 行业)

        Returns:
            行业贡献
        """
        # 计算各行业贡献
        contribution = portfolio_weights * industry_returns

        # 汇总
        total_contribution = contribution.sum()

        return pd.DataFrame({
            'industry': total_contribution.index,
            'contribution': total_contribution.values
        })

    def calc_style_attribution(self, portfolio_exposures: pd.DataFrame,
                               style_returns: pd.DataFrame) -> pd.DataFrame:
        """
        风格归因分析

        Args:
            portfolio_exposures: 组合风格暴露 (日期 x 风格)
            style_returns: 风格收益率 (日期 x 风格)

        Returns:
            风格贡献
        """
        contribution = portfolio_exposures * style_returns
        total_contribution = contribution.sum()

        return pd.DataFrame({
            'style': total_contribution.index,
            'contribution': total_contribution.values
        })

    # ==================== 完整绩效分析 ====================

    def analyze_performance(self, nav_series: pd.Series,
                           benchmark_nav: pd.Series = None,
                           risk_free_rate: float = 0.03) -> Dict:
        """
        完整绩效分析

        Args:
            nav_series: 策略净值序列
            benchmark_nav: 基准净值序列
            risk_free_rate: 无风险利率

        Returns:
            绩效分析结果
        """
        # 计算收益率
        returns = nav_series.pct_change().dropna()

        # 基本收益指标
        total_return = self.calc_total_return(nav_series)
        annual_return = self.calc_annual_return(nav_series)

        # 风险指标
        volatility = self.calc_volatility(returns)
        max_dd, dd_start, dd_end = self.calc_max_drawdown(nav_series)
        downside_vol = self.calc_downside_volatility(returns)

        # 风险调整收益
        sharpe = self.calc_sharpe_ratio(returns, risk_free_rate)
        sortino = self.calc_sortino_ratio(returns, risk_free_rate)
        calmar = self.calc_calmar_ratio(annual_return, max_dd)

        # 其他指标
        win_rate = self.calc_win_rate(returns)
        pl_ratio = self.calc_profit_loss_ratio(returns)

        result = {
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'max_drawdown': max_dd,
            'max_drawdown_start': dd_start,
            'max_drawdown_end': dd_end,
            'downside_volatility': downside_vol,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'win_rate': win_rate,
            'profit_loss_ratio': pl_ratio,
            'var_95': self.calc_var(returns, 0.95),
            'cvar_95': self.calc_cvar(returns, 0.95),
        }

        # 如果有基准数据
        if benchmark_nav is not None and len(benchmark_nav) > 0:
            benchmark_returns = benchmark_nav.pct_change().dropna()

            # 对齐数据
            common_index = returns.index.intersection(benchmark_returns.index)
            aligned_returns = returns.loc[common_index]
            aligned_benchmark = benchmark_returns.loc[common_index]

            if len(common_index) > 0:
                benchmark_total_return = self.calc_total_return(benchmark_nav)
                benchmark_annual_return = self.calc_annual_return(benchmark_nav)

                beta = self.calc_beta(aligned_returns, aligned_benchmark)
                alpha = self.calc_alpha(annual_return, benchmark_annual_return, beta, risk_free_rate)
                info_ratio = self.calc_information_ratio(aligned_returns, aligned_benchmark)

                result.update({
                    'benchmark_return': benchmark_annual_return,
                    'excess_return': annual_return - benchmark_annual_return,
                    'alpha': alpha,
                    'beta': beta,
                    'information_ratio': info_ratio,
                    'treynor_ratio': self.calc_treynor_ratio(returns, beta, risk_free_rate),
                })

        return result

    def generate_report(self, nav_series: pd.Series,
                       benchmark_nav: pd.Series = None,
                       title: str = "绩效分析报告") -> Dict:
        """
        生成完整报告

        Args:
            nav_series: 策略净值
            benchmark_nav: 基准净值
            title: 报告标题

        Returns:
            报告数据
        """
        # 绩效指标
        metrics = self.analyze_performance(nav_series, benchmark_nav)

        # 月度收益
        monthly_returns = self.calc_period_returns(nav_series, 'M')

        # 年度收益
        yearly_returns = self.calc_period_returns(nav_series, 'Y')

        # 回撤分析
        cummax = nav_series.cummax()
        drawdown = (nav_series - cummax) / cummax

        # 净值曲线数据
        nav_data = pd.DataFrame({
            'date': nav_series.index,
            'nav': nav_series.values,
            'cummax': cummax.values,
            'drawdown': drawdown.values
        })

        return {
            'title': title,
            'generated_at': datetime.now(),
            'metrics': metrics,
            'monthly_returns': monthly_returns.to_dict(),
            'yearly_returns': yearly_returns.to_dict(),
            'nav_data': nav_data.to_dict('records'),
            'summary': self._generate_summary(metrics)
        }

    def _generate_summary(self, metrics: Dict) -> str:
        """生成文字摘要"""
        summary = f"""
        策略年化收益率为 {metrics['annual_return']:.2%}，
        年化波动率为 {metrics['volatility']:.2%}，
        最大回撤为 {metrics['max_drawdown']:.2%}，
        夏普比率为 {metrics['sharpe_ratio']:.2f}，
        卡玛比率为 {metrics['calmar_ratio']:.2f}。
        """

        if 'excess_return' in metrics:
            summary += f"\n        相对基准超额收益为 {metrics['excess_return']:.2%}，信息比率为 {metrics['information_ratio']:.2f}。"

        return summary.strip()

    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()


@with_db
def analyze_backtest_performance(backtest_id: int, db: Session = None) -> Optional[Dict]:
    """
    分析回测绩效

    Args:
        backtest_id: 回测ID
        db: 数据库会话

    Returns:
        绩效分析结果
    """
    result = db.query(BacktestResult).filter(
        BacktestResult.backtest_id == backtest_id
    ).first()

    if not result:
        return None

    # 这里应该从存储的净值数据重建分析
    # 简化返回已有结果
    return {
        'total_return': result.total_return,
        'annual_return': result.annual_return,
        'max_drawdown': result.max_drawdown,
        'sharpe_ratio': result.sharpe_ratio,
        'calmar_ratio': result.calmar_ratio,
        'turnover_rate': result.turnover_rate,
        'win_rate': result.win_rate,
    }


@with_db
def analyze_portfolio_performance(portfolio_id: int, db: Session = None) -> Optional[Dict]:
    """
    分析组合绩效

    Args:
        portfolio_id: 组合ID
        db: 数据库会话

    Returns:
        绩效分析结果
    """
    navs = db.query(SimulatedPortfolioNav).filter(
        SimulatedPortfolioNav.portfolio_id == portfolio_id
    ).order_by(SimulatedPortfolioNav.trade_date).all()

    if not navs:
        return None

    nav_series = pd.Series(
        {n.trade_date: n.nav for n in navs}
    )

    analyzer = PerformanceAnalyzer(db)
    return analyzer.analyze_performance(nav_series)
