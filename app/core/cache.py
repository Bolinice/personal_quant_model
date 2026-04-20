"""
缓存服务 - 支持TTL + LRU驱逐 + Redis二级缓存 + 交易日失效策略
用于因子计算、IC分析等高频重复计算场景
"""
import hashlib
import json
import time
import logging
from typing import Callable, Optional, Any, List
from collections import OrderedDict
from datetime import date
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
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args[1:])
                key_parts.extend(str(k) + str(v) for k, v in sorted(kwargs.items()))
                cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()

                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                return result
            return wrapper
        return decorator

    def invalidate_by_prefix(self, prefix: str) -> int:
        """按前缀批量失效缓存"""
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._cache[k]
        return len(keys_to_delete)

    def invalidate_by_trade_date(self, trade_date: date) -> int:
        """按交易日失效缓存 (新交易日→因子缓存失效)"""
        date_str = str(trade_date)
        keys_to_delete = [k for k in self._cache if date_str in k]
        for k in keys_to_delete:
            del self._cache[k]
        return len(keys_to_delete)

    def invalidate_by_run_id(self, run_id: str) -> int:
        """按run_id批量失效缓存"""
        keys_to_delete = [k for k in self._cache if run_id in k]
        for k in keys_to_delete:
            del self._cache[k]
        return len(keys_to_delete)


class RedisCacheService:
    """Redis缓存服务 - 分布式二级缓存"""

    def __init__(self, redis_url: str = None, default_ttl: int = 600,
                 prefix: str = "quant:cache:"):
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._redis = None
        self._available = False

        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url)
                self._redis.ping()
                self._available = True
            except Exception as e:
                logger.warning(f"Redis cache unavailable: {e}")

    @property
    def available(self) -> bool:
        return self._available

    def get(self, key: str) -> Optional[Any]:
        if not self._available:
            return None
        try:
            data = self._redis.get(self._prefix + key)
            if data is not None:
                return json.loads(data)
        except Exception:
            pass
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        if not self._available:
            return
        if ttl is None:
            ttl = self._default_ttl
        try:
            self._redis.setex(self._prefix + key, ttl, json.dumps(value, default=str))
        except Exception:
            pass

    def delete(self, key: str):
        if not self._available:
            return
        try:
            self._redis.delete(self._prefix + key)
        except Exception:
            pass

    def invalidate_by_prefix(self, prefix: str) -> int:
        """按前缀批量失效"""
        if not self._available:
            return 0
        try:
            pattern = self._prefix + prefix + "*"
            keys = self._redis.keys(pattern)
            if keys:
                return self._redis.delete(*keys)
        except Exception:
            pass
        return 0


class TwoLevelCache:
    """
    二级缓存: L1=内存LRU, L2=Redis
    读取: L1 → L2 → miss
    写入: L1 + L2 同时写入
    """

    def __init__(self, l1: CacheService, l2: RedisCacheService = None):
        self.l1 = l1
        self.l2 = l2

    def get(self, key: str) -> Optional[Any]:
        # L1
        value = self.l1.get(key)
        if value is not None:
            return value

        # L2
        if self.l2 and self.l2.available:
            value = self.l2.get(key)
            if value is not None:
                # 回填L1
                self.l1.set(key, value)
                return value

        return None

    def set(self, key: str, value: Any, ttl: int = None):
        self.l1.set(key, value, ttl)
        if self.l2 and self.l2.available:
            self.l2.set(key, value, ttl)

    def delete(self, key: str):
        self.l1.delete(key)
        if self.l2 and self.l2.available:
            self.l2.delete(key)

    def invalidate_by_prefix(self, prefix: str) -> int:
        count = self.l1.invalidate_by_prefix(prefix)
        if self.l2 and self.l2.available:
            count += self.l2.invalidate_by_prefix(prefix)
        return count

    def invalidate_by_trade_date(self, trade_date: date) -> int:
        count = self.l1.invalidate_by_trade_date(trade_date)
        if self.l2 and self.l2.available:
            count += self.l2.invalidate_by_prefix(f"fv:*:{trade_date}")
        return count


# ==================== 全局缓存实例 ====================

cache_service = CacheService(max_size=5000, default_ttl=600)

factor_cache = CacheService(max_size=10000, default_ttl=1800)

# Redis二级缓存 (延迟初始化)
_redis_cache: Optional[RedisCacheService] = None

def get_two_level_cache() -> TwoLevelCache:
    """获取二级缓存实例 (延迟初始化Redis)"""
    global _redis_cache
    if _redis_cache is None:
        try:
            from app.core.config import settings
            _redis_cache = RedisCacheService(settings.REDIS_URL)
        except Exception:
            _redis_cache = RedisCacheService()  # unavailable
    return TwoLevelCache(factor_cache, _redis_cache)
