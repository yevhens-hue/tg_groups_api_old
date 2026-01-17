from datetime import datetime
from typing import List, Optional

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from mirrors import MERCHANTS, serpapi_google_search, classify_url
from tg_service import search_groups as tg_search, TgChat

# Загружаем переменные окружения из .env
load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="TG API",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# =====================================================
#                 MODELS
# =====================================================

class CollectMirrorsRequest(BaseModel):
    merchant: str
    keyword: str
    country: str = "in"
    lang: str = "en"
    limit: int = 20


class CollectMirrorsBatchRequest(BaseModel):
    merchants: List[str]
    keywords: List[str]
    country: str = "in"
    lang: str = "en"
    limit: int = 20


class SearchGroupsRequest(BaseModel):
    query: str = Field(..., description="Поисковый запрос в Telegram")
    limit: int = Field(10, description="Максимум результатов")
    types_only: str = Field("channel,megagroup,group", description="Типы чатов через запятую")
    min_members: int = Field(0, description="Мин. количество участников")


# =====================================================
#           MIRROR FINDER — SINGLE MERCHANT
# =====================================================

@app.post("/collect_mirrors")
async def collect_mirrors(req: CollectMirrorsRequest):
    if req.merchant not in MERCHANTS:
        return {"error": f"Unknown merchant: {req.merchant}"}

    cfg = MERCHANTS[req.merchant]
    query = f"{cfg['brand']} {req.keyword}"

    urls = serpapi_google_search(
        query,
        gl=req.country,
        hl=req.lang,
        num=req.limit,
    )

    results = [classify_url(u, cfg) for u in urls]

    grouped = {
        "main_mirror": [],
        "brand_like_mirror": [],
        "prelander": [],
        "other": [],
    }

    for r in results:
        grouped[r["type"]].append(r)

    return {
        "ok": True,
        "merchant": req.merchant,
        "keyword": req.keyword,
        "country": req.country,
        "lang": req.lang,
        "limit": req.limit,
        "results": grouped,
    }


# =====================================================
#           MIRROR FINDER — BATCH
# =====================================================

@app.post("/collect_mirrors_batch")
async def collect_mirrors_batch(req: CollectMirrorsBatchRequest):
    items = []

    for merchant in req.merchants:

        if merchant not in MERCHANTS:
            items.append({
                "merchant": merchant,
                "keyword": None,
                "error": f"Unknown merchant: {merchant}",
            })
            continue

        cfg = MERCHANTS[merchant]

        for keyword in req.keywords:
            query = f"{cfg['brand']} {keyword}"

            urls = serpapi_google_search(
                query,
                gl=req.country,
                hl=req.lang,
                num=req.limit,
            )

            results = [classify_url(u, cfg) for u in urls]

            grouped = {
                "main_mirror": [],
                "brand_like_mirror": [],
                "prelander": [],
                "other": [],
            }

            for r in results:
                grouped[r["type"]].append(r)

            items.append({
                "merchant": merchant,
                "keyword": keyword,
                "results": grouped,
            })

    return {
        "ok": True,
        "country": req.country,
        "lang": req.lang,
        "limit": req.limit,
        "items": items,
    }


# =====================================================
#           TELEGRAM GROUP SEARCH
# =====================================================

@app.post("/search_groups")
async def search_groups(req: SearchGroupsRequest):
    """
    Поиск каналов и групп в Telegram.
    Проксируем параметры в tg_service.search_groups().
    """
    try:
        result = await tg_search(
            query=req.query,           # ← ключевая правка: заменено q= на query=
            limit=req.limit,
            types_only=req.types_only,
            min_members=req.min_members,
        )
        return result

    except Exception as e:
        logger.exception("Error in /search_groups")
        raise HTTPException(status_code=500, detail=str(e))
