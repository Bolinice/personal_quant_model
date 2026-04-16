"""
多因子模型打分模块
实现等权加权、IC加权、打分排序、综合评分计算
"""
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from app.db.base import SessionLocal, with_db
from app.models.models import Model, ModelFactorWeight, ModelScore
from app.models.factors import Factor, FactorValue
from app.core.factor_preprocess import preprocess_factor_values
from app.core.logging import logger


class MultiFactorScorer:
    """多因子评分器"""

    def __init__(self, db: Session = None):
        self.db = db or SessionLocal()

    def get_factor_weights(self, model_id: int) -> Dict[int, float]:
        """
        获取模型因子权重

        Args:
            model_id: 模型ID

        Returns:
            因子ID到权重的映射
        """
        weights = self.db.query(ModelFactorWeight).filter(
            ModelFactorWeight.model_id == model_id
        ).all()

        return {w.factor_id: w.weight for w in weights}

    def get_factor_values(self, factor_id: int, trade_date: str,
                         ts_codes: List[str] = None) -> pd.Series:
        """
        获取因子值

        Args:
            factor_id: 因子ID
            trade_date: 交易日期
            ts_codes: 股票代码列表（可选）

        Returns:
            因子值序列
        """
        query = self.db.query(FactorValue).filter(
            FactorValue.factor_id == factor_id,
            FactorValue.trade_date == trade_date
        )

        if ts_codes:
            query = query.filter(FactorValue.security_id.in_(ts_codes))

        values = query.all()

        return pd.Series({v.security_id: v.value for v in values})

    # ==================== 加权方法 ====================

    def equal_weight(self, factor_scores: pd.DataFrame) -> pd.Series:
        """
        等权加权

        Args:
            factor_scores: 因子得分矩阵（行为股票，列为因子）

        Returns:
            综合得分
        """
        return factor_scores.mean(axis=1)

    def manual_weight(self, factor_scores: pd.DataFrame, weights: Dict[str, float]) -> pd.Series:
        """
        人工权重加权

        Args:
            factor_scores: 因子得分矩阵
            weights: 因子权重字典

        Returns:
            综合得分
        """
        weighted_sum = pd.Series(0, index=factor_scores.index)
        weight_sum = 0

        for col, weight in weights.items():
            if col in factor_scores.columns:
                weighted_sum += factor_scores[col] * weight
                weight_sum += abs(weight)

        if weight_sum == 0:
            return weighted_sum

        return weighted_sum / weight_sum

    def ic_weight(self, factor_scores: pd.DataFrame, ic_values: Dict[str, float]) -> pd.Series:
        """
        IC加权
        权重 = IC / sum(|IC|)

        Args:
            factor_scores: 因子得分矩阵
            ic_values: 各因子IC值

        Returns:
            综合得分
        """
        weighted_sum = pd.Series(0, index=factor_scores.index)
        ic_sum = 0

        for col, ic in ic_values.items():
            if col in factor_scores.columns and not np.isnan(ic):
                weighted_sum += factor_scores[col] * ic
                ic_sum += abs(ic)

        if ic_sum == 0:
            return self.equal_weight(factor_scores)

        return weighted_sum / ic_sum

    def icir_weight(self, factor_scores: pd.DataFrame, icir_values: Dict[str, float]) -> pd.Series:
        """
        ICIR加权
        权重 = ICIR / sum(|ICIR|)

        Args:
            factor_scores: 因子得分矩阵
            icir_values: 各因子ICIR值

        Returns:
            综合得分
        """
        weighted_sum = pd.Series(0, index=factor_scores.index)
        icir_sum = 0

        for col, icir in icir_values.items():
            if col in factor_scores.columns and not np.isnan(icir):
                weighted_sum += factor_scores[col] * icir
                icir_sum += abs(icir)

        if icir_sum == 0:
            return self.equal_weight(factor_scores)

        return weighted_sum / icir_sum

    # ==================== 综合评分计算 ====================

    def calculate_scores(self, model_id: int, trade_date: str,
                        ts_codes: List[str] = None,
                        weighting_method: str = 'equal') -> pd.DataFrame:
        """
        计算多因子综合评分

        Args:
            model_id: 模型ID
            trade_date: 交易日期
            ts_codes: 股票代码列表
            weighting_method: 加权方法 ('equal', 'manual', 'ic', 'icir')

        Returns:
            评分结果DataFrame，包含各因子得分和综合得分
        """
        # 获取模型配置
        model = self.db.query(Model).filter(Model.id == model_id).first()
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # 获取因子权重
        factor_weights = self.get_factor_weights(model_id)
        if not factor_weights:
            raise ValueError(f"No factor weights found for model {model_id}")

        # 获取所有因子值
        factor_scores = {}
        factor_codes = {}

        for factor_id in factor_weights.keys():
            factor = self.db.query(Factor).filter(Factor.id == factor_id).first()
            if factor:
                values = self.get_factor_values(factor_id, trade_date, ts_codes)
                if not values.empty:
                    # 预处理因子值
                    values = preprocess_factor_values(values)
                    factor_scores[factor.factor_code] = values
                    factor_codes[factor_id] = factor.factor_code

        if not factor_scores:
            raise ValueError(f"No factor values found for {trade_date}")

        # 构建因子得分矩阵
        scores_df = pd.DataFrame(factor_scores)

        # 计算综合得分
        if weighting_method == 'equal':
            scores_df['total_score'] = self.equal_weight(scores_df)
        elif weighting_method == 'manual':
            weights = {factor_codes[fid]: w for fid, w in factor_weights.items()}
            scores_df['total_score'] = self.manual_weight(scores_df, weights)
        elif weighting_method == 'ic':
            # 需要IC值，这里简化处理，使用等权
            scores_df['total_score'] = self.equal_weight(scores_df)
        elif weighting_method == 'icir':
            scores_df['total_score'] = self.equal_weight(scores_df)
        else:
            scores_df['total_score'] = self.equal_weight(scores_df)

        # 计算排名
        scores_df['rank'] = scores_df['total_score'].rank(ascending=False)
        scores_df['quantile'] = scores_df['total_score'].rank(pct=True)

        return scores_df

    def select_top_stocks(self, scores_df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
        """
        选择Top N股票

        Args:
            scores_df: 评分结果
            top_n: 选择数量

        Returns:
            Top N股票
        """
        return scores_df.nsmallest(top_n, 'rank')

    def generate_portfolio_weights(self, scores_df: pd.DataFrame,
                                   top_n: int = 50,
                                   method: str = 'equal') -> pd.Series:
        """
        生成组合权重

        Args:
            scores_df: 评分结果
            top_n: 持仓数量
            method: 权重方法 ('equal', 'score')

        Returns:
            权重序列
        """
        top_stocks = self.select_top_stocks(scores_df, top_n)

        if method == 'equal':
            weights = pd.Series(1.0 / top_n, index=top_stocks.index)
        elif method == 'score':
            scores = top_stocks['total_score']
            # 确保得分为正
            scores = scores - scores.min() + 0.01
            weights = scores / scores.sum()
        else:
            weights = pd.Series(1.0 / top_n, index=top_stocks.index)

        return weights

    def close(self):
        """关闭数据库连接"""
        if self.db:
            self.db.close()


@with_db
def run_model_scoring(model_id: int, trade_date: str,
                     ts_codes: List[str] = None, db: Session = None) -> List[ModelScore]:
    """
    运行模型评分并保存结果

    Args:
        model_id: 模型ID
        trade_date: 交易日期
        ts_codes: 股票代码列表
        db: 数据库会话

    Returns:
        模型评分列表
    """
    # 获取模型配置
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        logger.error(f"Model {model_id} not found")
        return []

    scorer = MultiFactorScorer(db)

    try:
        # 计算评分
        scores_df = scorer.calculate_scores(
            model_id, trade_date, ts_codes,
            model.weighting_method or 'equal'
        )

        # 保存结果
        results = []
        for ts_code, row in scores_df.iterrows():
            # 检查是否已存在
            existing = db.query(ModelScore).filter(
                ModelScore.model_id == model_id,
                ModelScore.trade_date == trade_date,
                ModelScore.security_id == ts_code
            ).first()

            if existing:
                existing.total_score = row['total_score']
            else:
                score = ModelScore(
                    model_id=model_id,
                    trade_date=trade_date,
                    security_id=ts_code,
                    total_score=row['total_score']
                )
                db.add(score)
                results.append(score)

        db.commit()
        logger.info(f"Calculated scores for {len(results)} stocks for model {model_id}")

        return results

    except Exception as e:
        logger.error(f"Error calculating scores: {e}")
        db.rollback()
        return []


@with_db
def get_model_portfolio(model_id: int, trade_date: str, top_n: int = 50,
                       db: Session = None) -> pd.DataFrame:
    """
    获取模型目标组合

    Args:
        model_id: 模型ID
        trade_date: 交易日期
        top_n: 持仓数量
        db: 数据库会话

    Returns:
        目标组合DataFrame
    """
    # 获取评分结果
    scores = db.query(ModelScore).filter(
        ModelScore.model_id == model_id,
        ModelScore.trade_date == trade_date
    ).order_by(ModelScore.total_score.desc()).limit(top_n).all()

    if not scores:
        return pd.DataFrame()

    # 构建等权组合
    weight = 1.0 / len(scores)

    return pd.DataFrame([{
        'security_id': s.security_id,
        'score': s.total_score,
        'weight': weight
    } for s in scores])
