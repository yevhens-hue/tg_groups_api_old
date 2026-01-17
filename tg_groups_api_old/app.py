import os
import time
import uuid
import asyncio
import logging
from typing import Optional, List, AsyncGenerator, Dict, Deque
from collections import deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

# Prometheus metrics (опционально)
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    # Fallback для случаев когда prometheus_client не установлен (тесты, dev)
    _PROMETHEUS_AVAILABLE = False
    # Создаём заглушки для метрик
    class _MetricStub:
        def labels(self, **kwargs):
            return self
        def inc(self, value=1):
            pass
        def observe(self, value):
            pass
        def set(self, value):
            pass
    Counter = Histogram = Gauge = _MetricStub
    generate_latest = lambda: b""
    CONTENT_TYPE_LATEST = "text/plain"

from context import request_id_var
import tg_service


# ---------------------------
# Logging (логирование)
# ---------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app")


# ---------------------------
# HTTP Timeout (таймаут на весь HTTP запрос)
# ---------------------------

HTTP_TIMEOUT_SEC = int(os.getenv("HTTP_TIMEOUT_SEC", "30"))


# ---------------------------
# Distributed rate limiter (Redis-based для горизонтального масштабирования)
# Fallback на in-memory если Redis недоступен
# ---------------------------

HTTP_RATE_LIMIT_RPM = int(os.getenv("HTTP_RATE_LIMIT_RPM", "60"))  # requests per minute per IP
_RATE_WINDOW_SEC = 60.0
_RATE_STATE_MAX_ITEMS = int(os.getenv("RATE_LIMITER_MAX_ITEMS", "10000"))  # Максимум IP в памяти
_rate_state: Dict[str, Deque[float]] = {}  # Fallback in-memory (bounded)
_rate_lock = asyncio.Lock()


def _get_client_ip(request: Request) -> str:
    """Получает IP клиента с санитизацией"""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()[:50]  # Ограничиваем длину
    if request.client and request.client.host:
        return request.client.host[:50]
    return "unknown"


def _sanitize_log_data(data: str, max_length: int = 100) -> str:
    """Санитизация данных для логов"""
    if not data:
        return ""
    # Обрезаем длинные строки
    sanitized = data[:max_length]
    # Удаляем потенциально опасные символы (упрощённо)
    sanitized = sanitized.replace("\n", " ").replace("\r", " ")
    return sanitized


async def _allow_request_with_info(ip: str) -> tuple[bool, int, int]:
    """
    Distributed rate limiter: сначала пробуем Redis, fallback на in-memory.
    Возвращает (allowed, remaining, reset_at)
    """
    now_ts = int(time.time())
    reset_at = now_ts + int(_RATE_WINDOW_SEC)
    
    # Пробуем Redis-based rate limiter если доступен
    if tg_service._cache_redis and tg_service._cache_redis._redis:
        try:
            redis_client = tg_service._cache_redis._redis
            key = f"rate_limit:{ip}"
            window_start = now_ts - int(_RATE_WINDOW_SEC)

            # Используем Redis sorted set для sliding window
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)  # Удаляем старые записи
            pipe.zcard(key)  # Считаем текущие запросы
            results = await pipe.execute()

            current_count = results[1] if len(results) > 1 else 0
            allowed = current_count < HTTP_RATE_LIMIT_RPM
            
            # Добавляем запрос только если разрешено
            if allowed:
                pipe2 = redis_client.pipeline()
                pipe2.zadd(key, {str(now_ts): now_ts})  # Добавляем текущий запрос
                pipe2.expire(key, int(_RATE_WINDOW_SEC) + 10)  # TTL чуть больше окна
                await pipe2.execute()
            
            remaining = max(0, HTTP_RATE_LIMIT_RPM - current_count - (1 if allowed else 0))
            return allowed, remaining, reset_at
        except Exception as exc:
            logger.warning("rate_limiter: redis failed, fallback to memory", extra={"reason": str(exc)})

    # Fallback на in-memory rate limiter (bounded)
    now = time.monotonic()
    async with _rate_lock:
        # Очистка старых записей и ограничение размера
        if len(_rate_state) > _RATE_STATE_MAX_ITEMS:
            # Удаляем самые старые IP (FIFO)
            oldest_ip = next(iter(_rate_state))
            _rate_state.pop(oldest_ip, None)
        
        q = _rate_state.get(ip)
        if q is None:
            q = deque()
            _rate_state[ip] = q

        while q and (now - q[0]) > _RATE_WINDOW_SEC:
            q.popleft()

        current_count = len(q)
        remaining = max(0, HTTP_RATE_LIMIT_RPM - current_count)
        allowed = current_count < HTTP_RATE_LIMIT_RPM
        
        if allowed:
            q.append(now)
        
        return allowed, remaining, reset_at


