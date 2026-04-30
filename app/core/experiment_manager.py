"""
实验管理平台

功能：
1. 实验版本控制：记录每次实验的参数、代码版本、数据版本
2. 参数追踪：自动记录所有超参数和配置
3. 结果对比：对比不同实验的回测结果
4. 可视化：生成实验对比图表
5. 最佳实验：自动识别最优实验配置

作者：Kiro
日期：2026-05
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict, field

from app.core.logging import logger


@dataclass
class ExperimentConfig:
    """实验配置"""
    # 基础信息
    name: str
    description: str
    tags: list[str] = field(default_factory=list)

    # 策略参数
    strategy_params: dict[str, Any] = field(default_factory=dict)

    # 因子参数
    factor_params: dict[str, Any] = field(default_factory=dict)

    # 回测参数
    backtest_params: dict[str, Any] = field(default_factory=dict)

    # 风险参数
    risk_params: dict[str, Any] = field(default_factory=dict)

    # 版本信息
    code_version: Optional[str] = None  # git commit hash
    data_version: Optional[str] = None  # 数据版本标识

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    def get_hash(self) -> str:
        """计算配置哈希值，用于去重"""
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]


@dataclass
class ExperimentResult:
    """实验结果"""
    # 收益指标
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float

    # 风险指标
    volatility: float
    downside_volatility: float
    var_95: float
    cvar_95: float

    # 交易指标
    turnover_rate: float
    win_rate: float
    profit_loss_ratio: float

    # 因子指标
    ic_mean: float
    ic_ir: float
    ic_win_rate: float

    # 其他指标
    total_trades: int
    holding_period: float

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    def get_score(self, weights: Optional[dict[str, float]] = None) -> float:
        """
        计算综合评分

        Args:
            weights: 指标权重，默认为均衡权重

        Returns:
            综合评分（0-100）
        """
        if weights is None:
            weights = {
                "annual_return": 0.25,
                "sharpe_ratio": 0.25,
                "max_drawdown": 0.15,
                "ic_ir": 0.15,
                "turnover_rate": 0.10,
                "win_rate": 0.10,
            }

        # 归一化各指标到0-100
        score = 0.0

        # 年化收益（假设15-30%为优秀）
        score += weights["annual_return"] * min(self.annual_return / 0.30 * 100, 100)

        # 夏普比率（假设1.5-3.0为优秀）
        score += weights["sharpe_ratio"] * min(self.sharpe_ratio / 3.0 * 100, 100)

        # 最大回撤（越小越好，假设5-20%）
        score += weights["max_drawdown"] * max((0.20 - abs(self.max_drawdown)) / 0.15 * 100, 0)

        # IC信息比率（假设1.0-3.0为优秀）
        score += weights["ic_ir"] * min(self.ic_ir / 3.0 * 100, 100)

        # 换手率（越低越好，假设50-200%）
        score += weights["turnover_rate"] * max((2.0 - self.turnover_rate) / 1.5 * 100, 0)

        # 胜率（假设50-70%为优秀）
        score += weights["win_rate"] * min(self.win_rate / 0.70 * 100, 100)

        return round(score, 2)


@dataclass
class Experiment:
    """实验记录"""
    id: str
    config: ExperimentConfig
    result: Optional[ExperimentResult] = None
    status: str = "created"  # created, running, completed, failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    artifacts: dict[str, str] = field(default_factory=dict)  # 文件路径

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        data = {
            "id": self.id,
            "config": self.config.to_dict(),
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "artifacts": self.artifacts,
        }
        if self.result:
            data["result"] = self.result.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Experiment":
        """从字典创建"""
        config = ExperimentConfig(**data["config"])
        result = ExperimentResult(**data["result"]) if data.get("result") else None
        return cls(
            id=data["id"],
            config=config,
            result=result,
            status=data["status"],
            created_at=data["created_at"],
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error_message=data.get("error_message"),
            artifacts=data.get("artifacts", {}),
        )


class ExperimentManager:
    """实验管理器"""

    def __init__(self, experiment_dir: str = "data/experiments"):
        """
        初始化实验管理器

        Args:
            experiment_dir: 实验数据目录
        """
        self.experiment_dir = Path(experiment_dir)
        self.experiment_dir.mkdir(parents=True, exist_ok=True)

        # 实验索引文件
        self.index_file = self.experiment_dir / "index.json"
        self._load_index()

        logger.info(f"实验管理器初始化完成，目录: {self.experiment_dir}")

    def _load_index(self):
        """加载实验索引"""
        if self.index_file.exists():
            with open(self.index_file, "r", encoding="utf-8") as f:
                self._index = json.load(f)
        else:
            self._index = {"experiments": {}, "tags": {}}

    def _save_index(self):
        """保存实验索引"""
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, ensure_ascii=False)

    def create_experiment(
        self,
        name: str,
        description: str,
        config: dict[str, Any],
        tags: Optional[list[str]] = None,
    ) -> Experiment:
        """
        创建新实验

        Args:
            name: 实验名称
            description: 实验描述
            config: 实验配置
            tags: 标签列表

        Returns:
            实验对象
        """
        # 生成实验ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exp_id = f"exp_{timestamp}"

        # 创建实验配置
        exp_config = ExperimentConfig(
            name=name,
            description=description,
            tags=tags or [],
            strategy_params=config.get("strategy_params", {}),
            factor_params=config.get("factor_params", {}),
            backtest_params=config.get("backtest_params", {}),
            risk_params=config.get("risk_params", {}),
            code_version=config.get("code_version"),
            data_version=config.get("data_version"),
        )

        # 创建实验对象
        experiment = Experiment(id=exp_id, config=exp_config)

        # 保存实验
        self._save_experiment(experiment)

        # 更新索引
        self._index["experiments"][exp_id] = {
            "name": name,
            "description": description,
            "tags": tags or [],
            "created_at": experiment.created_at,
            "status": experiment.status,
        }

        # 更新标签索引
        for tag in tags or []:
            if tag not in self._index["tags"]:
                self._index["tags"][tag] = []
            self._index["tags"][tag].append(exp_id)

        self._save_index()

        logger.info(f"创建实验: {exp_id} - {name}")
        return experiment

    def _save_experiment(self, experiment: Experiment):
        """保存实验到文件"""
        exp_file = self.experiment_dir / f"{experiment.id}.json"
        with open(exp_file, "w", encoding="utf-8") as f:
            json.dump(experiment.to_dict(), f, indent=2, ensure_ascii=False)

    def get_experiment(self, exp_id: str) -> Optional[Experiment]:
        """
        获取实验

        Args:
            exp_id: 实验ID

        Returns:
            实验对象，不存在返回None
        """
        exp_file = self.experiment_dir / f"{exp_id}.json"
        if not exp_file.exists():
            return None

        with open(exp_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return Experiment.from_dict(data)

    def update_experiment(
        self,
        exp_id: str,
        status: Optional[str] = None,
        result: Optional[ExperimentResult] = None,
        error_message: Optional[str] = None,
        artifacts: Optional[dict[str, str]] = None,
    ):
        """
        更新实验状态

        Args:
            exp_id: 实验ID
            status: 状态
            result: 结果
            error_message: 错误信息
            artifacts: 产物文件路径
        """
        experiment = self.get_experiment(exp_id)
        if not experiment:
            raise ValueError(f"实验不存在: {exp_id}")

        # 更新状态
        if status:
            experiment.status = status
            if status == "running" and not experiment.started_at:
                experiment.started_at = datetime.now().isoformat()
            elif status in ["completed", "failed"]:
                experiment.completed_at = datetime.now().isoformat()

        # 更新结果
        if result:
            experiment.result = result

        # 更新错误信息
        if error_message:
            experiment.error_message = error_message

        # 更新产物
        if artifacts:
            experiment.artifacts.update(artifacts)

        # 保存
        self._save_experiment(experiment)

        # 更新索引
        self._index["experiments"][exp_id]["status"] = experiment.status
        self._save_index()

        logger.info(f"更新实验: {exp_id}, 状态: {status}")

    def list_experiments(
        self,
        tags: Optional[list[str]] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[Experiment]:
        """
        列出实验

        Args:
            tags: 标签过滤
            status: 状态过滤
            limit: 最大数量

        Returns:
            实验列表
        """
        exp_ids = list(self._index["experiments"].keys())

        # 标签过滤
        if tags:
            filtered_ids = set()
            for tag in tags:
                if tag in self._index["tags"]:
                    filtered_ids.update(self._index["tags"][tag])
            exp_ids = [eid for eid in exp_ids if eid in filtered_ids]

        # 状态过滤
        if status:
            exp_ids = [
                eid for eid in exp_ids
                if self._index["experiments"][eid]["status"] == status
            ]

        # 按创建时间倒序
        exp_ids.sort(
            key=lambda eid: self._index["experiments"][eid]["created_at"],
            reverse=True,
        )

        # 限制数量
        exp_ids = exp_ids[:limit]

        # 加载实验
        experiments = []
        for exp_id in exp_ids:
            exp = self.get_experiment(exp_id)
            if exp:
                experiments.append(exp)

        return experiments

    def compare_experiments(
        self,
        exp_ids: list[str],
        metrics: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        对比实验

        Args:
            exp_ids: 实验ID列表
            metrics: 对比指标，None表示所有指标

        Returns:
            对比结果
        """
        if metrics is None:
            metrics = [
                "annual_return",
                "sharpe_ratio",
                "max_drawdown",
                "calmar_ratio",
                "ic_mean",
                "ic_ir",
                "turnover_rate",
                "win_rate",
            ]

        comparison = {
            "experiments": [],
            "metrics": {},
            "best": {},
        }

        # 收集实验数据
        for exp_id in exp_ids:
            exp = self.get_experiment(exp_id)
            if not exp or not exp.result:
                continue

            exp_data = {
                "id": exp.id,
                "name": exp.config.name,
                "score": exp.result.get_score(),
            }

            for metric in metrics:
                value = getattr(exp.result, metric, None)
                if value is not None:
                    exp_data[metric] = value

                    # 更新指标统计
                    if metric not in comparison["metrics"]:
                        comparison["metrics"][metric] = {
                            "values": [],
                            "best_exp": None,
                            "best_value": None,
                        }

                    comparison["metrics"][metric]["values"].append(value)

                    # 更新最佳值（收益类指标越大越好，风险类指标越小越好）
                    is_better = False
                    if metric in ["annual_return", "sharpe_ratio", "calmar_ratio", "ic_mean", "ic_ir", "win_rate"]:
                        # 越大越好
                        if (comparison["metrics"][metric]["best_value"] is None or
                            value > comparison["metrics"][metric]["best_value"]):
                            is_better = True
                    else:
                        # 越小越好
                        if (comparison["metrics"][metric]["best_value"] is None or
                            value < comparison["metrics"][metric]["best_value"]):
                            is_better = True

                    if is_better:
                        comparison["metrics"][metric]["best_value"] = value
                        comparison["metrics"][metric]["best_exp"] = exp.id

            comparison["experiments"].append(exp_data)

        # 找出综合评分最高的实验
        if comparison["experiments"]:
            best_exp = max(comparison["experiments"], key=lambda x: x["score"])
            comparison["best"]["overall"] = best_exp["id"]
            comparison["best"]["score"] = best_exp["score"]

        return comparison

    def get_best_experiment(
        self,
        tags: Optional[list[str]] = None,
        metric: str = "score",
    ) -> Optional[Experiment]:
        """
        获取最佳实验

        Args:
            tags: 标签过滤
            metric: 评价指标，默认为综合评分

        Returns:
            最佳实验
        """
        experiments = self.list_experiments(tags=tags, status="completed")

        if not experiments:
            return None

        # 过滤有结果的实验
        experiments = [exp for exp in experiments if exp.result]

        if not experiments:
            return None

        # 根据指标排序
        if metric == "score":
            best_exp = max(experiments, key=lambda exp: exp.result.get_score())
        elif metric in ["annual_return", "sharpe_ratio", "calmar_ratio", "ic_mean", "ic_ir", "win_rate"]:
            # 越大越好
            best_exp = max(experiments, key=lambda exp: getattr(exp.result, metric))
        else:
            # 越小越好
            best_exp = min(experiments, key=lambda exp: getattr(exp.result, metric))

        return best_exp

    def delete_experiment(self, exp_id: str):
        """
        删除实验

        Args:
            exp_id: 实验ID
        """
        # 删除文件
        exp_file = self.experiment_dir / f"{exp_id}.json"
        if exp_file.exists():
            exp_file.unlink()

        # 更新索引
        if exp_id in self._index["experiments"]:
            exp_info = self._index["experiments"][exp_id]

            # 从标签索引中移除
            for tag in exp_info.get("tags", []):
                if tag in self._index["tags"]:
                    self._index["tags"][tag] = [
                        eid for eid in self._index["tags"][tag] if eid != exp_id
                    ]

            # 从实验索引中移除
            del self._index["experiments"][exp_id]
            self._save_index()

        logger.info(f"删除实验: {exp_id}")

    def export_experiment(self, exp_id: str, output_path: str):
        """
        导出实验配置和结果

        Args:
            exp_id: 实验ID
            output_path: 输出路径
        """
        experiment = self.get_experiment(exp_id)
        if not experiment:
            raise ValueError(f"实验不存在: {exp_id}")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(experiment.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"导出实验: {exp_id} -> {output_path}")

    def import_experiment(self, input_path: str) -> Experiment:
        """
        导入实验

        Args:
            input_path: 输入路径

        Returns:
            实验对象
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        experiment = Experiment.from_dict(data)

        # 生成新ID（避免冲突）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment.id = f"exp_{timestamp}_imported"

        # 保存
        self._save_experiment(experiment)

        # 更新索引
        self._index["experiments"][experiment.id] = {
            "name": experiment.config.name,
            "description": experiment.config.description,
            "tags": experiment.config.tags,
            "created_at": experiment.created_at,
            "status": experiment.status,
        }

        for tag in experiment.config.tags:
            if tag not in self._index["tags"]:
                self._index["tags"][tag] = []
            self._index["tags"][tag].append(experiment.id)

        self._save_index()

        logger.info(f"导入实验: {experiment.id}")
        return experiment
