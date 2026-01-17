#!/usr/bin/env python3
"""
Скрипт для ручного логина на 1win.lat с сохранением сессии в persistent context.
После выполнения этого скрипта парсер будет автоматически использовать сохраненную авторизацию.
"""

import asyncio
import os
import subprocess
import signal
import time
from pathlib import Path
from playwright.async_api import async_playwright

# Путь к профилю браузера (такой же как в парсере)
USER_DATA_DIR = os.environ.get(
    "PAYMENT_PARSER_USER_DATA_DIR",
    os.path.join(os.path.expanduser("~"), ".cache", "1win_ar", "profile")
)

def cleanup_profile_lock(user_data_dir):
    """Удаляет файлы блокировки профиля браузера"""
    profile_path = Path(user_data_dir)
    
    # Удаляем SingletonLock файлы
    lock_files = [
        profile_path / "SingletonLock",
        profile_path / "SingletonSocket",
        profile_path / "SingletonCookie",
    ]
    
    for lock_file in lock_files:
        if lock_file.exists():
            try:
                lock_file.unlink()
                print(f"🗑️  Удален файл блокировки: {lock_file.name}")
            except Exception as e:
                print(f"⚠️  Не удалось удалить {lock_file.name}: {e}")
    
    # Пытаемся найти и завершить процессы Chromium с этим профилем
    try:
        # Ищем процессы, используя имя профиля в пути
        profile_str = str(user_data_dir)
        result = subprocess.run(
            ["pgrep", "-f", profile_str],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid and pid.strip():
                    try:
                        pid_int = int(pid.strip())
                        os.kill(pid_int, signal.SIGTERM)
                        print(f"🔪 Завершен процесс Chromium (PID: {pid_int})")
                        time.sleep(0.5)
                    except ProcessLookupError:
                        # Процесс уже завершен
                        pass
                    except Exception as e:
                        print(f"⚠️  Не удалось завершить процесс {pid}: {e}")
    except FileNotFoundError:
        # pgrep не найден (не критично)
        pass
    except Exception as e:
        print(f"⚠️  Не удалось проверить процессы: {e}")

async def login_manually():
    """Открывает браузер для ручного логина и сохраняет сессию"""
    user_data_dir = Path(USER_DATA_DIR)
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📂 Профиль браузера: {user_data_dir}")
    
    # Очищаем блокировки профиля перед запуском
    print("🔧 Проверяю и очищаю блокировки профиля...")
    cleanup_profile_lock(user_data_dir)
    time.sleep(2)  # Даем время на завершение процессов
    
    print("🌐 Открываю браузер...")
    
    playwright = await async_playwright().start()
    context = None
    try:
        # Запускаем браузер с persistent context в видимом режиме
        # Настройки для обхода детекции автоматизации
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,  # Видимый браузер для ручного логина
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Отключаем признаки автоматизации
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
            ],
            # Дополнительные опции для обхода детекции
            ignore_https_errors=False,
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"],
            color_scheme="dark" if "dark" in str(user_data_dir) else "light",
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Удаляем признаки автоматизации из page (ДО перехода на страницу!)
        await page.add_init_script("""
            // Удаляем webdriver флаг - самый важный для обхода детекции
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Маскируем permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Маскируем plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Маскируем languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Переопределяем Chrome runtime
            window.chrome = {
                runtime: {}
            };
            
            // Удаляем признаки Playwright
            delete window.__playwright;
            delete window.__pw_manual;
            delete window.__PW_inspect;
        """)
        
        # Переходим на страницу
        await page.goto("https://1win.lat/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)  # Даем время на полную загрузку
        
        print("\n" + "="*60)
        print("✅ Браузер открыт!")
        print("\n📋 Инструкция:")
        print("   1. Войдите в аккаунт на сайте 1win.lat")
        print("   2. Убедитесь, что вы успешно залогинились")
        print("   3. Нажмите Enter в этом терминале после входа")
        print("="*60 + "\n")
        
        # Ждем нажатия Enter от пользователя
        input("⏳ Нажмите Enter после успешного входа...")
        
        # Проверяем, что пользователь действительно залогинился
        try:
            deposit_button = page.locator('div:text("Deposit"), button:text("Deposit"), a:text("Deposit")').first
            is_deposit_visible = await deposit_button.is_visible(timeout=3000)
            if is_deposit_visible:
                print("✅ Отлично! Вы успешно залогинились. Сессия сохранена!")
            else:
                print("⚠️  Предупреждение: Кнопка Deposit не найдена.")
                print("   Убедитесь, что вы действительно залогинились.")
                confirm = input("   Продолжить сохранение сессии? (y/n): ")
                if confirm.lower() != 'y':
                    print("❌ Отменено.")
                    await context.close()
                    await playwright.stop()
                    return
                else:
                    print("✅ Сессия сохранена (без подтверждения)")
        except Exception as e:
            print(f"⚠️  Не удалось проверить авторизацию: {e}")
            print("   Сессия все равно будет сохранена.")
        
        # Закрываем браузер - persistent context сохранит cookies
        await context.close()
        await playwright.stop()
        
        print("\n✅ Авторизация сохранена!")
        print(f"📂 Профиль находится в: {user_data_dir}")
        print("\n📋 Теперь вы можете запускать парсер с параметром skip_login=true:")
        print("   curl -X POST 'http://localhost:8011/parse_payment_data_ar' \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -d '{\"email\": \"...\", \"password\": \"...\", \"spreadsheet_url\": \"...\", \"use_persistent_context\": true, \"skip_login\": true}'")
        
    except KeyboardInterrupt:
        print("\n❌ Прервано пользователем")
        if context:
            await context.close()
        await playwright.stop()
        # Очищаем блокировки после закрытия
        cleanup_profile_lock(user_data_dir)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        if context:
            try:
                await context.close()
            except:
                pass
        await playwright.stop()
        # Очищаем блокировки после ошибки
        cleanup_profile_lock(user_data_dir)

if __name__ == "__main__":
    asyncio.run(login_manually())
