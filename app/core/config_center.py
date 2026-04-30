"""
配置中心 V3 - 统一配置管理

功能:
  1. 热更新：配置变更无需重启服务
  2. 版本控制：配置变更历史追踪
  3. 配置验证：类型检查和范围验证
  4. 配置监听：配置变更事件通知
  5. 配置回滚：快速恢复到历史版本
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ConfigVersion:
    """配置版本"""

    version: str
    timestamp: str
    author: str
    description: str
    config_data: dict[str, Any]


@dataclass
class ConfigChangeEvent:
    """配置变更事件"""

    key: str
    old_value: Any
    new_value: Any
    timestamp: str
    author: str


class ConfigValidator:
    """配置验证器"""

    @staticmethod
    def validate_range(value: float, min_val: float, max_val: float, name: str) -> None:
        """验证数值范围"""
        if not min_val <= value <= max_val:
            raise ValueError(f"{name} 必须在 [{min_val}, {max_val}] 范围内，当前值: {value}")

    @staticmethod
    def validate_positive(value: float, name: str) -> None:
        """验证正数"""
        if value <= 0:
            raise ValueError(f"{name} 必须为正数，当前值: {value}")

    @staticmethod
    def validate_probability(value: float, name: str) -> None:
        """验证概率值"""
        ConfigValidator.validate_range(value, 0.0, 1.0, name)

    @staticmethod
    def validate_enum(value: str, allowed: list[str], name: str) -> None:
        """验证枚举值"""
        if value not in allowed:
            raise ValueError(f"{name} 必须是 {allowed} 之一，当前值: {value}")


class ConfigCenter:
    """配置中心 - 支持热更新和版本控制"""

    def __init__(
        self,
        config_dir: str | Path = "config",
        version_dir: str | Path = "data/config_versions",
        enable_hot_reload: bool = True,
    ):
        self.config_dir = Path(config_dir)
        self.version_dir = Path(version_dir)
        self.version_dir.mkdir(parents=True, exist_ok=True)

        self.enable_hot_reload = enable_hot_reload
        self._config: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._listeners: dict[str, list[Callable]] = {}
        self._version_history: list[ConfigVersion] = []

        # 加载配置
        self._load_config()
        self._load_version_history()

    def _load_config(self) -> None:
        """加载所有配置文件"""
        config = {}

        # 按顺序加载配置文件
        config_files = [
            "base.yaml",
            "universe.yaml",
            "factors.yaml",
            "labels.yaml",
            "model.yaml",
            "timing.yaml",
            "portfolio.yaml",
            "risk.yaml",
            "backtest.yaml",
            "monitoring.yaml",
        ]

        for filename in config_files:
            filepath = self.config_dir / filename
            if filepath.exists():
                with open(filepath, encoding="utf-8") as f:
                    file_config = yaml.safe_load(f) or {}
                config = self._deep_merge(config, file_config)

        with self._lock:
            self._config = config

        logger.info("配置加载完成: %d 个配置项", len(self._flatten_dict(config)))

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """深度合并字典"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _flatten_dict(self, d: dict, parent_key: str = "", sep: str = ".") -> dict:
        """扁平化字典"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号路径

        Examples:
            config.get("backtest.costs.commission_rate")
            config.get("factors.module_weights.quality_growth")
        """
        with self._lock:
            keys = key.split(".")
            value = self._config
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value

    def set(self, key: str, value: Any, author: str = "system", validate: bool = True) -> None:
        """
        设置配置值

        Args:
            key: 配置键（点号分隔）
            value: 配置值
            author: 修改者
            validate: 是否验证配置
        """
        if validate:
            self._validate_config(key, value)

        old_value = self.get(key)

        with self._lock:
            # 更新配置
            keys = key.split(".")
            config = self._config
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            config[keys[-1]] = value

            # 保存到文件
            self._save_config()

            # 创建版本
            self._create_version(author, f"更新 {key}")

        # 触发变更事件
        event = ConfigChangeEvent(
            key=key,
            old_value=old_value,
            new_value=value,
            timestamp=datetime.now().isoformat(),
            author=author,
        )
        self._notify_listeners(key, event)

        logger.info("配置已更新: %s = %s (作者: %s)", key, value, author)

    def _validate_config(self, key: str, value: Any) -> None:
        """验证配置值"""
        validator = ConfigValidator()

        # 交易成本验证
        if "commission_rate" in key or "stamp_tax" in key or "slippage" in key:
            validator.validate_range(value, 0.0, 0.01, key)

        # 权重验证
        elif "weight" in key and isinstance(value, (int, float)):
            validator.validate_range(value, 0.0, 1.0, key)

        # 正数验证
        elif any(x in key for x in ["min_", "max_", "threshold", "window"]):
            if isinstance(value, (int, float)):
                validator.validate_positive(value, key)

    def _save_config(self) -> None:
        """保存配置到文件"""
        # 按模块保存到不同文件
        module_map = {
            "backtest": "backtest.yaml",
            "universe": "universe.yaml",
            "factors": "factors.yaml",
            "labels": "labels.yaml",
            "model": "model.yaml",
            "timing": "timing.yaml",
            "portfolio": "portfolio.yaml",
            "risk": "risk.yaml",
            "monitoring": "monitoring.yaml",
        }

        for module, filename in module_map.items():
            if module in self._config:
                filepath = self.config_dir / filename
                with open(filepath, "w", encoding="utf-8") as f:
                    yaml.dump({module: self._config[module]}, f, allow_unicode=True, default_flow_style=False)

    def _create_version(self, author: str, description: str) -> None:
        """创建配置版本"""
        version = ConfigVersion(
            version=datetime.now().strftime("%Y%m%d_%H%M%S"),
            timestamp=datetime.now().isoformat(),
            author=author,
            description=description,
            config_data=self._config.copy(),
        )

        self._version_history.append(version)

        # 保存版本到文件
        version_file = self.version_dir / f"config_{version.version}.json"
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(asdict(version), f, ensure_ascii=False, indent=2, default=str)

        logger.info("配置版本已创建: %s", version.version)

    def _load_version_history(self) -> None:
        """加载版本历史"""
        version_files = sorted(self.version_dir.glob("config_*.json"))
        for version_file in version_files[-10:]:  # 只加载最近10个版本
            try:
                with open(version_file, encoding="utf-8") as f:
                    data = json.load(f)
                version = ConfigVersion(**data)
                self._version_history.append(version)
            except Exception as e:
                logger.warning("加载版本失败 %s: %s", version_file, e)

    def rollback(self, version: str) -> None:
        """回滚到指定版本"""
        target_version = None
        for v in self._version_history:
            if v.version == version:
                target_version = v
                break

        if not target_version:
            raise ValueError(f"版本不存在: {version}")

        with self._lock:
            self._config = target_version.config_data.copy()
            self._save_config()

        logger.info("配置已回滚到版本: %s", version)

    def get_version_history(self, limit: int = 10) -> list[ConfigVersion]:
        """获取版本历史"""
        return self._version_history[-limit:]

    def register_listener(self, key_pattern: str, callback: Callable[[ConfigChangeEvent], None]) -> None:
        """
        注册配置变更监听器

        Args:
            key_pattern: 配置键模式（支持通配符*）
            callback: 回调函数
        """
        if key_pattern not in self._listeners:
            self._listeners[key_pattern] = []
        self._listeners[key_pattern].append(callback)
        logger.info("已注册配置监听器: %s", key_pattern)

    def _notify_listeners(self, key: str, event: ConfigChangeEvent) -> None:
        """通知监听器"""
        for pattern, callbacks in self._listeners.items():
            if self._match_pattern(key, pattern):
                for callback in callbacks:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error("配置监听器执行失败: %s", e)

    def _match_pattern(self, key: str, pattern: str) -> bool:
        """匹配配置键模式"""
        if pattern == "*":
            return True
        if "*" in pattern:
            import re

            regex = pattern.replace(".", r"\.").replace("*", ".*")
            return bool(re.match(f"^{regex}$", key))
        return key == pattern

    def reload(self) -> None:
        """重新加载配置"""
        self._load_config()
        logger.info("配置已重新加载")

    def export_config(self, output_path: str | Path) -> None:
        """导出配置到文件"""
        output_path = Path(output_path)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
        logger.info("配置已导出到: %s", output_path)

    def get_all(self) -> dict[str, Any]:
        """获取所有配置"""
        with self._lock:
            return self._config.copy()


# 全局配置中心实例
_config_center: ConfigCenter | None = None


def get_config_center() -> ConfigCenter:
    """获取配置中心单例"""
    global _config_center
    if _config_center is None:
        _config_center = ConfigCenter()
    return _config_center


def get_config(key: str, default: Any = None) -> Any:
    """便捷函数：获取配置值"""
    return get_config_center().get(key, default)


def set_config(key: str, value: Any, author: str = "system") -> None:
    """便捷函数：设置配置值"""
    get_config_center().set(key, value, author)
