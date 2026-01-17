from typing import Optional, List, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from tg_service import search_groups as tg_search

app = FastAPI(title="TG API", docs_url="/docs", openapi_url="/openapi.json")


@app.get("/health")
async def health():
    return {"status": "ok"}


class SearchFilters(BaseModel):
    has_username: Optional[bool] = None
    india_only: Optional[bool] = None
    chat_type: Optional[Literal["group", "channel"]] = None  # фильтр тип чата


class SearchRequest(BaseModel):
    query: str
    limit: int = 20
    sort_by: Literal["title"] = "title"
    sort_order: Literal["asc", "desc"] = "asc"
    filters: Optional[SearchFilters] = None


class GroupResponse(BaseModel):
    id: int
    title: str
    username: Optional[str]
    is_megagroup: bool
    is_broadcast: bool
    chat_type: Literal["group", "channel"]
    subscribers_count: Optional[int] = None
    description: Optional[str] = None
    created_at: Optional[str] = None  # ISO-строка даты


class SearchResponse(BaseModel):
    ok: bool
    query: str
    total_found: int
    items: List[GroupResponse]


@app.post("/search_groups", response_model=SearchResponse)
async def search_groups(req: SearchRequest):
    # разбор фильтров
    only_username: Optional[bool] = None
    india_only: Optional[bool] = None
    chat_type: Optional[Literal["group", "channel"]] = None

    if req.filters:
        only_username = req.filters.has_username
        india_only = req.filters.india_only
        chat_type = req.filters.chat_type

    # вызываем Telethon-поиск (глобальный)
    groups = await tg_search(
        query=req.query,
        limit=req.limit,
        only_with_username=only_username,
        india_only=india_only,
        chat_type=chat_type,
    )

    # сортировка DESC при необходимости
    if req.sort_order == "desc":
        groups = list(reversed(groups))

    items = [
        GroupResponse(
            id=g.id,
            title=g.title,
            username=g.username,
            is_megagroup=g.is_megagroup,
            is_broadcast=g.is_broadcast,
            chat_type=g.chat_type,
            subscribers_count=g.subscribers_count,
            description=g.description,
            created_at=g.created_at,
        )
        for g in groups
    ]

    return SearchResponse(
        ok=True,
        query=req.query,
        total_found=len(items),
        items=items,
    )
