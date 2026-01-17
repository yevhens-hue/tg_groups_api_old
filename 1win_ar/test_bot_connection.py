#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения бота к Telegram API.
"""
import asyncio
import os
from telegram.ext import Application

TOKEN = '8324666844:AAGgN-DEt0fv43gAipQrFh2DWfaw0Jg0T2Q'

async def test_connection():
    """Проверка подключения бота."""
    print("=" * 60)
    print("🧪 ТЕСТ ПОДКЛЮЧЕНИЯ БОТА")
    print("=" * 60)
    print()
    
    try:
        app = Application.builder().token(TOKEN).build()
        
        # Проверка 1: Получение информации о боте
        print("1️⃣ Проверка информации о боте...")
        bot_info = await app.bot.get_me()
        print(f"   ✅ Бот найден: @{bot_info.username}")
        print(f"   Имя: {bot_info.first_name}")
        print(f"   ID: {bot_info.id}")
        print()
        
        # Проверка 2: Проверка webhook
        print("2️⃣ Проверка webhook...")
        webhook_info = await app.bot.get_webhook_info()
        if webhook_info.url:
            print(f"   ⚠️  Webhook установлен: {webhook_info.url}")
            print("   ❌ Это мешает polling! Удаляю webhook...")
            await app.bot.delete_webhook(drop_pending_updates=True)
            print("   ✅ Webhook удален")
        else:
            print("   ✅ Webhook не установлен (polling должен работать)")
        print()
        
        # Проверка 3: Получение обновлений
        print("3️⃣ Проверка получения обновлений...")
        updates = await app.bot.get_updates(limit=1, timeout=1)
        print(f"   ✅ API работает, получено обновлений: {len(updates)}")
        print()
        
        print("=" * 60)
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print("=" * 60)
        print()
        print("🚀 Бот готов к запуску!")
        print("   Запустите: python3 bot.py")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
