"""
在线学习与模型自我优化引擎
机构级核心: 滚动重训练、指数梯度权重更新、动态模型平均、超参数自适应、预测校准
"""
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from datetime import date, datetime
import numpy as np
import pandas as pd
from app.core.logging import logger


@dataclass
class ModelPerformance:
    """模型表现跟踪"""
    model_id: str
    sharpe: float = 0.0
    ic: float = 0.0
    icir: float = 0.0
    hit_rate: float = 0.0
    max_drawdown: float = 0.0
    weight: float = 1.0
    last_retrain_date: Optional[date] = None
    n_retrains: int = 0


class OnlineLearningEngine:
    """
    在线学习引擎
    核心理念: 模型不是静态的，需要持续学习、适应、校准
    """

    # 默认超参数搜索空间
    DEFAULT_LGBM_PARAM_SPACE = {
        'n_estimators': [100, 200, 300, 500],
        'max_depth': [3, 4, 5, 6, 7],
        'learning_rate': [0.01, 0.02, 0.05, 0.1],
        'num_leaves': [15, 31, 63],
        'min_child_samples': [20, 50, 100],
        'subsample': [0.6, 0.7, 0.8, 0.9],
        'colsample_bytree': [0.6, 0.7, 0.8, 0.9],
        'reg_alpha': [0, 0.01, 0.1, 1.0],
        'reg_lambda': [0, 0.01, 0.1, 1.0],
    }

    def __init__(self, model_performances: Optional[Dict[str, ModelPerformance]] = None):
        self.model_performances = model_performances or {}
        self._scalers: Dict[str, StandardScaler] = {}

    # ==================== 1. Walk-Forward 滚动重训练 ====================

    def retrain_walk_forward(self,
                              train_data: pd.DataFrame,
                              factor_cols: List[str],
                              return_col: str = 'forward_return',
                              model_type: str = 'lgbm',
                              model_config: Optional[Dict] = None,
                              val_ratio: float = 0.2) -> Any:
        """
        Walk-Forward 滚动重训练
        在训练集上训练模型，用验证集做早停

        Args:
            train_data: 训练数据 (含因子列 + 收益率列)
            factor_cols: 因子列名
            return_col: 收益率列名
            model_type: 模型类型 (lgbm / linear / ensemble)
            model_config: 模型配置
            val_ratio: 验证集比例
        """
        if train_data.empty or not factor_cols:
            return None

        X = train_data[factor_cols].values
        y = train_data[return_col].values

        # 清理缺失值
        valid_mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X = X[valid_mask]
        y = y[valid_mask]

        if len(X) < 50:
            logger.warning("Insufficient training data", extra={"n_samples": len(X)})
            return None

        # 标准化
        try:
            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
        except ImportError:
            scaler = None
            X_mean, X_std = X.mean(axis=0), X.std(axis=0)
            X_std[X_std == 0] = 1
            X_scaled = (X - X_mean) / X_std

        # 时间序列分割 (不用随机分割，防止未来函数)
        split_idx = int(len(X) * (1 - val_ratio))
        X_train, X_val = X_scaled[:split_idx], X_scaled[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        if model_type == 'lgbm':
            model = self._train_lgbm(X_train, y_train, X_val, y_val, model_config)
        elif model_type == 'linear':
            model = self._train_linear(X_train, y_train, model_config)
        else:
            model = self._train_lgbm(X_train, y_train, X_val, y_val, model_config)

        if model is not None:
            model._scaler = scaler if scaler else None
            model._factor_cols = factor_cols

        logger.info(
            "Walk-forward retraining completed",
            extra={
                "model_type": model_type,
                "n_train": len(X_train),
                "n_val": len(X_val),
                "n_features": len(factor_cols),
            },
        )

        return model

    def _train_lgbm(self, X_train, y_train, X_val, y_val, config=None):
        """训练LightGBM模型"""
        try:
            import lightgbm as lgb

            default_config = {
                'objective': 'regression',
                'metric': 'mse',
                'n_estimators': 300,
                'max_depth': 5,
                'learning_rate': 0.05,
                'num_leaves': 31,
                'min_child_samples': 50,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.01,
                'reg_lambda': 0.01,
                'verbose': -1,
                'n_jobs': -1,
                'random_state': 42,
            }
            if config:
                default_config.update(config)

            model = lgb.LGBMRegressor(**default_config)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(30, verbose=False)],
            )
            return model
        except ImportError:
            logger.warning("LightGBM not available, falling back to linear model")
            return self._train_linear(X_train, y_train)

    def _train_linear(self, X_train, y_train, config=None):
        """训练线性模型 (Ridge)"""
        from sklearn.linear_model import Ridge
        alpha = (config or {}).get('alpha', 1.0)
        model = Ridge(alpha=alpha)
        model.fit(X_train, y_train)
        return model

    # ==================== 2. 指数梯度权重更新 (EGU) ====================

    def update_weights_egu(self,
                            current_weights: Dict[str, float],
                            prediction_errors: Dict[str, float],
                            learning_rate: float = 0.1,
                            min_weight: float = 0.01) -> Dict[str, float]:
        """
        指数梯度更新 (Exponentiated Gradient Update)
        w_k(t+1) = w_k(t) * exp(-η * loss_k(t)) / Z

        Args:
            current_weights: 当前模型权重
            prediction_errors: 各模型近期预测误差 (MSE或IC的负值)
            learning_rate: 学习率 η
            min_weight: 最小权重
        """
        if not current_weights or not prediction_errors:
            return current_weights

        models = list(current_weights.keys())
        n = len(models)
        if n == 0:
            return current_weights

        # EGU更新
        new_weights = {}
        for model_id in models:
            w = current_weights.get(model_id, 1.0 / n)
            error = prediction_errors.get(model_id, 0)
            # 误差越小，权重越大
            new_weights[model_id] = w * np.exp(-learning_rate * error)

        # 归一化
        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: max(v / total, min_weight) for k, v in new_weights.items()}
        else:
            new_weights = {k: 1.0 / n for k in models}

        # 再次归一化 (因为min_weight可能导致总和>1)
        total = sum(new_weights.values())
        new_weights = {k: v / total for k, v in new_weights.items()}

        logger.info(
            "EGU weight update completed",
            extra={
                "n_models": n,
                "learning_rate": learning_rate,
                "weight_changes": {
                    k: round(new_weights[k] - current_weights.get(k, 0), 4)
                    for k in models
                },
            },
        )

        return new_weights

    # ==================== 3. 动态模型平均 (DMA) ====================

    def dynamic_model_average(self,
                               model_predictions: Dict[str, pd.Series],
                               recent_performance: Dict[str, ModelPerformance],
                               window: int = 60,
                               forgetting_factor: float = 0.95) -> pd.Series:
        """
        动态模型平均 (Dynamic Model Averaging)
        基于各模型近期表现动态调整权重，遗忘因子使近期表现权重更大

        Args:
            model_predictions: 各模型预测值
            recent_performance: 各模型近期表现
            window: 表现评估窗口
            forgetting_factor: 遗忘因子 (0-1, 越小遗忘越快)
        """
        if not model_predictions:
            return pd.Series(dtype=float)

        models = list(model_predictions.keys())
        n = len(models)

        if n == 1:
            return model_predictions[models[0]]

        # 基于ICIR计算权重
        weights = {}
        for model_id in models:
            perf = recent_performance.get(model_id)
            if perf:
                # ICIR越高权重越大，遗忘因子使近期表现更重要
                w = abs(perf.icir) * (forgetting_factor ** (window - perf.n_retrains))
                weights[model_id] = max(w, 0.01)
            else:
                weights[model_id] = 0.01

        # 归一化
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

        # 加权平均
        result = pd.Series(0.0, index=model_predictions[models[0]].index)
        for model_id, pred in model_predictions.items():
            result += weights[model_id] * pred

        logger.info(
            "Dynamic model averaging completed",
            extra={
                "n_models": n,
                "weights": {k: round(v, 4) for k, v in weights.items()},
            },
        )

        return result

    # ==================== 4. 超参数自适应 (贝叶斯优化) ====================

    def auto_tune_hyperparams(self,
                               param_space: Dict[str, List],
                               objective_fn: Callable[[Dict], float],
                               n_trials: int = 50,
                               timeout: int = 600,
                               direction: str = 'maximize') -> Dict[str, Any]:
        """
        超参数自适应优化
        优先使用Optuna贝叶斯优化，回退到随机搜索

        Args:
            param_space: 参数搜索空间
            objective_fn: 目标函数 (输入参数dict，输出float)
            n_trials: 试验次数
            timeout: 超时(秒)
            direction: 'maximize' or 'minimize'
        """
        best_params = {}
        best_score = -np.inf if direction == 'maximize' else np.inf

        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)

            def _objective(trial):
                params = {}
                for param_name, param_values in param_space.items():
                    if isinstance(param_values, list):
                        if all(isinstance(v, int) for v in param_values):
                            params[param_name] = trial.suggest_int(
                                param_name, min(param_values), max(param_values)
                            )
                        elif all(isinstance(v, float) for v in param_values):
                            params[param_name] = trial.suggest_float(
                                param_name, min(param_values), max(param_values)
                            )
                        else:
                            params[param_name] = trial.suggest_categorical(
                                param_name, param_values
                            )
                return objective_fn(params)

            study = optuna.create_study(direction=direction)
            study.optimize(_objective, n_trials=n_trials, timeout=timeout)

            best_params = study.best_params
            best_score = study.best_value

            logger.info(
                "Optuna hyperparameter optimization completed",
                extra={
                    "n_trials": len(study.trials),
                    "best_score": round(best_score, 6),
                    "best_params": best_params,
                },
            )

        except ImportError:
            # 回退: 随机搜索
            logger.info("Optuna not available, using random search")
            np.random.seed(42)

            for trial_idx in range(n_trials):
                params = {}
                for param_name, param_values in param_space.items():
                    params[param_name] = np.random.choice(param_values)

                score = objective_fn(params)

                if direction == 'maximize':
                    if score > best_score:
                        best_score = score
                        best_params = params
                else:
                    if score < best_score:
                        best_score = score
                        best_params = params

            logger.info(
                "Random search hyperparameter optimization completed",
                extra={
                    "n_trials": n_trials,
                    "best_score": round(best_score, 6),
                },
            )

        return {
            'best_params': best_params,
            'best_score': best_score,
            'n_trials': n_trials,
        }

    # ==================== 5. 预测校准 ====================

    def calibrate_predictions(self,
                               raw_predictions: np.ndarray,
                               validation_returns: np.ndarray,
                               method: str = 'isotonic') -> Any:
        """
        预测校准
        将原始预测值映射到更准确的概率/收益空间

        Args:
            raw_predictions: 原始预测值
            validation_returns: 验证集实际收益
            method: 'isotonic' (等距回归) 或 'platt' (Platt缩放)

        Returns:
            校准器对象 (可用于transform新数据)
        """
        valid_mask = ~(np.isnan(raw_predictions) | np.isnan(validation_returns))
        X = raw_predictions[valid_mask].reshape(-1, 1)
        y = validation_returns[valid_mask]

        if len(X) < 30:
            logger.warning("Insufficient data for calibration", extra={"n_samples": len(X)})
            return None

        if method == 'isotonic':
            try:
                from sklearn.isotonic import IsotonicRegression
                calibrator = IsotonicRegression(out_of_bounds='clip')
                calibrator.fit(X.ravel(), y)
            except ImportError:
                logger.warning("sklearn not available for isotonic calibration")
                return None
        elif method == 'platt':
            try:
                from sklearn.linear_model import LogisticRegression
                y_binary = (y > np.median(y)).astype(int)
                calibrator = LogisticRegression()
                calibrator.fit(X, y_binary)
            except ImportError:
                logger.warning("sklearn not available for Platt calibration")
                return None
        else:
            calibrator = None

        if calibrator:
            logger.info(
                "Prediction calibration completed",
                extra={"method": method, "n_samples": len(X)},
            )

        return calibrator

    def apply_calibration(self, calibrator: Any,
                           raw_predictions: np.ndarray,
                           method: str = 'isotonic') -> np.ndarray:
        """应用校准器"""
        if calibrator is None:
            return raw_predictions

        X = raw_predictions.reshape(-1, 1)
        if method == 'isotonic':
            return calibrator.transform(X.ravel())
        elif method == 'platt':
            return calibrator.predict_proba(X)[:, 1]
        return raw_predictions

    # ==================== 6. 模型表现跟踪 ====================

    def update_model_performance(self, model_id: str,
                                   predictions: np.ndarray,
                                   actual_returns: np.ndarray,
                                   trade_date: Optional[date] = None) -> ModelPerformance:
        """更新模型表现"""
        valid_mask = ~(np.isnan(predictions) | np.isnan(actual_returns))
        pred = predictions[valid_mask]
        actual = actual_returns[valid_mask]

        if len(pred) < 10:
            return self.model_performances.get(model_id, ModelPerformance(model_id=model_id))

        # IC
        ic = np.corrcoef(pred, actual)[0, 1] if len(pred) > 1 else 0

        # ICIR (假设日频)
        ic_std = 1.0 / np.sqrt(len(pred)) if len(pred) > 1 else 1.0
        icir = ic / ic_std if ic_std > 0 else 0

        # 命中率
        hit_rate = ((pred > 0) == (actual > 0)).mean()

        # Sharpe (基于预测收益构建多空组合)
        long_mask = pred > np.median(pred)
        short_mask = pred < np.median(pred)
        if long_mask.any() and short_mask.any():
            long_return = actual[long_mask].mean()
            short_return = actual[short_mask].mean()
            daily_return = long_return - short_return
            sharpe = daily_return / (actual.std() + 1e-8) * np.sqrt(252)
        else:
            sharpe = 0

        perf = ModelPerformance(
            model_id=model_id,
            sharpe=sharpe,
            ic=ic,
            icir=icir,
            hit_rate=hit_rate,
            last_retrain_date=trade_date,
        )

        # 更新重训练次数
        if model_id in self.model_performances:
            perf.n_retrains = self.model_performances[model_id].n_retrains + 1

        self.model_performances[model_id] = perf

        return perf

    def get_best_model(self, metric: str = 'icir') -> Optional[str]:
        """获取最佳模型"""
        if not self.model_performances:
            return None
        return max(self.model_performances.keys(),
                   key=lambda k: getattr(self.model_performances[k], metric, 0))

    # ==================== 7. 自适应重训练调度 ====================

    def should_retrain(self, model_id: str,
                        current_ic: float,
                        min_ic: float = 0.02,
                        min_icir: float = 0.3,
                        days_since_last: int = 0,
                        retrain_interval: int = 60) -> bool:
        """
        判断是否需要重训练
        触发条件:
        1. 距上次重训练超过retrain_interval天
        2. 近期IC低于阈值
        3. 近期ICIR低于阈值
        """
        if days_since_last >= retrain_interval:
            return True

        if abs(current_ic) < min_ic:
            return True

        perf = self.model_performances.get(model_id)
        if perf and abs(perf.icir) < min_icir:
            return True

        return False
