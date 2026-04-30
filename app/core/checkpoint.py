"""
断点续跑机制 — 支持日终流水线从失败点恢复

功能:
  1. 自动保存每步执行状态
  2. 失败后从断点恢复
  3. 跳过已完成步骤
  4. 清理过期检查点
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CheckpointState:
    """检查点状态"""

    trade_date: str
    last_completed_step: int
    timestamp: str
    context_data: dict[str, Any]


class CheckpointManager:
    """检查点管理器"""

    def __init__(self, checkpoint_dir: str = "data/checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, trade_date: date, step: int, context_data: dict[str, Any]) -> None:
        """保存检查点"""
        checkpoint_path = self._get_checkpoint_path(trade_date)
        state = CheckpointState(
            trade_date=str(trade_date),
            last_completed_step=step,
            timestamp=datetime.now().isoformat(),
            context_data=context_data,
        )

        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, ensure_ascii=False, indent=2, default=str)

        logger.info("检查点已保存: step=%d, path=%s", step, checkpoint_path)

    def load(self, trade_date: date) -> CheckpointState | None:
        """加载检查点"""
        checkpoint_path = self._get_checkpoint_path(trade_date)
        if not checkpoint_path.exists():
            return None

        try:
            with open(checkpoint_path, encoding="utf-8") as f:
                data = json.load(f)
            state = CheckpointState(**data)
            logger.info("检查点已加载: step=%d, time=%s", state.last_completed_step, state.timestamp)
            return state
        except Exception as e:
            logger.warning("检查点加载失败: %s", e)
            return None

    def delete(self, trade_date: date) -> None:
        """删除检查点"""
        checkpoint_path = self._get_checkpoint_path(trade_date)
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            logger.info("检查点已删除: %s", checkpoint_path)

    def cleanup_old(self, days: int = 7) -> int:
        """清理过期检查点"""
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted = 0

        for checkpoint_path in self.checkpoint_dir.glob("checkpoint_*.json"):
            try:
                with open(checkpoint_path, encoding="utf-8") as f:
                    data = json.load(f)
                timestamp = datetime.fromisoformat(data["timestamp"])
                if timestamp < cutoff_date:
                    checkpoint_path.unlink()
                    deleted += 1
            except Exception as e:
                logger.warning("清理检查点失败 %s: %s", checkpoint_path, e)

        if deleted > 0:
            logger.info("已清理 %d 个过期检查点", deleted)
        return deleted

    def _get_checkpoint_path(self, trade_date: date) -> Path:
        """获取检查点文件路径"""
        return self.checkpoint_dir / f"checkpoint_{trade_date.strftime('%Y%m%d')}.json"


def serialize_context(ctx: Any) -> dict[str, Any]:
    """序列化PipelineContext为可保存的字典"""
    import pandas as pd

    data = {}
    for key, value in ctx.__dict__.items():
        if value is None:
            data[key] = None
        elif isinstance(value, (str, int, float, bool)):
            data[key] = value
        elif isinstance(value, date):
            data[key] = str(value)
        elif isinstance(value, list):
            data[key] = value
        elif isinstance(value, dict):
            data[key] = value
        elif isinstance(value, pd.Series):
            data[key] = {"_type": "series", "data": value.to_dict()}
        elif isinstance(value, pd.DataFrame):
            data[key] = {"_type": "dataframe", "data": value.to_json(orient="records")}
        else:
            # 跳过无法序列化的对象（如Session）
            continue

    return data


def deserialize_context(data: dict[str, Any], ctx: Any) -> None:
    """从字典恢复PipelineContext"""
    import pandas as pd
    from datetime import date as date_type

    for key, value in data.items():
        if value is None:
            setattr(ctx, key, None)
        elif isinstance(value, dict) and "_type" in value:
            if value["_type"] == "series":
                setattr(ctx, key, pd.Series(value["data"]))
            elif value["_type"] == "dataframe":
                setattr(ctx, key, pd.read_json(value["data"], orient="records"))
        elif key == "trade_date" and isinstance(value, str):
            setattr(ctx, key, date_type.fromisoformat(value))
        else:
            setattr(ctx, key, value)
