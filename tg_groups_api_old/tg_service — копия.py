import os
from typing import List, Dict

from dotenv import load_dotenv
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession

# Локально читаем .env, на Render переменные уже есть в окружении
load_dotenv()

TG_API_ID = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")
TG_SESSION_STRING = os.getenv("TG_SESSION_STRING")

if not TG_API_ID or not TG_API_HASH:
    raise RuntimeError(
        "TG_API_ID / TG_API_HASH отсутствуют. "
        "Добавьте их в переменные окружения Render или в .env локально."
    )

if not TG_SESSION_STRING:
    raise RuntimeError(
        "TG_SESSION_STRING отсутствует. "
        "Установите его в Environment (StringSession из локального клиента)."
    )

TG_API_ID = int(TG_API_ID)

# Клиент на основе строковой сессии
client = TelegramClient(StringSession(TG_SESSION_STRING), TG_API_ID, TG_API_HASH)


async def ensure_connected() -> None:
    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        raise RuntimeError("Telegram клиент не авторизован (проверьте TG_SESSION_STRING).")


def _chat_type(chat: types.TypeChat) -> str:
    if isinstance(chat, types.Channel):
        return "channel" if chat.broadcast else "megagroup"
    if isinstance(chat, types.Chat):
        return "group"
    return "unknown"


async def search_groups(
    query: str,
    limit: int = 10,
    types_only: str = "channel,megagroup,group",
    min_members: int = 0,
) -> List[Dict]:
    await ensure_connected()

    type_set = {t.strip() for t in types_only.split(",") if t.strip()}
    result: List[Dict] = []

    resp = await client(
        functions.contacts.SearchRequest(
            q=query,
            limit=limit,
        )
    )

    for chat in resp.chats:
        t = _chat_type(chat)
        if type_set and t not in type_set:
            continue

        members = getattr(chat, "participants_count", None)
        if min_members and members is not None and members < min_members:
            continue

        result.append(
            {
                "id": chat.id,
                "title": getattr(chat, "title", ""),
                "username": getattr(chat, "username", None),
                "members_count": members,
                "type": t,
            }
        )

    return result
