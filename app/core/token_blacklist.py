"""
JWT Token黑名单服务
使用Redis存储已撤销的refresh token，支持自动过期
"""

import hashlib
from datetime import timedelta

from app.core.config import settings
from app.core.logging import logger


class TokenBlacklist:
    """Token黑名单服务 - Redis实现"""

    def __init__(self):
        self._redis = None
        self._available = False
        self._prefix = "auth:blacklist:"
        # 内存回退黑名单（Redis不可用时使用）
        self._memory_blacklist: set[str] = set()

        try:
            import redis

            self._redis = redis.from_url(settings.REDIS_URL)
            self._redis.ping()
            self._available = True
            logger.info("Token blacklist using Redis")
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory blacklist: {e}")

    @property
    def available(self) -> bool:
        """Redis是否可用"""
        return self._available

    def add(self, token: str, ttl_seconds: int | None = None) -> bool:
        """
        将token加入黑名单

        Args:
            token: JWT token原文
            ttl_seconds: 过期时间（秒），默认使用refresh token过期时间

        Returns:
            是否成功添加
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        if ttl_seconds is None:
            # 默认使用refresh token的过期时间
            ttl_seconds = int(timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())

        if self._available:
            try:
                # 使用SETEX设置带过期时间的key，自动清理过期token
                self._redis.setex(f"{self._prefix}{token_hash}", ttl_seconds, "1")
                return True
            except Exception as e:
                logger.error(f"Failed to add token to Redis blacklist: {e}")
                # Redis失败时回退到内存
                self._memory_blacklist.add(token_hash)
                return False
        else:
            # Redis不可用，使用内存黑名单
            self._memory_blacklist.add(token_hash)
            return True

    def is_blacklisted(self, token: str) -> bool:
        """
        检查token是否在黑名单中

        Args:
            token: JWT token原文

        Returns:
            是否在黑名单中
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        if self._available:
            try:
                exists = self._redis.exists(f"{self._prefix}{token_hash}")
                return bool(exists)
            except Exception as e:
                logger.error(f"Failed to check Redis blacklist: {e}")
                # Redis失败时检查内存黑名单
                return token_hash in self._memory_blacklist
        else:
            # Redis不可用，检查内存黑名单
            return token_hash in self._memory_blacklist

    def remove(self, token: str) -> bool:
        """
        从黑名单中移除token（通常不需要，Redis会自动过期）

        Args:
            token: JWT token原文

        Returns:
            是否成功移除
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        if self._available:
            try:
                self._redis.delete(f"{self._prefix}{token_hash}")
                return True
            except Exception as e:
                logger.error(f"Failed to remove token from Redis blacklist: {e}")
                return False
        else:
            self._memory_blacklist.discard(token_hash)
            return True

    def clear_all(self) -> int:
        """
        清空所有黑名单（仅用于测试）

        Returns:
            清除的token数量
        """
        count = 0
        if self._available:
            try:
                pattern = f"{self._prefix}*"
                cursor = 0
                keys = []
                while True:
                    cursor, batch = self._redis.scan(cursor, match=pattern, count=100)
                    keys.extend(batch)
                    if cursor == 0:
                        break
                if keys:
                    count = self._redis.delete(*keys)
            except Exception as e:
                logger.error(f"Failed to clear Redis blacklist: {e}")

        # 清空内存黑名单
        memory_count = len(self._memory_blacklist)
        self._memory_blacklist.clear()
        return count + memory_count

    def stats(self) -> dict:
        """
        获取黑名单统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "backend": "redis" if self._available else "memory",
            "memory_size": len(self._memory_blacklist),
        }

        if self._available:
            try:
                pattern = f"{self._prefix}*"
                cursor = 0
                count = 0
                while True:
                    cursor, batch = self._redis.scan(cursor, match=pattern, count=100)
                    count += len(batch)
                    if cursor == 0:
                        break
                stats["redis_size"] = count
            except Exception as e:
                logger.error(f"Failed to get Redis blacklist stats: {e}")
                stats["redis_size"] = -1

        return stats


# 全局单例
_token_blacklist: TokenBlacklist | None = None


def get_token_blacklist() -> TokenBlacklist:
    """获取token黑名单实例（延迟初始化）"""
    global _token_blacklist
    if _token_blacklist is None:
        _token_blacklist = TokenBlacklist()
    return _token_blacklist
