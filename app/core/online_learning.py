"""
在线学习模块 - Walk-Forward滚动训练 + TimeSeriesSplit交叉验证
核心: 用时序CV替代随机分割，防止未来函数泄漏
"""

import numpy as np
import pandas as pd

from app.core.logging import logger


class OnlineLearning:
    """
    在线学习引擎
    管理模型的滚动训练、评估和更新
    """

    def __init__(
        self,
        model_dir: str = "models/",
        n_splits: int = 5,
        min_train_samples: int = 200,
        early_stopping_rounds: int = 30,
    ):
        self.model_dir = model_dir
        self.n_splits = n_splits
        self.min_train_samples = min_train_samples
        self.early_stopping_rounds = early_stopping_rounds
        self._current_model = None
        self._model_version = 0

    def retrain_walk_forward(
        self,
        data_df: pd.DataFrame,
        factor_cols: list[str],
        return_col: str = "forward_return",
        date_col: str = "trade_date",
        train_window: int = 504,
        test_window: int = 63,
        gap: int = 21,
        retrain_freq: int = 63,
        model_config: dict | None = None,
    ) -> list[dict]:
        """
        Walk-Forward滚动训练
        使用TimeSeriesSplit进行时序交叉验证，替代简单的时间比例分割

        Args:
            data_df: 包含因子+收益率+日期的DataFrame
            factor_cols: 因子列名
            return_col: 收益率列名
            date_col: 日期列名
            train_window: 训练窗口(交易日数)
            test_window: 测试窗口
            gap: 训练/测试间隔(防止信息泄漏)
            retrain_freq: 重训练频率
            model_config: 模型参数

        Returns:
            各窗口评估结果列表
        """
        from app.core.model_trainer import ModelTrainer

        trainer = ModelTrainer(
            model_dir=self.model_dir,
            n_splits=self.n_splits,
            min_train_samples=self.min_train_samples,
            early_stopping_rounds=self.early_stopping_rounds,
        )

        wf_results = trainer.walk_forward_train(
            data_df=data_df,
            factor_cols=factor_cols,
            return_col=return_col,
            date_col=date_col,
            train_window=train_window,
            test_window=test_window,
            gap=gap,
            retrain_freq=retrain_freq,
            model_config=model_config,
        )

        # 转换为字典格式返回
        results = []
        for r in wf_results:
            results.append(
                {
                    "train_start": r.train_start,
                    "train_end": r.train_end,
                    "test_start": r.test_start,
                    "test_end": r.test_end,
                    "test_ic": r.test_ic,
                    "test_icir": r.test_icir,
                    "test_rank_ic": r.test_rank_ic,
                }
            )

        # 更新当前模型为最后一个窗口的模型
        if wf_results and wf_results[-1].model is not None:
            self._current_model = wf_results[-1].model
            self._model_version += 1
            logger.info(
                f"Model updated to version {self._model_version}",
                extra={
                    "train_end": str(wf_results[-1].train_end),
                    "test_ic": wf_results[-1].test_ic,
                },
            )

        return results

    def train_with_timeseries_cv(
        self,
        factor_df: pd.DataFrame,
        return_series: pd.Series,
        factor_cols: list[str],
        model_config: dict | None = None,
        monotone_constraints: dict[str, int] | None = None,
    ) -> dict | None:
        """
        使用TimeSeriesSplit交叉验证训练模型
        替代原有的简单时间比例分割

        Args:
            factor_df: 因子值DataFrame
            return_series: 前瞻收益率Series
            factor_cols: 因子列名
            model_config: 模型参数
            monotone_constraints: 单调约束

        Returns:
            训练结果 {model, cv_metrics, feature_importance}
        """
        from app.core.model_trainer import ModelTrainer

        trainer = ModelTrainer(
            model_dir=self.model_dir,
            n_splits=self.n_splits,
            min_train_samples=self.min_train_samples,
            early_stopping_rounds=self.early_stopping_rounds,
        )

        trained = trainer.train_lgbm(
            factor_df=factor_df,
            return_series=return_series,
            factor_cols=factor_cols,
            model_config=model_config,
            monotone_constraints=monotone_constraints,
        )

        if trained is None:
            return None

        self._current_model = trained
        self._model_version += 1

        return {
            "model": trained.model,
            "scaler": trained.scaler,
            "cv_metrics": trained.cv_metrics,
            "feature_importance": trained.feature_importance,
            "model_version": self._model_version,
        }

    def predict(self, factor_df: pd.DataFrame, factor_cols: list[str]) -> pd.Series | None:
        """
        使用当前模型预测

        Args:
            factor_df: 因子值DataFrame
            factor_cols: 因子列名

        Returns:
            预测值Series
        """
        if self._current_model is None:
            logger.warning("No model available for prediction")
            return None

        from app.core.model_trainer import ModelTrainer

        trainer = ModelTrainer(model_dir=self.model_dir)
        return trainer.predict(self._current_model, factor_df, factor_cols)

    def get_model_info(self) -> dict:
        """获取当前模型信息"""
        if self._current_model is None:
            return {"status": "no_model", "version": 0}

        return {
            "status": "active",
            "version": self._model_version,
            "train_date": str(self._current_model.train_date),
            "model_type": self._current_model.model_type,
            "n_factors": len(self._current_model.factor_cols),
            "cv_metrics": self._current_model.cv_metrics,
            "top_features": dict(
                sorted(
                    self._current_model.feature_importance.items(),
                    key=lambda x: -x[1],
                )[:10]
            ),
        }

    def evaluate_model(self, factor_df: pd.DataFrame, return_series: pd.Series, factor_cols: list[str]) -> dict:
        """
        评估当前模型在给定数据上的表现

        Args:
            factor_df: 因子值DataFrame
            return_series: 实际收益率Series
            factor_cols: 因子列名

        Returns:
            评估指标 {ic, rank_ic, rmse, n_samples}
        """
        predictions = self.predict(factor_df, factor_cols)
        if predictions is None:
            return {}

        common_idx = predictions.index.intersection(return_series.index)
        pred = predictions.loc[common_idx].values
        actual = return_series.loc[common_idx].values

        valid = ~(np.isnan(pred) | np.isnan(actual))
        pred = pred[valid]
        actual = actual[valid]

        if len(pred) < 10:
            return {}

        ic = np.corrcoef(pred, actual)[0, 1]
        rank_ic = pd.Series(pred).rank().corr(pd.Series(actual).rank())
        rmse = np.sqrt(np.mean((pred - actual) ** 2))

        return {
            "ic": round(ic, 4) if not np.isnan(ic) else 0.0,
            "rank_ic": round(rank_ic, 4) if not np.isnan(rank_ic) else 0.0,
            "rmse": round(rmse, 6),
            "n_samples": len(pred),
        }
