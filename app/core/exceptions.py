"""
统一异常处理体系
==================
扩展自 app/core/errors.py，提供更完善的异常分类和上下文信息

异常分类:
- QuantPlatformException: 平台基础异常
- DataSourceException: 数据源异常（可重试）
- CalculationException: 计算异常（不可重试）
- DatabaseException: 数据库异常（部分可重试）
- ValidationException: 数据验证异常（不可重试）
- ConfigurationException: 配置异常（不可重试）
- AuthenticationException: 认证异常（不可重试）
- PermissionException: 权限异常（不可重试）
"""

from typing import Any


class QuantPlatformException(Exception):
    """平台基础异常 - 所有自定义异常的基类"""

    def __init__(
        self,
        message: str,
        error_code: str,
        context: dict[str, Any] | None = None,
        retryable: bool = False,
    ):
        """
        Args:
            message: 错误消息
            error_code: 错误码（用于前端展示和日志检索）
            context: 错误上下文（包含相关参数、状态等）
            retryable: 是否可重试
        """
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.retryable = retryable
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式（用于API响应）"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "retryable": self.retryable,
        }


# ==================== 数据源异常 ====================


class DataSourceException(QuantPlatformException):
    """数据源异常（可重试）- 网络请求、API调用失败等"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="DATA_SOURCE_ERROR",
            context=context,
            retryable=True,
        )


class TushareException(DataSourceException):
    """Tushare数据源异常"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        context = context or {}
        context["data_source"] = "tushare"
        super().__init__(message=message, context=context)


class AKShareException(DataSourceException):
    """AKShare数据源异常"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        context = context or {}
        context["data_source"] = "akshare"
        super().__init__(message=message, context=context)


class DataNotAvailableException(DataSourceException):
    """数据不可用异常（例如停牌、退市）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message=message, context=context)


# ==================== 计算异常 ====================


class CalculationException(QuantPlatformException):
    """计算异常（不可重试）- 因子计算、回测计算失败等"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="CALCULATION_ERROR",
            context=context,
            retryable=False,
        )


class FactorCalculationException(CalculationException):
    """因子计算异常"""

    def __init__(self, factor_name: str, message: str, context: dict[str, Any] | None = None):
        context = context or {}
        context["factor_name"] = factor_name
        super().__init__(message=f"因子 {factor_name} 计算失败: {message}", context=context)


class BacktestException(CalculationException):
    """回测异常"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message=message, context=context)


class OptimizationException(CalculationException):
    """组合优化异常"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message=message, context=context)


# ==================== 数据库异常 ====================


class DatabaseException(QuantPlatformException):
    """数据库异常（部分可重试）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None, retryable: bool = False):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            context=context,
            retryable=retryable,
        )


class DatabaseDeadlockException(DatabaseException):
    """数据库死锁异常（可重试）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message=message, context=context, retryable=True)


class DatabaseConnectionException(DatabaseException):
    """数据库连接异常（可重试）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message=message, context=context, retryable=True)


class DatabaseIntegrityException(DatabaseException):
    """数据库完整性异常（不可重试）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message=message, context=context, retryable=False)


# ==================== 验证异常 ====================


class ValidationException(QuantPlatformException):
    """数据验证异常（不可重试）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            context=context,
            retryable=False,
        )


class DataQualityException(ValidationException):
    """数据质量异常（缺失值过多、异常值等）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message=message, context=context)


class LookaheadBiasException(ValidationException):
    """前瞻偏差异常（PIT约束违反）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message=message, context=context)


# ==================== 配置异常 ====================


class ConfigurationException(QuantPlatformException):
    """配置异常（不可重试）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            context=context,
            retryable=False,
        )


class InvalidConfigException(ConfigurationException):
    """无效配置异常"""

    def __init__(self, config_key: str, message: str, context: dict[str, Any] | None = None):
        context = context or {}
        context["config_key"] = config_key
        super().__init__(message=f"配置项 {config_key} 无效: {message}", context=context)


# ==================== 认证与权限异常 ====================


class AuthenticationException(QuantPlatformException):
    """认证异常（不可重试）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            context=context,
            retryable=False,
        )


class PermissionException(QuantPlatformException):
    """权限异常（不可重试）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="PERMISSION_ERROR",
            context=context,
            retryable=False,
        )


class UsageLimitException(PermissionException):
    """用量限制异常"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message=message, context=context)


# ==================== 业务异常 ====================


class BusinessException(QuantPlatformException):
    """业务异常（不可重试）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="BUSINESS_ERROR",
            context=context,
            retryable=False,
        )


class InsufficientDataException(BusinessException):
    """数据不足异常（例如股票池过小、历史数据不足）"""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message=message, context=context)


class InvalidParameterException(BusinessException):
    """无效参数异常"""

    def __init__(self, param_name: str, message: str, context: dict[str, Any] | None = None):
        context = context or {}
        context["param_name"] = param_name
        super().__init__(message=f"参数 {param_name} 无效: {message}", context=context)