async def _allow_request(ip: str) -> bool:
    """Backward compatibility wrapper"""
    allowed, _, _ = await _allow_request_with_info(ip)
    return allowed


# ---------------------------
# Prometheus Metrics (опционально)
# ---------------------------

if _PROMETHEUS_AVAILABLE:
    http_requests_total = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )

    http_request_duration_seconds = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "endpoint"],
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0),
    )

    telegram_rpc_total = Counter(
        "telegram_rpc_total",
        "Total Telegram RPC calls",
        ["op", "status"],
    )

    telegram_rpc_duration_seconds = Histogram(
        "telegram_rpc_duration_seconds",
        "Telegram RPC duration in seconds",
        ["op"],
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0),
    )

    cache_operations_total = Counter(
        "cache_operations_total",
        "Cache operations",
        ["operation", "cache_type", "result"],
    )

    circuit_breaker_state = Gauge(
        "circuit_breaker_state",
        "Circuit breaker state (0=closed, 1=half_open, 2=open)",
    )

    rate_limit_rejected_total = Counter(
        "rate_limit_rejected_total",
        "Total rate limit rejections",
        ["ip"],
    )
else:
    # Заглушки для случаев когда prometheus недоступен
    _stub = _MetricStub()
    http_requests_total = _stub
    http_request_duration_seconds = _stub
    telegram_rpc_total = _stub
    telegram_rpc_duration_seconds = _stub
    cache_operations_total = _stub
    circuit_breaker_state = _stub
    rate_limit_rejected_total = _stub


# ---------------------------
# Lifespan (startup / shutdown)
# ---------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    try:
        await tg_service.cache_init()
        await tg_service.ensure_connected()
        logger.info("startup ok")
    except Exception as exc:
        logger.warning("startup partial", extra={"reason": tg_service._telethon_error_reason(exc)})

    yield

    # Graceful shutdown
    logger.info("shutdown: starting graceful shutdown")
    shutdown_tasks = []

    # Закрываем Telegram client
    shutdown_tasks.append(tg_service.disconnect())

    # Закрываем Redis connection pool
    shutdown_tasks.append(tg_service.cache_close())

    # Ждём завершения всех задач с timeout
    try:
        await asyncio.wait_for(asyncio.gather(*shutdown_tasks, return_exceptions=True), timeout=10.0)
        logger.info("shutdown: completed")
    except asyncio.TimeoutError:
        logger.warning("shutdown: timeout, forcing exit")
    except Exception as exc:
        logger.warning("shutdown: error", extra={"reason": str(exc)})


app = FastAPI(lifespan=lifespan)


# ---------------------------
# Models
# ---------------------------

class SearchGroupsRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(10, ge=1, le=100)
    types_only: str = "channel,megagroup,group"
    min_members: int = Field(0, ge=0)
    include_admins: bool = Field(False, description="Include admin info and creation date for Google Sheets export")
    no_cache: bool = Field(False, description="Skip cache and fetch fresh data")


