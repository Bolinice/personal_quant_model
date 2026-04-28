"""
多因子模型打分模块
实现ADD 8节: 等权加权、人工权重、IC/IR动态加权、分层筛选
机构级增强: LightGBM排序模型、Stacking集成、对抗性验证、滚动IC动态加权
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.factor_preprocess import preprocess_factor_values
from app.core.logging import logger
from app.models.factors import Factor, FactorValue
from app.models.models import Model, ModelFactorWeight


class MultiFactorScorer:
    """多因子评分器 - 符合ADD 8节"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== 加权方法 (ADD 8.2节) ====================

    def equal_weight(self, factor_scores: pd.DataFrame) -> pd.Series:
        """
        等权加权 (ADD 8.2.1节)
        Score_i = (1/K) * Σ z_{i,k}
        """
        return factor_scores.mean(axis=1)

    def manual_weight(self, factor_scores: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
        """
        人工权重加权 (ADD 8.2.2节)
        Score_i = Σ w_k * z_{i,k}, Σw_k = 1
        """
        weighted_sum = pd.Series(0.0, index=factor_scores.index)
        weight_sum = 0

        for col, weight in weights.items():
            if col in factor_scores.columns:
                weighted_sum += factor_scores[col] * weight
                weight_sum += abs(weight)

        if weight_sum == 0:
            return self.equal_weight(factor_scores)  # 权重全零时退化等权，避免除零

        return weighted_sum / weight_sum

    def ic_weight(self, factor_scores: pd.DataFrame, ic_values: dict[str, float]) -> pd.Series:
        """
        IC动态加权 (ADD 8.2.3节)
        w_k ∝ IC_k / Σ|IC_j|
        """
        weighted_sum = pd.Series(0.0, index=factor_scores.index)
        ic_sum = 0

        for col, ic in ic_values.items():
            if col in factor_scores.columns and not np.isnan(ic):
                weighted_sum += factor_scores[col] * ic
                ic_sum += abs(ic)

        if ic_sum == 0:
            return self.equal_weight(factor_scores)

        return weighted_sum / ic_sum

    def icir_weight(self, factor_scores: pd.DataFrame, icir_values: dict[str, float]) -> pd.Series:
        """
        ICIR加权 (ADD 8.2.3节)
        w_k ∝ ICIR_k / Σ|ICIR_j|
        """
        weighted_sum = pd.Series(0.0, index=factor_scores.index)
        icir_sum = 0

        for col, icir in icir_values.items():
            if col in factor_scores.columns and not np.isnan(icir):
                weighted_sum += factor_scores[col] * icir
                icir_sum += abs(icir)

        if icir_sum == 0:
            return self.equal_weight(factor_scores)

        return weighted_sum / icir_sum

    # ==================== IC加权 + ML融合 ====================

    def fused_ic_ml_score(
        self,
        factor_scores: pd.DataFrame,
        ml_predictions: pd.Series,
        ic_weights: dict[str, float],
        ml_weight: float = 0.4,
        ic_weight_total: float = 0.6,
        method: str = "simple",
    ) -> pd.Series:
        """
        IC加权 + ML模型预测融合
        将传统因子IC加权评分与ML模型预测融合，兼顾可解释性和非线性捕获能力

        Args:
            factor_scores: 因子得分矩阵 (行=股票, 列=因子)
            ml_predictions: ML模型预测值Series (index=股票代码)
            ic_weights: IC/ICIR权重 {factor_name: weight}
            ml_weight: ML预测权重 (默认0.4)
            ic_weight_total: IC加权权重 (默认0.6, ml_weight+ic_weight_total应=1)
            method: 融合方法
                'simple' - 简单加权: score = α*ic_score + (1-α)*ml_score
                'dynamic' - 动态权重: 根据近期IC和ML的ICIR动态调整α
                'hierarchical' - 分层融合: IC粗筛 → ML精排

        Returns:
            融合评分Series
        """
        # 1. 计算IC加权评分
        if ic_weights:
            ic_score = self.icir_weight(factor_scores, ic_weights)  # ICIR比IC更稳定，IC除以标准差降低噪声因子权重
        else:
            ic_score = self.equal_weight(factor_scores)

        # 2. 标准化ML预测 (z-score)
        # ML输出量纲与IC评分不同，必须对齐尺度才能融合
        ml_score = ml_predictions.copy()
        ml_mean = ml_score.mean()
        ml_std = ml_score.std()
        ml_score = (ml_score - ml_mean) / ml_std if ml_std > 0 else pd.Series(0.0, index=ml_score.index)

        # 3. 对齐index
        common_idx = ic_score.index.intersection(ml_score.index)
        if len(common_idx) == 0:
            return ic_score

        ic_aligned = ic_score.loc[common_idx]
        ml_aligned = ml_score.loc[common_idx]

        # 4. 融合
        if method == "simple":
            result = self._fuse_simple(ic_aligned, ml_aligned, ic_weight_total, ml_weight)

        elif method == "dynamic":
            result = self._fuse_dynamic(ic_aligned, ml_aligned, ic_weight_total, ml_weight)

        elif method == "hierarchical":
            result = self._fuse_hierarchical(ic_aligned, ml_aligned, factor_scores.loc[common_idx])

        else:
            result = self._fuse_simple(ic_aligned, ml_aligned, ic_weight_total, ml_weight)

        # 保留不在ML预测中的股票 (仅IC评分)
        # ML模型可能因缺失值无法预测部分股票，这些股票仍用IC评分兜底
        missing_idx = ic_score.index.difference(ml_score.index)
        if len(missing_idx) > 0:
            result = pd.concat([result, ic_score.loc[missing_idx]])

        logger.info(
            "IC+ML fusion completed",
            extra={
                "method": method,
                "ml_weight": ml_weight,
                "n_common": len(common_idx),
                "n_ic_only": len(missing_idx),
            },
        )

        return result

    @staticmethod
    def _fuse_simple(ic_score: pd.Series, ml_score: pd.Series, ic_weight: float, ml_weight: float) -> pd.Series:
        """简单加权融合: score = α*ic + (1-α)*ml"""
        return ic_weight * ic_score + ml_weight * ml_score

    @staticmethod
    def _fuse_dynamic(
        ic_score: pd.Series, ml_score: pd.Series, ic_base_weight: float, ml_base_weight: float
    ) -> pd.Series:
        """
        动态权重融合
        根据IC和ML评分的分散度动态调整权重
        分散度越高(信息含量越大)的信号获得更大权重
        核心思想: 信号区分度强时更可信，区分度弱(趋同)时降低其权重
        """
        ic_dispersion = ic_score.std()
        ml_dispersion = ml_score.std()

        if ic_dispersion + ml_dispersion > 0:
            # 按分散度比例分配权重，1e-8防止除零
            ic_adj = ic_base_weight * (ic_dispersion / (ic_dispersion + ml_dispersion + 1e-8))
            ml_adj = ml_base_weight * (ml_dispersion / (ic_dispersion + ml_dispersion + 1e-8))
            total = ic_adj + ml_adj
            if total > 0:
                ic_adj /= total
                ml_adj /= total
        else:
            ic_adj = ic_base_weight
            ml_adj = ml_base_weight

        return ic_adj * ic_score + ml_adj * ml_score

    @staticmethod
    def _fuse_hierarchical(
        ic_score: pd.Series, ml_score: pd.Series, factor_scores: pd.DataFrame, top_pct: float = 0.5
    ) -> pd.Series:
        """
        分层融合: IC粗筛 → ML精排
        1. 用IC评分选前top_pct的股票池
        2. 在股票池内用ML评分排序
        3. 池外股票用IC评分
        """
        threshold = ic_score.quantile(1 - top_pct)
        pool_mask = ic_score >= threshold

        result = ic_score.copy()
        if pool_mask.sum() > 10:  # 池内至少10只股票才用ML精排，样本过少ML排序不可靠
            # 池内: ML评分排序 (保留相对排序)
            pool_ml = ml_score.loc[pool_mask]
            # 将ML评分映射到IC评分的池内范围
            # 映射尺度而非直接替换，保证池内外评分可比
            ic_pool_min = ic_score.loc[pool_mask].min()
            ic_pool_max = ic_score.loc[pool_mask].max()
            ml_min = pool_ml.min()
            ml_max = pool_ml.max()
            if ml_max > ml_min:
                mapped_ml = ic_pool_min + (pool_ml - ml_min) / (ml_max - ml_min) * (ic_pool_max - ic_pool_min)
                result.loc[pool_mask] = mapped_ml

        return result

    def hierarchical_filter(self, factor_scores: pd.DataFrame, hierarchy: list[dict]) -> pd.Series:
        """
        分层筛选 (ADD 8.2.4节)
        例如: 先按质量因子筛前50% → 再按估值筛前50% → 最后按动量排序

        Args:
            factor_scores: 因子得分矩阵
            hierarchy: 分层配置 [{factors: [...], method: 'top_pct', param: 0.5}, ...]
        """
        remaining = factor_scores.index.tolist()

        for step in hierarchy:
            factors = step.get("factors", [])
            method = step.get("method", "top_pct")
            param = step.get("param", 0.5)

            if not factors:
                continue

            # 计算当前层综合得分
            step_scores = factor_scores.loc[remaining, factors].mean(axis=1)

            if method == "top_pct":
                threshold = step_scores.quantile(1 - param)
                remaining = step_scores[step_scores >= threshold].index.tolist()
            elif method == "top_n":
                remaining = step_scores.nlargest(int(param)).index.tolist()

            if not remaining:
                break

        # 最终排序
        return factor_scores.loc[remaining].mean(axis=1)

    # ==================== 机构级扩展评分方法 ====================

    def rolling_ic_weight(self, factor_scores: pd.DataFrame, ic_history: pd.DataFrame, lookback: int = 60) -> pd.Series:
        """
        滚动IC动态加权
        使用过去lookback期的IC均值作为权重，比静态IC更适应市场变化

        Args:
            factor_scores: 当期因子得分矩阵
            ic_history: IC历史 DataFrame with columns [trade_date, factor_code, ic]
            lookback: 回看期数
        """
        if ic_history.empty:
            return self.equal_weight(factor_scores)

        # 计算滚动IC均值
        # 滚动IC比全历史IC更能捕捉因子有效性时变特征
        recent_ic = ic_history.tail(lookback)
        ic_means = recent_ic.groupby("factor_code")["ic"].mean()

        weighted_sum = pd.Series(0.0, index=factor_scores.index)
        ic_sum = 0

        for col in factor_scores.columns:
            if col in ic_means.index and not np.isnan(ic_means[col]):
                weighted_sum += factor_scores[col] * ic_means[col]
                ic_sum += abs(ic_means[col])

        if ic_sum == 0:
            return self.equal_weight(factor_scores)

        return weighted_sum / ic_sum

    def compute_ic_weights(
        self,
        factor_df: pd.DataFrame,
        return_df: pd.DataFrame,
        lookback: int = 60,
        method: str = "icir",
        forward_period: int = 20,
    ) -> dict[str, float]:
        """
        计算IC/ICIR权重 (向量化: merge+groupby替代三重循环)

        Args:
            factor_df: 因子值DataFrame, 需包含 trade_date, security_id, factor_code, value
            return_df: 收益率DataFrame, 需包含 trade_date, security_id, forward_return
            lookback: 回看期数
            method: 'ic' = IC均值加权, 'icir' = ICIR加权
            forward_period: 前瞻期

        Returns:
            {factor_code: weight}
        """
        if factor_df.empty or return_df.empty:
            return {}

        factor_codes = factor_df["factor_code"].unique() if "factor_code" in factor_df.columns else []
        if len(factor_codes) == 0:
            return {}

        # 取最近lookback期的日期
        all_dates = sorted(factor_df["trade_date"].unique())
        recent_dates = set(all_dates[-lookback:])

        # 向量化: merge因子和收益，一次计算所有IC
        # 替代逐因子逐日期三重循环，性能提升显著
        merged = pd.merge(
            factor_df[factor_df["trade_date"].isin(recent_dates)][
                ["trade_date", "security_id", "factor_code", "value"]
            ],
            return_df[["trade_date", "security_id", "forward_return"]],
            on=["trade_date", "security_id"],
            how="inner",
        )
        if merged.empty:
            return {}

        # 按factor_code+trade_date分组计算IC
        def _calc_ic(g):
            if len(g) < 10:  # 截面样本不足10时IC不可靠，跳过
                return np.nan
            valid = g["value"].notna() & g["forward_return"].notna()
            if valid.sum() < 10:
                return np.nan
            return g.loc[valid, "value"].corr(g.loc[valid, "forward_return"])

        ic_df = (
            merged.groupby(["factor_code", "trade_date"]).apply(_calc_ic).reset_index(name="ic")
        )
        ic_df = ic_df.dropna(subset=["ic"])

        if ic_df.empty:
            return {}

        # 计算权重
        weights = {}
        for fc in factor_codes:
            fc_ic = ic_df[ic_df["factor_code"] == fc]["ic"]
            if len(fc_ic) == 0:
                continue
            if method == "ic":
                weights[fc] = fc_ic.mean()
            elif method == "icir":
                ic_mean = fc_ic.mean()
                ic_std = fc_ic.std()
                if ic_std > 0:
                    weights[fc] = ic_mean / ic_std
                else:
                    weights[fc] = 0

        # 归一化: 只保留正权重
        # IC/ICIR为负说明因子反向有效，应反向使用而非直接丢弃，
        # 但此处归一化阶段只保留正权重，反向因子在预处理阶段已通过direction翻转
        positive_weights = {k: v for k, v in weights.items() if v > 0}
        if not positive_weights:
            return weights

        total = sum(positive_weights.values())
        return {k: v / total for k, v in positive_weights.items()}

    def lightgbm_score(
        self,
        factor_scores: pd.DataFrame,
        returns: pd.Series = None,
        model_params: dict | None = None,
        monotone_constraints: dict[str, int] | None = None,
    ) -> pd.Series:
        """
        LightGBM排序模型
        将股票选择建模为排序问题，使用lambdarank目标函数

        Args:
            factor_scores: 因子得分矩阵
            returns: 收益率标签(训练时需要)
            model_params: LightGBM参数
            monotone_constraints: 单调约束 {factor_name: 1或-1}
        """
        try:
            import lightgbm as lgb
        except ImportError:
            logger.warning("lightgbm not available, falling back to ICIR weight")
            return self.icir_weight(factor_scores, dict.fromkeys(factor_scores.columns, 1.0))

        if returns is None:
            logger.warning("No returns provided for LightGBM, using equal weight")
            return self.equal_weight(factor_scores)

        params = model_params or {
            "objective": "lambdarank",
            "metric": "ndcg",
            "learning_rate": 0.05,
            "max_depth": 4,  # 浅树防止过拟合，A股截面数据噪声大
            "num_leaves": 15,  # 与max_depth=4匹配，2^4=16
            "min_data_in_leaf": 50,  # 叶节点最少样本，避免在小盘股上过拟合
            "feature_fraction": 0.8,  # 列采样降低因子间共线性风险
            "bagging_fraction": 0.8,  # 行采样增强鲁棒性
            "bagging_freq": 5,
            "lambda_l1": 0.1,  # L1正则化，自动做因子选择
            "lambda_l2": 0.1,  # L2正则化，抑制共线性因子权重过大
            "verbosity": -1,
        }

        # 准备训练数据
        valid_mask = returns.notna() & factor_scores.notna().all(axis=1)
        X_train = factor_scores.loc[valid_mask].values
        y_train = returns.loc[valid_mask].values

        if len(X_train) < 100:  # 样本不足100时ML模型不可靠，退化等权
            return self.equal_weight(factor_scores)

        # 将收益率转换为排名标签
        # LambdaRank用相对排序而非绝对收益训练，对异常值更鲁棒
        y_rank = pd.Series(y_train).rank(pct=True).values

        # 单调约束
        # 强制模型在指定因子上单调递增/递减，保证经济逻辑不被ML破坏
        if monotone_constraints:
            constraints = []
            for col in factor_scores.columns:
                constraints.append(monotone_constraints.get(col, 0))
            params["monotone_constraints"] = constraints

        # 训练模型
        train_data = lgb.Dataset(X_train, label=y_rank, group=[len(X_train)])
        model = lgb.train(params, train_data, num_boost_round=100)

        # 预测
        predictions = model.predict(factor_scores.values)
        return pd.Series(predictions, index=factor_scores.index)

    def stacking_score(
        self,
        factor_scores: pd.DataFrame,
        returns: pd.Series = None,
        base_models: list[str] | None = None,
        n_folds: int = 5,
    ) -> pd.Series:
        """
        Stacking集成评分 (机构级: K折交叉验证+元学习器)
        1. K折生成out-of-fold预测
        2. 训练元学习器(Ridge回归)组合基模型
        3. 预测时各基模型预测→元学习器组合

        Args:
            factor_scores: 因子得分矩阵
            returns: 收益率标签
            base_models: 基模型列表 ['linear', 'lightgbm', 'icir']
            n_folds: 交叉验证折数
        """
        if base_models is None:
            base_models = ["linear", "icir"]

        if returns is None or returns.isna().all():
            # 无标签时退化为简单平均
            base_predictions = {}
            for model_name in base_models:
                if model_name == "linear":
                    base_predictions["linear"] = self.equal_weight(factor_scores)
                elif model_name == "icir":
                    base_predictions["icir"] = self.icir_weight(
                        factor_scores, dict.fromkeys(factor_scores.columns, 1.0)
                    )
            if not base_predictions:
                return self.equal_weight(factor_scores)
            meta_df = pd.DataFrame(base_predictions)
            return meta_df.mean(axis=1)

        # K折交叉验证生成out-of-fold预测
        n_samples = len(factor_scores)
        indices = np.arange(n_samples)
        np.random.shuffle(indices)
        fold_size = n_samples // n_folds

        oof_predictions = {name: np.full(n_samples, np.nan) for name in base_models}

        for fold in range(n_folds):
            val_idx = indices[fold * fold_size : (fold + 1) * fold_size]
            train_idx = np.setdiff1d(indices, val_idx)

            train_scores = factor_scores.iloc[train_idx]
            train_returns = returns.iloc[train_idx]
            val_scores = factor_scores.iloc[val_idx]

            # 各基模型在训练集训练，验证集预测
            for model_name in base_models:
                if model_name == "linear":
                    pred = self.equal_weight(val_scores)
                elif model_name == "icir":
                    # 在训练集上计算ICIR权重
                    icir_vals = {}
                    for col in train_scores.columns:
                        corr = train_scores[col].corr(train_returns)
                        if not np.isnan(corr):
                            icir_vals[col] = corr
                    pred = self.icir_weight(val_scores, icir_vals) if icir_vals else self.equal_weight(val_scores)
                elif model_name == "lightgbm":
                    pred = self.lightgbm_score(val_scores, train_returns)
                else:
                    pred = self.equal_weight(val_scores)

                oof_predictions[model_name][val_idx] = pred.values

        # 训练元学习器 (Ridge回归)
        oof_df = pd.DataFrame(oof_predictions, index=factor_scores.index)
        valid_mask = oof_df.notna().all(axis=1) & returns.notna()

        if valid_mask.sum() < 20:  # OOF样本不足20时元学习器不可靠，退化为简单平均
            return oof_df.mean(axis=1)

        try:
            from sklearn.linear_model import Ridge

            meta_X = oof_df.loc[valid_mask].values
            meta_y = returns.loc[valid_mask].values
            meta_learner = Ridge(alpha=1.0)  # Ridge做元学习器而非OLS，正则化防止对单一基模型过拟合
            meta_learner.fit(meta_X, meta_y)

            # 用元学习器组合基模型的完整预测
            full_predictions = {}
            for model_name in base_models:
                if model_name == "linear":
                    full_predictions[model_name] = self.equal_weight(factor_scores)
                elif model_name == "icir":
                    full_predictions[model_name] = self.icir_weight(
                        factor_scores, dict.fromkeys(factor_scores.columns, 1.0)
                    )
                elif model_name == "lightgbm":
                    full_predictions[model_name] = self.lightgbm_score(factor_scores, returns)

            full_df = pd.DataFrame(full_predictions, index=factor_scores.index)
            combined = meta_learner.predict(full_df.values)
            return pd.Series(combined, index=factor_scores.index)

        except ImportError:
            # sklearn不可用，退化为加权平均
            return oof_df.mean(axis=1)

    def adversarial_validation(
        self, train_data: pd.DataFrame, test_data: pd.DataFrame, factor_cols: list[str], threshold_auc: float = 0.55
    ) -> dict:
        # AUC=0.5表示无法区分，>0.55即认为存在可检测的分布漂移
        # 阈值设0.55而非0.5是为了容忍轻微噪声，避免误报
        """
        对抗性验证
        检测训练集和测试集的分布漂移，识别失效因子

        Args:
            train_data: 训练期数据
            test_data: 测试期数据
            factor_cols: 因子列名
            threshold_auc: AUC阈值(超过此值表示存在分布漂移)

        Returns:
            漂移检测结果
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.metrics import roc_auc_score
        except ImportError:
            logger.warning("sklearn not available for adversarial validation")
            return {"has_drift": False, "drifted_factors": []}

        # 构建二分类问题: 区分训练期和测试期
        train_features = train_data[factor_cols].fillna(0)
        test_features = test_data[factor_cols].fillna(0)

        X = pd.concat([train_features, test_features], axis=0)
        y = np.concatenate([np.zeros(len(train_features)), np.ones(len(test_features))])

        clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        clf.fit(X, y)
        y_pred_proba = clf.predict_proba(X)[:, 1]
        auc = roc_auc_score(y, y_pred_proba)

        # 识别漂移最大的因子
        feature_importance = dict(zip(factor_cols, clf.feature_importances_))
        drifted_factors = [
            f
            for f, imp in sorted(feature_importance.items(), key=lambda x: -x[1])
            if imp > 1.0 / len(factor_cols) * 2  # 重要性超过平均2倍视为漂移因子
        ]

        return {
            "has_drift": auc > threshold_auc,
            "auc": round(auc, 4),
            "drifted_factors": drifted_factors,
            "feature_importance": feature_importance,
        }

    # ==================== 无数据库便捷函数 ====================

    @staticmethod
    def score_from_factor_df(
        factor_df: pd.DataFrame,
        method: str = "equal",
        weights: dict[str, float] | None = None,
        ic_values: dict[str, float] | None = None,
        icir_values: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """
        不依赖数据库的评分便捷函数
        直接从因子DataFrame计算综合评分

        Args:
            factor_df: 因子得分矩阵（行=股票，列=因子）
            method: 加权方法 ('equal', 'manual', 'ic', 'icir')
            weights: 人工权重
            ic_values: IC值
            icir_values: ICIR值

        Returns:
            评分结果DataFrame，包含 total_score, rank, quantile
        """
        scorer = MultiFactorScorer.__new__(MultiFactorScorer)
        scorer.db = None

        # 排除非因子列
        # 这些元数据列不是因子得分，参与加权计算会导致结果错误
        skip_cols = {"security_id", "ts_code", "trade_date", "data_source", "amount_is_estimated"}
        factor_cols = [c for c in factor_df.columns if c not in skip_cols]
        scores_matrix = factor_df[factor_cols].copy()

        # 计算综合得分
        if method == "equal":
            factor_df["total_score"] = scorer.equal_weight(scores_matrix)
        elif method == "manual" and weights:
            factor_df["total_score"] = scorer.manual_weight(scores_matrix, weights)
        elif method == "ic" and ic_values:
            factor_df["total_score"] = scorer.ic_weight(scores_matrix, ic_values)
        elif method == "icir" and icir_values:
            factor_df["total_score"] = scorer.icir_weight(scores_matrix, icir_values)
        else:
            factor_df["total_score"] = scorer.equal_weight(scores_matrix)

        # 排名
        factor_df["rank"] = factor_df["total_score"].rank(ascending=False)
        factor_df["quantile"] = factor_df["total_score"].rank(pct=True)

        return factor_df

    # ==================== 综合评分计算 ====================

    def calculate_scores(
        self, model_id: int, trade_date: date, ts_codes: list[str] | None = None, weighting_method: str = "equal"
    ) -> pd.DataFrame:
        """
        计算多因子综合评分

        Args:
            model_id: 模型ID
            trade_date: 交易日期
            ts_codes: 股票代码列表
            weighting_method: 加权方法

        Returns:
            评分结果DataFrame
        """
        model = self.db.query(Model).filter(Model.id == model_id).first()
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # 获取因子权重
        factor_weights = (
            self.db.query(ModelFactorWeight)
            .filter(
                ModelFactorWeight.model_id == model_id,
                ModelFactorWeight.is_active,
            )
            .all()
        )

        if not factor_weights:
            raise ValueError(f"No factor weights for model {model_id}")

        # 批量查询所有因子定义 (避免N+1)
        factor_ids = [fw.factor_id for fw in factor_weights]
        factors = self.db.query(Factor).filter(Factor.id.in_(factor_ids)).all()
        factor_map = {f.id: f for f in factors}

        # 批量查询所有因子值 (避免N+1)
        fv_query = self.db.query(FactorValue).filter(
            FactorValue.factor_id.in_(factor_ids),
            FactorValue.trade_date == trade_date,
        )
        if ts_codes:
            fv_query = fv_query.filter(FactorValue.security_id.in_(ts_codes))
        all_values = fv_query.all()

        # 按factor_id分组
        values_by_factor = {}
        for v in all_values:
            values_by_factor.setdefault(v.factor_id, []).append(v)

        # 获取因子值并构建得分矩阵
        factor_scores = {}
        factor_codes = {}
        factor_directions = {}

        for fw in factor_weights:
            factor = factor_map.get(fw.factor_id)
            if not factor:
                continue

            values = values_by_factor.get(fw.factor_id, [])
            if not values:
                continue

            series = pd.Series({v.security_id: v.value for v in values})

            # 预处理
            # direction=1因子越大越好，direction=-1因子越小越好，预处理时会翻转
            direction = fw.direction or factor.direction or 1
            series = preprocess_factor_values(series, direction=direction)

            factor_scores[factor.factor_code] = series
            factor_codes[fw.factor_id] = factor.factor_code
            factor_directions[factor.factor_code] = direction

        if not factor_scores:
            raise ValueError(f"No factor values for {trade_date}")

        # 构建得分矩阵
        scores_df = pd.DataFrame(factor_scores)

        # 计算综合得分
        if weighting_method == "equal":
            scores_df["total_score"] = self.equal_weight(scores_df)
        elif weighting_method == "manual":
            weights = {factor_codes[fw.factor_id]: fw.weight for fw in factor_weights}
            scores_df["total_score"] = self.manual_weight(scores_df, weights)
        elif weighting_method == "ic":
            # IC动态加权 (机构级: 从实际IC计算权重)
            ic_weights = self.compute_ic_weights(
                self._build_factor_ic_data(factor_weights, trade_date, ts_codes),
                self._get_forward_return_data(trade_date),
                method="ic",
            )
            if ic_weights:
                scores_df["total_score"] = self.ic_weight(scores_df, ic_weights)
            else:
                scores_df["total_score"] = self.equal_weight(scores_df)
        elif weighting_method == "icir":
            # ICIR动态加权
            icir_weights = self.compute_ic_weights(
                self._build_factor_ic_data(factor_weights, trade_date, ts_codes),
                self._get_forward_return_data(trade_date),
                method="icir",
            )
            if icir_weights:
                scores_df["total_score"] = self.icir_weight(scores_df, icir_weights)
            else:
                scores_df["total_score"] = self.equal_weight(scores_df)
        elif weighting_method == "lightgbm":
            scores_df["total_score"] = self.lightgbm_score(scores_df)
        elif weighting_method == "stacking":
            scores_df["total_score"] = self.stacking_score(scores_df)
        elif weighting_method == "rolling_ic":
            scores_df["total_score"] = self.equal_weight(scores_df)
        else:
            scores_df["total_score"] = self.equal_weight(scores_df)

        # 排名
        scores_df["rank"] = scores_df["total_score"].rank(ascending=False)
        scores_df["quantile"] = scores_df["total_score"].rank(pct=True)

        return scores_df

    def select_top_stocks(self, scores_df: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
        """选择Top N股票"""
        return scores_df.nsmallest(top_n, "rank")

    def generate_portfolio_weights(
        self,
        scores_df: pd.DataFrame,
        top_n: int = 50,
        method: str = "equal",
        prev_weights: pd.Series = None,
        turnover_penalty: float = 0.0,
        risk_model=None,
        expected_returns: pd.Series = None,
        cov_matrix: np.ndarray = None,
    ) -> pd.Series:
        """
        生成组合权重 (ADD 10.3节 + 机构级增强)

        Args:
            scores_df: 评分结果
            top_n: 持仓数量
            method: 权重方法 ('equal', 'score', 'benchmark_enhanced', 'mean_cvar', 'hrp')
            prev_weights: 上期权重(用于换手率控制)
            turnover_penalty: 换手率惩罚系数(lambda_turn)
            risk_model: 风险模型实例(用于Mean-CVaR)
            expected_returns: 预期收益(用于Mean-CVaR)
            cov_matrix: 协方差矩阵(用于Mean-CVaR/HRP)
        """
        top_stocks = self.select_top_stocks(scores_df, top_n)

        if method == "equal":
            # 等权 (ADD 10.3.1节)
            weights = pd.Series(1.0 / top_n, index=top_stocks.index)
        elif method == "score":
            # 分数加权 (ADD 10.3.2节)
            scores = top_stocks["total_score"]
            scores = scores - scores.min() + 0.01  # +0.01避免最低分股票权重为零
            weights = scores / scores.sum()
        elif method == "benchmark_enhanced":
            # 基准增强权重 (ADD 10.3.3节) - 简化实现
            scores = top_stocks["total_score"]
            scores = scores - scores.min() + 0.01
            weights = scores / scores.sum()
        elif method == "mean_cvar":
            # Mean-CVaR优化
            weights = self._mean_cvar_weights(top_stocks, risk_model, expected_returns, cov_matrix)
        elif method == "hrp":
            # 层次风险平价
            weights = self._hrp_weights(top_stocks, cov_matrix)
        else:
            weights = pd.Series(1.0 / top_n, index=top_stocks.index)

        # 换手率惩罚: 如果有上期权重，应用L1惩罚
        if prev_weights is not None and turnover_penalty > 0:
            weights = self._apply_turnover_penalty(weights, prev_weights, turnover_penalty)

        return weights

    def _mean_cvar_weights(
        self, top_stocks: pd.DataFrame, risk_model, expected_returns: pd.Series, cov_matrix: np.ndarray
    ) -> pd.Series:
        """Mean-CVaR优化权重 (委托给PortfolioOptimizer)"""
        if risk_model is None or expected_returns is None:
            scores = top_stocks["total_score"]
            scores = scores - scores.min() + 0.01
            return scores / scores.sum()

        try:
            from app.core.portfolio_optimizer import PortfolioOptimizer

            optimizer = PortfolioOptimizer()
            result = optimizer.mean_cvar_optimize(
                expected_returns=expected_returns.values,
                cov_matrix=cov_matrix,
                max_weight=1.0 / len(top_stocks) * 2,  # 单只股票权重上限为等权的2倍，兼顾集中度与灵活性
            )
            if "weights" in result:
                return pd.Series(result["weights"], index=top_stocks.index)
        except Exception as e:
            logger.warning(f"Mean-CVaR optimization failed: {e}")

        scores = top_stocks["total_score"]
        scores = scores - scores.min() + 0.01
        return scores / scores.sum()

    def _hrp_weights(self, top_stocks: pd.DataFrame, cov_matrix: np.ndarray = None) -> pd.Series:
        """层次风险平价 (委托给PortfolioOptimizer)"""
        n = len(top_stocks)
        if cov_matrix is None or n < 3:
            return pd.Series(1.0 / n, index=top_stocks.index)

        try:
            from app.core.portfolio_optimizer import PortfolioOptimizer

            optimizer = PortfolioOptimizer()
            return optimizer.hrp_optimize(cov_matrix, index=top_stocks.index)
        except Exception as e:
            logger.warning(f"HRP failed: {e}, falling back to equal weight")
            return pd.Series(1.0 / n, index=top_stocks.index)

    def _apply_turnover_penalty(self, weights: pd.Series, prev_weights: pd.Series, penalty: float) -> pd.Series:
        """
        L1换手率惩罚
        优化: max w'*alpha - lambda_turn * |w - w_prev|_1

        简化实现: 对换手部分施加惩罚
        """
        common = weights.index.intersection(prev_weights.index)
        if len(common) == 0:
            return weights

        turnover = (weights.loc[common] - prev_weights.loc[common]).abs().sum()

        # 如果换手率过高，向prev_weights收缩
        if turnover > 0 and penalty > 0:
            shrinkage = min(penalty * turnover, 0.5)  # 最多收缩50%，防止过度锚定上期权重丧失调仓能力
            adjusted = weights * (1 - shrinkage) + prev_weights.reindex(weights.index).fillna(0) * shrinkage
            # 归一化
            if adjusted.sum() > 0:
                adjusted = adjusted / adjusted.sum()
            return adjusted

        return weights

    def calc_market_impact(
        self,
        target_weights: pd.Series,
        prev_weights: pd.Series,
        daily_volumes: pd.Series,
        volatilities: pd.Series,
        total_aum: float,
    ) -> pd.Series:
        """
        平方根市场冲击模型 (Almgren-Chriss简化)
        Impact = sigma * sqrt(Q / (0.1 * V))

        Args:
            target_weights: 目标权重
            prev_weights: 当前权重
            daily_volumes: 日均成交额
            volatilities: 日波动率
            total_aum: 总AUM
        """
        common = target_weights.index.intersection(prev_weights.index).intersection(daily_volumes.index)

        if len(common) == 0:
            return pd.Series(0.0, index=target_weights.index)

        # 交易金额
        weight_change = (target_weights.loc[common] - prev_weights.loc[common]).abs()
        trade_amount = weight_change * total_aum

        # 市场冲击
        impact = pd.Series(0.0, index=common)
        for idx in common:
            if daily_volumes.loc[idx] > 0:
                participation = trade_amount.loc[idx] / daily_volumes.loc[idx]
                vol = volatilities.get(idx, 0.02)
                impact.loc[idx] = vol * np.sqrt(participation / 0.1)  # 平方根法则，0.1为参与率归一化基准

        return impact

    def close(self):
        if self.db:
            self.db.close()

    # ==================== IC权重计算辅助方法 ====================

    def _build_factor_ic_data(
        self, factor_weights, trade_date: date, ts_codes: list[str] | None = None
    ) -> pd.DataFrame:
        """构建IC计算所需的因子数据 (批量查询，避免N+1)"""
        factor_ids = [fw.factor_id for fw in factor_weights]

        # 批量查询因子定义
        factors = self.db.query(Factor).filter(Factor.id.in_(factor_ids)).all()
        factor_map = {f.id: f for f in factors}

        # 批量查询因子值
        fv_query = self.db.query(FactorValue).filter(
            FactorValue.factor_id.in_(factor_ids),
            FactorValue.trade_date == trade_date,
        )
        if ts_codes:
            fv_query = fv_query.filter(FactorValue.security_id.in_(ts_codes))
        all_values = fv_query.all()

        records = []
        for v in all_values:
            factor = factor_map.get(v.factor_id)
            if not factor:
                continue
            records.append(
                {
                    "trade_date": trade_date,
                    "security_id": v.security_id,
                    "factor_code": factor.factor_code,
                    "value": v.value,
                }
            )
        return pd.DataFrame(records) if records else pd.DataFrame()

    def _get_forward_return_data(self, trade_date: date, forward_period: int = 20) -> pd.DataFrame:
        # forward_period=20对应约1个月交易日，是因子预测的典型时间窗口
        """获取前瞻收益数据 (向量化计算，避免逐股票循环)"""
        try:
            from datetime import timedelta

            from app.models.market import StockDaily

            end_date = trade_date + timedelta(days=forward_period + 30)  # +30天缓冲确保覆盖自然日中非交易日
            stocks = (
                self.db.query(StockDaily)
                .filter(
                    StockDaily.trade_date >= trade_date,
                    StockDaily.trade_date <= end_date,
                )
                .all()
            )
            if not stocks:
                return pd.DataFrame()
            price_df = pd.DataFrame(
                [
                    {
                        "trade_date": s.trade_date,
                        "security_id": s.ts_code,
                        "close": float(s.close) if s.close else np.nan,
                    }
                    for s in stocks
                ]
            )
            # 向量化计算前瞻收益
            # 按股票分组shift，避免逐股票循环，性能显著提升
            price_df = price_df.dropna(subset=["close"]).sort_values(["security_id", "trade_date"])
            price_df["fwd_close"] = price_df.groupby("security_id")["close"].shift(-forward_period)
            price_df["forward_return"] = price_df["fwd_close"] / price_df["close"] - 1
            result = price_df[["trade_date", "security_id", "forward_return"]].dropna(subset=["forward_return"])
            return result if not result.empty else pd.DataFrame()
        except Exception:
            return pd.DataFrame()
