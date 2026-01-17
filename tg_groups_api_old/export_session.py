import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("TG_API_ID"))
API_HASH = os.getenv("TG_API_HASH")
SESSION_PATH = os.getenv("TG_SESSION_PATH", "tg_groups_session.session")

async def main():
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("Not authorized. Run login.py locally first.")
        await client.disconnect()
        return

    s = StringSession.save(client.session)
    print("\n==== YOUR STRING SESSION BELOW ====\n")
    print(s)
    print("\n==== END STRING SESSION ====\n")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
