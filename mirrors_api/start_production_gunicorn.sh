#!/usr/bin/env bash
set -e

# Production startup script с Gunicorn + Uvicorn workers
# Рекомендуется для высоконагруженных систем
# Использование: ./start_production_gunicorn.sh

# Переходим в папку проекта
cd "$(dirname "$0")"

# Проверяем наличие виртуального окружения
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found. Run: python3 -m venv .venv"
    exit 1
fi

# Активируем виртуальное окружение
source .venv/bin/activate

# Проверяем наличие gunicorn
if ! command -v gunicorn &> /dev/null; then
    echo "Installing gunicorn..."
    pip install gunicorn
fi

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

# Параметры для gunicorn
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-"8011"}
WORKERS=${WORKERS:-"4"}
WORKER_CLASS=${WORKER_CLASS:-"uvicorn.workers.UvicornWorker"}
LOG_LEVEL=${LOG_LEVEL:-"info"}

echo "Starting mirrors_api with Gunicorn..."
echo "Host: $HOST"
echo "Port: $PORT"
echo "Workers: $WORKERS"
echo "Worker class: $WORKER_CLASS"
echo "Log level: $LOG_LEVEL"

# Запускаем gunicorn с uvicorn workers
exec gunicorn app:app \
    --bind "$HOST:$PORT" \
    --workers "$WORKERS" \
    --worker-class "$WORKER_CLASS" \
    --log-level "$LOG_LEVEL" \
    --access-logfile - \
    --error-logfile - \
    --timeout 120 \
    --keep-alive 30 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --preload


