#!/usr/bin/env python3
"""
Скрипт для ПЕРВОГО логина и сохранения сессии.
Запускать один раз, чтобы сохранить cookies и session в persistent context.
После этого можно использовать run_parser_ar.py с skip_login=True
"""
import asyncio
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from services.payment_parser_ar import parse_payment_data_1win

# Настройки
TOKEN_FILE = Path(__file__).parent / "token.json"
# Persistent context сохраняется в .cache директории
PERSISTENT_CONTEXT_DIR = Path.home() / ".cache" / "1win_ar" / "profile"

async def main():
    """Первый логин и сохранение сессии."""
    print("=" * 70)
    print("🔐 ПЕРВЫЙ ЛОГИН И СОХРАНЕНИЕ СЕССИИ")
    print("=" * 70)
    print()
    print("Этот скрипт выполнит логин один раз и сохранит сессию.")
    print("После этого можно использовать run_parser_ar.py с skip_login=True")
    print()
    
    # Параметры
    email = "perymury78@gmail.com"
    password = '%m^%G5"}4m'
    base_url = "https://1win.lat/"
    
    print(f"📧 Email: {email}")
    print(f"🌐 URL: {base_url}")
    print()
    
    # Проверяем, есть ли уже сохраненная сессия
    if PERSISTENT_CONTEXT_DIR.exists():
        print(f"⚠️  Внимание: найдена существующая сессия в {PERSISTENT_CONTEXT_DIR}")
        response = input("   Перезаписать? (y/n): ").strip().lower()
        if response != 'y':
            print("❌ Отменено")
            return
    
    print("🚀 Запуск парсера с логином...")
    print("⏳ Браузер откроется - войдите в аккаунт, если потребуется")
    print("⏳ Сессия будет сохранена для последующих запусков")
    print()
    
    try:
        payment_data = await parse_payment_data_1win(
            email=email,
            password=password,
            base_url=base_url,
            wait_seconds=30,
            use_persistent_context=True,  # Используем persistent context для сохранения сессии
            skip_login=False,  # ПЕРВЫЙ РАЗ - делаем логин
        )
        
        print()
        print("=" * 70)
        print("✅ РЕЗУЛЬТАТ:")
        print("=" * 70)
        print(f"  Success: {payment_data.get('success')}")
        print(f"  CVU: {payment_data.get('cvu', 'не найден')}")
        print(f"  Recipient: {payment_data.get('recipient', 'не найден')}")
        print(f"  Bank: {payment_data.get('bank', 'не найден')}")
        print(f"  Amount: {payment_data.get('amount', 'не найдена')}")
        print(f"  Method: {payment_data.get('method', 'не найден')}")
        
        if payment_data.get('error'):
            print(f"  ⚠️  Error: {payment_data.get('error')}")
        
        print()
        
        # Проверяем, что persistent context существует (сессия сохранена)
        if PERSISTENT_CONTEXT_DIR.exists():
            print(f"✅ Сессия сохранена в: {PERSISTENT_CONTEXT_DIR}")
            print()
            print("📝 Теперь можно использовать:")
            print("   python3 run_parser_ar.py")
            print("   или вызывать парсер через API с skip_login=True")
        else:
            print("⚠️  Внимание: сессия может сохраняться автоматически при использовании persistent context")
            print(f"   Проверьте папку: {PERSISTENT_CONTEXT_DIR}")
        
    except Exception as e:
        print(f"❌ Ошибка при логине: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 70)
    print("Завершено")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
