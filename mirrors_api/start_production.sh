#!/usr/bin/env bash
set -e

# Production startup script для mirrors_api
# Использование: ./start_production.sh

# Переходим в папку проекта
cd "$(dirname "$0")"

# Проверяем наличие виртуального окружения
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found. Run: python3 -m venv .venv"
    exit 1
fi

# Активируем виртуальное окружение
source .venv/bin/activate

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Creating from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Please edit .env file and set required variables"
        exit 1
    else
        echo "Error: .env.example not found. Please create .env file manually."
        exit 1
    fi
fi

# Подгружаем переменные из .env
set -a
source .env
set +a

# Проверяем обязательные переменные
if [ -z "$SERPER_API_KEY" ]; then
    echo "Error: SERPER_API_KEY is not set in .env"
    exit 1
fi

# Устанавливаем переменные окружения для production
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Параметры для uvicorn
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-"8011"}
WORKERS=${WORKERS:-"4"}
LOG_LEVEL=${LOG_LEVEL:-"info"}

echo "Starting mirrors_api in production mode..."
echo "Host: $HOST"
echo "Port: $PORT"
echo "Workers: $WORKERS"
echo "Log level: $LOG_LEVEL"

# Запускаем uvicorn с production настройками
exec uvicorn app:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level "$LOG_LEVEL" \
    --no-access-log \
    --proxy-headers \
    --forwarded-allow-ips "*" \
    --timeout-keep-alive 300 \
    --timeout-graceful-shutdown 60

