# collect_mirrors.py

import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from merchants_config import MERCHANTS

# твой ключ SerpAPI
SERPAPI_API_KEY = "f1d398bf2f711547f0165e09ebbbf344bf6da001cbcba9e89c42af83ae865556"


def get_domain(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def serpapi_google_search(query: str, gl="in", hl="en", num=10):
    url = "https://serpapi.com/search"
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": num,
        "gl": gl,
        "hl": hl,
    }

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    links = []
    for item in data.get("organic_results", []):
        link = item.get("link")
        if link:
            links.append(link)

    return links


def fetch_final_url(url: str, timeout: int = 15) -> str:
    """
    Получаем финальный URL с учётом 301/302-редиректов.
    Без headless-браузера, просто follow redirects.
    """
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        return resp.url
    except Exception:
        return url


def page_links_merchant(html: str, merchant_cfg: dict) -> bool:
    """
    Грубая проверка: есть ли внутри страницы ссылки на бренд / оф. домены.
    Если есть — считаем, что это прокладка.
    """
    brand = merchant_cfg["brand"].lower()
    official = [d.lower() for d in merchant_cfg["official_domains"]]

    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").lower()
        if brand in href:
            return True
        if any(dom in href for dom in official):
            return True
    return False


def classify_url(url: str, merchant_cfg: dict) -> dict:
    """
    Классифицируем один URL:
    - main_mirror        — оф. домен
    - brand_like_mirror  — домен похож на бренд (1xbet-...)
    - prelander          — страница, внутри которой ссылки на мерчанта
    - other              — всё остальное
    """
    brand = merchant_cfg["brand"].lower()
    official = [d.lower() for d in merchant_cfg["official_domains"]]

    original_url = url
    final_url = fetch_final_url(original_url)
    final_domain = get_domain(final_url)

    # 1) оф. домен / зеркало
    if final_domain in official:
        return {
            "type": "main_mirror",
            "original_url": original_url,
            "final_url": final_url,
            "domain": final_domain,
        }

    # 2) домен с брендом в имени
    if brand in final_domain:
        return {
            "type": "brand_like_mirror",
            "original_url": original_url,
            "final_url": final_url,
            "domain": final_domain,
        }

    # 3) пробуем определить прокладку
    try:
        resp = requests.get(final_url, timeout=15)
        html = resp.text
        if page_links_merchant(html, merchant_cfg):
            return {
                "type": "prelander",
                "original_url": original_url,
                "final_url": final_url,
                "domain": final_domain,
            }
    except Exception:
        pass

    # 4) мусор
    return {
        "type": "other",
        "original_url": original_url,
        "final_url": final_url,
        "domain": final_domain,
    }


if __name__ == "__main__":
    merchant_id = "1xbet"
    merchant_cfg = MERCHANTS[merchant_id]

    keyword = "cricket betting"
    query = f'{merchant_cfg["brand"]} {keyword}'

    print("Query:", query)

    urls = serpapi_google_search(query, gl="in", hl="en", num=20)
    print("Total URLs:", len(urls))

    results = []
    for u in urls:
        res = classify_url(u, merchant_cfg)
        results.append(res)

    print("\nClassified results:")
    for r in results:
        print(f"{r['type']:18} | {r['domain']:25} | {r['final_url']}")

    # Если нужен только список зеркал и прокладок — можно отфильтровать
    mirrors_only = [r for r in results if r["type"] != "other"]

    print("\nMirrors / prelanders only:")
    for r in mirrors_only:
        print(f"{r['type']:18} | {r['domain']:25} | {r['final_url']}")

