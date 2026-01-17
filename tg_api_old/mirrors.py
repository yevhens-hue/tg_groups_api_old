import os
from typing import Dict, List
from urllib.parse import urlparse

import requests


# ==========
#  CONFIG
# ==========

# Мерчанты, с которыми будем работать
MERCHANTS: Dict[str, Dict] = {
    "1xbet": {
        "brand": "1xbet",
        "official_domains": ["1xbet.com", "1xbet.xyz", "indi.1xbet.com"],
    },
    "dafabet": {
        "brand": "dafabet",
        "official_domains": ["dafabet.com", "dafabet.net", "dafabetindia.com"],
    },
    "stake": {
        "brand": "stake",
        "official_domains": ["stake.com"],
    },
    "parimatch": {
        "brand": "parimatch",
        "official_domains": ["parimatch.com", "parimatch.in"],
    },
    "4rabet": {
        "brand": "4rabet",
        "official_domains": ["4rabet.com", "4rabet.in"],
    },
    "playinexch": {
        "brand": "playinexch",
        "official_domains": ["playinexch.com", "playinexch.co"],
    },
    "bcgame": {
        "brand": "bc game",
        "official_domains": ["bc.game"],
    },
    "1win": {
        "brand": "1win",
        "official_domains": ["1win.com", "1win.in", "1win.xyz"],
    },
    "melbet": {
        "brand": "melbet",
        "official_domains": ["melbet.com", "melbet.in"],
    },
    "fun88": {
        "brand": "fun88",
        "official_domains": ["fun88.com", "fun88india.com"],
    },
}


# ==========
#  UTILS
# ==========

def _get_domain(url: str) -> str:
    """Нормализуем домен: вырезаем схему, www и сабдомены."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
    except Exception:
        return ""

    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


# ==========
#  SERPAPI
# ==========

def serpapi_google_search(
    query: str,
    gl: str = "in",
    hl: str = "en",
    num: int = 20,
) -> List[str]:
    """
    Простой клиент к SerpAPI: возвращает список URL из organic_results.
    """
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY is not set in environment")

    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "gl": gl,
        "hl": hl,
        "num": num,
    }

    resp = requests.get("https://serpapi.com/search", params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    urls: List[str] = []
    for item in data.get("organic_results", []):
        link = item.get("link")
        if link:
            urls.append(link)

    return urls


# ==========
#  CLASSIFIER
# ==========

def classify_url(url: str, cfg: Dict) -> Dict:
    """
    Классифицируем URL:
    - main_mirror: домен в official_domains
    - brand_like_mirror: домен содержит бренд
    - prelander: в финальном URL есть бренд, но домен не похож
    - other: всё остальное
    """
    brand = cfg["brand"].lower().replace(" ", "")
    official = {d.lower() for d in cfg.get("official_domains", [])}

    # Получаем финальный URL после редиректов
    try:
        resp = requests.get(url, allow_redirects=True, timeout=15)
        final_url = str(resp.url)
    except Exception:
        final_url = url

    domain = _get_domain(final_url)

    t = "other"

    # 1) официальный домен
    if domain in official:
        t = "main_mirror"
    # 2) домен похож на бренд
    elif brand and brand in domain.replace(" ", ""):
        t = "brand_like_mirror"
    # 3) бренд в финальном URL (страница явно про мерчанта)
    elif brand and brand in final_url.lower().replace(" ", ""):
        t = "prelander"

    return {
        "type": t,
        "original_url": url,
        "final_url": final_url,
        "domain": domain,
    }

