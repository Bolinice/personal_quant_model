"""
日志模块 - 支持结构化JSON日志 + 性能计时装饰器
"""
import logging
import sys
import json
import time
import functools
from pathlib import Path
from typing import Optional, Dict, Any

# 创建日志目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)


class JsonFormatter(logging.Formatter):
    """结构化JSON日志格式器"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 合并extra字段
        if hasattr(record, 'extra') and isinstance(record.extra, dict):
            log_entry.update(record.extra)

        # 标准extra字段
        for key in ('trade_date', 'factor_id', 'security_id', 'n_stocks',
                     'duration_ms', 'cache_hit', 'error_type'):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """标准文本日志格式器"""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        # 附加extra字段
        extra_parts = []
        for key in ('trade_date', 'factor_id', 'security_id', 'n_stocks',
                     'duration_ms', 'cache_hit'):
            if hasattr(record, key):
                extra_parts.append(f"{key}={getattr(record, key)}")
        if extra_parts:
            base += " | " + " ".join(extra_parts)
        return base


def setup_logging(log_level: str = "INFO", log_format: str = "text") -> logging.Logger:
    """初始化日志系统"""
    log_cfg = logging.getLogger("quant_platform")
    log_cfg.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 清除已有handlers
    log_cfg.handlers.clear()

    if log_format == "json":
        formatter = JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    else:
        formatter = TextFormatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # 文件handler
    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    log_cfg.addHandler(file_handler)

    # 控制台handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    log_cfg.addHandler(console_handler)

    return log_cfg


# 默认初始化
logger = setup_logging()


def log_execution_time(func=None, *, level: str = "info"):
    """
    性能计时装饰器
    记录函数执行耗时到日志

    用法:
        @log_execution_time
        def slow_function(): ...

        @log_execution_time(level="warning")
        def potentially_slow(): ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000
                log_method = getattr(logger, level, logger.info)
                log_method(
                    f"{fn.__name__} completed",
                    extra={"duration_ms": round(elapsed_ms, 2)}
                )
                return result
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    f"{fn.__name__} failed after {elapsed_ms:.0f}ms: {e}",
                    extra={"duration_ms": round(elapsed_ms, 2)}
                )
                raise
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
