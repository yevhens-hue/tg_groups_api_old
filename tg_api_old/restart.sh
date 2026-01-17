#!/bin/bash

# Переходим в папку скрипта (tg_api)
cd "$(dirname "$0")"

# Активируем виртуальное окружение
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

echo "🔫 Killing old uvicorn on port 8010 (if any)..."
pkill -f "app:app --host 0.0.0.0 --port 8010" 2>/dev/null || true

sleep 1

echo "🚀 Starting uvicorn app:app on port 8010..."
uvicorn app:app --host 0.0.0.0 --port 8010