class TgChat(BaseModel):
    id: int
    title: str
    username: Optional[str] = None
    members_count: Optional[int] = None
    type: str
    status: str
    reason: Optional[str] = None
    # Дополнительные поля для Google Sheets export через n8n
    created_at: Optional[str] = None  # Дата создания группы (ISO format)
    admin_id: Optional[int] = None  # ID первого админа
    admin_username: Optional[str] = None  # Username первого админа
    admin_last_seen_at: Optional[str] = None  # Когда админ был в сети последний раз (ISO format)
    admin_last_seen_status: Optional[str] = None  # Статус админа (online, offline, recently, etc.)
    is_megagroup: Optional[bool] = None  # Является ли мегагруппой
    is_broadcast: Optional[bool] = None  # Является ли broadcast каналом
    description: Optional[str] = None  # Описание группы/канала


class TgChatResponse(BaseModel):
    ok: bool
    query: str
    items: List[TgChat]


class GetAdminsRequest(BaseModel):
    chat_id: int
    limit: int = Field(100, ge=1, le=500)


class TgAdmin(BaseModel):
    chat_id: int
    admin_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: str           # статус присутствия юзера
    item_status: str      # статус выполнения элемента
    reason: Optional[str] = None
    last_seen_at: Optional[str] = None


# ---------------------------
# Middleware
# ---------------------------

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)

    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    ip = _get_client_ip(request)
    allowed, remaining, reset_at = await _allow_request_with_info(ip)
    if not allowed:
        rate_limit_rejected_total.labels(ip=ip[:20]).inc()  # Обрезаем IP для метрик
        response = JSONResponse(
            status_code=429,
            content={"ok": False, "reason": "rate_limited_http", "limit_rpm": HTTP_RATE_LIMIT_RPM},
        )
        response.headers["X-RateLimit-Limit"] = str(HTTP_RATE_LIMIT_RPM)
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        return response
    
    response = await call_next(request)
    # Добавляем rate limit headers
    response.headers["X-RateLimit-Limit"] = str(HTTP_RATE_LIMIT_RPM)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_at)
    return response


@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=HTTP_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"ok": False, "reason": "http_timeout", "timeout_sec": HTTP_TIMEOUT_SEC},
        )


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Middleware для логирования всех запросов с timing"""
    start_time = time.time()
    request_id = request_id_var.get() or "unknown"
    method = request.method
    endpoint = request.url.path
    ip = _get_client_ip(request)
    
    # Санитизация query для логов
    query_sanitized = None
    if hasattr(request, "query_params") and request.query_params:
        query_sanitized = _sanitize_log_data(str(request.query_params), max_length=100)
    
    logger.info(
        "request_start",
        extra={
            "request_id": request_id,
            "method": method,
            "endpoint": endpoint,
            "ip": ip[:20],  # Обрезаем IP для безопасности
            "query": query_sanitized,
        },
    )
    
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        status = response.status_code
        
        logger.info(
            "request_complete",
            extra={
                "request_id": request_id,
                "method": method,
                "endpoint": endpoint,
                "status": status,
                "duration_ms": round(duration * 1000, 2),
            },
        )
        return response
    except Exception as exc:
        duration = time.time() - start_time
        logger.error(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": method,
                "endpoint": endpoint,
                "duration_ms": round(duration * 1000, 2),
                "error": str(exc)[:200],  # Обрезаем длинные ошибки
            },
            exc_info=True,
        )
        raise


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware для сбора метрик Prometheus"""
    start_time = time.time()
    method = request.method
    endpoint = request.url.path

    # Обновляем состояние circuit breaker
    circuit_breaker_state.set(tg_service.get_circuit_breaker_state())

    try:
        response = await call_next(request)
        status = response.status_code
        duration = time.time() - start_time

        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)

        return response
    except Exception as exc:
        status = 500
        duration = time.time() - start_time
        http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        raise


# ---------------------------
# Endpoints
# ---------------------------

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"ok": True, "service": "tg_groups_api_old"}


