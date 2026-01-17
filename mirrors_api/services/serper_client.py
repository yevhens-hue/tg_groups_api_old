# services/serper_client.py
import os
from typing import List, Optional
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

import structlog
from config import get_settings
from .cache import get_serper_cache
from .circuit_breaker import get_serper_circuit_breaker

logger = structlog.get_logger()
settings = get_settings()

SERPER_API_KEY = os.getenv("SERPER_API_KEY") or settings.SERPER_API_KEY
SERPER_URL = "https://google.serper.dev/search"


class SerperError(Exception):
    pass


async def _search_domains_impl(
    query: str,
    num: int = 10,
    country: str = "in",
    lang: str = "en",
) -> List[str]:
    """
    Внутренняя реализация поиска без кэша и circuit breaker.
    """
    if not SERPER_API_KEY:
        raise SerperError("SERPER_API_KEY is not set in environment")

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "q": query,
        "num": num,
        "gl": country,
        "hl": lang,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(SERPER_URL, headers=headers, json=payload)
        if resp.status_code != 200:
            raise SerperError(f"Serper error {resp.status_code}: {resp.text}")

        data = resp.json()

    urls: List[str] = []
    for item in data.get("organic", []):
        url = item.get("link")
        if url:
            urls.append(url)

    return urls


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((SerperError, httpx.HTTPError)),
    reraise=True,
)
async def _search_domains_with_retry(
    query: str,
    num: int = 10,
    country: str = "in",
    lang: str = "en",
) -> List[str]:
    """Поиск с retry логикой."""
    return await _search_domains_impl(query, num, country, lang)


async def search_domains(
    query: str,
    num: int = 10,
    country: str = "in",
    lang: str = "en",
    use_cache: bool = True,
) -> List[str]:
    """
    Делает запрос в Serper.dev и возвращает список URL из органической выдачи.
    Использует кэш, circuit breaker и retry логику.
    """
    cache = get_serper_cache()
    circuit_breaker = get_serper_circuit_breaker()
    
    # Создаем ключ кэша
    cache_key = cache._make_key("serper", query=query, num=num, country=country, lang=lang)
    
    # Проверяем кэш
    if use_cache:
        cached_result = await cache.get(cache_key)
        if cached_result is not None:
            logger.debug("serper_cache_hit", query=query[:50])
            return cached_result
    
    # Вызываем через circuit breaker с retry
    try:
        urls = await circuit_breaker.call(
            _search_domains_with_retry,
            query=query,
            num=num,
            country=country,
            lang=lang,
        )
        
        # Сохраняем в кэш
        if use_cache:
            await cache.set(cache_key, urls, ttl=21600)  # 6 часов
        
        logger.info("serper_search_success", query=query[:50], urls_count=len(urls))
        return urls
        
    except Exception as e:
        logger.error("serper_search_failed", query=query[:50], error=str(e))
        raise SerperError(f"Failed to search: {str(e)}") from e
