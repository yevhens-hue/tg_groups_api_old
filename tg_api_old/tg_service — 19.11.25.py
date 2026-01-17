import os
from typing import Optional, List, Literal
from datetime import datetime

from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.types import Channel, Chat

# Тип чата: группа или канал
ChatType = Literal["group", "channel"]

# Эвристические ключевые слова для индийских чатов (если включён india_only)
INDIA_KEYWORDS = [
    "india",
    "indian",
    "bharat",
    "🇮🇳",
    "hindi",
    "tamil",
    "telugu",
    "malayalam",
    "kannada",
    "bengali",
    "punjabi",
    "upi",
    "rupee",
    "inr",
]

# Читаем креды из окружения (.env)
API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]

# sessions/tg_session.session — файл сессии Telethon
SESSION_PATH = os.path.join("sessions", "tg_session")

client = TelegramClient(SESSION_PATH, API_ID, API_HASH)


async def init_client() -> TelegramClient:
    """Инициализируем и запускаем клиента один раз."""
    if not client.is_connected():
        await client.start()
    return client


class TgChat:
    """Унифицированная модель канала/группы для FastAPI."""

    def __init__(
        self,
        id: int,
        title: str,
        username: Optional[str],
        is_megagroup: bool,
        is_broadcast: bool,
        chat_type: ChatType,
        subscribers_count: Optional[int] = None,
        description: Optional[str] = None,
        created_at: Optional[str] = None,  # ISO-строка
    ):
        self.id = id
        self.title = title
        self.username = username
        self.is_megagroup = is_megagroup
        self.is_broadcast = is_broadcast
        self.chat_type = chat_type
        self.subscribers_count = subscribers_count
        self.description = description
        self.created_at = created_at


def is_india_chat(title: str, username: Optional[str]) -> bool:
    """Эвристика, что чат «индийский» по названию / username."""
    text = f"{title} {username or ''}".lower()
    return any(k in text for k in INDIA_KEYWORDS)


async def get_chat_details(cl: TelegramClient, chat) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Получаем:
    - количество подписчиков (participants_count)
    - описание (about)
    - дату создания (из поля date, если есть)
    Возвращаем (subscribers_count, description, created_at_iso)
    """
    subscribers_count: Optional[int] = None
    description: Optional[str] = None

    # дата обычно есть прямо в объекте чата
    raw_date = getattr(chat, "date", None)
    created_at_iso: Optional[str] = None
    if isinstance(raw_date, datetime):
        created_at_iso = raw_date.isoformat()

    try:
        if isinstance(chat, Channel):
            full = await cl(GetFullChannelRequest(chat))
            full_chat = getattr(full, "full_chat", None)
            if full_chat is not None:
                subscribers_count = getattr(full_chat, "participants_count", None)
                description = getattr(full_chat, "about", None)

        elif isinstance(chat, Chat):
            full = await cl(GetFullChatRequest(chat.id))
            full_chat = getattr(full, "full_chat", None)
            if full_chat is not None:
                subscribers_count = getattr(full_chat, "participants_count", None)
                description = getattr(full_chat, "about", None)

    except Exception:
        # Игнорируем ошибки (например, нет доступа / ограничение Telegram)
        pass

    return subscribers_count, description, created_at_iso


async def search_groups(
    query: str,
    limit: int = 20,
    only_with_username: Optional[bool] = None,
    india_only: Optional[bool] = None,
    chat_type: Optional[ChatType] = None,  # None — и группы, и каналы
) -> List[TgChat]:
    """
    ГЛОБАЛЬНЫЙ поиск по Telegram (не по твоим диалогам).

    query               — строка поиска
    limit               — максимум результатов
    only_with_username  — True: только с @username,
                          False: только без @username,
                          None: не фильтровать
    india_only          — True: дополнительно фильтровать по INDIA_KEYWORDS
    chat_type           — "group", "channel" или None (оба)
    """
    cl = await init_client()
    q = query.strip()
    if not q:
        return []

    # Берём запас по количеству, потому что потом ещё фильтруем
    raw_limit = max(limit * 3, 50)

    # Глобальный поиск Telegram
    result = await cl(SearchRequest(q=q, limit=raw_limit))

    out: List[TgChat] = []

    for chat in result.chats:
        if not isinstance(chat, (Channel, Chat)):
            continue

        title: str = getattr(chat, "title", "") or ""
        username: Optional[str] = getattr(chat, "username", None)
        is_megagroup: bool = bool(getattr(chat, "megagroup", False))
        is_broadcast: bool = bool(getattr(chat, "broadcast", False))

        # Определяем тип: группа или канал
        if isinstance(chat, Chat):
            chat_type_value: ChatType = "group"
        elif isinstance(chat, Channel):
            chat_type_value = "group" if is_megagroup else "channel"
        else:
            chat_type_value = "group"

        # Фильтр по типу, если задан
        if chat_type is not None and chat_type_value != chat_type:
            continue

        # Фильтр по username
        if only_with_username is True and not username:
            continue
        if only_with_username is False and username:
            continue

        # Фильтр «только Индия» (опционально)
        if india_only:
            if not is_india_chat(title, username):
                continue

        # Дополнительный запрос: подписчики, описание, дата
        subscribers_count, description, created_at_iso = await get_chat_details(cl, chat)

        out.append(
            TgChat(
                id=chat.id,
                title=title,
                username=username,
                is_megagroup=is_megagroup,
                is_broadcast=is_broadcast,
                chat_type=chat_type_value,
                subscribers_count=subscribers_count,
                description=description,
                created_at=created_at_iso,
            )
        )

        if len(out) >= limit:
            break

    # Лёгкая сортировка по названию
    out.sort(key=lambda c: c.title.lower())
    return out
