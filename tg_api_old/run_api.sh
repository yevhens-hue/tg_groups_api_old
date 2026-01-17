#!/bin/bash

echo "🚀 RUN API SCRIPT STARTED"
echo "📁 Moving into script directory..."
cd "$(dirname "$0")"
echo "   Current folder: $(pwd)"

echo "🧹 Killing old uvicorn processes..."
pkill -9 -f uvicorn 2>/dev/null || true

echo "🧹 Killing old Python processes (only user-owned)..."
pkill -9 -f Python 2>/dev/null || true

sleep 1

echo "🔍 Checking port 8011..."
if lsof -i :8011 >/dev/null 2>&1; then
  echo "❌ Port 8011 is STILL taken!"
  echo "   Here is what holds it:"
  lsof -i :8011
  echo "❗ Please kill manually."
  exit 1
else
  echo "✅ Port 8011 is free."
fi

echo "💚 Activating virtual environment..."
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
  echo "   ✓ VENV activated"
else
  echo "❌ ERROR: .venv not found in $(pwd)"
  exit 1
fi

echo "🔥 Starting API on http://127.0.0.1:8011 ..."
echo "   Press CTRL+C to stop."

uvicorn app:app --host 0.0.0.0 --port 8011
#!/bin/bash

echo "🚀 RUN API SCRIPT STARTED"
echo "📁 Moving into script directory..."
cd "$(dirname "$0")"
echo "   Current folder: $(pwd)"

echo "🧹 Killing old uvicorn processes..."
pkill -9 -f uvicorn 2>/dev/null || true

echo "🧹 Killing old Python processes (only user-owned)..."
pkill -9 -f Python 2>/dev/null || true

sleep 1

echo "🔍 Checking port 8011..."
if lsof -i :8011 >/dev/null 2>&1; then
  echo "❌ Port 8011 is STILL taken!"
  echo "   Here is what holds it:"
  lsof -i :8011
  echo "❗ Please kill manually."
  exit 1
else
  echo "✅ Port 8011 is free."
fi

echo "💚 Activating virtual environment..."
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
  echo "   ✓ VENV activated"
else
  echo "❌ ERROR: .venv not found in $(pwd)"
  exit 1
fi

echo "🔥 Starting API on http://127.0.0.1:8011 ..."
echo "   Press CTRL+C to stop."

uvicorn app:app --host 0.0.0.0 --port 8011

