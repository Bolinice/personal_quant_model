"""
模型训练器 - LightGBM训练 + 时序交叉验证 + Walk-Forward滚动训练
核心: TimeSeriesSplit防止未来函数、OOF预测评估、特征重要性分析、模型持久化
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.logging import logger


@dataclass
class TrainedModel:
    """训练好的模型"""

    model: Any
    scaler: Any
    factor_cols: list[str]
    cv_metrics: dict = field(default_factory=dict)
    oof_predictions: np.ndarray | None = None
    feature_importance: dict = field(default_factory=dict)
    train_date: date | None = None
    model_config: dict = field(default_factory=dict)
    model_type: str = "lgbm"


@dataclass
class WalkForwardResult:
    """Walk-Forward单窗口结果"""

    train_start: date | None = None
    train_end: date | None = None
    test_start: date | None = None
    test_end: date | None = None
    model: TrainedModel | None = None
    test_predictions: pd.Series | None = None
    test_ic: float = 0.0
    test_icir: float = 0.0
    test_rank_ic: float = 0.0


class ModelTrainer:
    """
    模型训练器
    核心理念: 量化模型必须用TimeSeriesSplit防止未来函数，Walk-Forward验证防止过拟合
    """

    # LightGBM默认参数 (保守，防止过拟合)
    DEFAULT_LGBM_CONFIG = {
        "objective": "regression",
        "metric": "mse",
        "n_estimators": 300,
        "max_depth": 5,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_child_samples": 50,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "verbose": -1,
        "n_jobs": -1,
        "random_state": 42,
    }

    # LightGBM排序模型默认参数
    DEFAULT_LGBM_RANK_CONFIG = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.05,
        "num_leaves": 15,
        "min_child_samples": 50,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "verbose": -1,
        "n_jobs": -1,
        "random_state": 42,
    }

    def __init__(
        self,
        model_dir: str = "models/",
        n_splits: int = 5,
        min_train_samples: int = 200,
        early_stopping_rounds: int = 30,
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.n_splits = n_splits
        self.min_train_samples = min_train_samples
        self.early_stopping_rounds = early_stopping_rounds

    # ==================== 1. LightGBM回归训练 (TimeSeriesSplit CV) ====================

    def train_lgbm(
        self,
        factor_df: pd.DataFrame,
        return_series: pd.Series,
        factor_cols: list[str],
        model_config: dict | None = None,
        monotone_constraints: dict[str, int] | None = None,
    ) -> TrainedModel | None:
        """
        时序交叉验证训练LightGBM回归模型
        使用TimeSeriesSplit确保训练数据始终在验证数据之前，防止未来函数

        Args:
            factor_df: 因子值DataFrame (index=股票代码, columns=因子名)
            return_series: 前瞻收益率Series (index=股票代码)
            factor_cols: 用于训练的因子列名
            model_config: LightGBM参数覆盖
            monotone_constraints: 单调约束 {factor_name: 1或-1}
        """
        try:
            import lightgbm as lgb
            from sklearn.model_selection import TimeSeriesSplit
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            logger.warning("lightgbm/sklearn not available, cannot train model")
            return None

        # 准备数据
        X, y, _valid_idx = self._prepare_training_data(factor_df, return_series, factor_cols)
        if X is None:
            return None

        config = {**self.DEFAULT_LGBM_CONFIG}
        if model_config:
            config.update(model_config)

        # 单调约束
        if monotone_constraints:
            constraints = [monotone_constraints.get(col, 0) for col in factor_cols]
            config["monotone_constraints"] = constraints

        # TimeSeriesSplit交叉验证
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        oof_predictions = np.full(len(y), np.nan)
        cv_metrics = {}
        fold_models = []

        for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            if len(X_train) < self.min_train_samples:
                logger.warning(f"Fold {fold_idx}: insufficient training samples ({len(X_train)})")
                continue

            # 标准化 (仅在训练集上fit)
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)

            # 训练
            model = lgb.LGBMRegressor(**config)
            model.fit(
                X_train_scaled,
                y_train,
                eval_set=[(X_val_scaled, y_val)],
                callbacks=[lgb.early_stopping(self.early_stopping_rounds, verbose=False)],
            )

            # OOF预测
            val_pred = model.predict(X_val_scaled)
            oof_predictions[val_idx] = val_pred

            # 折内指标
            ic = self._calc_ic(val_pred, y_val)
            rank_ic = self._calc_rank_ic(val_pred, y_val)
            rmse = np.sqrt(np.mean((val_pred - y_val) ** 2))

            cv_metrics[f"fold_{fold_idx}"] = {
                "ic": round(ic, 4),
                "rank_ic": round(rank_ic, 4),
                "rmse": round(rmse, 6),
                "n_train": len(X_train),
                "n_val": len(X_val),
            }
            fold_models.append((model, scaler))

            logger.info(
                f"Fold {fold_idx}: IC={ic:.4f}, RankIC={rank_ic:.4f}, RMSE={rmse:.6f}",
            )

        if not fold_models:
            logger.warning("No valid folds completed")
            return None

        # 全量重训练 (用全部数据)
        full_scaler = StandardScaler()
        X_scaled = full_scaler.fit_transform(X)
        full_model = lgb.LGBMRegressor(**config)
        full_model.fit(X_scaled, y)

        # 特征重要性
        feature_importance = dict(
            zip(
                factor_cols,
                full_model.feature_importances_ / full_model.feature_importances_.sum(),
                strict=False,
            )
        )

        # 汇总CV指标
        cv_metrics["overall"] = self._summarize_cv_metrics(cv_metrics)

        trained = TrainedModel(
            model=full_model,
            scaler=full_scaler,
            factor_cols=factor_cols,
            cv_metrics=cv_metrics,
            oof_predictions=oof_predictions,
            feature_importance=feature_importance,
            train_date=datetime.now(tz=timezone.utc).date(),
            model_config=config,
            model_type="lgbm",
        )

        logger.info(
            "LightGBM training completed",
            extra={
                "n_samples": len(X),
                "n_features": len(factor_cols),
                "n_folds": len(fold_models),
                "overall_ic": cv_metrics["overall"].get("ic", 0),
                "overall_rank_ic": cv_metrics["overall"].get("rank_ic", 0),
            },
        )

        return trained

    # ==================== 2. LightGBM排序模型 ====================

    def train_lgbm_rank(
        self,
        factor_df: pd.DataFrame,
        return_series: pd.Series,
        factor_cols: list[str],
        model_config: dict | None = None,
    ) -> TrainedModel | None:
        """
        LightGBM LambdaRank排序模型
        将股票选择建模为排序问题，用lambdarank目标函数

        Args:
            factor_df: 因子值DataFrame
            return_series: 收益率标签
            factor_cols: 因子列名
            model_config: LightGBM参数覆盖
        """
        try:
            import lightgbm as lgb
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            logger.warning("lightgbm/sklearn not available")
            return None

        X, y, _valid_idx = self._prepare_training_data(factor_df, return_series, factor_cols)
        if X is None:
            return None

        config = {**self.DEFAULT_LGBM_RANK_CONFIG}
        if model_config:
            config.update(model_config)

        # 标准化
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # 将收益率转换为排名标签
        y_rank = pd.Series(y).rank(pct=True).values

        # 训练 (lambdarank需要group参数)
        train_data = lgb.Dataset(X_scaled, label=y_rank, group=[len(X_scaled)])
        model = lgb.train(config, train_data, num_boost_round=config.get("n_estimators", 200))

        # 特征重要性
        feature_importance = dict(
            zip(
                factor_cols,
                model.feature_importance() / model.feature_importance().sum(),
                strict=False,
            )
        )

        trained = TrainedModel(
            model=model,
            scaler=scaler,
            factor_cols=factor_cols,
            feature_importance=feature_importance,
            train_date=datetime.now(tz=timezone.utc).date(),
            model_config=config,
            model_type="lgbm_rank",
        )

        logger.info(
            "LightGBM Rank training completed",
            extra={"n_samples": len(X), "n_features": len(factor_cols)},
        )

        return trained

    # ==================== 3. Walk-Forward滚动训练 ====================

    def walk_forward_train(
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
    ) -> list[WalkForwardResult]:
        """
        Walk-Forward滚动训练
        每个窗口: 训练模型 → 测试期预测 → 下一窗口重新训练
        gap期防止信息泄漏

        Args:
            data_df: 包含因子+收益率+日期的DataFrame
            factor_cols: 因子列名
            return_col: 收益率列名
            date_col: 日期列名
            train_window: 训练窗口(交易日数)
            test_window: 测试窗口
            gap: 训练/测试间隔
            retrain_freq: 重训练频率
            model_config: 模型参数
        """
        if date_col not in data_df.columns:
            logger.warning(f"Date column '{date_col}' not found")
            return []

        dates = sorted(data_df[date_col].unique())
        T = len(dates)
        results = []

        start = 0
        while start + train_window + gap + test_window <= T:
            train_end = start + train_window
            test_start = train_end + gap
            test_end = test_start + test_window

            train_dates = set(dates[start:train_end])
            test_dates = set(dates[test_start:test_end])

            train_data = data_df[data_df[date_col].isin(train_dates)]
            test_data = data_df[data_df[date_col].isin(test_dates)]

            if len(train_data) < self.min_train_samples or len(test_data) < 50:
                start += retrain_freq
                continue

            # 训练
            train_returns = train_data.set_index(train_data.index)[return_col]
            trained = self.train_lgbm(
                train_data[[*factor_cols, return_col]],
                train_returns,
                factor_cols,
                model_config=model_config,
            )

            if trained is None:
                start += retrain_freq
                continue

            # 测试期预测
            test_factor_df = test_data[factor_cols]
            test_returns = test_data[return_col]
            test_pred = self.predict(trained, test_factor_df, factor_cols)

            # 评估
            test_ic = self._calc_ic(test_pred.values, test_returns.values)
            test_rank_ic = self._calc_rank_ic(test_pred.values, test_returns.values)
            # ICIR需要多期IC序列，单期IC无法计算ICIR
            # 这里先记录IC，ICIR在所有窗口完成后用多期IC序列计算
            test_icir = np.nan

            wf_result = WalkForwardResult(
                train_start=dates[start],
                train_end=dates[train_end - 1],
                test_start=dates[test_start],
                test_end=dates[min(test_end - 1, T - 1)],
                model=trained,
                test_predictions=test_pred,
                test_ic=round(test_ic, 4),
                test_icir=round(test_icir, 2),
                test_rank_ic=round(test_rank_ic, 4),
            )
            results.append(wf_result)

            logger.info(
                f"WF window: train={dates[start]}~{dates[train_end - 1]}, "
                f"test={dates[test_start]}~{dates[min(test_end - 1, T - 1)]}, "
                f"IC={test_ic:.4f}, RankIC={test_rank_ic:.4f}",
            )

            start += retrain_freq

        if results:
            avg_ic = np.mean([r.test_ic for r in results])
            avg_rank_ic = np.mean([r.test_rank_ic for r in results])
            consistency = sum(1 for r in results if r.test_ic > 0) / len(results)

            # 用多期IC序列计算ICIR: ICIR = mean(IC) / std(IC)
            ic_series = np.array([r.test_ic for r in results])
            ic_std = np.std(ic_series) if len(ic_series) > 1 else 0
            overall_icir = float(np.mean(ic_series) / ic_std) if ic_std > 0 else 0.0
            # 回填每个窗口的ICIR为整体ICIR
            for r in results:
                r.test_icir = round(overall_icir, 2)

            logger.info(
                "Walk-Forward training completed",
                extra={
                    "n_windows": len(results),
                    "avg_ic": round(avg_ic, 4),
                    "avg_rank_ic": round(avg_rank_ic, 4),
                    "overall_icir": round(overall_icir, 2),
                    "consistency": round(consistency, 4),
                },
            )

        return results

    # ==================== 4. 预测 ====================

    def predict(self, trained_model: TrainedModel, factor_df: pd.DataFrame, factor_cols: list[str]) -> pd.Series:
        """
        使用训练好的模型预测

        Args:
            trained_model: TrainedModel对象
            factor_df: 因子值DataFrame
            factor_cols: 因子列名

        Returns:
            预测值Series (index与factor_df相同)
        """
        if trained_model.model is None:
            return pd.Series(dtype=float)

        # 准备特征
        available_cols = [c for c in factor_cols if c in factor_df.columns]
        if not available_cols:
            return pd.Series(dtype=float)

        X = factor_df[available_cols].values

        # 填充缺失值
        nan_mask = np.isnan(X).any(axis=1)
        X = np.nan_to_num(X, nan=0.0)

        # 标准化
        if trained_model.scaler is not None:
            try:
                X_scaled = trained_model.scaler.transform(X)
            except Exception:
                X_scaled = X
        else:
            X_scaled = X

        # 预测
        try:
            predictions = trained_model.model.predict(X_scaled)
        except Exception as e:
            logger.warning(f"Prediction failed: {e}")
            return pd.Series(dtype=float)

        result = pd.Series(predictions, index=factor_df.index)
        # 缺失值位置设为NaN
        result[nan_mask] = np.nan

        return result

    # ==================== 5. 模型持久化 ====================

    def save_model(self, trained_model: TrainedModel, name: str) -> str:
        """
        保存模型到磁盘

        Args:
            trained_model: TrainedModel对象
            name: 模型名称

        Returns:
            保存路径
        """
        import pickle

        model_path = self.model_dir / f"{name}.pkl"

        # 分离不可pickle的模型对象
        save_data = {
            "factor_cols": trained_model.factor_cols,
            "cv_metrics": trained_model.cv_metrics,
            "feature_importance": trained_model.feature_importance,
            "train_date": trained_model.train_date,
            "model_config": trained_model.model_config,
            "model_type": trained_model.model_type,
        }

        # 保存sklearn scaler
        if trained_model.scaler is not None:
            save_data["scaler"] = trained_model.scaler

        # 保存LightGBM模型
        if trained_model.model_type in ("lgbm", "lgbm_rank"):
            lgbm_path = self.model_dir / f"{name}_lgbm.txt"
            try:
                import lightgbm as lgb

                if isinstance(trained_model.model, lgb.LGBMRegressor):
                    trained_model.model.booster_.save_model(str(lgbm_path))
                else:
                    trained_model.model.save_model(str(lgbm_path))
                save_data["lgbm_path"] = str(lgbm_path)
            except Exception as e:
                logger.warning(f"Failed to save LightGBM model: {e}")
                save_data["model_pickle"] = pickle.dumps(trained_model.model)

        with open(model_path, "wb") as f:
            pickle.dump(save_data, f)

        logger.info(f"Model saved: {model_path}")
        return str(model_path)

    def load_model(self, name: str) -> TrainedModel | None:
        """
        从磁盘加载模型

        Args:
            name: 模型名称

        Returns:
            TrainedModel对象
        """
        import pickle

        model_path = self.model_dir / f"{name}.pkl"
        if not model_path.exists():
            logger.warning(f"Model not found: {model_path}")
            return None

        with open(model_path, "rb") as f:
            save_data = pickle.load(f)

        # 加载LightGBM模型
        model = None
        if "lgbm_path" in save_data:
            try:
                import lightgbm as lgb

                lgbm_path = save_data["lgbm_path"]
                if save_data.get("model_type") == "lgbm_rank":
                    model = lgb.Booster(model_file=lgbm_path)
                else:
                    booster = lgb.Booster(model_file=lgbm_path)
                    # 使用sklearn兼容方式加载: 先创建空模型再注入Booster
                    model = lgb.LGBMRegressor()
                    model.booster_ = booster  # 公开API
                    model._Booster = booster  # 兼容旧版本
                    model.fitted_ = True
                    # 设置n_features_in_避免sklearn check_is_fitted失败
                    if "factor_cols" in save_data:
                        model.n_features_in_ = len(save_data["factor_cols"])
            except Exception as e:
                logger.warning(f"Failed to load LightGBM model: {e}")
        elif "model_pickle" in save_data:
            model = pickle.loads(save_data["model_pickle"])

        trained = TrainedModel(
            model=model,
            scaler=save_data.get("scaler"),
            factor_cols=save_data.get("factor_cols", []),
            cv_metrics=save_data.get("cv_metrics", {}),
            feature_importance=save_data.get("feature_importance", {}),
            train_date=save_data.get("train_date"),
            model_config=save_data.get("model_config", {}),
            model_type=save_data.get("model_type", "lgbm"),
        )

        logger.info(f"Model loaded: {model_path}")
        return trained

    # ==================== 6. 特征重要性 ====================

    def get_feature_importance(self, trained_model: TrainedModel, top_n: int = 20) -> dict[str, float]:
        """
        获取特征重要性 (top N)

        Args:
            trained_model: TrainedModel对象
            top_n: 返回前N个重要特征

        Returns:
            {factor_name: importance} 按重要性降序
        """
        if not trained_model.feature_importance:
            return {}

        sorted_features = sorted(
            trained_model.feature_importance.items(),
            key=lambda x: -x[1],
        )

        return dict(sorted_features[:top_n])

    # ==================== 辅助方法 ====================

    def _prepare_training_data(
        self, factor_df: pd.DataFrame, return_series: pd.Series, factor_cols: list[str]
    ) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        """准备训练数据，处理缺失值"""
        available_cols = [c for c in factor_cols if c in factor_df.columns]
        if not available_cols:
            logger.warning("No valid factor columns found")
            return None, None, None

        # 对齐index
        common_idx = factor_df.index.intersection(return_series.index)
        if len(common_idx) < self.min_train_samples:
            logger.warning(f"Insufficient samples: {len(common_idx)}")
            return None, None, None

        X = factor_df.loc[common_idx, available_cols].values
        y = return_series.loc[common_idx].values

        # 清理缺失值
        valid_mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X = X[valid_mask]
        y = y[valid_mask]

        if len(X) < self.min_train_samples:
            logger.warning(f"Insufficient valid samples: {len(X)}")
            return None, None, None

        return X, y, np.where(valid_mask)[0]

    @staticmethod
    def _calc_ic(predictions: np.ndarray, actual: np.ndarray) -> float:
        """计算IC (Pearson相关系数)"""
        valid = ~(np.isnan(predictions) | np.isnan(actual))
        if valid.sum() < 10:
            return 0.0
        corr = np.corrcoef(predictions[valid], actual[valid])[0, 1]
        return corr if not np.isnan(corr) else 0.0

    @staticmethod
    def _calc_rank_ic(predictions: np.ndarray, actual: np.ndarray) -> float:
        """计算Rank IC (Spearman秩相关)"""
        valid = ~(np.isnan(predictions) | np.isnan(actual))
        if valid.sum() < 10:
            return 0.0
        pred_rank = pd.Series(predictions[valid]).rank()
        actual_rank = pd.Series(actual[valid]).rank()
        corr = pred_rank.corr(actual_rank)
        return corr if not np.isnan(corr) else 0.0

    @staticmethod
    def _summarize_cv_metrics(cv_metrics: dict) -> dict:
        """汇总CV指标"""
        fold_metrics = [v for k, v in cv_metrics.items() if k.startswith("fold_")]
        if not fold_metrics:
            return {}

        summary = {}
        for metric_name in ["ic", "rank_ic", "rmse"]:
            values = [m[metric_name] for m in fold_metrics if metric_name in m]
            if values:
                summary[metric_name] = round(np.mean(values), 4)
                summary[f"{metric_name}_std"] = round(np.std(values), 4)
                summary[f"{metric_name}_min"] = round(np.min(values), 4)
                summary[f"{metric_name}_max"] = round(np.max(values), 4)

        # ICIR = IC_mean / IC_std
        if "ic" in summary and "ic_std" in summary and summary["ic_std"] > 0:
            summary["icir"] = round(summary["ic"] / summary["ic_std"], 2)

        return summary
