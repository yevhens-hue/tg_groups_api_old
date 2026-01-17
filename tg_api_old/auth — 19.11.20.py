from typing import Optional, List, Literal

from fastapi import FastAPI
from pydantic import BaseModel

from tg_service import search_groups as tg_search

app = FastAPI(title="TG API", docs_url="/docs", openapi_url="/openapi.json")


@app.get("/health")
async def health():
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from tg_service import search_groups as tg_search, TgChat

app = FastAPI(title="TG API", docs_url="/docs", openapi_url="/openapi.json")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Pydantic-модели ----------

class SearchRequest(BaseModel):
    query: str
    limit: int = 20


class AdminInfo(BaseModel):
    id: int
    username: Optional[str] = None
    is_bot: bool
    is_verified: bool
    role: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    last_seen_status: Optional[str] = None


class GroupItem(BaseModel):
    id: int
    title: str
    username: Optional[str]
    is_megagroup: bool
    is_broadcast: bool
    chat_type: str
    subscribers_count: Optional[int]
    description: Optional[str]
    created_at: Optional[str]

    admins: List[AdminInfo] = Field(default_factory=list)


class SearchResponse(BaseModel):
    ok: bool
    query: str
    total_found: int
    items: List[GroupItem]


def tg_chat_to_item(chat: TgChat) -> GroupItem:
    """Конвертация нашего TgChat из tg_service в Pydantic-модель GroupItem."""
    return GroupItem(
        id=chat.id,
        title=chat.title,
        username=chat.username,
        is_megagroup=chat.is_megagroup,
        is_broadcast=chat.is_broadcast,
        chat_type=chat.chat_type,
        subscribers_count=chat.subscribers_count,
        description=chat.description,
        created_at=chat.created_at,
        admins=[AdminInfo(**a) for a in chat.admins],
    )


# ---------- Эндпоинт поиска ----------

@app.post("/search_groups", response_model=SearchResponse)
async def search_groups_endpoint(req: SearchRequest):
    chats: List[TgChat] = await tg_search(
        query=req.query,
        limit=req.limit,
        # пока без доп. фильтров — при желании добавим позже
        only_with_username=None,
        india_only=None,
        chat_type=None,
    )

    items = [tg_chat_to_item(c) for c in chats]

    return SearchResponse(
        ok=True,
        query=req.query,
        total_found=len(items),
        items=items,
    )
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
