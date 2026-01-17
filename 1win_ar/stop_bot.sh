#!/bin/bash
# Скрипт для остановки всех экземпляров бота

echo "🛑 Остановка всех экземпляров бота..."

# Находим все процессы
pids=$(pgrep -f "python3 bot.py")

if [ -z "$pids" ]; then
    echo "✅ Бот не запущен"
else
    echo "   Найдено процессов: $(echo $pids | wc -w)"
    for pid in $pids; do
        echo "   Останавливаю PID: $pid"
        kill $pid 2>/dev/null
    done
    
    sleep 2
    
    # Проверяем, остались ли процессы
    remaining=$(pgrep -f "python3 bot.py")
    if [ -n "$remaining" ]; then
        echo "   Принудительная остановка..."
        pkill -9 -f "python3 bot.py"
    fi
    
    echo "✅ Все экземпляры бота остановлены"
fi
