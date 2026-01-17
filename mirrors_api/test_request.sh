#!/bin/bash
# Скрипт для тестирования парсера платежных данных

echo "🚀 Тестирование парсера платежных данных для Аргентины"
echo "=" | awk '{printf "%.60s\n", $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1}'
echo ""

# Проверяем, что сервер запущен
if ! curl -s http://localhost:8011/health > /dev/null 2>&1; then
    echo "❌ Сервер не запущен на порту 8011"
    echo "Запустите сервер:"
    echo "  source .venv/bin/activate"
    echo "  nohup uvicorn app:app --host 0.0.0.0 --port 8011 > server.log 2>&1 &"
    exit 1
fi

echo "✅ Сервер доступен"
echo ""

# Тестовый запрос
echo "📤 Отправка запроса к /parse_payment_data_ar"
echo "⚠️  Это может занять 30-60 секунд..."
echo ""

response=$(curl -s -X POST "http://localhost:8011/parse_payment_data_ar" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "perymury78@gmail.com",
    "password": "%m^%G5\"}4m",
    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit?gid=516142479#gid=516142479",
    "wait_seconds": 20
  }' \
  -w "\n\nHTTP Status: %{http_code}\nTime: %{time_total}s\n")

echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"

echo ""
echo "=" | awk '{printf "%.60s\n", $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1 $1}'
echo ""
echo "📋 Для просмотра логов сервера:"
echo "   tail -f server.log"
