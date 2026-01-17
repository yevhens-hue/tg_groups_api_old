# services/circuit_breaker.py
import asyncio
import time
from typing import Optional, Callable, Any
from enum import Enum

import structlog

logger = structlog.get_logger()


class CircuitState(Enum):
    CLOSED = "closed"  # Нормальная работа
    OPEN = "open"  # Сломан, не пропускает запросы
    HALF_OPEN = "half_open"  # Тестирует восстановление


class CircuitBreaker:
    """
    Circuit Breaker для защиты от каскадных сбоев.
    Используется для Serper API и других внешних зависимостей.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Вызвать функцию через circuit breaker."""
        async with self._lock:
            # Проверяем состояние
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time < self.recovery_timeout:
                    logger.warning(
                        "circuit_breaker_open",
                        state=self.state.value,
                        wait_remaining=self.recovery_timeout - (time.time() - self.last_failure_time),
                    )
                    raise Exception(f"Circuit breaker is OPEN. Try again later.")
                else:
                    # Переходим в HALF_OPEN для тестирования
                    self.state = CircuitState.HALF_OPEN
                    logger.info("circuit_breaker_half_open")

        # Пытаемся вызвать функцию
        try:
            result = await func(*args, **kwargs)
            # Успех - сбрасываем счетчик
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.CLOSED
                    logger.info("circuit_breaker_closed")
                self.failure_count = 0
            return result

        except self.expected_exception as e:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.error(
                        "circuit_breaker_opened",
                        failure_count=self.failure_count,
                        error=str(e),
                    )
                else:
                    logger.warning(
                        "circuit_breaker_failure",
                        failure_count=self.failure_count,
                        threshold=self.failure_threshold,
                    )

            raise

    def reset(self):
        """Сбросить circuit breaker в начальное состояние."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        logger.info("circuit_breaker_reset")


# Глобальные circuit breakers
_serper_circuit_breaker: Optional[CircuitBreaker] = None


def get_serper_circuit_breaker() -> CircuitBreaker:
    """Получить circuit breaker для Serper API."""
    global _serper_circuit_breaker
    if _serper_circuit_breaker is None:
        _serper_circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=Exception,
        )
    return _serper_circuit_breaker

