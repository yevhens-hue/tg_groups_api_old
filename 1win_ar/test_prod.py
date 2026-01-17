#!/usr/bin/env python3
"""
Автоматический тест парсера в продакшене.
"""
import asyncio
import sys
from pathlib import Path

# Импортируем парсер
from services.payment_parser_ar import parse_payment_data_1win

async def test_in_production():
    """Тест парсера в продакшене."""
    print("=" * 70)
    print("🚀 ТЕСТИРОВАНИЕ В ПРОДАКШЕНЕ")
    print("=" * 70)
    print()
    
    # Параметры
    email = "perymury78@gmail.com"
    password = '%m^%G5"}4m'
    base_url = "https://1win.lat/"
    
    print(f"📧 Email: {email}")
    print(f"🌐 URL: {base_url}")
    print()
    print("⏳ Запуск парсера...")
    print("⏳ Это может занять 1-2 минуты...")
    print()
    
    try:
        payment_data = await parse_payment_data_1win(
            email=email,
            password=password,
            base_url=base_url,
            wait_seconds=30,
            use_persistent_context=True,
            skip_login=False,  # Полный цикл с логином
        )
        
        print()
        print("=" * 70)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТА:")
        print("=" * 70)
        print()
        
        # Основные результаты
        success = payment_data.get('success', False)
        print(f"✅ Success: {success}")
        print(f"  CVU: {payment_data.get('cvu', 'НЕ НАЙДЕН')}")
        print(f"  Recipient: {payment_data.get('recipient', 'НЕ НАЙДЕН')}")
        print(f"  Bank: {payment_data.get('bank', 'НЕ НАЙДЕН')}")
        print(f"  Amount: {payment_data.get('amount', 'НЕ НАЙДЕНА')}")
        print(f"  Method: {payment_data.get('method', 'НЕ НАЙДЕН')}")
        print(f"  URL: {payment_data.get('url', 'НЕ НАЙДЕН')}")
        print()
        
        # Проверка ключевых моментов
        print("🔍 ПРОВЕРКА КЛЮЧЕВЫХ ЭТАПОВ:")
        print()
        
        # Проверка Deposit кнопки
        if payment_data.get('provider_screenshot_path'):
            print(f"✅ Скриншот провайдера создан: {Path(payment_data['provider_screenshot_path']).name}")
        else:
            print("⚠️  Скриншот провайдера не создан")
        
        # Проверка данных
        has_cvu = payment_data.get('cvu') is not None
        has_recipient = payment_data.get('recipient') is not None
        has_bank = payment_data.get('bank') is not None
        has_amount = payment_data.get('amount') is not None
        
        print()
        print("📋 СТАТУС ИЗВЛЕЧЕНИЯ ДАННЫХ:")
        print(f"  CVU: {'✅ НАЙДЕН' if has_cvu else '❌ НЕ НАЙДЕН'}")
        print(f"  Recipient: {'✅ НАЙДЕН' if has_recipient else '❌ НЕ НАЙДЕН'}")
        print(f"  Bank: {'✅ НАЙДЕН' if has_bank else '❌ НЕ НАЙДЕН'}")
        print(f"  Amount: {'✅ НАЙДЕНА' if has_amount else '❌ НЕ НАЙДЕНА'}")
        print()
        
        # Проверка скриншотов
        screenshots_dir = Path.home() / ".cache" / "1win_ar" / "screenshots"
        if screenshots_dir.exists():
            recent_screenshots = sorted(screenshots_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
            if recent_screenshots:
                print("📸 ПОСЛЕДНИЕ СКРИНШОТЫ:")
                for screenshot in recent_screenshots:
                    print(f"  - {screenshot.name}")
        
        # Финальный статус
        print()
        print("=" * 70)
        if success and (has_cvu or has_recipient or has_bank):
            print("✅ ТЕСТ ПРОЙДЕН: Данные успешно извлечены!")
        elif success:
            print("⚠️  ТЕСТ ЧАСТИЧНО УСПЕШЕН: Парсинг завершен, но данные не извлечены")
            print("   Проверьте логи и скриншоты для диагностики")
        else:
            print("❌ ТЕСТ НЕ ПРОЙДЕН: Парсинг не завершен успешно")
            print("   Проверьте логи и скриншоты для диагностики")
        print("=" * 70)
        
        # Ошибки
        if payment_data.get('error'):
            print()
            print("⚠️  ОШИБКИ:")
            print(f"   {payment_data.get('error')}")
        
        return payment_data
        
    except Exception as e:
        print()
        print("=" * 70)
        print("❌ КРИТИЧЕСКАЯ ОШИБКА")
        print("=" * 70)
        print(f"Ошибка: {e}")
        print()
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    try:
        result = asyncio.run(test_in_production())
        sys.exit(0 if result and result.get('success') else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Тест прерван пользователем")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {e}")
        sys.exit(1)
