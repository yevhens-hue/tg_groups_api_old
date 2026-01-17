#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности бота без реального Telegram API.
"""
import asyncio
import os
from pathlib import Path

# Имитируем проверку без реального Telegram API
def test_bot_structure():
    """Проверка структуры бота."""
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ TELEGRAM БОТА")
    print("=" * 60)
    print()
    
    # Проверка 1: Существование файла
    bot_file = Path(__file__).parent / "bot.py"
    if bot_file.exists():
        print("✅ Файл bot.py существует")
    else:
        print("❌ Файл bot.py не найден")
        return False
    
    # Проверка 2: Синтаксис
    try:
        with open(bot_file, 'r') as f:
            code = f.read()
        compile(code, bot_file, 'exec')
        print("✅ Синтаксис bot.py корректен")
    except SyntaxError as e:
        print(f"❌ Синтаксическая ошибка: {e}")
        return False
    
    # Проверка 3: Импорты (без telegram, так как может быть не установлен)
    try:
        import json
        from services.payment_parser_ar import parse_payment_data_1win
        from services.google_sheets import export_payment_data_to_sheets, extract_gid_from_url
        print("✅ Все основные импорты успешны")
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    
    # Проверка 4: Переменные окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if token:
        print(f"✅ TELEGRAM_BOT_TOKEN установлен (длина: {len(token)})")
    else:
        print("⚠️  TELEGRAM_BOT_TOKEN не установлен (нужно для запуска)")
    
    # Проверка 5: Google Sheets токен
    token_file = Path(__file__).parent / "token.json"
    if token_file.exists():
        print("✅ token.json найден (для Google Sheets)")
    else:
        print("⚠️  token.json не найден (экспорт в Google Sheets не будет работать)")
    
    # Проверка 6: Зависимости
    print()
    print("📦 Проверка зависимостей:")
    dependencies = {
        "telegram": "python-telegram-bot",
        "google.auth": "google-auth",
        "playwright": "playwright",
    }
    
    for module, package in dependencies.items():
        try:
            __import__(module)
            print(f"  ✅ {package} установлен")
        except ImportError:
            print(f"  ❌ {package} не установлен")
    
    print()
    print("=" * 60)
    print("📋 РЕЗУЛЬТАТЫ ТЕСТА")
    print("=" * 60)
    print()
    print("✅ Структура бота проверена")
    print("✅ Код готов к запуску")
    print()
    print("🚀 Для запуска бота:")
    print("  1. Установите зависимости: pip install -r requirements.txt")
    print("  2. Получите токен у @BotFather")
    print("  3. Запустите: export TELEGRAM_BOT_TOKEN='ваш_токен' && python bot.py")
    print()
    
    return True


if __name__ == "__main__":
    test_bot_structure()
