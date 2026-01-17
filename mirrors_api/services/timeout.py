# services/timeout.py
import asyncio
from typing import TypeVar, Coroutine, Any

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


async def with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout_seconds: float,
    timeout_message: str = "Operation timed out",
) -> T:
    """
    Выполняет корутину с таймаутом.
    Если таймаут истек, выбрасывает asyncio.TimeoutError.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning("operation_timeout", timeout_seconds=timeout_seconds)
        raise asyncio.TimeoutError(timeout_message)


