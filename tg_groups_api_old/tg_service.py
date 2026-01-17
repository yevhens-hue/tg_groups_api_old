import os
import asyncio
import random
import logging
import time
import json
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

from telethon import TelegramClient, errors, functions, types
from telethon.sessions import StringSession

from context import request_id_var

# Optional .env for local runs only
if os.getenv("LOAD_DOTENV", "0") == "1":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

logger = logging.getLogger(__name__)

# Redis optional
try:
    import redis.asyncio as redis  # type: ignore
    _REDIS_AVAILABLE = True
except Exception:
    redis = None  # type: ignore
    _REDIS_AVAILABLE = False


# ---------------------------
# Settings (no hard-fail on import)
# ---------------------------

TG_SESSION_STRING = os.getenv("TG_SESSION_STRING")
TG_SESSION_PATH = os.getenv("TG_SESSION_PATH", "tg_groups_session.session")

RPC_TIMEOUT_SEC = int(os.getenv("TG_RPC_TIMEOUT_SEC", "25"))
RPC_MAX_RETRIES = int(os.getenv("TG_RPC_MAX_RETRIES", "2"))
RPC_BACKOFF_BASE = float(os.getenv("TG_RPC_BACKOFF_BASE", "0.6"))
RPC_BACKOFF_MAX = float(os.getenv("TG_RPC_BACKOFF_MAX", "5.0"))

# IMPORTANT: increase flood wait cap
FLOODWAIT_MAX_SLEEP_SEC = int(os.getenv("TG_FLOODWAIT_MAX_SLEEP_SEC", "420"))

CACHE_SEARCH_TTL_SEC = int(os.getenv("CACHE_SEARCH_TTL_SEC", "600"))
CACHE_ADMINS_TTL_SEC = int(os.getenv("CACHE_ADMINS_TTL_SEC", "1800"))
CACHE_MAX_ITEMS = int(os.getenv("CACHE_MAX_ITEMS", "512"))

REDIS_URL = os.getenv("REDIS_URL", "").strip()

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SEC = int(os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SEC", "60"))
CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS = int(os.getenv("CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS", "3"))


def _log_extra(**kwargs):
    rid = request_id_var.get()
    base = {"request_id": rid} if rid else {}
    base.update(kwargs)
    return base


def _telethon_error_reason(exc: Exception) -> str:
    if isinstance(exc, errors.FloodWaitError):
        return "flood_wait"
    if isinstance(exc, errors.SlowModeWaitError):
        return "rate_limited"
    if isinstance(exc, errors.UserPrivacyRestrictedError):
        return "blocked_privacy"
    if isinstance(
        exc,
        (
            errors.UserNotParticipantError,
            errors.ChannelPrivateError,
            errors.ChatAdminRequiredError,
        ),
    ):
        return "not_participant"
    if isinstance(exc, errors.UsernameNotOccupiedError):
        return "not_found"
    if isinstance(exc, (errors.UsernameInvalidError, errors.PeerIdInvalidError, errors.ChatIdInvalidError)):
        return "invalid"
    if isinstance(exc, errors.InviteHashInvalidError):
        return "invalid"
    if isinstance(exc, errors.ChatWriteForbiddenError):
        return "blocked_privacy"
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    return "unknown_error"


def _failed_search_item(reason: str) -> Dict:
    return {
        "id": 0,
        "title": "",
        "username": None,
        "members_count": None,
        "type": "unknown",
        "status": "failed",
        "reason": reason,
        # Всегда включаем поля для Google Sheets
        "created_at": None,
        "admin_id": None,
        "admin_username": None,
        "admin_last_seen_at": None,
        "admin_last_seen_status": None,
        "is_megagroup": None,
        "is_broadcast": None,
        "description": None,
    }


def _failed_admin_item(chat_id: int, reason: str) -> Dict:
    return {
        "chat_id": chat_id,
        "admin_id": 0,
        "username": None,
        "first_name": None,
        "last_name": None,
        "status": "unknown",
        "item_status": "failed",
        "reason": reason,
        "last_seen_at": None,
    }


def _require_tg_env() -> tuple[int, str]:
    """
    Strict check, but only when we actually need Telegram.
    """
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    if not api_id or not api_hash:
        raise RuntimeError(
            "TG_API_ID / TG_API_HASH отсутствуют. "
            "Добавьте их в env (Render Environment) или .env (локально с LOAD_DOTENV=1)."
        )
    return int(api_id), api_hash


def _cache_key(parts: Tuple[Any, ...]) -> str:
    raw = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), default=str)
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"tg_groups_api:{h}"


