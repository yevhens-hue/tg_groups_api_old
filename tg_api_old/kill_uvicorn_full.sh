#!/bin/bash

set -e

echo "📁 Переход в каталог скрипта..."
cd "$(dirname "$0")"
echo "   Текущая папка: $(pwd)"

echo "🧨 Убиваю все процессы uvicorn..."
pkill -9 -f uvicorn 2>/dev/null || true

echo "🧨 Убиваю все процессы Python..."
pkill -9 -f Python 2>/dev/null || true

sleep 1

echo "🔍 Проверяю порт 8010..."
if lsof -i :8010 >/dev/null 2>&1; then
  echo "❌ Порт 8010 всё ещё занят:"
  lsof -i :8010
  echo "   Придётся убивать по PID вручную."
  exit 1
else
  echo "✅ Порт 8010 свободен."
fi

echo "💚 Активирую виртуальное окружение..."
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
else
  echo "❌ Не найдено .venv/bin/activate в $(pwd)"
  exit 1
fi

echo "🚀 Запускаю uvicorn app:app на порту 8010 (без reload)..."
uvicorn app:app --host 0.0.0.0 --port 8010
ø

