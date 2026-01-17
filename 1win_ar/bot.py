#!/usr/bin/env python3
"""
Telegram бот для запуска парсеров 1win через команды в группе.
"""
import asyncio
import os
import json
import sys
import signal
import logging
from pathlib import Path
from datetime import datetime

# Попытка загрузить .env файл (опционально)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv не установлен, используем только переменные окружения

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from services.payment_parser_ar import parse_payment_data_1win
from services.google_sheets import export_payment_data_to_sheets, extract_gid_from_url

# Настройки
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
PERSISTENT_CONTEXT_DIR = Path.home() / ".cache" / "1win_ar" / "profile"

# Учетные данные (можно также через переменные окружения)
EMAIL = os.getenv("1WIN_EMAIL", "perymury78@gmail.com")
PASSWORD = os.getenv("1WIN_PASSWORD", '%m^%G5"}4m')
BASE_URL = os.getenv("1WIN_BASE_URL", "https://1win.lat/")

# Google Sheets настройки
TOKEN_FILE = Path(__file__).parent / "token.json"
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit?gid=516142479#gid=516142479"


def get_access_token_from_file():
    """Получить access token из token.json и обновить если нужно."""
    if not TOKEN_FILE.exists():
        return None
    
    try:
        with open(TOKEN_FILE, 'r') as f:
            token_data = json.load(f)
        
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        
        # Обновляем токен если истек
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Сохраняем обновленный токен
                with open(TOKEN_FILE, 'w') as f:
                    f.write(creds.to_json())
        
        return creds.token
    except Exception as e:
        print(f"Ошибка получения токена: {e}")
        return None


