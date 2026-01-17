import os
import asyncio
from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
)

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION_PATH = os.path.join("sessions", "tg_session")

client = TelegramClient(SESSION_PATH, API_ID, API_HASH)


async def auth():
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print("✅ Уже авторизован:", me.username or me.id)
        return

    phone = input("📞 Телефон: ").strip()
    await client.send_code_request(phone)

    while True:
        code = input("🔢 Код: ").strip()
        try:
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                pwd = input("🔐 2FA пароль: ").strip()
                await client.sign_in(password=pwd)
            break
        except PhoneCodeInvalidError:
            print("❌ Неверный код, попробуй ещё раз")
        except PhoneCodeExpiredError:
            print("⌛ Код просрочен, отправляю новый...")
            await client.send_code_request(phone)

    if await client.is_user_authorized():
        me = await client.get_me()
        print("✅ Авторизация успешна:", me.username or me.id)
    else:
        print("❗ Не авторизован (какая-то ошибка)")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(auth())
