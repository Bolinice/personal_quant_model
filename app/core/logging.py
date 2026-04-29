"""
日志模块 - 支持 structlog 结构化日志 + 性能计时装饰器

structlog 优势:
- 内置上下文变量（request_id 自动绑定）
- 原生 JSON 输出 + 处理器管道
- 兼容标准 logging，无需一次性重写
- OpenTelemetry 集成友好
"""

import functools
import json
import logging
import sys
import time
from pathlib import Path

import structlog

# 创建日志目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)


# ==================== structlog 配置 ====================


def _configure_structlog(log_level: str = "INFO", log_format: str = "text") -> None:
    """配置 structlog 处理器管道

    Args:
        log_level: 日志级别
        log_format: "json" 或 "text"
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        # JSON 输出: 生产环境
        renderer = structlog.processors.JSONRenderer(serializer=json.dumps, ensure_ascii=False)
    else:
        # 控制台输出: 开发环境
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 配置标准 logging handler，使 structlog 与标准 logging 互通
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            *shared_processors,
            renderer,
        ],
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers.clear()

    # 文件 handler
    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


# ==================== 兼容层 ====================


class JsonFormatter(logging.Formatter):
    """结构化JSON日志格式器（兼容层，structlog 已替代）"""

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
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_entry.update(record.extra)

        # 标准extra字段
        for key in ("trade_date", "factor_id", "security_id", "n_stocks", "duration_ms", "cache_hit", "error_type"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """标准文本日志格式器（兼容层）"""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        # 附加extra字段
        extra_parts = [
            f"{key}={getattr(record, key)}"
            for key in ("trade_date", "factor_id", "security_id", "n_stocks", "duration_ms", "cache_hit")
            if hasattr(record, key)
        ]
        if extra_parts:
            base += " | " + " ".join(extra_parts)
        return base


def setup_logging(log_level: str = "INFO", log_format: str = "text") -> logging.Logger:
    """初始化日志系统（structlog + 标准logging 互通）"""
    _configure_structlog(log_level, log_format)
    return logging.getLogger("quant_platform")


# 默认初始化
logger = setup_logging()

# structlog logger（推荐新代码使用）
slogger = structlog.get_logger()


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
                log_method(f"{fn.__name__} completed", extra={"duration_ms": round(elapsed_ms, 2)})
                return result
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    f"{fn.__name__} failed after {elapsed_ms:.0f}ms: {e}", extra={"duration_ms": round(elapsed_ms, 2)}
                )
                raise

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator
