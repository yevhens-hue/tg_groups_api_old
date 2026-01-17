import os
from typing import Optional, List

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

# Берём креды из переменных окружения (.env)
API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]

# sessions/tg_session.session — твой файл сессии Telethon
SESSION_PATH = os.path.join("sessions", "tg_session")

client = TelegramClient(SESSION_PATH, API_ID, API_HASH)


async def init_client() -> TelegramClient:
    """Гарантированно запускаем клиента один раз."""
    if not client.is_connected():
        await client.start()
    return client


class TgGroup:
    def __init__(
        self,
        id: int,
        title: str,
        username: Optional[str],
        is_megagroup: bool,
        is_broadcast: bool,
    ):
        self.id = id
        self.title = title
        self.username = username
        self.is_megagroup = is_megagroup
        self.is_broadcast = is_broadcast


async def search_groups(
    query: str,
    limit: int = 20,
    only_with_username: Optional[bool] = None,
    max_dialogs: int = 300,
) -> List[TgGroup]:
    """
    Быстрый поиск групп/каналов среди диалогов аккаунта.

    query               — строка поиска в title/username
    limit               — сколько максимум вернуть
    only_with_username  — True: только с @username,
                          False: только без @username,
                          None: без фильтра
    max_dialogs         — сколько максимум диалогов просматривать
                          (для скорости)
    """
    cl = await init_client()
    q = query.lower().strip()

    results: List[TgGroup] = []

    # Итерируемся по диалогам потоково, а не загружаем всё разом
    async for d in cl.iter_dialogs(limit=max_dialogs):
        entity = d.entity

        # интересуют только группы/каналы
        if not isinstance(entity, (Channel, Chat)):
            continue

        title = getattr(entity, "title", "") or ""
        username = getattr(entity, "username", None)
        is_megagroup = bool(getattr(entity, "megagroup", False))
        is_broadcast = bool(getattr(entity, "broadcast", False))

        searchable = f"{title} {username or ''}".lower()
        if q not in searchable:
            continue

        # фильтр по наличию username
        if only_with_username is True and not username:
            continue
        if only_with_username is False and username:
            continue

        results.append(
            TgGroup(
                id=entity.id,
                title=title,
                username=username,
                is_megagroup=is_megagroup,
                is_broadcast=is_broadcast,
            )
        )

        # как только набрали нужный лимит — сразу выходим
        if len(results) >= limit:
            break

    # сортировка по названию
    results.sort(key=lambda g: g.title.lower())

    return results[:limit]
