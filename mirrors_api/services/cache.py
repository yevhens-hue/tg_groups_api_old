# services/cache.py
import asyncio
import hashlib
import time
from typing import Optional, Dict, Any
from collections import OrderedDict

import structlog

logger = structlog.get_logger()


class TTLCache:
    """
    In-memory кэш с TTL (Time To Live).
    Используется для кэширования результатов Serper API.
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 21600):  # 6 часов по умолчанию
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = asyncio.Lock()

    def _make_key(self, *args, **kwargs) -> str:
        """Создать ключ кэша из аргументов."""
        key_str = str(args) + str(sorted(kwargs.items()))
        return hashlib.sha256(key_str.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша, если оно не истекло."""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            if time.time() > entry["expires_at"]:
                # TTL истек
                del self._cache[key]
                logger.debug("cache_expired", key=key[:16])
                return None

            # Перемещаем в конец (LRU)
            self._cache.move_to_end(key)
            logger.debug("cache_hit", key=key[:16])
            return entry["value"]

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Установить значение в кэш с TTL."""
        ttl = ttl or self.default_ttl
        expires_at = time.time() + ttl

        async with self._lock:
            # Если достигли лимита, удаляем самый старый элемент
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._cache.popitem(last=False)  # Удаляем первый (самый старый)

            self._cache[key] = {
                "value": value,
                "expires_at": expires_at,
            }
            self._cache.move_to_end(key)
            logger.debug("cache_set", key=key[:16], ttl=ttl)

    async def clear(self) -> None:
        """Очистить весь кэш."""
        async with self._lock:
            self._cache.clear()
            logger.info("cache_cleared")

    async def stats(self) -> Dict[str, Any]:
        """Статистика кэша."""
        async with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "default_ttl": self.default_ttl,
            }


# Глобальный кэш для Serper результатов
_serper_cache: Optional[TTLCache] = None


def get_serper_cache() -> TTLCache:
    """Получить глобальный кэш для Serper."""
    global _serper_cache
    if _serper_cache is None:
        _serper_cache = TTLCache(max_size=1000, default_ttl=21600)  # 6 часов
    return _serper_cache

