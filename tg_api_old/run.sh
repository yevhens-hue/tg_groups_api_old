#!/usr/bin/env bash
set -e
cd /Users/yevhen.shaforostov/tg_api
source .venv/bin/activate
lsof -nP -iTCP:8010 -sTCP:LISTEN -t | xargs -r kill -9
pkill -f "uvicorn app:app" || true
nohup uvicorn app:app --host 127.0.0.1 --port 8010 --reload --env-file .env > uvicorn.log 2>&1 &
sleep 1
pgrep -f "uvicorn app:app" >/dev/null || (echo "uvicorn failed" && exit 1)
pkill -f "ngrok http 8010" || true
nohup ngrok http 8010 > ngrok.log 2>&1 &
sleep 2
URL=$(curl -s localhost:4040/api/tunnels | sed -n 's/.*"public_url":"\([^"]*\)".*/\1/p' | head -1)
echo "$URL"
echo "$URL" > .current_ngrok_url
curl -s "$URL/health" || true
