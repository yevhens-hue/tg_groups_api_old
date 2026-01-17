# services/keepalive.py
import asyncio
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger()


class KeepAliveService:
    """
    Сервис для поддержания активности приложения.
    Периодически делает запросы к health endpoint для предотвращения таймаутов.
    """

    def __init__(self, health_url: str = "http://localhost:8011/health", interval: int = 60):
        self.health_url = health_url
        self.interval = interval
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def _health_check(self):
        """Выполняет health check."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.health_url)
                if response.status_code == 200:
                    logger.debug("keepalive_health_check_ok", status_code=200)
                else:
                    logger.warning(
                        "keepalive_health_check_failed",
                        status_code=response.status_code,
                    )
        except Exception as e:
            logger.warning("keepalive_health_check_error", error=str(e))

    async def _run(self):
        """Основной цикл keep-alive."""
        while self._running:
            try:
                await self._health_check()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                logger.info("keepalive_cancelled")
                break
            except Exception as e:
                logger.error("keepalive_error", error=str(e), exc_info=True)
                await asyncio.sleep(self.interval)

    async def start(self):
        """Запустить keep-alive сервис."""
        if self._running:
            logger.warning("keepalive_already_running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("keepalive_started", interval=self.interval, url=self.health_url)

    async def stop(self):
        """Остановить keep-alive сервис."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("keepalive_stopped")


# Глобальный экземпляр
_keepalive_service: Optional[KeepAliveService] = None


def get_keepalive_service(health_url: str = "http://localhost:8011/health", interval: int = 60) -> KeepAliveService:
    """Получить глобальный keep-alive сервис."""
    global _keepalive_service
    if _keepalive_service is None:
        _keepalive_service = KeepAliveService(health_url=health_url, interval=interval)
    return _keepalive_service


