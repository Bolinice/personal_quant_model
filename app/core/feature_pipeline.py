"""
特征工程流水线 - 自动化特征生成、筛选和版本管理

功能:
  1. 特征生成：自动生成衍生特征
  2. 特征筛选：基于重要性和相关性筛选特征
  3. 特征评估：计算IC、IR、覆盖率等指标
  4. 特征版本管理：追踪特征变更历史
  5. 特征存储：持久化特征数据
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

logger = logging.getLogger(__name__)


@dataclass
class FeatureMetrics:
    """特征评估指标"""

    name: str
    ic_mean: float  # IC均值
    ic_std: float  # IC标准差
    ir: float  # 信息比率 (IC均值/IC标准差)
    coverage: float  # 覆盖率
    correlation_max: float  # 与其他特征的最大相关系数
    importance: float  # 特征重要性（综合评分）


@dataclass
class FeatureVersion:
    """特征版本"""

    version: str
    timestamp: str
    author: str
    description: str
    features: list[str]
    metrics: dict[str, dict[str, float]]


class FeatureGenerator:
    """特征生成器 - 自动生成衍生特征"""

    @staticmethod
    def generate_interaction_features(
        df: pd.DataFrame,
        feature_pairs: list[tuple[str, str]],
        operations: list[str] = ["multiply", "divide", "add", "subtract"],
    ) -> pd.DataFrame:
        """
        生成交互特征

        Args:
            df: 原始特征DataFrame
            feature_pairs: 特征对列表
            operations: 操作类型列表

        Returns:
            包含交互特征的DataFrame
        """
        result = df.copy()

        for f1, f2 in feature_pairs:
            if f1 not in df.columns or f2 not in df.columns:
                continue

            # 乘法
            if "multiply" in operations:
                result[f"{f1}_x_{f2}"] = df[f1] * df[f2]

            # 除法
            if "divide" in operations:
                result[f"{f1}_div_{f2}"] = df[f1] / (df[f2] + 1e-8)

            # 加法
            if "add" in operations:
                result[f"{f1}_add_{f2}"] = df[f1] + df[f2]

            # 减法
            if "subtract" in operations:
                result[f"{f1}_sub_{f2}"] = df[f1] - df[f2]

        logger.info("生成交互特征: %d 个特征对 -> %d 个新特征", len(feature_pairs), len(result.columns) - len(df.columns))
        return result

    @staticmethod
    def generate_polynomial_features(df: pd.DataFrame, features: list[str], degree: int = 2) -> pd.DataFrame:
        """
        生成多项式特征

        Args:
            df: 原始特征DataFrame
            features: 特征列表
            degree: 多项式阶数

        Returns:
            包含多项式特征的DataFrame
        """
        result = df.copy()

        for feature in features:
            if feature not in df.columns:
                continue

            for d in range(2, degree + 1):
                result[f"{feature}_pow{d}"] = df[feature] ** d

        logger.info("生成多项式特征: %d 个特征 -> %d 个新特征", len(features), len(result.columns) - len(df.columns))
        return result

    @staticmethod
    def generate_rolling_features(
        df: pd.DataFrame,
        features: list[str],
        windows: list[int] = [5, 10, 20],
        operations: list[str] = ["mean", "std", "max", "min"],
    ) -> pd.DataFrame:
        """
        生成滚动窗口特征

        Args:
            df: 原始特征DataFrame（需要按时间排序）
            features: 特征列表
            windows: 窗口大小列表
            operations: 操作类型列表

        Returns:
            包含滚动特征的DataFrame
        """
        result = df.copy()

        for feature in features:
            if feature not in df.columns:
                continue

            for window in windows:
                if "mean" in operations:
                    result[f"{feature}_ma{window}"] = df[feature].rolling(window).mean()

                if "std" in operations:
                    result[f"{feature}_std{window}"] = df[feature].rolling(window).std()

                if "max" in operations:
                    result[f"{feature}_max{window}"] = df[feature].rolling(window).max()

                if "min" in operations:
                    result[f"{feature}_min{window}"] = df[feature].rolling(window).min()

        logger.info("生成滚动特征: %d 个特征 -> %d 个新特征", len(features), len(result.columns) - len(df.columns))
        return result


class FeatureSelector:
    """特征筛选器 - 基于重要性和相关性筛选特征"""

    def __init__(
        self,
        ic_threshold: float = 0.02,
        ir_threshold: float = 0.5,
        coverage_threshold: float = 0.8,
        correlation_threshold: float = 0.9,
    ):
        self.ic_threshold = ic_threshold
        self.ir_threshold = ir_threshold
        self.coverage_threshold = coverage_threshold
        self.correlation_threshold = correlation_threshold

    def select_by_ic(self, metrics: dict[str, FeatureMetrics]) -> list[str]:
        """基于IC筛选特征"""
        selected = []
        for name, metric in metrics.items():
            if abs(metric.ic_mean) >= self.ic_threshold and metric.ir >= self.ir_threshold:
                selected.append(name)

        logger.info("IC筛选: %d/%d 特征通过", len(selected), len(metrics))
        return selected

    def select_by_coverage(self, df: pd.DataFrame, features: list[str]) -> list[str]:
        """基于覆盖率筛选特征"""
        selected = []
        for feature in features:
            if feature not in df.columns:
                continue

            coverage = 1 - df[feature].isna().sum() / len(df)
            if coverage >= self.coverage_threshold:
                selected.append(feature)

        logger.info("覆盖率筛选: %d/%d 特征通过", len(selected), len(features))
        return selected

    def select_by_correlation(self, df: pd.DataFrame, features: list[str]) -> list[str]:
        """基于相关性筛选特征（去除高度相关的特征）"""
        if not features:
            return []

        # 计算相关系数矩阵
        corr_matrix = df[features].corr().abs()

        # 找出高度相关的特征对
        selected = []
        dropped = set()

        for i, feature in enumerate(features):
            if feature in dropped:
                continue

            selected.append(feature)

            # 找出与当前特征高度相关的其他特征
            for j in range(i + 1, len(features)):
                other_feature = features[j]
                if other_feature in dropped:
                    continue

                if corr_matrix.loc[feature, other_feature] >= self.correlation_threshold:
                    dropped.add(other_feature)

        logger.info("相关性筛选: %d/%d 特征通过 (去除 %d 个高相关特征)", len(selected), len(features), len(dropped))
        return selected


class FeatureEvaluator:
    """特征评估器 - 计算特征评估指标"""

    @staticmethod
    def calculate_ic(factor: pd.Series, returns: pd.Series) -> tuple[float, float]:
        """
        计算IC (Information Coefficient)

        Args:
            factor: 因子值
            returns: 收益率

        Returns:
            (IC均值, IC标准差)
        """
        # 对齐索引
        common_idx = factor.index.intersection(returns.index)
        factor_aligned = factor.loc[common_idx]
        returns_aligned = returns.loc[common_idx]

        # 去除NaN
        mask = ~(factor_aligned.isna() | returns_aligned.isna())
        factor_clean = factor_aligned[mask]
        returns_clean = returns_aligned[mask]

        if len(factor_clean) < 10:
            return 0.0, 0.0

        # 计算Spearman相关系数
        ic, _ = spearmanr(factor_clean, returns_clean)

        return ic, 0.0  # 单期IC，标准差为0

    @staticmethod
    def calculate_coverage(factor: pd.Series) -> float:
        """计算覆盖率"""
        return 1 - factor.isna().sum() / len(factor)

    @staticmethod
    def evaluate_features(
        df: pd.DataFrame, features: list[str], returns: pd.Series | None = None
    ) -> dict[str, FeatureMetrics]:
        """
        评估特征

        Args:
            df: 特征DataFrame
            features: 特征列表
            returns: 收益率Series（可选）

        Returns:
            特征评估指标字典
        """
        metrics = {}

        # 计算相关系数矩阵
        corr_matrix = df[features].corr().abs()

        for feature in features:
            if feature not in df.columns:
                continue

            # 计算IC
            ic_mean, ic_std = 0.0, 0.0
            if returns is not None:
                ic_mean, ic_std = FeatureEvaluator.calculate_ic(df[feature], returns)

            # 计算IR
            ir = ic_mean / (ic_std + 1e-8) if ic_std > 0 else 0.0

            # 计算覆盖率
            coverage = FeatureEvaluator.calculate_coverage(df[feature])

            # 计算与其他特征的最大相关系数
            correlation_max = 0.0
            if feature in corr_matrix.columns:
                corr_values = corr_matrix[feature].drop(feature)
                if len(corr_values) > 0:
                    correlation_max = corr_values.max()

            # 计算综合重要性评分
            importance = abs(ic_mean) * coverage * (1 - correlation_max * 0.5)

            metrics[feature] = FeatureMetrics(
                name=feature,
                ic_mean=ic_mean,
                ic_std=ic_std,
                ir=ir,
                coverage=coverage,
                correlation_max=correlation_max,
                importance=importance,
            )

        logger.info("特征评估完成: %d 个特征", len(metrics))
        return metrics


class FeaturePipeline:
    """特征工程流水线 - 统一管理特征生成、筛选和版本控制"""

    def __init__(self, feature_dir: str | Path = "data/features", version_dir: str | Path = "data/feature_versions"):
        self.feature_dir = Path(feature_dir)
        self.version_dir = Path(version_dir)
        self.feature_dir.mkdir(parents=True, exist_ok=True)
        self.version_dir.mkdir(parents=True, exist_ok=True)

        self.generator = FeatureGenerator()
        self.selector = FeatureSelector()
        self.evaluator = FeatureEvaluator()
        self.version_history: list[FeatureVersion] = []

        self._load_version_history()

    def run(
        self,
        df: pd.DataFrame,
        base_features: list[str],
        returns: pd.Series | None = None,
        generate_interactions: bool = True,
        generate_polynomials: bool = False,
        author: str = "system",
        description: str = "自动生成特征",
    ) -> tuple[pd.DataFrame, list[str]]:
        """
        运行特征工程流水线

        Args:
            df: 原始特征DataFrame
            base_features: 基础特征列表
            returns: 收益率Series（用于IC计算）
            generate_interactions: 是否生成交互特征
            generate_polynomials: 是否生成多项式特征
            author: 作者
            description: 描述

        Returns:
            (特征DataFrame, 筛选后的特征列表)
        """
        logger.info("=" * 80)
        logger.info("特征工程流水线启动")
        logger.info("=" * 80)

        # 1. 特征生成
        result_df = df.copy()

        if generate_interactions:
            # 生成交互特征（选择重要特征对）
            important_features = base_features[:10]  # 取前10个重要特征
            feature_pairs = [(important_features[i], important_features[j]) for i in range(len(important_features)) for j in range(i + 1, len(important_features))]
            result_df = self.generator.generate_interaction_features(result_df, feature_pairs[:20])  # 限制特征对数量

        if generate_polynomials:
            # 生成多项式特征
            result_df = self.generator.generate_polynomial_features(result_df, base_features[:5], degree=2)

        all_features = [c for c in result_df.columns if c not in ["security_id", "trade_date"]]
        logger.info("特征生成完成: %d 个特征", len(all_features))

        # 2. 特征评估
        metrics = self.evaluator.evaluate_features(result_df, all_features, returns)

        # 3. 特征筛选
        # 3a. IC筛选
        selected_by_ic = self.selector.select_by_ic(metrics) if returns is not None else all_features

        # 3b. 覆盖率筛选
        selected_by_coverage = self.selector.select_by_coverage(result_df, selected_by_ic)

        # 3c. 相关性筛选
        selected_features = self.selector.select_by_correlation(result_df, selected_by_coverage)

        logger.info("特征筛选完成: %d -> %d 个特征", len(all_features), len(selected_features))

        # 4. 创建版本
        self._create_version(selected_features, metrics, author, description)

        logger.info("=" * 80)
        logger.info("特征工程流水线完成")
        logger.info("=" * 80)

        return result_df[selected_features], selected_features

    def _create_version(
        self, features: list[str], metrics: dict[str, FeatureMetrics], author: str, description: str
    ) -> None:
        """创建特征版本"""
        version = FeatureVersion(
            version=datetime.now().strftime("%Y%m%d_%H%M%S"),
            timestamp=datetime.now().isoformat(),
            author=author,
            description=description,
            features=features,
            metrics={name: asdict(metric) for name, metric in metrics.items() if name in features},
        )

        self.version_history.append(version)

        # 保存版本到文件
        version_file = self.version_dir / f"features_{version.version}.json"
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(asdict(version), f, ensure_ascii=False, indent=2, default=str)

        logger.info("特征版本已创建: %s", version.version)

    def _load_version_history(self) -> None:
        """加载版本历史"""
        version_files = sorted(self.version_dir.glob("features_*.json"))
        for version_file in version_files[-10:]:  # 只加载最近10个版本
            try:
                with open(version_file, encoding="utf-8") as f:
                    data = json.load(f)
                version = FeatureVersion(**data)
                self.version_history.append(version)
            except Exception as e:
                logger.warning("加载版本失败 %s: %s", version_file, e)

    def get_version_history(self, limit: int = 10) -> list[FeatureVersion]:
        """获取版本历史"""
        return self.version_history[-limit:]

    def save_features(self, df: pd.DataFrame, features: list[str], name: str) -> None:
        """保存特征数据"""
        output_file = self.feature_dir / f"{name}.parquet"
        df[features].to_parquet(output_file, index=False)
        logger.info("特征已保存到: %s", output_file)

    def load_features(self, name: str) -> pd.DataFrame:
        """加载特征数据"""
        input_file = self.feature_dir / f"{name}.parquet"
        if not input_file.exists():
            raise FileNotFoundError(f"特征文件不存在: {input_file}")

        df = pd.read_parquet(input_file)
        logger.info("特征已加载: %s (%d 行 x %d 列)", input_file, len(df), len(df.columns))
        return df
