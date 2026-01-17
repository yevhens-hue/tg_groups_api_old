#!/usr/bin/env python3
"""
Тестовый скрипт для парсера платежных данных Аргентины.
"""
import asyncio
import json
from services.payment_parser_ar import parse_payment_data_1win
from services.google_sheets import export_payment_data_to_sheets, extract_spreadsheet_id, extract_gid_from_url


async def test_payment_parser():
    """Тест парсера платежных данных."""
    print("=" * 60)
    print("Тест парсера платежных данных для Аргентины")
    print("=" * 60)
    print()
    
    # Тестовые данные
    email = "perymury78@gmail.com"
    password = '%m^%G5"}4m'
    base_url = "https://1win.lat/"
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit?gid=516142479#gid=516142479"
    
    print(f"Email: {email}")
    print(f"Base URL: {base_url}")
    print(f"Spreadsheet URL: {spreadsheet_url[:80]}...")
    print()
    
    # Тест 1: Проверка извлечения spreadsheet_id и gid
    print("Тест 1: Извлечение spreadsheet_id и gid из URL")
    try:
        spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
        gid = extract_gid_from_url(spreadsheet_url)
        print(f"✅ Spreadsheet ID: {spreadsheet_id}")
        print(f"✅ GID: {gid}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    print()
    
    # Тест 2: Парсинг платежных данных (это займет время)
    print("Тест 2: Парсинг платежных данных с сайта")
    print("⚠️  Это может занять 30-60 секунд...")
    print()
    
    try:
        payment_data = await parse_payment_data_1win(
            email=email,
            password=password,
            base_url=base_url,
            wait_seconds=20,  # Увеличенное время ожидания
        )
        
        print("Результаты парсинга:")
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
            
            # Тест 3: Экспорт в Google Sheets (требует access token)
            print()
            print("Тест 3: Экспорт в Google Sheets")
            print("⚠️  Требуется GOOGLE_SHEETS_ACCESS_TOKEN")
            print()
            
            # Проверяем наличие access token
            import os
            access_token = os.getenv("GOOGLE_SHEETS_ACCESS_TOKEN")
            
            if access_token:
                print(f"✅ Access token найден (длина: {len(access_token)})")
                print("⚠️  Пропускаем реальный экспорт для безопасности (закомментируйте для теста)")
                # Раскомментируйте для реального теста:
                # try:
                #     export_result = await export_payment_data_to_sheets(
                #         payment_data=payment_data,
                #         spreadsheet_id_or_url=spreadsheet_url,
                #         access_token=access_token,
                #         gid=gid,
                #     )
                #     print(f"✅ Экспорт успешен!")
                #     print(f"   Updated rows: {export_result.get('updates', {}).get('updatedRows', 0)}")
                # except Exception as e:
                #     print(f"❌ Ошибка экспорта: {e}")
            else:
                print("⚠️  GOOGLE_SHEETS_ACCESS_TOKEN не установлен в переменных окружения")
                print("   Для полного теста установите токен:")
                print("   export GOOGLE_SHEETS_ACCESS_TOKEN=your_token_here")
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
    print("Тест завершен")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_payment_parser())
