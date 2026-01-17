#!/bin/bash
# Скрипт для мониторинга теста

echo "🔍 Мониторинг теста парсера..."
echo "Нажмите Ctrl+C для выхода"
echo ""

PID_FILE="/tmp/test_prod_pid.txt"
LOG_FILE="/tmp/test_prod_output.log"

if [ ! -f "$PID_FILE" ]; then
    echo "❌ PID файл не найден. Тест, возможно, не запущен."
    exit 1
fi

PID=$(cat "$PID_FILE")

if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "⚠️  Процесс $PID не найден. Проверяю лог..."
    echo ""
    if [ -f "$LOG_FILE" ]; then
        cat "$LOG_FILE"
    else
        echo "❌ Лог файл не найден"
    fi
    exit 1
fi

echo "✅ Процесс запущен (PID: $PID)"
echo "📋 Последние 30 строк лога:"
echo ""

tail -30 "$LOG_FILE" 2>/dev/null || echo "Лог еще создается..."

echo ""
echo "Для полного лога: tail -f $LOG_FILE"
echo "Для остановки: kill $PID"
