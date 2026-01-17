# services/browser_pool.py
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright

logger = structlog.get_logger()


class BrowserPool:
    """
    Пул браузеров для переиспользования Playwright инстансов.
    Уменьшает overhead от запуска браузеров на каждый запрос.
    """

    def __init__(self, max_browsers: int = 5):
        self.max_browsers = max_browsers
        self._playwright: Optional[Playwright] = None
        self._browsers: list[Browser] = []
        self._available: asyncio.Queue = asyncio.Queue(maxsize=max_browsers)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self):
        """Инициализация пула браузеров."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            self._playwright = await async_playwright().start()
            
            # Создаем начальные браузеры
            for _ in range(min(2, self.max_browsers)):
                browser = await self._playwright.chromium.launch(headless=True)
                self._browsers.append(browser)
                await self._available.put(browser)

            self._initialized = True
            logger.info("browser_pool_initialized", count=len(self._browsers))

    async def get_browser(self) -> Browser:
        """Получить браузер из пула или создать новый."""
        if not self._initialized:
            await self.initialize()

        try:
            # Пытаемся получить из очереди (неблокирующе)
            browser = self._available.get_nowait()
            return browser
        except asyncio.QueueEmpty:
            # Если очередь пуста, проверяем можем ли создать новый
            async with self._lock:
                if len(self._browsers) < self.max_browsers:
                    browser = await self._playwright.chromium.launch(headless=True)
                    self._browsers.append(browser)
                    logger.debug("browser_created", total=len(self._browsers))
                    return browser
                else:
                    # Ждем освобождения браузера
                    browser = await self._available.get()
                    return browser

    async def return_browser(self, browser: Browser):
        """Вернуть браузер в пул."""
        if browser in self._browsers:
            try:
                self._available.put_nowait(browser)
            except asyncio.QueueFull:
                # Если очередь полна, просто закрываем браузер
                await browser.close()
                async with self._lock:
                    if browser in self._browsers:
                        self._browsers.remove(browser)

    @asynccontextmanager
    async def acquire(self):
        """Context manager для получения браузера."""
        browser = await self.get_browser()
        try:
            yield browser
        finally:
            await self.return_browser(browser)

    async def close_all(self):
        """Закрыть все браузеры и playwright."""
        async with self._lock:
            for browser in self._browsers:
                try:
                    await browser.close()
                except Exception:
                    pass
            self._browsers.clear()
            
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

        self._initialized = False
        logger.info("browser_pool_closed")


# Глобальный пул браузеров
_browser_pool: Optional[BrowserPool] = None


def get_browser_pool() -> BrowserPool:
    """Получить глобальный пул браузеров."""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool(max_browsers=5)
    return _browser_pool


async def close_browser_pool():
    """Закрыть глобальный пул браузеров (для shutdown)."""
    global _browser_pool
    if _browser_pool:
        await _browser_pool.close_all()
        _browser_pool = None

