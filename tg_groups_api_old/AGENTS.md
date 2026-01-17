# Repository Guidelines

## Project Structure & Module Organization
This is a small FastAPI service that wraps Telegram lookups with Telethon.
- `app.py` defines the FastAPI app and HTTP endpoints.
- `tg_service.py` holds Telegram client setup and query helpers.
- `login.py` and `export_session.py` are local utilities for creating session strings.
- `requirements.txt` lists Python dependencies.
- `start.sh` runs the API with Uvicorn.

## Build, Test, and Development Commands
Install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Run the API locally:
```bash
./start.sh
# or
uvicorn app:app --host 0.0.0.0 --port 8010
```
Generate a Telegram session string:
```bash
python login.py
```

## Configuration & Security Notes
Required environment variables:
- `TG_API_ID`, `TG_API_HASH`
Optional:
- `TG_SESSION_STRING` (preferred for deployments)
- `TG_SESSION_NAME` or `TG_SESSION_PATH` (file-based sessions)
- `REDIS_URL` (for distributed rate limiting and shared cache)
- `HTTP_RATE_LIMIT_RPM` (default: 60 requests per minute per IP)
- `RATE_LIMITER_MAX_ITEMS` (default: 10000, max IPs in memory fallback)
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD` (default: 5)
- `CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SEC` (default: 60)
- `CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS` (default: 3)
- `TG_RPC_TIMEOUT_SEC` (default: 25)
- `TG_RPC_MAX_RETRIES` (default: 2)
- `TG_FLOODWAIT_MAX_SLEEP_SEC` (default: 420)
- `CACHE_SEARCH_TTL_SEC` (default: 600)
- `CACHE_ADMINS_TTL_SEC` (default: 1800)
- `HTTP_TIMEOUT_SEC` (default: 30)
- `LOG_LEVEL` (default: INFO)

Keep `.env` or session files out of source control.

## Coding Style & Naming Conventions
Use PEP 8 with 4-space indentation and snake_case names. Prefer type hints on public functions and data models. Keep API request/response models in `app.py` and business logic in `tg_service.py`.

## Testing Guidelines
Run tests:
```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Tests are located in `tests/` directory. Use `test_*.py` naming convention.

## Commit & Pull Request Guidelines
Commit messages in history are short, imperative, and task-focused (e.g., "Add get_group_admins endpoint"). Follow that style.
Pull requests should include:
- A brief description of behavior changes.
- Any required env var updates or deployment notes.
- Example API calls when adding endpoints.
