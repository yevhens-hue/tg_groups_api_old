#!/usr/bin/env bash
# Скрипт для остановки сервера на порту 8011

echo "Stopping mirrors_api server on port 8011..."

# Находим процессы на порту 8011
PIDS=$(lsof -ti :8011 2>/dev/null)

if [ -z "$PIDS" ]; then
    echo "No processes found on port 8011"
    exit 0
fi

echo "Found processes: $PIDS"
kill $PIDS 2>/dev/null

# Ждем немного
sleep 2

# Проверяем, остались ли процессы
REMAINING=$(lsof -ti :8011 2>/dev/null)
if [ -n "$REMAINING" ]; then
    echo "Force killing remaining processes..."
    kill -9 $REMAINING 2>/dev/null
    sleep 1
fi

# Финальная проверка
if lsof -i :8011 >/dev/null 2>&1; then
    echo "Warning: Some processes may still be running"
else
    echo "✓ Server stopped successfully"
fi


