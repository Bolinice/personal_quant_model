"""
机器学习增强模型集成
整合LightGBM、Stacking、对抗性验证、因子挖掘等ML能力
提供统一的ML增强量化模型接口
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from app.core.logging import logger

if TYPE_CHECKING:
    from app.core.model_scorer import MultiFactorScorer
    from app.core.model_trainer import ModelTrainer, TrainedModel


@dataclass
class MLModelConfig:
    """ML模型配置"""

    model_type: str = "lgbm"  # lgbm, lgbm_rank, stacking, ensemble
    use_time_series_cv: bool = True  # 是否使用时序交叉验证
    n_splits: int = 5  # CV折数
    train_window: int = 504  # 训练窗口（交易日）
    test_window: int = 63  # 测试窗口
    gap: int = 21  # 训练/测试间隔
    retrain_freq: int = 63  # 重训练频率
    early_stopping_rounds: int = 30  # 早停轮数
    feature_selection: bool = True  # 是否进行特征选择
    feature_selection_threshold: float = 0.01  # 特征重要性阈值
    adversarial_validation: bool = True  # 是否进行对抗性验证
    drift_threshold: float = 0.55  # 分布漂移阈值
    monotone_constraints: dict[str, int] | None = None  # 单调约束
    model_params: dict[str, Any] = field(default_factory=dict)  # 模型参数


@dataclass
class MLPredictionResult:
    """ML预测结果"""

    predictions: pd.Series  # 预测值
    feature_importance: dict[str, float]  # 特征重要性
    model_metrics: dict[str, Any]  # 模型指标
    drift_info: dict[str, Any] | None = None  # 分布漂移信息
    selected_features: list[str] | None = None  # 选中的特征
    model: Any = None  # 训练好的模型


class MLIntegration:
    """
    机器学习集成框架
    提供统一的ML增强量化模型接口
    """

    def __init__(
        self,
        scorer: MultiFactorScorer | None = None,
        trainer: ModelTrainer | None = None,
        config: MLModelConfig | None = None,
    ):
        self.scorer = scorer
        self.trainer = trainer
        self.config = config or MLModelConfig()

    # ==================== 1. 端到端训练与预测 ====================

    def train_and_predict(
        self,
        train_factor_df: pd.DataFrame,
        train_returns: pd.Series,
        test_factor_df: pd.DataFrame,
        factor_cols: list[str],
    ) -> MLPredictionResult:
        """
        端到端训练与预测流程
        1. 对抗性验证检测分布漂移
        2. 特征选择
        3. 训练模型
        4. 预测

        Args:
            train_factor_df: 训练期因子数据
            train_returns: 训练期收益率
            test_factor_df: 测试期因子数据
            factor_cols: 因子列名

        Returns:
            MLPredictionResult
        """
        # 1. 对抗性验证
        drift_info = None
        if self.config.adversarial_validation and self.scorer:
            drift_info = self.scorer.adversarial_validation(
                train_factor_df,
                test_factor_df,
                factor_cols,
                threshold_auc=self.config.drift_threshold,
            )
            if drift_info.get("has_drift"):
                logger.warning(
                    f"Distribution drift detected: AUC={drift_info['auc']}, "
                    f"drifted_factors={drift_info['drifted_factors']}"
                )

        # 2. 特征选择
        selected_features = factor_cols
        if self.config.feature_selection and self.trainer:
            selected_features = self._select_features(
                train_factor_df,
                train_returns,
                factor_cols,
                threshold=self.config.feature_selection_threshold,
            )
            logger.info(f"Feature selection: {len(factor_cols)} -> {len(selected_features)}")

        # 3. 训练模型
        if not self.trainer:
            from app.core.model_trainer import ModelTrainer

            self.trainer = ModelTrainer(
                n_splits=self.config.n_splits,
                early_stopping_rounds=self.config.early_stopping_rounds,
            )

        trained_model = self._train_model(
            train_factor_df,
            train_returns,
            selected_features,
        )

        if trained_model is None:
            logger.warning("Model training failed, returning empty predictions")
            return MLPredictionResult(
                predictions=pd.Series(dtype=float),
                feature_importance={},
                model_metrics={},
                drift_info=drift_info,
                selected_features=selected_features,
            )

        # 4. 预测
        predictions = self.trainer.predict(trained_model, test_factor_df, selected_features)

        return MLPredictionResult(
            predictions=predictions,
            feature_importance=trained_model.feature_importance,
            model_metrics=trained_model.cv_metrics,
            drift_info=drift_info,
            selected_features=selected_features,
            model=trained_model,
        )

    # ==================== 2. Walk-Forward滚动训练 ====================

    def walk_forward_backtest(
        self,
        data_df: pd.DataFrame,
        factor_cols: list[str],
        return_col: str = "forward_return",
        date_col: str = "trade_date",
    ) -> dict[str, Any]:
        """
        Walk-Forward滚动回测
        每个窗口重新训练模型，模拟真实交易环境

        Args:
            data_df: 包含因子+收益率+日期的DataFrame
            factor_cols: 因子列名
            return_col: 收益率列名
            date_col: 日期列名

        Returns:
            回测结果字典
        """
        if not self.trainer:
            from app.core.model_trainer import ModelTrainer

            self.trainer = ModelTrainer(
                n_splits=self.config.n_splits,
                early_stopping_rounds=self.config.early_stopping_rounds,
            )

        results = self.trainer.walk_forward_train(
            data_df=data_df,
            factor_cols=factor_cols,
            return_col=return_col,
            date_col=date_col,
            train_window=self.config.train_window,
            test_window=self.config.test_window,
            gap=self.config.gap,
            retrain_freq=self.config.retrain_freq,
            model_config=self.config.model_params,
        )

        if not results:
            return {"success": False, "message": "No valid windows"}

        # 汇总结果
        ic_series = [r.test_ic for r in results]
        rank_ic_series = [r.test_rank_ic for r in results]

        summary = {
            "success": True,
            "n_windows": len(results),
            "avg_ic": round(np.mean(ic_series), 4),
            "avg_rank_ic": round(np.mean(rank_ic_series), 4),
            "ic_std": round(np.std(ic_series), 4),
            "rank_ic_std": round(np.std(rank_ic_series), 4),
            "icir": round(np.mean(ic_series) / np.std(ic_series), 2) if np.std(ic_series) > 0 else 0.0,
            "ic_positive_rate": round(sum(1 for ic in ic_series if ic > 0) / len(ic_series), 4),
            "ic_min": round(min(ic_series), 4),
            "ic_max": round(max(ic_series), 4),
            "windows": [
                {
                    "train_start": r.train_start,
                    "train_end": r.train_end,
                    "test_start": r.test_start,
                    "test_end": r.test_end,
                    "test_ic": r.test_ic,
                    "test_rank_ic": r.test_rank_ic,
                }
                for r in results
            ],
        }

        logger.info(
            "Walk-Forward backtest completed",
            extra={
                "n_windows": summary["n_windows"],
                "avg_ic": summary["avg_ic"],
                "icir": summary["icir"],
                "ic_positive_rate": summary["ic_positive_rate"],
            },
        )

        return summary

    # ==================== 3. 集成模型 ====================

    def train_ensemble(
        self,
        train_factor_df: pd.DataFrame,
        train_returns: pd.Series,
        factor_cols: list[str],
        base_models: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        训练集成模型
        结合多个基模型（LightGBM、线性、ICIR等）

        Args:
            train_factor_df: 训练期因子数据
            train_returns: 训练期收益率
            factor_cols: 因子列名
            base_models: 基模型列表 ['lgbm', 'linear', 'icir']

        Returns:
            集成模型结果
        """
        if base_models is None:
            base_models = ["lgbm", "linear", "icir"]

        if not self.scorer:
            from app.core.model_scorer import MultiFactorScorer

            self.scorer = MultiFactorScorer.__new__(MultiFactorScorer)
            self.scorer.db = None

        # 训练各基模型
        base_predictions = {}
        base_metrics = {}

        for model_name in base_models:
            if model_name == "lgbm":
                # LightGBM模型
                if not self.trainer:
                    from app.core.model_trainer import ModelTrainer

                    self.trainer = ModelTrainer(
                        n_splits=self.config.n_splits,
                        early_stopping_rounds=self.config.early_stopping_rounds,
                    )

                trained = self.trainer.train_lgbm(
                    train_factor_df,
                    train_returns,
                    factor_cols,
                    model_config=self.config.model_params,
                    monotone_constraints=self.config.monotone_constraints,
                )

                if trained and trained.oof_predictions is not None:
                    base_predictions["lgbm"] = pd.Series(trained.oof_predictions, index=train_factor_df.index)
                    base_metrics["lgbm"] = trained.cv_metrics

            elif model_name == "linear":
                # 线性模型（等权）
                factor_scores_df = train_factor_df[factor_cols]
                if isinstance(factor_scores_df, pd.DataFrame):
                    base_predictions["linear"] = self.scorer.equal_weight(factor_scores_df)

            elif model_name == "icir":
                # ICIR加权
                # 计算各因子与收益率的相关性作为ICIR权重
                icir_weights = {}
                for col in factor_cols:
                    if col in train_factor_df.columns:
                        factor_series = train_factor_df[col]
                        if isinstance(factor_series, pd.Series):
                            corr = factor_series.corr(train_returns)
                            if not np.isnan(corr):
                                icir_weights[col] = corr

                factor_scores_df = train_factor_df[factor_cols]
                if isinstance(factor_scores_df, pd.DataFrame):
                    base_predictions["icir"] = self.scorer.icir_weight(factor_scores_df, icir_weights)

        if not base_predictions:
            return {"success": False, "message": "No base models trained"}

        # 元学习器组合
        ensemble_pred = self._train_meta_learner(base_predictions, train_returns)

        # 评估
        ensemble_ic = self._calc_ic(ensemble_pred.values, train_returns.values)
        ensemble_rank_ic = self._calc_rank_ic(ensemble_pred.values, train_returns.values)

        result = {
            "success": True,
            "base_models": list(base_predictions.keys()),
            "base_metrics": base_metrics,
            "ensemble_ic": round(ensemble_ic, 4),
            "ensemble_rank_ic": round(ensemble_rank_ic, 4),
            "ensemble_predictions": ensemble_pred,
        }

        logger.info(
            "Ensemble training completed",
            extra={
                "n_base_models": len(base_predictions),
                "ensemble_ic": result["ensemble_ic"],
                "ensemble_rank_ic": result["ensemble_rank_ic"],
            },
        )

        return result

    # ==================== 4. 自动特征工程 ====================

    def auto_feature_engineering(
        self,
        factor_df: pd.DataFrame,
        factor_cols: list[str],
        max_features: int = 50,
    ) -> pd.DataFrame:
        """
        自动特征工程
        生成交互特征、多项式特征等

        Args:
            factor_df: 因子数据
            factor_cols: 原始因子列名
            max_features: 最大特征数

        Returns:
            增强后的因子DataFrame
        """
        enhanced_df = factor_df[factor_cols].copy()

        # 1. 交互特征（前N个重要因子的两两交互）
        n_interact = min(5, len(factor_cols))
        for i in range(n_interact):
            for j in range(i + 1, n_interact):
                col1, col2 = factor_cols[i], factor_cols[j]
                if col1 in enhanced_df.columns and col2 in enhanced_df.columns:
                    # 乘积
                    enhanced_df[f"{col1}_x_{col2}"] = enhanced_df[col1] * enhanced_df[col2]
                    # 比值（避免除零）
                    enhanced_df[f"{col1}_div_{col2}"] = enhanced_df[col1] / (enhanced_df[col2].abs() + 1e-6)

        # 2. 多项式特征（平方、立方）
        for col in factor_cols[:10]:  # 只对前10个因子生成多项式
            if col in enhanced_df.columns:
                enhanced_df[f"{col}_sq"] = enhanced_df[col] ** 2
                enhanced_df[f"{col}_cb"] = enhanced_df[col] ** 3

        # 3. 排名特征
        for col in factor_cols[:10]:
            if col in enhanced_df.columns:
                enhanced_df[f"{col}_rank"] = enhanced_df[col].rank(pct=True)

        # 4. 限制特征数量
        if len(enhanced_df.columns) > max_features:
            # 保留原始因子 + 随机选择部分生成特征
            original_cols = [c for c in factor_cols if c in enhanced_df.columns]
            generated_cols = [c for c in enhanced_df.columns if c not in original_cols]
            selected_generated = np.random.choice(
                generated_cols, size=max_features - len(original_cols), replace=False
            ).tolist()
            enhanced_df = enhanced_df[original_cols + selected_generated]

        logger.info(f"Feature engineering: {len(factor_cols)} -> {len(enhanced_df.columns)} features")

        return enhanced_df

    # ==================== 5. 因子挖掘 ====================

    def factor_mining(
        self,
        data_df: pd.DataFrame,
        candidate_factors: list[str],
        return_col: str,
        min_ic: float = 0.03,
        min_icir: float = 1.0,
        lookback: int = 252,
    ) -> dict[str, Any]:
        """
        因子挖掘
        从候选因子中筛选出有效因子

        Args:
            data_df: 包含因子和收益率的DataFrame
            candidate_factors: 候选因子列名
            return_col: 收益率列名
            min_ic: 最小IC阈值
            min_icir: 最小ICIR阈值
            lookback: 回看期数

        Returns:
            因子挖掘结果
        """
        factor_stats = []

        for factor in candidate_factors:
            if factor not in data_df.columns:
                continue

            # 计算IC序列
            ic_series = []
            dates = sorted(data_df["trade_date"].unique()) if "trade_date" in data_df.columns else []

            if not dates:
                # 无日期列，计算单期IC
                corr = data_df[factor].corr(data_df[return_col])
                if not np.isnan(corr):
                    ic_series = [corr]
            else:
                # 按日期计算IC序列
                for dt in dates[-lookback:]:
                    day_data = data_df[data_df["trade_date"] == dt]
                    if len(day_data) >= 30:  # 至少30个样本
                        corr = day_data[factor].corr(day_data[return_col])
                        if not np.isnan(corr):
                            ic_series.append(corr)

            if not ic_series:
                continue

            # 计算统计量
            ic_mean = np.mean(ic_series)
            ic_std = np.std(ic_series)
            icir = ic_mean / ic_std if ic_std > 0 else 0.0
            ic_positive_rate = sum(1 for ic in ic_series if ic > 0) / len(ic_series)

            factor_stats.append(
                {
                    "factor": factor,
                    "ic_mean": round(ic_mean, 4),
                    "ic_std": round(ic_std, 4),
                    "icir": round(icir, 2),
                    "ic_positive_rate": round(ic_positive_rate, 4),
                    "n_periods": len(ic_series),
                }
            )

        # 筛选有效因子
        valid_factors = [
            f
            for f in factor_stats
            if abs(f["ic_mean"]) >= min_ic and abs(f["icir"]) >= min_icir and f["ic_positive_rate"] >= 0.5
        ]

        result = {
            "n_candidates": len(candidate_factors),
            "n_valid": len(valid_factors),
            "valid_factors": sorted(valid_factors, key=lambda x: -abs(x["icir"])),
            "all_stats": sorted(factor_stats, key=lambda x: -abs(x["icir"])),
        }

        logger.info(
            "Factor mining completed",
            extra={
                "n_candidates": result["n_candidates"],
                "n_valid": result["n_valid"],
                "top_factor": result["valid_factors"][0]["factor"] if result["valid_factors"] else None,
            },
        )

        return result

    # ==================== 6. 模型诊断 ====================

    def diagnose_model(
        self,
        trained_model: TrainedModel,
        test_factor_df: pd.DataFrame,
        test_returns: pd.Series,
        factor_cols: list[str],
    ) -> dict[str, Any]:
        """
        模型诊断
        分析模型性能、特征重要性、预测分布等

        Args:
            trained_model: 训练好的模型
            test_factor_df: 测试期因子数据
            test_returns: 测试期收益率
            factor_cols: 因子列名

        Returns:
            诊断结果
        """
        if not self.trainer:
            from app.core.model_trainer import ModelTrainer

            self.trainer = ModelTrainer()

        # 预测
        predictions = self.trainer.predict(trained_model, test_factor_df, factor_cols)

        # 性能指标
        pred_array = np.asarray(predictions.values)
        ret_array = np.asarray(test_returns.values)
        test_ic = self._calc_ic(pred_array, ret_array)
        test_rank_ic = self._calc_rank_ic(pred_array, ret_array)

        # 预测分布
        pred_stats = {
            "mean": round(predictions.mean(), 6),
            "std": round(predictions.std(), 6),
            "min": round(predictions.min(), 6),
            "max": round(predictions.max(), 6),
            "q25": round(predictions.quantile(0.25), 6),
            "q50": round(predictions.quantile(0.50), 6),
            "q75": round(predictions.quantile(0.75), 6),
        }

        # 分位数收益
        quantile_returns = self._calc_quantile_returns(predictions, test_returns, n_quantiles=5)

        # 特征重要性
        top_features = dict(
            sorted(trained_model.feature_importance.items(), key=lambda x: -x[1])[:20]
        )

        result = {
            "test_ic": round(test_ic, 4),
            "test_rank_ic": round(test_rank_ic, 4),
            "prediction_stats": pred_stats,
            "quantile_returns": quantile_returns,
            "top_features": top_features,
            "cv_metrics": trained_model.cv_metrics,
        }

        logger.info(
            "Model diagnosis completed",
            extra={
                "test_ic": result["test_ic"],
                "test_rank_ic": result["test_rank_ic"],
                "top_feature": list(top_features.keys())[0] if top_features else None,
            },
        )

        return result

    # ==================== 辅助方法 ====================

    def _select_features(
        self,
        factor_df: pd.DataFrame,
        returns: pd.Series,
        factor_cols: list[str],
        threshold: float = 0.01,
    ) -> list[str]:
        """
        特征选择
        基于特征重要性筛选特征
        """
        if not self.trainer:
            from app.core.model_trainer import ModelTrainer

            self.trainer = ModelTrainer(n_splits=3)  # 快速CV

        # 训练初步模型获取特征重要性
        trained = self.trainer.train_lgbm(
            factor_df,
            returns,
            factor_cols,
            model_config={"n_estimators": 100},  # 快速训练
        )

        if trained is None or not trained.feature_importance:
            return factor_cols

        # 筛选重要特征
        selected = [f for f, imp in trained.feature_importance.items() if imp >= threshold]

        # 至少保留5个特征
        if len(selected) < 5:
            selected = sorted(trained.feature_importance.items(), key=lambda x: -x[1])[:5]
            selected = [f for f, _ in selected]

        return selected

    def _train_model(
        self,
        factor_df: pd.DataFrame,
        returns: pd.Series,
        factor_cols: list[str],
    ) -> TrainedModel | None:
        """训练模型（根据配置选择模型类型）"""
        if self.config.model_type == "lgbm":
            return self.trainer.train_lgbm(
                factor_df,
                returns,
                factor_cols,
                model_config=self.config.model_params,
                monotone_constraints=self.config.monotone_constraints,
            )
        elif self.config.model_type == "lgbm_rank":
            return self.trainer.train_lgbm_rank(
                factor_df,
                returns,
                factor_cols,
                model_config=self.config.model_params,
            )
        else:
            return self.trainer.train_lgbm(factor_df, returns, factor_cols)

    def _train_meta_learner(
        self,
        base_predictions: dict[str, pd.Series],
        returns: pd.Series,
    ) -> pd.Series:
        """训练元学习器组合基模型"""
        try:
            from sklearn.linear_model import Ridge

            # 构建元特征
            meta_df = pd.DataFrame(base_predictions)
            common_idx = meta_df.index.intersection(returns.index)

            if len(common_idx) < 20:
                # 样本不足，简单平均
                return meta_df.mean(axis=1)

            X_meta = meta_df.loc[common_idx].values
            y_meta = returns.loc[common_idx].values

            # Ridge回归
            meta_learner = Ridge(alpha=1.0)
            meta_learner.fit(X_meta, y_meta)

            # 预测
            ensemble_pred = meta_learner.predict(meta_df.values)
            return pd.Series(ensemble_pred, index=meta_df.index)

        except ImportError:
            # sklearn不可用，简单平均
            return pd.DataFrame(base_predictions).mean(axis=1)

    def _calc_quantile_returns(
        self,
        predictions: pd.Series,
        returns: pd.Series,
        n_quantiles: int = 5,
    ) -> dict[str, float]:
        """计算分位数收益"""
        common_idx = predictions.index.intersection(returns.index)
        if len(common_idx) < n_quantiles * 10:
            return {}

        pred_aligned = predictions.loc[common_idx]
        ret_aligned = returns.loc[common_idx]

        # 分位数
        quantiles = pd.qcut(pred_aligned, q=n_quantiles, labels=False, duplicates="drop")

        quantile_returns = {}
        for q in range(n_quantiles):
            mask = quantiles == q
            if mask.sum() > 0:
                quantile_returns[f"Q{q+1}"] = round(ret_aligned[mask].mean(), 6)

        return quantile_returns

    @staticmethod
    def _calc_ic(predictions: np.ndarray[Any, Any], actual: np.ndarray[Any, Any]) -> float:
        """计算IC"""
        valid = ~(np.isnan(predictions) | np.isnan(actual))
        if valid.sum() < 10:
            return 0.0
        corr = np.corrcoef(predictions[valid], actual[valid])[0, 1]
        return corr if not np.isnan(corr) else 0.0

    @staticmethod
    def _calc_rank_ic(predictions: np.ndarray[Any, Any], actual: np.ndarray[Any, Any]) -> float:
        """计算Rank IC"""
        valid = ~(np.isnan(predictions) | np.isnan(actual))
        if valid.sum() < 10:
            return 0.0
        pred_rank = pd.Series(predictions[valid]).rank()
        actual_rank = pd.Series(actual[valid]).rank()
        corr = pred_rank.corr(actual_rank)
        return corr if not np.isnan(corr) else 0.0


