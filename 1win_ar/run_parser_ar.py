#!/usr/bin/env python3
"""
Скрипт для запуска парсера платежных данных для Аргентины (1win.lat)
с автоматическим экспортом в Google Sheets.
"""
import asyncio
import json
import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from services.payment_parser_ar import parse_payment_data_1win
from services.google_sheets import export_payment_data_to_sheets, extract_gid_from_url

# Настройки
TOKEN_FILE = Path(__file__).parent / "token.json"
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'  # Добавлен scope для Drive API
]


def get_access_token_from_file():
    """Получить access token из token.json и обновить если нужно."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(f"Файл {TOKEN_FILE} не найден!")
    
    with open(TOKEN_FILE, 'r') as f:
        token_data = json.load(f)
    
    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
    
    # Обновляем токен если истек
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print("🔄 Обновление access token...")
            creds.refresh(Request())
            # Сохраняем обновленный токен
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
            print("✅ Токен обновлен!")
    
    return creds.token


async def main():
    """Основная функция запуска парсера."""
    print("=" * 60)
    print("Парсер платежных данных 1win.lat (Аргентина)")
    print("=" * 60)
    print()
    
    # Параметры
    email = "perymury78@gmail.com"
    password = '%m^%G5"}4m'  # Пароль уже сохранен, так как используется persistent context
    
    base_url = "https://1win.lat/"
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit?gid=516142479#gid=516142479"
    
    print(f"📧 Email: {email}")
    print(f"🌐 URL: {base_url}")
    print(f"📊 Spreadsheet: {spreadsheet_url[:60]}...")
    print()
    
    # Получаем access token
    try:
        print("🔐 Получение access token...")
        access_token = get_access_token_from_file()
        print("✅ Access token получен!")
        print()
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return
    
    # Запускаем парсер
    print("🚀 Запуск парсера...")
    print("⏳ Это может занять 30-60 секунд...")
    print()
    
    # Проверяем, есть ли сохраненная сессия
    from pathlib import Path
    PERSISTENT_CONTEXT_DIR = Path.home() / ".cache" / "1win_ar" / "profile"
    skip_login = PERSISTENT_CONTEXT_DIR.exists()
    
    if skip_login:
        print("✅ Найдена сохраненная сессия - используем автоматический логин")
        print(f"   (если нужно перелогиниться, удалите папку {PERSISTENT_CONTEXT_DIR})")
    else:
        print("⚠️  Сохраненная сессия не найдена - будет выполнен логин")
        print("   После успешного логина сессия будет сохранена автоматически")
    
    print()
    
    try:
        payment_data = await parse_payment_data_1win(
            email=email,
            password=password,
            base_url=base_url,
            wait_seconds=30,
            use_persistent_context=True,
            skip_login=skip_login,  # Автоматически определяем, нужен ли логин
        )
        
        print()
        print("=" * 60)
        print("Результаты парсинга:")
        print("=" * 60)
        print(f"  Success: {payment_data.get('success')}")
        print(f"  CVU: {payment_data.get('cvu', 'не найден')}")
        print(f"  Recipient: {payment_data.get('recipient', 'не найден')}")
        print(f"  Bank: {payment_data.get('bank', 'не найден')}")
        print(f"  Amount: {payment_data.get('amount', 'не найдена')}")
        print(f"  Method: {payment_data.get('method', 'не найден')}")
        print(f"  Payment Type: {payment_data.get('payment_type', 'не найден')}")
        print(f"  URL: {payment_data.get('url', 'не найден')}")
        
        if payment_data.get('error'):
            print(f"  ⚠️  Error: {payment_data.get('error')}")
        
        print()
        
        if payment_data.get('success'):
            print("✅ Парсинг успешен!")
            
            # Экспортируем в Google Sheets
            print()
            print("📊 Экспорт в Google Sheets...")
            print(f"   Данные для экспорта:")
            print(f"     CVU: {payment_data.get('cvu', 'None')}")
            print(f"     Recipient: {payment_data.get('recipient', 'None')}")
            print(f"     Bank: {payment_data.get('bank', 'None')}")
            print(f"     Amount: {payment_data.get('amount', 'None')}")
            try:
                gid = extract_gid_from_url(spreadsheet_url)
                export_result = await export_payment_data_to_sheets(
                    payment_data=payment_data,
                    spreadsheet_id_or_url=spreadsheet_url,
                    access_token=access_token,
                    gid=gid,
                )
                
                print("✅ Данные успешно экспортированы в Google Sheets!")
                print(f"   Updated rows: {export_result.get('updates', {}).get('updatedRows', 0)}")
                print(f"   Range: {export_result.get('updates', {}).get('updatedRange', 'N/A')}")
            except Exception as e:
                print(f"❌ Ошибка экспорта в Google Sheets: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("❌ Парсинг не удался")
            print("   Проверьте:")
            print("   1. Правильность учетных данных")
            print("   2. Доступность сайта 1win.lat")
            print("   3. Структуру страницы (возможно, она изменилась)")
        
    except Exception as e:
        print(f"❌ Ошибка при парсинге: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("Завершено")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
