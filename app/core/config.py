import hashlib
import json
import time
from typing import Callable, Optional, Any
from functools import wraps
from app.core.logging import logger

class CacheService:
    """内存缓存服务"""

    def __init__(self):
        self._cache = {}

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 300):
        """设置缓存"""
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)

    def delete(self, key: str):
        """删除缓存"""
        if key in self._cache:
            del self._cache[key]

    def clear(self):
        """清空缓存"""
        self._cache.clear()

    def cache_decorator(self, ttl: int = 300):
        """缓存装饰器"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 生成缓存键
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(str(k) + str(v) for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()

                # 尝试从缓存获取
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for key: {func.__name__}")
                    return cached_value

                # 执行函数并缓存结果
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                logger.debug(f"Cached result for key: {func.__name__}")

                return result
            return wrapper
        return decorator

# 全局缓存服务实例
cache_service = CacheService()
