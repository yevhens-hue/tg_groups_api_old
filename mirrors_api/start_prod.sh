#!/usr/bin/env bash
set -e

# Production startup script - финальная версия
# Использование: ./start_prod.sh

cd "$(dirname "$0")"

# Проверки
if [ ! -d ".venv" ]; then
    echo "❌ Error: Virtual environment not found"
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

source .venv/bin/activate

if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "Create .env file with SERPER_API_KEY"
    exit 1
fi

set -a
source .env
set +a

if [ -z "$SERPER_API_KEY" ]; then
    echo "❌ Error: SERPER_API_KEY is not set in .env"
    exit 1
fi

# Production настройки
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Параметры из .env или значения по умолчанию
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-"8011"}
WORKERS=${WORKERS:-"4"}
LOG_LEVEL=${LOG_LEVEL:-"info"}

echo "🚀 Starting mirrors_api in PRODUCTION mode..."
echo "📍 Host: $HOST"
echo "🔌 Port: $PORT"
echo "👷 Workers: $WORKERS"
echo "📊 Log level: $LOG_LEVEL"
echo "🌍 Environment: ${ENVIRONMENT:-development}"
echo ""

# Запуск
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


