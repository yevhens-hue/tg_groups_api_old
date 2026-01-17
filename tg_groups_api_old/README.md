# Telegram Groups API

Production-ready FastAPI service for Telegram group lookups with Telethon.

## 🚀 Quick Start

### 🆕 Установка на новом компьютере

**Полная инструкция:** [`SETUP_NEW_COMPUTER.md`](SETUP_NEW_COMPUTER.md)

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/yevhens-hue/tg_groups_api_old.git
cd tg_groups_api_old

# 2. Создайте виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или .venv\Scripts\activate  # Windows

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Создайте .env файл с TG_API_ID, TG_API_HASH
# 5. Создайте сессию: python login.py
# 6. Запустите: ./start.sh
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TG_API_ID=your_api_id
export TG_API_HASH=your_api_hash
export TG_SESSION_STRING=your_session_string  # Generate with: python login.py

# Run
./start.sh
```

### Production Deployment (Render.com)

1. **Connect Repository** to Render
2. **Set Environment Variables:**
   - `TG_API_ID` (required)
   - `TG_API_HASH` (required)
   - `TG_SESSION_STRING` (required)
   - `REDIS_URL` (optional, recommended for scaling)
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `./start.sh`

## 📋 Features

- ✅ Circuit Breaker (protects against API failures)
- ✅ Distributed Rate Limiter (Redis-based)
- ✅ Auto-reconnect (Telegram & Redis)
- ✅ Prometheus Metrics (full observability)
- ✅ Request Logging (with sanitization)
- ✅ Graceful Shutdown (proper cleanup)
- ✅ Health Monitoring (periodic checks)

## 📡 API Endpoints

### `POST /search_groups`
Search for Telegram groups/channels.

**Request:**
```json
{
  "query": "python",
  "limit": 10,
  "types_only": "channel,megagroup,group",
  "min_members": 0
}
```

**Response:**
```json
{
  "ok": true,
  "query": "python",
  "items": [
    {
      "id": 123456789,
      "title": "Python Community",
      "username": "python",
      "members_count": 10000,
      "type": "channel",
      "status": "ok",
      "reason": null
    }
  ]
}
```

### `POST /get_group_admins`
Get administrators of a Telegram group.

**Request:**
```json
{
  "chat_id": -1001234567890,
  "limit": 100
}
```

**Response:**
```json
[
  {
    "chat_id": -1001234567890,
    "admin_id": 123456789,
    "username": "admin",
    "first_name": "Admin",
    "last_name": null,
    "status": "online",
    "item_status": "ok",
    "reason": null,
    "last_seen_at": null
  }
]
```

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "ok": true,
  "telegram": "ok",
  "me_id": 123456789,
  "redis": "ok"
}
```

### `GET /metrics`
Prometheus metrics endpoint.

## 🔧 Configuration

See `AGENTS.md` for full configuration options.

## 📚 Documentation

- `DEPLOY.md` - Full deployment guide
- `QUICK_DEPLOY.md` - Quick reference
- `CHANGELOG.md` - Version history

## 🧪 Testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## 📊 Monitoring

- **Metrics:** `/metrics` (Prometheus format)
- **Health:** `/health` (check every 60s)
- **Logs:** Structured logging with request_id tracking

## 🔒 Security

- Rate limiting: 60 requests/minute per IP (configurable)
- Request sanitization in logs
- Session string in environment variables (never in code)

## 📝 License

See repository for license information.



