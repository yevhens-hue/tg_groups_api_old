#!/bin/bash
# Скрипт для запуска бота в фоновом режиме

cd "$(dirname "$0")"
export TELEGRAM_BOT_TOKEN='8324666844:AAGgN-DEt0fv43gAipQrFh2DWfaw0Jg0T2Q'

# Проверяем, не запущен ли уже бот
if pgrep -f "python3 bot.py" > /dev/null; then
    echo "⚠️  Бот уже запущен!"
    echo "   PID: $(pgrep -f 'python3 bot.py')"
    exit 1
fi

# Запускаем бота в фоне
echo "🚀 Запуск бота в фоновом режиме..."
nohup python3 bot.py > bot.log 2>&1 &

# Ждем немного и проверяем
sleep 2
if pgrep -f "python3 bot.py" > /dev/null; then
    echo "✅ Бот запущен!"
    echo "   PID: $(pgrep -f 'python3 bot.py')"
    echo "   Логи: bot.log"
    echo ""
    echo "📋 Команды для управления:"
    echo "   Остановить: pkill -f 'python3 bot.py'"
    echo "   Логи: tail -f bot.log"
    echo "   Статус: ps aux | grep 'python3 bot.py'"
else
    echo "❌ Не удалось запустить бота"
    echo "   Проверьте логи: cat bot.log"
    exit 1
fi
