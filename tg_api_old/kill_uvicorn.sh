#!/bin/bash

# Скрипт для убийства всех uvicorn на 8010 и перезапуска TG API

set -e

echo "👉 Работаю из каталога: $(pwd)"

# Переходим в папку скрипта (tg_api)
cd "$(dirname "$0")"

echo "🔍 Ищу процессы на порту 8010..."
PIDS=$(lsof -ti tcp:8010 || true)

if [ -n "$PIDS" ]; then
  echo "🔫 Убиваю процессы на 8010: $PIDS"
  kill -9 $PIDS || true
else
  echo "✅ Порт 8010 свободен"
fi

echo "🔍 Убиваю процессы uvicorn app:app (если есть)..."
pkill -f "uvicorn app:app --reload --port 8010" 2>/dev/null || true

sleep 1

echo "✅ Проверяю порт 8010 ещё раз..."
if lsof -ti tcp:8010 >/dev/null 2>&1; then
  echo "❌ Порт 8010 всё ещё занят, что-то держится. Проверь руками: lsof -i :8010"
  exit 1
fi

echo "💚 Активирую виртуальное окружение..."
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
else
  echo "❌ Не найден .venv/activate в $(pwd)"
  exit 1
fi

echo "🚀 Стартую uvicorn app:app --reload --port 8010"
uvicorn app:app --reload --port 8010