async def parse_ar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /parse_ar - запуск парсера для Аргентины."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    # Проверяем токен
    if not TELEGRAM_BOT_TOKEN:
        await update.message.reply_text(
            "❌ Ошибка: TELEGRAM_BOT_TOKEN не настроен!\n"
            "Установите переменную окружения TELEGRAM_BOT_TOKEN"
        )
        return
    
    # Отправляем сообщение о начале парсинга
    status_message = await update.message.reply_text(
        f"🚀 Запуск парсера 1win AR (Аргентина)...\n"
        f"⏳ Это может занять 30-60 секунд...\n"
        f"👤 Запросил: @{username}"
    )
    
    try:
        # Проверяем, есть ли сохраненная сессия
        skip_login = PERSISTENT_CONTEXT_DIR.exists()
        
        # Запускаем парсер
        payment_data = await parse_payment_data_1win(
            email=EMAIL,
            password=PASSWORD,
            base_url=BASE_URL,
            wait_seconds=30,
            use_persistent_context=True,
            skip_login=skip_login,
        )
        
        # Формируем ответ
        if payment_data.get("success"):
            result_text = "✅ Парсинг успешно завершен!\n\n"
            result_text += f"📊 Результаты:\n"
            result_text += f"  • CVU: {payment_data.get('cvu', 'не найден')}\n"
            result_text += f"  • Recipient: {payment_data.get('recipient', 'не найден')}\n"
            result_text += f"  • Bank: {payment_data.get('bank', 'не найден')}\n"
            result_text += f"  • Amount: {payment_data.get('amount', 'не найдена')}\n"
            result_text += f"  • Method: {payment_data.get('method', 'не найден')}\n"
            result_text += f"  • Payment Type: {payment_data.get('payment_type', 'не найден')}\n"
            
            if payment_data.get("url"):
                result_text += f"\n🔗 URL: {payment_data.get('url')}\n"
            
            # Пытаемся экспортировать в Google Sheets
            try:
                access_token = get_access_token_from_file()
                if access_token:
                    result_text += "\n📊 Экспорт в Google Sheets..."
                    await status_message.edit_text(result_text)
                    
                    gid = extract_gid_from_url(SPREADSHEET_URL)
                    export_result = await export_payment_data_to_sheets(
                        payment_data=payment_data,
                        spreadsheet_id_or_url=SPREADSHEET_URL,
                        access_token=access_token,
                        gid=gid,
                    )
                    
                    result_text += " ✅\n"
                    result_text += f"📋 Данные добавлены в таблицу (строка {export_result.get('updates', {}).get('updatedRange', 'N/A')})"
                else:
                    result_text += "\n⚠️ Google Sheets токен не найден - данные не экспортированы"
            except Exception as e:
                result_text += f"\n⚠️ Ошибка экспорта в Google Sheets: {str(e)[:100]}"
        else:
            error = payment_data.get("error", "Неизвестная ошибка")
            result_text = f"❌ Парсинг не удался:\n{error}\n"
            
            if payment_data.get("cvu"):
                result_text += f"\n⚠️ Частичные данные:\n"
                result_text += f"  • CVU: {payment_data.get('cvu')}\n"
                result_text += f"  • Recipient: {payment_data.get('recipient', 'не найден')}\n"
                result_text += f"  • Bank: {payment_data.get('bank', 'не найден')}\n"
        
        # Обновляем сообщение с результатами
        await status_message.edit_text(result_text)
        
    except Exception as e:
        error_text = f"❌ Ошибка при запуске парсера:\n{str(e)}"
        await status_message.edit_text(error_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help - справка по командам."""
    help_text = (
        "🤖 Бот для запуска парсеров 1win\n\n"
        "📋 Доступные команды:\n"
        "  /parse_ar или /ar - Запустить парсер для Аргентины (1win.lat)\n"
        "  /help - Показать эту справку\n\n"
        "💡 Использование:\n"
        "Отправьте команду в группу, чтобы запустить соответствующий парсер.\n\n"
        "📊 Данные автоматически экспортируются в Google Sheets."
    )
    await update.message.reply_text(help_text)


def main():
    """Главная функция для запуска бота."""
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не установлен!")
        print("Установите переменную окружения TELEGRAM_BOT_TOKEN")
        print("Получите токен у @BotFather в Telegram")
        return
    
    # Проверяем, не запущен ли уже другой экземпляр бота
    import subprocess
    import time
    running_processes = subprocess.run(
        ["pgrep", "-f", "python3 bot.py"],
        capture_output=True,
        text=True
    )
    if running_processes.returncode == 0:
        pids = running_processes.stdout.strip().split('\n')
        pids = [p for p in pids if p and str(os.getpid()) not in p]
        if pids:
            print("⚠️  ВНИМАНИЕ: Обнаружены запущенные экземпляры бота!")
            print(f"   Найдено процессов: {len(pids)} (PID: {', '.join(pids)})")
            print("   Останавливаю старые экземпляры...")
            subprocess.run(["pkill", "-f", "python3 bot.py"], capture_output=True)
            print("✅ Старые экземпляры остановлены. Ждем 5 секунд...")
            time.sleep(5)
            
            # Проверяем еще раз
            running_processes = subprocess.run(
                ["pgrep", "-f", "python3 bot.py"],
                capture_output=True,
                text=True
            )
            if running_processes.returncode == 0:
                remaining_pids = [p for p in running_processes.stdout.strip().split('\n') if p and str(os.getpid()) not in p]
                if remaining_pids:
                    print(f"❌ Не удалось остановить все экземпляры!")
                    print(f"   Остались процессы: {', '.join(remaining_pids)}")
                    print("   Выполните вручную: ./stop_bot.sh")
                    return
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("parse_ar", parse_ar_command))
    application.add_handler(CommandHandler("ar", parse_ar_command))  # Короткая версия
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", help_command))  # /start тоже показывает справку
    
    # Проверяем, не запущен ли уже другой экземпляр
    import sys
    import signal
    
    def signal_handler(sig, frame):
        print("\n\n🛑 Остановка бота...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Добавляем обработчик ошибок для логирования
    import logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.WARNING
    )
    
    # Запускаем бота
    print("🤖 Бот запущен и ожидает команды...")
    print(f"📋 Доступные команды: /parse_ar, /ar, /help")
    print(f"📊 Google Sheets: {SPREADSHEET_URL[:60]}...")
    print("💡 Отправьте /start или /help в Telegram для проверки")
    print()
    print("⚠️  ВАЖНО: Не закрывайте этот терминал!")
    print("   Бот должен работать постоянно для ответа на команды.")
    print()
    
    # Добавляем обработку ошибок
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Игнорируем старые обновления
            close_loop=False,  # Не закрываем event loop при ошибках
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Бот остановлен пользователем (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        error_msg = str(e)
        if "Conflict" in error_msg or "getUpdates" in error_msg:
            print(f"\n❌ Конфликт: Другой экземпляр бота уже запущен!")
            print("   Решение:")
            print("   1. Найдите и остановите другой экземпляр:")
            print("      pkill -f 'python3 bot.py'")
            print("   2. Подождите 5 секунд")
            print("   3. Запустите бота снова")
        else:
            print(f"\n❌ Ошибка при запуске бота: {error_msg}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
