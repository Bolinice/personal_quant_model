"""
YAML配置加载器 V2
==================
支持:
- 多YAML文件加载与合并
- 环境覆盖(production.yaml)
- 配置验证
- 缓存
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# 配置文件目录
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"

# 配置文件列表(按优先级从低到高)
CONFIG_FILES = [
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


class ConfigLoader:
    """YAML配置加载器"""

    _instance: Optional["ConfigLoader"] = None
    _config: dict[str, Any] = {}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_dir: str | None = None, env: str | None = None):
        if self._config:
            return  # 已初始化
        self._config_dir = Path(config_dir) if config_dir else CONFIG_DIR
        self._env = env or os.getenv("APP_ENV", "development")
        self._config = self._load_all()

    def _load_yaml(self, filepath: Path) -> dict[str, Any]:
        """加载单个YAML文件"""
        if not filepath.exists():
            logger.warning(f"配置文件不存在: {filepath}")
            return {}
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data or {}

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """深度合并两个字典"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _load_all(self) -> dict[str, Any]:
        """加载所有配置文件"""
        config = {}

        # 按顺序加载基础配置
        for filename in CONFIG_FILES:
            filepath = self._config_dir / filename
            file_config = self._load_yaml(filepath)
            if file_config:
                config = self._deep_merge(config, file_config)

        # 加载环境覆盖配置
        env_file = self._config_dir / f"{self._env}.yaml"
        if env_file.exists():
            env_config = self._load_yaml(env_file)
            if env_config:
                config = self._deep_merge(config, env_config)

        logger.info(f"配置加载完成: dir={self._config_dir}, env={self._env}")
        return config

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值, 支持点号分隔的路径

        Examples:
            config.get("universe.core.min_list_days")
            config.get("factors.module_weights.quality_growth")
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_section(self, section: str) -> dict[str, Any]:
        """获取整个配置段"""
        return self._config.get(section, {})

    def get_all(self) -> dict[str, Any]:
        """获取全部配置"""
        return self._config.copy()

    def reload(self) -> None:
        """重新加载配置"""
        self._config = self._load_all()


def get_config() -> ConfigLoader:
    """获取配置加载器单例"""
    return ConfigLoader()


def get_config_value(key: str, default: Any = None) -> Any:
    """便捷函数: 获取配置值"""
    return get_config().get(key, default)
