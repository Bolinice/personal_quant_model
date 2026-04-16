"""
组合构建与调仓模块
实现Top N选股、等权组合、行业约束、调仓生成
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, with_db
from app.models.models import Model, ModelScore
from app.models.portfolios import Portfolio, PortfolioPosition, RebalanceRecord
from app.models.market import StockDaily, StockIndustry
from app.core.logging import logger


class PortfolioBuilder:
    """组合构建器"""

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    # ==================== 选股方法 ====================

    def select_top_n(self, scores: pd.Series, n: int = 50) -> List[str]:
        """
        Top N选股

        Args:
            scores: 评分序列
            n: 选择数量

        Returns:
            选中的股票代码列表
        """
        return scores.nlargest(n).index.tolist()

    def select_by_quantile(self, scores: pd.Series, quantile: float = 0.1) -> List[str]:
        """
        按分位数选股

        Args:
            scores: 评分序列
            quantile: 分位数阈值（选择前quantile比例的股票）

        Returns:
            选中的股票代码列表
        """
        threshold = scores.quantile(1 - quantile)
        return scores[scores >= threshold].index.tolist()

    def select_with_constraints(self, scores: pd.Series,
                                industry_data: pd.Series,
                                max_per_industry: int = 5,
                                n: int = 50) -> List[str]:
        """
        带行业约束的选股

        Args:
            scores: 评分序列
            industry_data: 行业数据序列
            max_per_industry: 每个行业最大持仓数
            n: 总持仓数

        Returns:
            选中的股票代码列表
        """
        selected = []
        industry_count = {}

        # 按评分排序
        sorted_stocks = scores.sort_values(ascending=False)

        for stock in sorted_stocks.index:
            if len(selected) >= n:
                break

            industry = industry_data.get(stock, 'Unknown')
            current_count = industry_count.get(industry, 0)

            if current_count < max_per_industry:
                selected.append(stock)
                industry_count[industry] = current_count + 1

        return selected

    # ==================== 权重分配方法 ====================

    def equal_weight(self, stocks: List[str]) -> pd.Series:
        """
        等权组合

        Args:
            stocks: 股票列表

        Returns:
            权重序列
        """
        weight = 1.0 / len(stocks)
        return pd.Series(weight, index=stocks)

    def score_weight(self, stocks: List[str], scores: pd.Series) -> pd.Series:
        """
        按评分加权

        Args:
            stocks: 股票列表
            scores: 评分序列

        Returns:
            权重序列
        """
        stock_scores = scores[stocks]
        # 确保得分为正
        stock_scores = stock_scores - stock_scores.min() + 0.01
        weights = stock_scores / stock_scores.sum()
        return weights

    def market_cap_weight(self, stocks: List[str], market_caps: pd.Series) -> pd.Series:
        """
        按市值加权

        Args:
            stocks: 股票列表
            market_caps: 市值序列

        Returns:
            权重序列
        """
        caps = market_caps[stocks]
        weights = caps / caps.sum()
        return weights

    def risk_parity_weight(self, stocks: List[str], volatilities: pd.Series) -> pd.Series:
        """
        风险平价权重

        Args:
            stocks: 股票列表
            volatilities: 波动率序列

        Returns:
            权重序列
        """
        vols = volatilities[stocks]
        # 风险平价：权重与波动率成反比
        inv_vol = 1.0 / vols
        weights = inv_vol / inv_vol.sum()
        return weights

    def risk_model_weight(self, stocks: List[str],
                          expected_returns: pd.Series,
                          cov_matrix: pd.DataFrame,
                          risk_aversion: float = 1.0,
                          max_position: float = 0.10) -> pd.Series:
        """
        基于风险模型的优化权重

        Args:
            stocks: 股票列表
            expected_returns: 期望收益
            cov_matrix: 协方差矩阵
            risk_aversion: 风险厌恶系数
            max_position: 单只股票最大权重

        Returns:
            权重序列
        """
        from app.core.portfolio_optimizer import PortfolioOptimizer

        optimizer = PortfolioOptimizer()

        # 截取相关股票的数据
        mu = expected_returns.reindex(stocks).dropna()
        sigma = cov_matrix.reindex(mu.index, mu.index)

        if mu.empty or sigma.empty:
            return self.equal_weight(stocks)

        weights = optimizer.mean_variance_optimize(
            mu, sigma,
            risk_aversion=risk_aversion,
            max_position=max_position
        )

        return weights

    def risk_parity_weight_model(self, stocks: List[str],
                                  cov_matrix: pd.DataFrame,
                                  max_position: float = 0.10) -> pd.Series:
        """
        基于风险模型的风险平价权重

        Args:
            stocks: 股票列表
            cov_matrix: 协方差矩阵
            max_position: 单只股票最大权重

        Returns:
            权重序列
        """
        from app.core.portfolio_optimizer import PortfolioOptimizer

        optimizer = PortfolioOptimizer()

        sigma = cov_matrix.reindex(stocks, stocks)
        if sigma.empty:
            return self.equal_weight(stocks)

        weights = optimizer.risk_parity_optimize(sigma, max_position=max_position)

        return weights

    # ==================== 行业约束 ====================

    def apply_industry_constraint(self, weights: pd.Series,
                                  industry_data: pd.Series,
                                  max_industry_weight: float = 0.3) -> pd.Series:
        """
        应用行业权重约束

        Args:
            weights: 原始权重
            industry_data: 行业数据
            max_industry_weight: 单个行业最大权重

        Returns:
            调整后的权重
        """
        adjusted_weights = weights.copy()

        # 计算各行业权重
        industry_weights = {}
        for stock, weight in weights.items():
            industry = industry_data.get(stock, 'Unknown')
            industry_weights[industry] = industry_weights.get(industry, 0) + weight

        # 调整超限行业
        for industry, ind_weight in industry_weights.items():
            if ind_weight > max_industry_weight:
                # 按比例缩减该行业内股票权重
                scale = max_industry_weight / ind_weight
                for stock in weights.index:
                    if industry_data.get(stock, 'Unknown') == industry:
                        adjusted_weights[stock] *= scale

        # 重新归一化
        adjusted_weights = adjusted_weights / adjusted_weights.sum()

        return adjusted_weights

    def apply_position_limit(self, weights: pd.Series,
                             max_position: float = 0.05) -> pd.Series:
        """
        应用单只股票仓位限制

        Args:
            weights: 原始权重
            max_position: 单只股票最大权重

        Returns:
            调整后的权重
        """
        adjusted_weights = weights.copy()
        excess = 0

        # 找出超限股票
        for stock, weight in weights.items():
            if weight > max_position:
                excess += weight - max_position
                adjusted_weights[stock] = max_position

        # 将超限部分分配给未超限股票
        under_limit_stocks = weights[weights <= max_position]
        if not under_limit_stocks.empty and excess > 0:
            redistribute = excess / len(under_limit_stocks)
            for stock in under_limit_stocks.index:
                adjusted_weights[stock] = min(
                    adjusted_weights[stock] + redistribute,
                    max_position
                )

        # 重新归一化
        adjusted_weights = adjusted_weights / adjusted_weights.sum()

        return adjusted_weights

    # ==================== 完整组合构建 ====================

    def build_portfolio(self, model_id: int, trade_date: str,
                       top_n: int = 50,
                       weighting_method: str = 'equal',
                       max_position: float = 0.05,
                       max_industry_weight: float = 0.3) -> pd.DataFrame:
        """
        构建投资组合

        Args:
            model_id: 模型ID
            trade_date: 交易日期
            top_n: 持仓数量
            weighting_method: 权重方法
            max_position: 单只股票最大权重
            max_industry_weight: 单个行业最大权重

        Returns:
            组合DataFrame
        """
        # 获取模型评分
        scores = self.db.query(ModelScore).filter(
            ModelScore.model_id == model_id,
            ModelScore.trade_date == trade_date
        ).order_by(ModelScore.total_score.desc()).limit(top_n * 2).all()

        if not scores:
            logger.warning(f"No scores found for model {model_id} on {trade_date}")
            return pd.DataFrame()

        # 转换为Series
        scores_series = pd.Series({s.security_id: s.total_score for s in scores})

        # 获取行业数据
        industries = self._get_industry_data(scores_series.index.tolist())

        # 选股
        selected = self.select_with_constraints(
            scores_series, industries, max_per_industry=10, n=top_n
        )

        if not selected:
            return pd.DataFrame()

        # 分配权重
        if weighting_method == 'equal':
            weights = self.equal_weight(selected)
        elif weighting_method == 'score':
            weights = self.score_weight(selected, scores_series)
        elif weighting_method == 'risk_model':
            # 需要外部传入cov_matrix和expected_returns
            # 回退到等权
            weights = self.equal_weight(selected)
        else:
            weights = self.equal_weight(selected)

        # 应用约束
        weights = self.apply_position_limit(weights, max_position)
        weights = self.apply_industry_constraint(weights, industries, max_industry_weight)

        # 构建结果
        result = pd.DataFrame({
            'security_id': weights.index,
            'weight': weights.values,
            'score': [scores_series.get(s, 0) for s in weights.index],
            'industry': [industries.get(s, 'Unknown') for s in weights.index]
        })

        return result

    def _get_industry_data(self, ts_codes: List[str]) -> pd.Series:
        """获取行业数据"""
        industries = self.db.query(StockIndustry).filter(
            StockIndustry.ts_code.in_(ts_codes)
        ).all()

        return pd.Series({i.ts_code: i.industry_name for i in industries})

    # ==================== 调仓生成 ====================

    def generate_rebalance(self, current_positions: Dict[str, float],
                          target_portfolio: pd.DataFrame,
                          trade_date: str) -> Dict:
        """
        生成调仓方案

        Args:
            current_positions: 当前持仓 {ts_code: weight}
            target_portfolio: 目标组合
            trade_date: 交易日期

        Returns:
            调仓方案
        """
        current_stocks = set(current_positions.keys())
        target_stocks = set(target_portfolio['security_id'].tolist())

        # 需要卖出的股票
        to_sell = []
        for stock in current_stocks - target_stocks:
            to_sell.append({
                'ts_code': stock,
                'current_weight': current_positions[stock],
                'target_weight': 0,
                'adjust_weight': -current_positions[stock]
            })

        # 需要买入的股票
        to_buy = []
        for _, row in target_portfolio[target_portfolio['security_id'].isin(target_stocks - current_stocks)].iterrows():
            to_buy.append({
                'ts_code': row['security_id'],
                'current_weight': 0,
                'target_weight': row['weight'],
                'adjust_weight': row['weight']
            })

        # 需要调整的股票
        to_adjust = []
        for stock in current_stocks & target_stocks:
            current_weight = current_positions[stock]
            target_weight = target_portfolio[target_portfolio['security_id'] == stock]['weight'].iloc[0]
            adjust_weight = target_weight - current_weight

            if abs(adjust_weight) > 0.001:  # 忽略微小调整
                to_adjust.append({
                    'ts_code': stock,
                    'current_weight': current_weight,
                    'target_weight': target_weight,
                    'adjust_weight': adjust_weight
                })

        # 计算换手率
        total_turnover = (
            sum(abs(s['adjust_weight']) for s in to_sell) +
            sum(abs(b['adjust_weight']) for b in to_buy) +
            sum(abs(a['adjust_weight']) for a in to_adjust)
        ) / 2

        return {
            'trade_date': trade_date,
            'sell_list': to_sell,
            'buy_list': to_buy,
            'adjust_list': to_adjust,
            'total_turnover': total_turnover,
            'stocks_to_trade': len(to_sell) + len(to_buy) + len(to_adjust)
        }

    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()


@with_db
def generate_model_portfolio(model_id: int, trade_date: str, db: Session = None) -> Optional[Portfolio]:
    """
    生成模型目标组合

    Args:
        model_id: 模型ID
        trade_date: 交易日期
        db: 数据库会话

    Returns:
        组合对象
    """
    # 获取模型配置
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        logger.error(f"Model {model_id} not found")
        return None

    builder = PortfolioBuilder(db)

    try:
        # 构建组合
        portfolio_df = builder.build_portfolio(
            model_id, trade_date,
            top_n=model.hold_count or 50,
            weighting_method=model.weighting_method or 'equal'
        )

        if portfolio_df.empty:
            logger.warning(f"Failed to build portfolio for model {model_id}")
            return None

        # 创建组合记录
        portfolio = Portfolio(
            model_id=model_id,
            trade_date=trade_date,
            target_exposure=1.0
        )
        db.add(portfolio)
        db.flush()

        # 创建持仓记录
        for _, row in portfolio_df.iterrows():
            position = PortfolioPosition(
                portfolio_id=portfolio.id,
                security_id=row['security_id'],
                weight=row['weight']
            )
            db.add(position)

        db.commit()
        logger.info(f"Generated portfolio for model {model_id} on {trade_date}")

        return portfolio

    except Exception as e:
        logger.error(f"Error generating portfolio: {e}")
        db.rollback()
        return None


@with_db
def generate_rebalance_record(model_id: int, trade_date: str, db: Session = None) -> Optional[RebalanceRecord]:
    """
    生成调仓记录

    Args:
        model_id: 模型ID
        trade_date: 交易日期
        db: 数据库会话

    Returns:
        调仓记录
    """
    # 获取当前持仓
    current_portfolio = db.query(Portfolio).filter(
        Portfolio.model_id == model_id
    ).order_by(Portfolio.trade_date.desc()).first()

    if not current_portfolio:
        logger.warning(f"No current portfolio found for model {model_id}")
        return None

    # 获取当前持仓权重
    current_positions = db.query(PortfolioPosition).filter(
        PortfolioPosition.portfolio_id == current_portfolio.id
    ).all()

    current_weights = {p.security_id: p.weight for p in current_positions}

    # 构建目标组合
    builder = PortfolioBuilder(db)
    target_portfolio = builder.build_portfolio(model_id, trade_date)

    if target_portfolio.empty:
        return None

    # 生成调仓方案
    rebalance = builder.generate_rebalance(current_weights, target_portfolio, trade_date)

    # 保存调仓记录
    record = RebalanceRecord(
        model_id=model_id,
        trade_date=trade_date,
        rebalance_type='scheduled',
        buy_list=rebalance['buy_list'],
        sell_list=rebalance['sell_list'],
        total_turnover=rebalance['total_turnover']
    )

    db.add(record)
    db.commit()

    logger.info(f"Generated rebalance record for model {model_id} on {trade_date}")

    return record
