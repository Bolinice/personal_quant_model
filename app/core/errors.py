"""
结构化错误体系
==============
领域化错误层级，每个错误类映射到特定告警通道和1严重级别。

层级：
  QuantPlatformError
  ├── DataError
  │   ├── LookaheadBiasError      — 检测到未来数据（最严重）
  │   ├── DataStaleError          — 数据过期
  │   └── DataQualityError        — 数据质量问题
  ├── FactorDegradationError      — 因子 IC 衰减超阈值
  ├── TradingRuleViolationError   — 回测违反 A 股交易规则
  └── PortfolioRiskError          — 组合风险超限
"""
from enum import Enum


class ErrorSeverity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ErrorCode(str, Enum):
    # Data errors
    LOOKAHEAD_BIAS = "DATA_001"
    DATA_STALE = "DATA_002"
    DATA_QUALITY = "DATA_003"
    # Factor errors
    FACTOR_DEGRADATION = "FACTOR_001"
    FACTOR_IC_BELOW_THRESHOLD = "FACTOR_002"
    # Trading rule errors
    T_PLUS_1_VIOLATION = "TRADE_001"
    PRICE_LIMIT_VIOLATION = "TRADE_002"
    LOT_SIZE_VIOLATION = "TRADE_003"
    # Portfolio risk errors
    POSITION_LIMIT_BREACH = "RISK_001"
    SECTOR_CONCENTRATION_BREACH = "RISK_002"
    TURNOVER_LIMIT_BREACH = "RISK_003"


# Severity mapping
ERROR_SEVERITY = {
    ErrorCode.LOOKAHEAD_BIAS: ErrorSeverity.EMERGENCY,
    ErrorCode.DATA_STALE: ErrorSeverity.WARNING,
    ErrorCode.DATA_QUALITY: ErrorSeverity.WARNING,
    ErrorCode.FACTOR_DEGRADATION: ErrorSeverity.CRITICAL,
    ErrorCode.FACTOR_IC_BELOW_THRESHOLD: ErrorSeverity.WARNING,
    ErrorCode.T_PLUS_1_VIOLATION: ErrorSeverity.EMERGENCY,
    ErrorCode.PRICE_LIMIT_VIOLATION: ErrorSeverity.CRITICAL,
    ErrorCode.LOT_SIZE_VIOLATION: ErrorSeverity.CRITICAL,
    ErrorCode.POSITION_LIMIT_BREACH: ErrorSeverity.EMERGENCY,
    ErrorCode.SECTOR_CONCENTRATION_BREACH: ErrorSeverity.CRITICAL,
    ErrorCode.TURNOVER_LIMIT_BREACH: ErrorSeverity.WARNING,
}


class QuantPlatformError(Exception):
    """平台基础错误"""

    def __init__(self, code: ErrorCode, message: str, detail: dict | None = None):
        self.code = code
        self.severity = ERROR_SEVERITY.get(code, ErrorSeverity.WARNING)
        self.detail = detail or {}
        super().__init__(message)


class DataError(QuantPlatformError):
    """数据源/质量问题"""

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(ErrorCode.DATA_QUALITY, message, detail)


class LookaheadBiasError(DataError):
    """检测到未来数据 — 最严重的量化系统错误"""

    def __init__(self, message: str, detail: dict | None = None):
        self.code = ErrorCode.LOOKAHEAD_BIAS
        self.severity = ErrorSeverity.EMERGENCY
        self.detail = detail or {}
        super(DataError, self).__init__(message)


class DataStaleError(DataError):
    """数据过期"""

    def __init__(self, message: str, detail: dict | None = None):
        self.code = ErrorCode.DATA_STALE
        self.severity = ErrorSeverity.WARNING
        self.detail = detail or {}
        super(DataError, self).__init__(message)


class FactorDegradationError(QuantPlatformError):
    """因子 IC 衰减超阈值"""

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(ErrorCode.FACTOR_DEGRADATION, message, detail)


class TradingRuleViolationError(QuantPlatformError):
    """回测违反 A 股交易规则"""

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(ErrorCode.T_PLUS_1_VIOLATION, message, detail)


class PortfolioRiskError(QuantPlatformError):
    """组合风险超限"""

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(ErrorCode.POSITION_LIMIT_BREACH, message, detail)
