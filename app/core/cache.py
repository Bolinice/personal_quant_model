"""
缓存服务 - 支持TTL + LRU驱逐
用于因子计算、IC分析等高频重复计算场景
"""
import hashlib
import json
import time
from typing import Callable, Optional, Any
from collections import OrderedDict
from functools import wraps
from app.core.logging import logger


class CacheService:
    """内存缓存服务 - TTL + LRU驱逐"""

    def __init__(self, max_size: int = 6000, default_ttl: int = 300):
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                # LRU: 移到末尾
                self._cache.move_to_end(key)
                self._hits += 1
                return value
            else:
                del self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        """设置缓存"""
        if ttl is None:
            ttl = self._default_ttl
        expiry = time.time() + ttl

        # LRU驱逐
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._cache.popitem(last=False)

        self._cache[key] = (value, expiry)
        self._cache.move_to_end(key)

    def delete(self, key: str):
        """删除缓存"""
        if key in self._cache:
            del self._cache[key]

    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict:
        """缓存统计"""
        total = self._hits + self._misses
        return {
            'size': len(self._cache),
            'max_size': self._max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': self._hits / total if total > 0 else 0,
        }

    def cache_decorator(self, ttl: int = None):
        """缓存装饰器"""
        if ttl is None:
            ttl = self._default_ttl

        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 生成缓存键
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args[1:])  # 跳过self
                key_parts.extend(str(k) + str(v) for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()

                # 尝试从缓存获取
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                # 执行函数并缓存结果
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                return result
            return wrapper
        return decorator


# 全局缓存服务实例
cache_service = CacheService(max_size=5000, default_ttl=600)

# 因子计算专用缓存 (更大容量, 更长TTL)
factor_cache = CacheService(max_size=10000, default_ttl=1800)
