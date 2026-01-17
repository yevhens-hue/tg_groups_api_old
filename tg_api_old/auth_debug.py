import asyncio
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError,
    FloodWaitError, PhoneNumberBannedError
)

API_ID = 23888829
API_HASH = "4f788fb07410a66dee1a28fabbe36db0"
SESSION = "/Users/yevhen.shaforostov/tg_api/sessions/telegram_session"

async def main():
    c = TelegramClient(SESSION, API_ID, API_HASH)
    await c.connect()
    print("connected:", c.is_connected())

    if await c.is_user_authorized():
        me = await c.get_me()
        print("✅ already authorized as:", me.username or me.id)
        await c.disconnect(); return

    phone = input("📱 Phone (+380...): ").strip()
    try:
        await c.send_code_request(phone)
        print("code sent")
    except PhoneNumberBannedError:
        print("🚫 Phone number is banned"); await c.disconnect(); return
    except FloodWaitError as e:
        print(f"⏳ Flood wait: {e.seconds}s"); await c.disconnect(); return

    while True:
        code = input("🔢 Code: ").strip()
        try:
            try:
                await c.sign_in(phone, code)
            except SessionPasswordNeededError:
                pwd = input("🔐 2FA password: ").strip()
                await c.sign_in(password=pwd)
            break
        except PhoneCodeInvalidError:
            print("❌ invalid code, try again")
            continue
        except PhoneCodeExpiredError:
            print("⌛ code expired; sending new...")
            await c.send_code_request(phone)

    print("authorized:", await c.is_user_authorized())
    me = await c.get_me()
    print("✅ authorized as:", me.username or me.id)
    await c.disconnect()

asyncio.run(main())