# ---------------------------
# Circuit Breaker для Telegram API
# ---------------------------

class _CircuitBreaker:
    """
    Circuit breaker для защиты от каскадных отказов Telegram API.
    States: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int, recovery_timeout_sec: int, half_open_max_calls: int):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.half_open_max_calls = half_open_max_calls
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, coro):
        async with self._lock:
            now = time.monotonic()

            # Переход из OPEN в HALF_OPEN после recovery timeout
            if self.state == self.OPEN:
                if self.last_failure_time and (now - self.last_failure_time) >= self.recovery_timeout_sec:
                    self.state = self.HALF_OPEN
                    self.half_open_calls = 0
                    logger.info("circuit_breaker: OPEN -> HALF_OPEN", extra=_log_extra())
                else:
                    raise RuntimeError("circuit_breaker_open")

            # В HALF_OPEN ограничиваем количество попыток
            if self.state == self.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    raise RuntimeError("circuit_breaker_half_open_limit")

        try:
            result = await coro
            # Успешный вызов - сбрасываем счетчики
            async with self._lock:
                if self.state == self.HALF_OPEN:
                    self.state = self.CLOSED
                    self.failure_count = 0
                    self.half_open_calls = 0
                    logger.info("circuit_breaker: HALF_OPEN -> CLOSED", extra=_log_extra())
                elif self.state == self.CLOSED:
                    self.failure_count = 0
            return result
        except Exception as exc:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.monotonic()

                if self.state == self.HALF_OPEN:
                    # В HALF_OPEN любая ошибка возвращает в OPEN
                    self.state = self.OPEN
                    self.half_open_calls = 0
                    logger.warning("circuit_breaker: HALF_OPEN -> OPEN", extra=_log_extra(reason=_telethon_error_reason(exc)))
                elif self.state == self.CLOSED and self.failure_count >= self.failure_threshold:
                    # В CLOSED превышение порога -> OPEN
                    self.state = self.OPEN
                    logger.warning(
                        "circuit_breaker: CLOSED -> OPEN",
                        extra=_log_extra(failures=self.failure_count, reason=_telethon_error_reason(exc)),
                    )
                else:
                    self.half_open_calls += 1

            raise


_circuit_breaker = _CircuitBreaker(
    failure_threshold=CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    recovery_timeout_sec=CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SEC,
    half_open_max_calls=CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS,
)


def get_circuit_breaker_state() -> int:
    """
    Возвращает состояние circuit breaker для метрик:
    0 = CLOSED, 1 = HALF_OPEN, 2 = OPEN
    """
    state_map = {
        _CircuitBreaker.CLOSED: 0,
        _CircuitBreaker.HALF_OPEN: 1,
        _CircuitBreaker.OPEN: 2,
    }
    return state_map.get(_circuit_breaker.state, 2)


class _TTLCache:
    def __init__(self, max_items: int):
        self.max_items = max_items
        self._data: Dict[str, Tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        now = time.monotonic()
        async with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._data.pop(key, None)
                return None
            return value

    async def set(self, key: str, value: Any, ttl_sec: int) -> None:
        now = time.monotonic()
        expires_at = now + max(1, ttl_sec)
        async with self._lock:
            if len(self._data) >= self.max_items:
                self._data.pop(next(iter(self._data)))
            self._data[key] = (expires_at, value)


class _RedisCache:
    def __init__(self, url: str):
        self.url = url
        self._redis = None
        self._pool = None

    async def connect(self):
        if not _REDIS_AVAILABLE or redis is None:
            raise RuntimeError("redis_package_missing")
        # Connection pooling для переиспользования соединений
        # Используем from_url с параметром connection_pool для автоматического создания пула
        self._redis = redis.from_url(
            self.url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,  # Максимум соединений в пуле
        )
        await self._redis.ping()
        # Сохраняем ссылку на pool для закрытия
        if hasattr(self._redis, 'connection_pool'):
            self._pool = self._redis.connection_pool

    async def close(self):
        """Закрыть connection pool"""
        if self._pool:
            await self._pool.aclose()
            self._pool = None
            self._redis = None

    async def get(self, key: str) -> Any | None:
        assert self._redis is not None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                payload = await self._redis.get(key)
                if payload is None:
                    return None
                try:
                    return json.loads(payload)
                except Exception:
                    return None
            except Exception as exc:
                if attempt < max_retries - 1:
                    logger.warning("redis get failed, retrying", extra=_log_extra(key=key[:50], attempt=attempt, reason=str(exc)))
                    await asyncio.sleep(0.1 * (attempt + 1))
                    # Пробуем переподключиться
                    try:
                        await self._redis.ping()
                    except Exception:
                        try:
                            await self.connect()
                        except Exception:
                            pass
                else:
                    logger.warning("redis get failed after retries", extra=_log_extra(key=key[:50], reason=str(exc)))
                    raise

    async def set(self, key: str, value: Any, ttl_sec: int) -> None:
        assert self._redis is not None
        max_retries = 3
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        for attempt in range(max_retries):
            try:
                await self._redis.setex(key, max(1, ttl_sec), payload)
                return
            except Exception as exc:
                if attempt < max_retries - 1:
                    logger.warning("redis set failed, retrying", extra=_log_extra(key=key[:50], attempt=attempt, reason=str(exc)))
                    await asyncio.sleep(0.1 * (attempt + 1))
                    # Пробуем переподключиться
                    try:
                        await self._redis.ping()
                    except Exception:
                        try:
                            await self.connect()
                        except Exception:
                            pass
                else:
                    logger.warning("redis set failed after retries", extra=_log_extra(key=key[:50], reason=str(exc)))
                    raise


_cache_fallback = _TTLCache(max_items=CACHE_MAX_ITEMS)
_cache_redis: _RedisCache | None = None


async def cache_init() -> None:
    global _cache_redis
    if not REDIS_URL:
        logger.info("cache: redis disabled (REDIS_URL missing)")
        return
    if redis is None:
        logger.warning("cache: redis disabled (package missing)")
        return
    try:
        c = _RedisCache(REDIS_URL)
        await c.connect()
        _cache_redis = c
        logger.info("cache: redis enabled with connection pooling")
    except Exception as exc:
        logger.warning("cache: redis connection failed", extra=_log_extra(reason=str(exc)))
        _cache_redis = None


async def cache_close() -> None:
    """Закрыть Redis connection pool при shutdown"""
    global _cache_redis
    if _cache_redis:
        try:
            await _cache_redis.close()
            logger.info("cache: redis connection pool closed")
        except Exception as exc:
            logger.warning("cache: redis close failed", extra=_log_extra(reason=str(exc)))
        finally:
            _cache_redis = None


async def cache_get(parts: Tuple[Any, ...]) -> Any | None:
    key = _cache_key(parts)
    if _cache_redis is not None:
        try:
            val = await _cache_redis.get(key)
            if val is not None:
                # Метрики будут добавлены через app.py если доступны
                return val
        except Exception:
            pass
    return await _cache_fallback.get(key)


async def cache_set(parts: Tuple[Any, ...], value: Any, ttl_sec: int) -> None:
    key = _cache_key(parts)
    if _cache_redis is not None:
        try:
            await _cache_redis.set(key, value, ttl_sec)
            return
        except Exception as exc:
            logger.warning("cache: redis set failed", extra=_log_extra(reason=str(exc)))
    await _cache_fallback.set(key, value, ttl_sec)


async def _sleep_backoff(attempt: int) -> None:
    base = min(RPC_BACKOFF_MAX, RPC_BACKOFF_BASE * (2 ** attempt))
    jitter = random.uniform(0, base / 2)
    await asyncio.sleep(base + jitter)


async def _rpc(call_coro, *, op: str):
    last_exc: Exception | None = None
    start_time = time.monotonic()

    for attempt in range(RPC_MAX_RETRIES + 1):
        try:
            # Circuit breaker проверка перед вызовом
            try:
                result = await _circuit_breaker.call(
                    asyncio.wait_for(call_coro, timeout=RPC_TIMEOUT_SEC)
                )
                duration = time.monotonic() - start_time
                # Метрики будут добавлены через app.py если доступны
                return result
            except RuntimeError as cb_exc:
                if "circuit_breaker" in str(cb_exc):
                    logger.warning("circuit_breaker: request rejected", extra=_log_extra(op=op, state=_circuit_breaker.state))
                    raise RuntimeError("telegram_circuit_breaker_open")
                raise

        except errors.FloodWaitError as exc:
            wait_s = int(getattr(exc, "seconds", 0) or 0)
            wait_s_capped = min(wait_s, FLOODWAIT_MAX_SLEEP_SEC)
            logger.warning(
                "telethon flood wait",
                extra=_log_extra(op=op, attempt=attempt, wait_s=wait_s, sleep_s=wait_s_capped),
            )
            if wait_s_capped > 0:
                await asyncio.sleep(wait_s_capped)
            last_exc = exc

        except errors.SlowModeWaitError as exc:
            logger.warning("telethon slow mode wait", extra=_log_extra(op=op, attempt=attempt))
            last_exc = exc
            if attempt < RPC_MAX_RETRIES:
                await _sleep_backoff(attempt)

        except (asyncio.TimeoutError, errors.RPCError) as exc:
            last_exc = exc
            logger.warning(
                "telethon rpc temporary error",
                extra=_log_extra(op=op, attempt=attempt, reason=_telethon_error_reason(exc)),
            )
            if attempt < RPC_MAX_RETRIES:
                await _sleep_backoff(attempt)

        except Exception as exc:
            last_exc = exc
            logger.exception("telethon unknown error", extra=_log_extra(op=op, attempt=attempt))
            break

    if last_exc:
        raise last_exc
    raise RuntimeError("rpc_failed_without_exception")


# ---------------------------
# Lazy TelegramClient (создаём только когда нужен)
# ---------------------------

client: TelegramClient | None = None
_client_lock = asyncio.Lock()
_last_health_check: float = 0.0
_HEALTH_CHECK_INTERVAL = 300.0  # Проверка здоровья каждые 5 минут


async def get_client() -> TelegramClient:
    global client
    if client is not None:
        return client

    async with _client_lock:
        if client is not None:
            return client

        api_id, api_hash = _require_tg_env()
        if TG_SESSION_STRING:
            client = TelegramClient(StringSession(TG_SESSION_STRING), api_id, api_hash)
        else:
            client = TelegramClient(TG_SESSION_PATH, api_id, api_hash)

        return client


async def ensure_connected() -> None:
    """
    Обеспечивает подключение к Telegram с auto-reconnect и health monitoring.
    """
    global _last_health_check
    c = await get_client()
    max_reconnect_attempts = 3
    reconnect_delay = 1.0
    now = time.monotonic()
    
    # Периодическая проверка здоровья соединения
    needs_health_check = (now - _last_health_check) > _HEALTH_CHECK_INTERVAL
    
    for attempt in range(max_reconnect_attempts):
        try:
            if not c.is_connected():
                await c.connect()
            if not await c.is_user_authorized():
                raise RuntimeError("telegram_not_authorized")
            
            # Периодическая проверка здоровья или принудительная
            if needs_health_check or attempt == 0:
                try:
                    await asyncio.wait_for(c.get_me(), timeout=5.0)
                    _last_health_check = now
                except Exception:
                    # Соединение есть, но не отвечает - переподключаемся
                    logger.warning("telegram connection stale, reconnecting", extra=_log_extra(attempt=attempt))
                    try:
                        await c.disconnect()
                    except Exception:
                        pass
                    await c.connect()
                    _last_health_check = now
            return
        except Exception as exc:
            if attempt < max_reconnect_attempts - 1:
                logger.warning(
                    "telegram connection failed, retrying",
                    extra=_log_extra(attempt=attempt, reason=_telethon_error_reason(exc)),
                )
                await asyncio.sleep(reconnect_delay * (attempt + 1))
            else:
                raise RuntimeError("telegram_not_authorized")


async def disconnect() -> None:
    global client
    if client is None:
        return
    try:
        await client.disconnect()
    finally:
        client = None


def _format_datetime(dt) -> Optional[str]:
    """
    Форматирует datetime в формат: 2025-10-11 9:19:35 (без ведущего нуля в часах)
    """
    if dt is None:
        return None
    try:
        formatted = None
        if hasattr(dt, "strftime"):
            # datetime объект
            formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(dt, (int, float)):
            # Unix timestamp
            formatted = datetime.fromtimestamp(dt).strftime("%Y-%m-%d %H:%M:%S")
        else:
            # Попробуем преобразовать в строку
            formatted = str(dt)
        
        # Убираем ведущий ноль в часах: "2025-10-11 09:19:35" -> "2025-10-11 9:19:35"
        if formatted:
            # Заменяем " 0X:" на " X:" где X - цифра (часы от 0 до 9)
            formatted = re.sub(r' 0(\d:)', r' \1', formatted)
        
        return formatted
    except Exception:
        return None


def _user_status_to_str_and_last_seen(user: types.User) -> (str, Optional[str]):
    status = getattr(user, "status", None)

    if isinstance(status, types.UserStatusOnline):
        return "online", None
    if isinstance(status, types.UserStatusOffline):
        dt = getattr(status, "was_online", None)
        return "offline", _format_datetime(dt)
    if isinstance(status, types.UserStatusRecently):
        return "recently", None
    if isinstance(status, types.UserStatusLastWeek):
        return "last_week", None
    if isinstance(status, types.UserStatusLastMonth):
        return "last_month", None

    return "unknown", None


async def search_groups(
    query: str,
    limit: int = 10,
    types_only: str = "channel,megagroup,group",
    min_members: int = 0,
    include_admins: bool = False,
    no_cache: bool = False,
) -> List[Dict]:
    await ensure_connected()
    c = await get_client()

    parts = ("search_groups", query, int(limit), types_only, int(min_members), include_admins)
    cached = None
    if not no_cache:
        cached = await cache_get(parts)
    if cached is not None:
        logger.info(
            "search_groups cache hit",
            extra=_log_extra(query=(query or "")[:80], include_admins=include_admins),
        )
        return cached
    
    logger.info(
        "search_groups starting",
        extra=_log_extra(query=(query or "")[:80], limit=limit, include_admins=include_admins),
    )

    type_set = {t.strip() for t in types_only.split(",") if t.strip()}
    result: List[Dict] = []

    try:
        resp = await _rpc(c(functions.contacts.SearchRequest(q=query, limit=limit)), op="search_groups")
    except Exception as exc:
        reason = _telethon_error_reason(exc)
        logger.warning("search_groups failed", extra=_log_extra(reason=reason))
        return [_failed_search_item(reason)]

    for chat in getattr(resp, "chats", []):
        try:
            t = "unknown"
            if isinstance(chat, types.Channel):
                t = "channel" if chat.broadcast else "megagroup"
            elif isinstance(chat, types.Chat):
                t = "group"

            if type_set and t not in type_set:
                continue

            members = getattr(chat, "participants_count", None)
            if min_members and members is not None and members < min_members:
                continue

            # Определяем is_megagroup и is_broadcast
            is_megagroup = None
            is_broadcast = None
            if isinstance(chat, types.Channel):
                is_megagroup = not getattr(chat, "broadcast", True)
                is_broadcast = getattr(chat, "broadcast", False)
            elif isinstance(chat, types.Chat):
                is_megagroup = True
                is_broadcast = False

            item = {
                "id": chat.id,
                "title": getattr(chat, "title", ""),
                "username": getattr(chat, "username", None),
                "members_count": members,
                "type": t,
                "status": "ok",
                "reason": None,
                # Всегда добавляем поля для Google Sheets (даже если None)
                "created_at": None,
                "admin_id": None,
                "admin_username": None,
                "admin_last_seen_at": None,
                "admin_last_seen_status": None,
                "is_megagroup": is_megagroup,
                "is_broadcast": is_broadcast,
                "description": None,
            }

            # Дополнительные поля для Google Sheets export
            # ВАЖНО: Пытаемся получить данные даже если include_admins=False для обратной совместимости
            # но только если это не увеличит нагрузку слишком сильно
            should_fetch_admins = include_admins
            
            logger.debug(
                "processing chat",
                extra=_log_extra(chat_id=chat.id, include_admins=include_admins, should_fetch=should_fetch_admins, chat_type=t),
            )
            
            if should_fetch_admins:
                try:
                    # Получаем полную информацию о группе для created_at и админов
                    if isinstance(chat, types.Channel):
                        try:
                            full_channel = await _rpc(
                                c(functions.channels.GetFullChannelRequest(channel=chat)),
                                op="get_full_channel",
                            )
                            full_chat = getattr(full_channel, "full_chat", None)
                            if full_chat:
                                # Описание
                                about = getattr(full_chat, "about", None)
                                if about:
                                    item["description"] = about
                                
                                # Дата создания - пробуем разные источники
                                date = getattr(full_chat, "date", None)
                                if not date:
                                    # Пробуем из самого chat объекта
                                    date = getattr(chat, "date", None)
                                if date:
                                    item["created_at"] = _format_datetime(date)
                                    if item["created_at"] is None:
                                        logger.warning(
                                            "failed to format date",
                                            extra=_log_extra(chat_id=chat.id, date=date),
                                        )
                            
                            # Получаем первого админа
                            try:
                                logger.debug(
                                    "fetching admins for channel",
                                    extra=_log_extra(chat_id=chat.id, chat_title=item.get("title", "")[:50]),
                                )
                                # Используем GetParticipantsRequest через _rpc для лучшей обработки ошибок
                                participants_req = await _rpc(
                                    c(functions.channels.GetParticipantsRequest(
                                        channel=chat,
                                        filter=types.ChannelParticipantsAdmins(),
                                        offset=0,
                                        limit=1,
                                        hash=0,
                                    )),
                                    op="get_channel_admins",
                                )
                                
                                # Извлекаем пользователей из ответа
                                admin_user = None
                                if hasattr(participants_req, "users") and participants_req.users:
                                    admin_user = participants_req.users[0]
                                elif hasattr(participants_req, "participants") and participants_req.participants:
                                    # Если есть participants, получаем user_id и ищем в users
                                    participant = participants_req.participants[0]
                                    user_id = getattr(participant, "user_id", None)
                                    if user_id and hasattr(participants_req, "users"):
                                        for u in participants_req.users:
                                            if getattr(u, "id", None) == user_id:
                                                admin_user = u
                                                break
                                
                                if admin_user:
                                    item["admin_id"] = getattr(admin_user, "id", None)
                                    item["admin_username"] = getattr(admin_user, "username", None)
                                    admin_status, admin_last_seen = _user_status_to_str_and_last_seen(admin_user)
                                    item["admin_last_seen_status"] = admin_status
                                    item["admin_last_seen_at"] = admin_last_seen
                                    logger.info(
                                        "admin info retrieved for channel",
                                        extra=_log_extra(
                                            chat_id=chat.id,
                                            admin_id=item["admin_id"],
                                            admin_username=item["admin_username"],
                                            admin_status=admin_status,
                                        ),
                                    )
                                else:
                                    logger.warning(
                                        "no admin user found in participants response",
                                        extra=_log_extra(
                                            chat_id=chat.id,
                                            has_users=hasattr(participants_req, "users"),
                                            users_count=len(getattr(participants_req, "users", [])),
                                            has_participants=hasattr(participants_req, "participants"),
                                        ),
                                    )
                            except Exception as admin_exc:
                                error_reason = _telethon_error_reason(admin_exc)
                                logger.warning(
                                    "failed to get admin info for channel",
                                    extra=_log_extra(
                                        chat_id=chat.id,
                                        reason=error_reason,
                                        error_type=type(admin_exc).__name__,
                                        error_details=str(admin_exc)[:200],
                                    ),
                                )
                                # Не прерываем выполнение, просто оставляем поля null
                        except Exception as channel_exc:
                            logger.warning(
                                "failed to get full channel",
                                extra=_log_extra(chat_id=chat.id, reason=_telethon_error_reason(channel_exc)),
                            )
                    elif isinstance(chat, types.Chat):
                        try:
                            full_chat_req = await _rpc(
                                c(functions.messages.GetFullChatRequest(chat_id=chat.id)),
                                op="get_full_chat",
                            )
                            full_chat = getattr(full_chat_req, "full_chat", None)
                            if full_chat:
                                # Описание (для Chat обычно нет, но проверим)
                                about = getattr(full_chat, "about", None)
                                if about:
                                    item["description"] = about
                                
                                # Дата создания
                                date = getattr(full_chat, "date", None)
                                if not date:
                                    date = getattr(chat, "date", None)
                                if date:
                                    item["created_at"] = _format_datetime(date)
                                    if item["created_at"] is None:
                                        logger.warning(
                                            "failed to format date",
                                            extra=_log_extra(chat_id=chat.id, date=date),
                                        )
                                
                                # Получаем первого админа
                                try:
                                    logger.debug(
                                        "fetching admins for chat",
                                        extra=_log_extra(chat_id=chat.id, chat_title=item.get("title", "")[:50]),
                                    )
                                    user_by_id = {u.id: u for u in getattr(full_chat_req, "users", [])}
                                    participants = getattr(full_chat, "participants", None)
                                    admin_user = None
                                    
                                    if participants:
                                        participants_list = getattr(participants, "participants", [])
                                        logger.debug(
                                            "processing participants",
                                            extra=_log_extra(chat_id=chat.id, participants_count=len(participants_list)),
                                        )
                                        for p in participants_list:
                                            if isinstance(p, (types.ChatParticipantAdmin, types.ChatParticipantCreator)):
                                                user_id = getattr(p, "user_id", None)
                                                admin_user = user_by_id.get(user_id)
                                                if admin_user:
                                                    logger.debug(
                                                        "found admin participant",
                                                        extra=_log_extra(chat_id=chat.id, user_id=user_id),
                                                    )
                                                    break # Нашли первого админа
                                    
                                    if admin_user:
                                        item["admin_id"] = getattr(admin_user, "id", None)
                                        item["admin_username"] = getattr(admin_user, "username", None)
                                        admin_status, admin_last_seen = _user_status_to_str_and_last_seen(admin_user)
                                        item["admin_last_seen_status"] = admin_status
                                        item["admin_last_seen_at"] = admin_last_seen
                                        logger.info(
                                            "admin info retrieved for chat",
                                            extra=_log_extra(
                                                chat_id=chat.id,
                                                admin_id=item["admin_id"],
                                                admin_username=item["admin_username"],
                                                admin_status=admin_status,
                                            ),
                                        )
                                    else:
                                        logger.warning(
                                            "no admin user found in chat",
                                            extra=_log_extra(
                                                chat_id=chat.id,
                                                has_participants=participants is not None,
                                                participants_count=len(getattr(participants, "participants", [])) if participants else 0,
                                                users_count=len(user_by_id),
                                            ),
                                        )
                                except Exception as admin_exc:
                                    error_reason = _telethon_error_reason(admin_exc)
                                    logger.warning(
                                        "failed to get admin info for chat",
                                        extra=_log_extra(
                                            chat_id=chat.id,
                                            reason=error_reason,
                                            error_type=type(admin_exc).__name__,
                                            error_details=str(admin_exc)[:200],
                                        ),
                                    )
                        except Exception as chat_exc:
                            logger.warning(
                                "failed to get full chat",
                                extra=_log_extra(chat_id=chat.id, reason=_telethon_error_reason(chat_exc)),
                            )
                except Exception as full_exc:
                    # Если не удалось получить полную информацию, продолжаем без неё
                    logger.warning(
                        "failed to get full chat info",
                        extra=_log_extra(chat_id=chat.id, reason=_telethon_error_reason(full_exc)),
                    )

            result.append(item)
        except Exception as exc:
            result.append(_failed_search_item(_telethon_error_reason(exc)))

    failed_count = sum(1 for item in result if item.get("status") == "failed")
    # Подсчитываем сколько групп получили админскую информацию
    admins_found = sum(1 for item in result if item.get("admin_id") is not None)
    created_at_found = sum(1 for item in result if item.get("created_at") is not None)
    logger.info(
        "search_groups result",
        extra=_log_extra(
            query=(query or "")[:80],
            limit=limit,
            results=len(result),
            failed=failed_count,
            include_admins=include_admins,
            admins_found=admins_found,
            created_at_found=created_at_found,
        ),
    )

    await cache_set(parts, result, ttl_sec=CACHE_SEARCH_TTL_SEC)
    return result


async def get_group_admins(chat_id: int, limit: int = 100) -> List[Dict]:
    await ensure_connected()
    c = await get_client()

    parts = ("get_group_admins", int(chat_id), int(limit))
    cached = await cache_get(parts)
    if cached is not None:
        logger.info("get_group_admins cache hit", extra=_log_extra(chat_id=chat_id))
        return cached

    try:
        entity = await _rpc(c.get_entity(chat_id), op="get_entity")
    except Exception as exc:
        reason = _telethon_error_reason(exc)
        logger.warning("get_entity failed", extra=_log_extra(chat_id=chat_id, reason=reason))
        return [_failed_admin_item(chat_id, reason)]

    admins: List[Dict] = []

    if isinstance(entity, types.Channel):
        try:
            users = await _rpc(
                c.get_participants(entity, filter=types.ChannelParticipantsAdmins),
                op="get_participants_admins",
            )
        except Exception as exc:
            reason = _telethon_error_reason(exc)
            logger.warning("get_participants_admins failed", extra=_log_extra(chat_id=chat_id, reason=reason))
            return [_failed_admin_item(chat_id, reason)]

        for u in users[:limit]:
            try:
                user_status, last_seen = _user_status_to_str_and_last_seen(u)
                admins.append(
                    {
                        "chat_id": chat_id,
                        "admin_id": getattr(u, "id", 0),
                        "username": getattr(u, "username", None),
                        "first_name": getattr(u, "first_name", None),
                        "last_name": getattr(u, "last_name", None),
                        "status": user_status,
                        "item_status": "ok",
                        "reason": None,
                        "last_seen_at": last_seen,
                    }
                )
            except Exception as exc:
                admins.append(
                    {
                        "chat_id": chat_id,
                        "admin_id": getattr(u, "id", 0),
                        "username": getattr(u, "username", None),
                        "first_name": getattr(u, "first_name", None),
                        "last_name": getattr(u, "last_name", None),
                        "status": "unknown",
                        "item_status": "failed",
                        "reason": _telethon_error_reason(exc),
                        "last_seen_at": None,
                    }
                )

        failed_count = sum(1 for a in admins if a.get("item_status") == "failed")
        logger.info(
            "get_group_admins result (channel)",
            extra=_log_extra(chat_id=chat_id, results=len(admins), failed=failed_count),
        )

        await cache_set(parts, admins, ttl_sec=CACHE_ADMINS_TTL_SEC)
        return admins

    if isinstance(entity, types.Chat):
        try:
            full = await _rpc(c(functions.messages.GetFullChatRequest(chat_id=chat_id)), op="get_full_chat")
        except Exception as exc:
            reason = _telethon_error_reason(exc)
            logger.warning("get_full_chat failed", extra=_log_extra(chat_id=chat_id, reason=reason))
            return [_failed_admin_item(chat_id, reason)]

        user_by_id = {u.id: u for u in getattr(full, "users", [])}

        participants = []
        full_chat = getattr(full, "full_chat", None)
        chat_participants = getattr(full_chat, "participants", None)
        if chat_participants is not None:
            for p in getattr(chat_participants, "participants", []):
                if isinstance(p, (types.ChatParticipantAdmin, types.ChatParticipantCreator)):
                    participants.append(p)

        for p in participants[:limit]:
            u = user_by_id.get(p.user_id)
            if not u:
                admins.append(
                    {
                        "chat_id": chat_id,
                        "admin_id": p.user_id,
                        "username": None,
                        "first_name": None,
                        "last_name": None,
                        "status": "unknown",
                        "item_status": "partial",
                        "reason": "not_found",
                        "last_seen_at": None,
                    }
                )
                continue

            try:
                user_status, last_seen = _user_status_to_str_and_last_seen(u)
                admins.append(
                    {
                        "chat_id": chat_id,
                        "admin_id": getattr(u, "id", 0),
                        "username": getattr(u, "username", None),
                        "first_name": getattr(u, "first_name", None),
                        "last_name": getattr(u, "last_name", None),
                        "status": user_status,
                        "item_status": "ok",
                        "reason": None,
                        "last_seen_at": last_seen,
                    }
                )
            except Exception as exc:
                admins.append(
                    {
                        "chat_id": chat_id,
                        "admin_id": getattr(u, "id", 0),
                        "username": getattr(u, "username", None),
                        "first_name": getattr(u, "first_name", None),
                        "last_name": getattr(u, "last_name", None),
                        "status": "unknown",
                        "item_status": "failed",
                        "reason": _telethon_error_reason(exc),
                        "last_seen_at": None,
                    }
                )

        failed_count = sum(1 for a in admins if a.get("item_status") == "failed")
        logger.info(
            "get_group_admins result (chat)",
            extra=_log_extra(chat_id=chat_id, results=len(admins), failed=failed_count),
        )

        result = admins[:limit]
        await cache_set(parts, result, ttl_sec=CACHE_ADMINS_TTL_SEC)
        return result

    logger.warning("unsupported entity type", extra=_log_extra(chat_id=chat_id, entity_type=type(entity).__name__))
    return [_failed_admin_item(chat_id, "unsupported_chat_type")]
