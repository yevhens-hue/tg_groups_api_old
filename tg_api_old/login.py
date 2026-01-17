from telethon import TelegramClient
import os
import asyncio

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION_PATH = os.path.join("sessions", "tg_session")

client = TelegramClient(SESSION_PATH, API_ID, API_HASH)


async def main():
    # запускаем клиента и проходим логин
    await client.start()
    print("Logged in successfully!")


if __name__ == "__main__":
    asyncio.run(main())
