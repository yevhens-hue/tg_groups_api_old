import os
import asyncio

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

TG_API_ID = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")

if not TG_API_ID or not TG_API_HASH:
    raise RuntimeError("Нужны TG_API_ID и TG_API_HASH в .env или окружении")

TG_API_ID = int(TG_API_ID)


async def main():
    print("Logging in... После логина выведу TG_SESSION_STRING.")
    async with TelegramClient(StringSession(), TG_API_ID, TG_API_HASH) as client:
        session_str = client.session.save()
        print("\n=== TG_SESSION_STRING ===\n")
        print(session_str)
        print("\n=== /TG_SESSION_STRING ===\n")


if __name__ == "__main__":
    asyncio.run(main())
