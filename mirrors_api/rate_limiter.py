# rate_limiter.py
import asyncio
import time
from collections import defaultdict
from typing import Dict, Tuple

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger()


class RateLimiter:
    """
    Простой in-memory rate limiter на основе sliding window.
    Для продакшена лучше использовать Redis.
    """

    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str) -> Tuple[bool, int]:
        """
        Проверяет, разрешен ли запрос.
        Возвращает (is_allowed, remaining_requests).
        """
        async with self._lock:
            now = time.time()
            window_start = now - 60  # Последняя минута

            # Очищаем старые запросы
            self._requests[key] = [
                req_time for req_time in self._requests[key]
                if req_time > window_start
            ]

            # Проверяем лимит
            if len(self._requests[key]) >= self.requests_per_minute:
                return False, 0

            # Добавляем текущий запрос
            self._requests[key].append(now)
            remaining = self.requests_per_minute - len(self._requests[key])

            return True, remaining


# Глобальный rate limiter
_rate_limiter: RateLimiter = None


def get_rate_limiter(requests_per_minute: int = 60) -> RateLimiter:
    """Получить глобальный rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(requests_per_minute=requests_per_minute)
    return _rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware для rate limiting.
    Использует IP адрес как ключ.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rate_limiter = get_rate_limiter(requests_per_minute)

    async def dispatch(self, request: Request, call_next):
        # Получаем IP адрес
        client_ip = request.client.host if request.client else "unknown"

        # Проверяем rate limit
        is_allowed, remaining = await self.rate_limiter.is_allowed(client_ip)

        if not is_allowed:
            logger.warning(
                "rate_limit_exceeded",
                ip=client_ip,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {self.rate_limiter.requests_per_minute} requests per minute",
                    "request_id": getattr(request.state, "request_id", None),
                },
                headers={
                    "X-RateLimit-Limit": str(self.rate_limiter.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "60",
                },
            )

        # Добавляем заголовки rate limit
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

