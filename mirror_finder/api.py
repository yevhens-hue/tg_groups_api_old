# api.py

from fastapi import FastAPI
from pydantic import BaseModel

from collect_mirrors import serpapi_google_search, classify_url
from merchants_config import MERCHANTS

app = FastAPI()


class CollectRequest(BaseModel):
    merchant: str
    keyword: str
    country: str = "in"
    lang: str = "en"
    limit: int = 20


@app.post("/collect_mirrors")
def collect_mirrors(req: CollectRequest):
    if req.merchant not in MERCHANTS:
        return {"error": f"Unknown merchant: {req.merchant}"}

    cfg = MERCHANTS[req.merchant]

    query = f"{cfg['brand']} {req.keyword}"

    urls = serpapi_google_search(query, gl=req.country, hl=req.lang, num=req.limit)

    results = []
    for u in urls:
        r = classify_url(u, cfg)
        results.append(r)

    # группировка по типам
    grouped = {
        "main_mirror": [],
        "brand_like_mirror": [],
        "prelander": [],
        "other": []
    }

    for r in results:
        grouped[r["type"]].append(r)

    return {
        "ok": True,
        "merchant": req.merchant,
        "keyword": req.keyword,
        "country": req.country,
        "results": grouped
    }

