import redis
from typing import Optional, Any, Callable
from functools import wraps
from app.core.config import settings
import json
import time

class CacheService:
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.redis_host or 'localhost',
            port=settings.redis_port or 6379,
            db=0,
            decode_responses=True
        )

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        value = self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """设置缓存值"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            return self.redis.setex(key, ttl, value)
        except Exception as e:
            print(f"Cache set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        return self.redis.delete(key) > 0

    def clear_pattern(self, pattern: str) -> int:
        """清除匹配模式的缓存"""
        keys = self.redis.keys(pattern)
        if keys:
            return self.redis.delete(*keys)
        return 0

    def cache_decorator(self, ttl: int = 3600):
        """缓存装饰器"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 生成缓存键
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

                # 尝试从缓存获取
                cached_result = self.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # 执行函数
                result = await func(*args, **kwargs)

                # 存入缓存
                self.set(cache_key, result, ttl)

                return result
            return wrapper
        return decorator

cache_service = CacheService()