# ==================== 便捷函数 ====================


def quick_ml_predict(
    train_factor_df: pd.DataFrame,
    train_returns: pd.Series,
    test_factor_df: pd.DataFrame,
    factor_cols: list[str],
    model_type: str = "lgbm",
) -> pd.Series:
    """
    快速ML预测（无需配置）

    Args:
        train_factor_df: 训练期因子数据
        train_returns: 训练期收益率
        test_factor_df: 测试期因子数据
        factor_cols: 因子列名
        model_type: 模型类型

    Returns:
        预测值Series
    """
    config = MLModelConfig(model_type=model_type, n_splits=3)
    ml = MLIntegration(config=config)

    result = ml.train_and_predict(
        train_factor_df,
        train_returns,
        test_factor_df,
        factor_cols,
    )

    return result.predictions


def quick_factor_mining(
    data_df: pd.DataFrame,
    candidate_factors: list[str],
    return_col: str = "forward_return",
) -> list[str]:
    """
    快速因子挖掘（返回有效因子列表）

    Args:
        data_df: 包含因子和收益率的DataFrame
        candidate_factors: 候选因子列名
        return_col: 收益率列名

    Returns:
        有效因子列表
    """
    ml = MLIntegration()
    result = ml.factor_mining(data_df, candidate_factors, return_col)

    return [f["factor"] for f in result["valid_factors"]]