@app.get("/health")
async def health():
    health_status = {"ok": True}
    try:
        await tg_service.ensure_connected()
        client = await tg_service.get_client()
        me = await tg_service._rpc(client.get_me(), op="health_get_me")
        health_status["telegram"] = "ok"
        health_status["me_id"] = getattr(me, "id", None)
    except Exception as exc:
        health_status["ok"] = False
        health_status["telegram"] = "failed"
        health_status["reason"] = tg_service._telethon_error_reason(exc)

    # Проверяем Redis если доступен
    if tg_service._cache_redis and tg_service._cache_redis._redis:
        try:
            await tg_service._cache_redis._redis.ping()
            health_status["redis"] = "ok"
        except Exception:
            health_status["redis"] = "failed"
    else:
        health_status["redis"] = "disabled"

    return health_status


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    if not _PROMETHEUS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "reason": "prometheus_client_not_installed"},
        )
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Глобальный обработчик исключений для структурированных ответов"""
    request_id = request_id_var.get() or "unknown"
    reason = tg_service._telethon_error_reason(exc)
    
    # Определяем статус код
    status_code = 500
    if "circuit_breaker" in str(exc):
        status_code = 503  # Service Unavailable
    elif "rate_limited" in reason or "flood_wait" in reason:
        status_code = 429  # Too Many Requests
    elif "not_found" in reason or "invalid" in reason:
        status_code = 404  # Not Found
    elif "not_participant" in reason or "blocked_privacy" in reason:
        status_code = 403  # Forbidden
    
    logger.error(
        "unhandled_exception",
        extra={
            "request_id": request_id,
            "endpoint": request.url.path,
            "method": request.method,
            "reason": reason,
            "error": str(exc)[:200],
        },
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "reason": reason,
            "request_id": request_id,
            "error": str(exc)[:200] if status_code == 500 else None,  # Детали только для 500
        },
    )


@app.post("/search_groups", response_model=TgChatResponse)
async def search_groups(req: SearchGroupsRequest):
    try:
        # ВАЖНО: Логируем тип include_admins для отладки
        include_admins_type = type(req.include_admins).__name__
        include_admins_value = req.include_admins
        logger.info(
            "search_groups request",
            extra={
                "query": req.query[:80] if req.query else "",
                "limit": req.limit,
                "min_members": req.min_members,
                "types_only": req.types_only,
                "include_admins": include_admins_value,
                "include_admins_type": include_admins_type,  # Для отладки - должен быть 'bool'
            },
        )
        
        # КРИТИЧНО: Проверяем что include_admins действительно True
        if not include_admins_value:
            logger.warning(
                "include_admins is False - admin data will not be fetched",
                extra={"query": req.query[:80] if req.query else ""},
            )
        items = await tg_service.search_groups(
            query=req.query,
            limit=req.limit,
            types_only=req.types_only,
            min_members=req.min_members,
            include_admins=req.include_admins,
            no_cache=req.no_cache,
        )
        # Логируем результат для отладки
        admins_count = sum(1 for item in items if item.get("admin_id") is not None)
        created_at_count = sum(1 for item in items if item.get("created_at") is not None)
        logger.info(
            "search_groups response",
            extra={
                "query": req.query[:80] if req.query else "",
                "items_count": len(items),
                "include_admins": req.include_admins,
                "admins_found": admins_count,
                "created_at_found": created_at_count,
            },
        )
        return {"ok": True, "query": req.query, "items": items}
    except Exception as exc:
        reason = tg_service._telethon_error_reason(exc)
        logger.exception("search_groups endpoint failed", extra={"reason": reason})
        return JSONResponse(status_code=500, content={"ok": False, "query": req.query, "items": [], "reason": reason})


@app.post("/get_group_admins", response_model=List[TgAdmin])
async def get_group_admins(req: GetAdminsRequest):
    try:
        return await tg_service.get_group_admins(chat_id=req.chat_id, limit=req.limit)
    except Exception as exc:
        reason = tg_service._telethon_error_reason(exc)
        logger.exception("get_group_admins endpoint failed", extra={"reason": reason, "chat_id": req.chat_id})
        # сохраняем контракт: endpoint возвращает список
        return JSONResponse(status_code=500, content=[tg_service._failed_admin_item(req.chat_id, reason)])
