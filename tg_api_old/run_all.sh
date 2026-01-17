echo "🌐 Запускаю ngrok..."
nohup ngrok http "${PORT}" > "$LOGDIR/ngrok.log" 2>&1 &

# Ждём, пока поднимется API ngrok и появится https-туннель
URL=""
for i in $(seq 1 20); do
  # Проверяем, отвечает ли веб-интерфейс ngrok и есть ли JSON
  if curl -sS http://127.0.0.1:4040/api/tunnels >/dev/null 2>&1; then
    URL=$(curl -s http://127.0.0.1:4040/api/tunnels | python3 - "$PORT" <<'PY'
import sys, json
data = json.load(sys.stdin)
tunnels = data.get("tunnels", [])
https = [t for t in tunnels if t.get("proto") == "https"]
print(https[0]["public_url"] if https else "")
PY
)
    if [ -n "$URL" ]; then
      break
    fi
  fi
  echo "⏳ Жду активации ngrok… ($i/20)"
  sleep 1
done

echo "------------------------------------------------------------"
if [ -n "${URL:-}" ]; then
  echo "✅ Туннель:  ${URL}"
  echo "📄 Swagger:  ${URL}/docs"
else
  echo "❌ Не удалось автоматически получить URL."
  echo "Открой панель ngrok: http://127.0.0.1:4040  (там будет ссылка)"
  echo "Логи uvicorn: $LOGDIR/uvicorn.log"
  echo "Логи ngrok:   $LOGDIR/ngrok.log"
fi
echo "------------------------------------------------------------"
#!/usr/bin/env bash
set -euo pipefail

PORT=${PORT:-8000}
ROOT="$HOME/tg_api"
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"

echo "🧹 Останавливаю старые процессы (если есть)…"
pkill -f "uvicorn app:app" 2>/dev/null || true
pkill -f "ngrok http ${PORT}" 2>/dev/null || true
sleep 1

echo "🚀 Запускаю FastAPI…"
nohup python3 -m uvicorn app:app --host 127.0.0.1 --port "$PORT" --reload \
  >"$LOGDIR/uvicorn.log" 2>&1 &

# ждём, пока поднимется API
for i in {1..30}; do
  curl -sf "http://127.0.0.1:${PORT}/docs" >/dev/null && break || sleep 1
done

if curl -sf "http://127.0.0.1:${PORT}/docs" >/dev/null; then
  echo "✅ FastAPI поднялся: http://127.0.0.1:${PORT}"
else
  echo "⚠️ FastAPI не отвечает на порту ${PORT}"
fi

echo "🌐 Запускаю ngrok…"
nohup ngrok http "${PORT}" >"$LOGDIR/ngrok.log" 2>&1 &

# ждём локальный API ngrok
for i in {1..30}; do
  curl -sf http://127.0.0.1:4040/api/tunnels >/dev/null && break || sleep 1
done

URL=$(curl -sf http://127.0.0.1:4040/api/tunnels | python3 - <<'PY'
import sys, json
data=json.load(sys.stdin)
for t in data.get('tunnels', []):
    u=t.get('public_url','')
    if u.startswith('https://'):
        print(u)
        break
PY
)

echo "----------------------------------------------"
if [ -n "${URL:-}" ]; then
  echo "✅ Туннель:  ${URL}"
  echo "📄 Swagger:  ${URL}/docs"
else
  echo "❌ Не удалось автоматически получить URL."
  echo "Открой панель ngrok: http://127.0.0.1:4040  (там будет ссылка)"
  echo "Логи uvicorn: $LOGDIR/uvicorn.log"
  echo "Логи ngrok:   $LOGDIR/ngrok.log"
fi
echo "----------------------------------------------"
