from typing import List, Optional
import asyncio
import os

import structlog
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl, Field

from logging_config import configure_logging
from middleware import RequestIDMiddleware
from middleware_metrics import MetricsMiddleware
from middleware_request_logging import RequestLoggingMiddleware
from rate_limiter import RateLimitMiddleware
from config import get_settings
from exception_handlers import (
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler,
)
from metrics import get_metrics_collector
from db import get_db
from models import Mirror
from services.mirrors import (
    collect_mirrors_for_all,
    collect_mirrors_for_batch,
)
from services.browser_resolver import resolve_url as resolve_single_url
from services.interactive_collector import resolve_urls_for_merchant
from services.interactive_full import collect_mirrors_interactive_for_merchant
from services.browser_pool import get_browser_pool, close_browser_pool
from services.serper_client import SerperError
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Настраиваем логирование при старте
configure_logging()
logger = structlog.get_logger()

# =======================
#  СОЗДАЕМ ПРИЛОЖЕНИЕ
# =======================

app = FastAPI(
    title="Merchant mirrors API",
    version="0.9.0",
    description="Production-ready API for collecting merchant mirrors",
)

# Добавляем exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Добавляем middleware в правильном порядке (последний добавленный выполняется первым)
# Порядок: RequestLogging -> Metrics -> RateLimit -> RequestID
settings = get_settings()

# Request logging (опционально, только в development)
if settings.ENVIRONMENT == "development":
    app.add_middleware(RequestLoggingMiddleware, log_request_body=False, log_response_body=False)

app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)  # Настраиваемый лимит
app.add_middleware(RequestIDMiddleware)

# CORS настройки
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Семафор для ограничения параллельных фоновых задач
background_tasks_semaphore = asyncio.Semaphore(5)  # Максимум 5 параллельных фоновых задач


# =======================
#  LIFECYCLE EVENTS
# =======================

@app.on_event("startup")
async def startup_event():
    """Инициализация при старте приложения."""
    from config import get_settings
    from services.keepalive import get_keepalive_service
    
    settings = get_settings()
    logger.info("app_starting", environment=settings.ENVIRONMENT)
    
    # Инициализируем browser pool
    browser_pool = get_browser_pool()
    await browser_pool.initialize()
    
    # Запускаем keep-alive если включен
    if settings.KEEPALIVE_ENABLED:
        keepalive = get_keepalive_service(
            health_url=settings.KEEPALIVE_URL,
            interval=settings.KEEPALIVE_INTERVAL,
        )
        await keepalive.start()
    
    logger.info("app_started", environment=settings.ENVIRONMENT)


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при остановке приложения."""
    from config import get_settings
    from services.keepalive import get_keepalive_service
    
    settings = get_settings()
    logger.info("app_shutting_down", environment=settings.ENVIRONMENT)
    
    # Останавливаем keep-alive
    if settings.KEEPALIVE_ENABLED:
        try:
            keepalive = get_keepalive_service()
            await keepalive.stop()
        except Exception as e:
            logger.error("error_stopping_keepalive", error=str(e))
    
    # Закрываем browser pool
    try:
        await close_browser_pool()
    except Exception as e:
        logger.error("error_closing_browser_pool", error=str(e))
    
    # Закрываем соединения с БД
    try:
        from db import engine
        engine.dispose()
    except Exception as e:
        logger.error("error_closing_db", error=str(e))
    
    logger.info("app_shutdown", environment=settings.ENVIRONMENT)


# =======================
#  УТИЛИТА: запуск async в BackgroundTasks (ИСПРАВЛЕНО)
# =======================

async def run_background_task(coro):
    """
    Правильный способ запуска async задач в BackgroundTasks.
    Используем asyncio.create_task вместо asyncio.run().
    """
    async with background_tasks_semaphore:
        try:
            await coro
        except asyncio.CancelledError:
            logger.warning("background_task_cancelled")
            raise
        except Exception as e:
            logger.error("background_task_failed", error=str(e), exc_info=True)


# =====================================
#  НОВЫЕ ИНТЕРАКТИВНЫЕ ЭНДПОИНТЫ (Playwright)
# =====================================

class ResolveUrlRequest(BaseModel):
    url: HttpUrl
    wait_seconds: int = Field(default=8, ge=1, le=30, description="Wait time in seconds (1-30)")
    click_texts: List[str] | None = None


class ResolveUrlResponse(BaseModel):
    start_url: str
    final_url: str
    redirects: List[str]
    ok: bool
    error: str | None = None


class ResolveUrlBatchRequest(BaseModel):
    merchant: str
    urls: List[HttpUrl] = Field(..., max_length=50, description="Max 50 URLs per batch")
    wait_seconds: int = Field(default=8, ge=1, le=30)
    click_texts: List[str] | None = None


class ResolveUrlBatchResponseItem(BaseModel):
    merchant: str
    start_url: str
    final_url: str | None
    redirects: List[str]
    ok: bool
    error: str | None = None


@app.post(
    "/resolve_url",
    response_model=ResolveUrlResponse,
    summary="Resolve Url Endpoint",
)
async def resolve_url_endpoint(req: ResolveUrlRequest):
    """
    Открывает страницу через Playwright,
    отслеживает редиректы и пытается нажать типовые кнопки.
    """
    try:
        final_url, redirects = await resolve_single_url(
            url=str(req.url),
            wait_seconds=req.wait_seconds,
            click_texts=req.click_texts,
        )
        return ResolveUrlResponse(
            start_url=str(req.url),
            final_url=final_url,
            redirects=redirects,
            ok=True,
            error=None,
        )
    except Exception as e:
        logger.error("resolve_url_failed", url=str(req.url)[:100], error=str(e))
        return ResolveUrlResponse(
            start_url=str(req.url),
            final_url=str(req.url),
            redirects=[str(req.url)],
            ok=False,
            error=str(e),
        )


@app.post(
    "/resolve_url_batch",
    response_model=List[ResolveUrlBatchResponseItem],
    summary="Resolve Url Batch Endpoint",
)
async def resolve_url_batch_endpoint(req: ResolveUrlBatchRequest):
    """
    Прогоняет список URL одного мерчанта через Playwright.
    """
    results = await resolve_urls_for_merchant(
        merchant=req.merchant,
        urls=[str(u) for u in req.urls],
        click_texts=req.click_texts,
        wait_seconds=req.wait_seconds,
    )
    return results


# =====================================
#  FULL INTERACTIVE: merchant -> Serper -> Playwright
# =====================================

class CollectInteractiveRequest(BaseModel):
    merchant: str
    keywords: List[str]
    country: str = "in"
    lang: str = "en"
    limit: int = Field(default=10, ge=1, le=100, description="Max 100 results")
    click_texts: List[str] | None = None
    wait_seconds: int = Field(default=8, ge=1, le=30)


@app.post(
    "/collect_mirrors_interactive",
    summary="Collect Mirrors Interactive",
)
async def collect_mirrors_interactive_endpoint(req: CollectInteractiveRequest):
    """
    Полный интерактивный сбор зеркал для одного мерчанта:
      1. Поиск доменов через Serper.dev
      2. Прогонка каждого URL через Playwright (клики, редиректы)
      3. Возвращаем финальный список зеркал
    """
    try:
        results = await collect_mirrors_interactive_for_merchant(
            merchant=req.merchant,
            keywords=req.keywords,
            country=req.country,
            lang=req.lang,
            limit=req.limit,
            click_texts=req.click_texts,
            wait_seconds=req.wait_seconds,
        )

        return {
            "ok": True,
            "merchant": req.merchant,
            "count": len(results),
            "items": results,
        }
    except SerperError as e:
        logger.error("collect_interactive_serper_error", merchant=req.merchant, error=str(e))
        raise HTTPException(status_code=503, detail=f"Serper API error: {str(e)}")
    except Exception as e:
        logger.error("collect_interactive_failed", merchant=req.merchant, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# =======================================
#  BATCH / ALL + SYNC endpoint для диагностики
# =======================================

class BatchItem(BaseModel):
    merchant: str
    keywords: List[str]
    country: str = "in"
    lang: str = "en"
    limit: int = Field(default=10, ge=1, le=100)
    brand_pattern: Optional[str] = None


class CollectBatchRequest(BaseModel):
    items: List[BatchItem] = Field(..., max_length=20, description="Max 20 items per batch")


class CollectAllRequest(BaseModel):
    merchants: Optional[List[str]] = None
    limit: int = Field(default=10, ge=1, le=100)


@app.get("/health", summary="Health Check")
async def health():
    """
    Health check с проверкой зависимостей.
    """
    from services.browser_pool import get_browser_pool
    from services.circuit_breaker import get_serper_circuit_breaker
    from db import engine
    
    status = {
        "status": "ok",
        "version": "0.9.0",
        "dependencies": {},
    }
    
    # Проверка БД
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status["dependencies"]["database"] = "ok"
    except Exception as e:
        status["dependencies"]["database"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    # Проверка browser pool
    try:
        browser_pool = get_browser_pool()
        if browser_pool._initialized:
            status["dependencies"]["browser_pool"] = {
                "status": "ok",
                "browsers_count": len(browser_pool._browsers),
                "max_browsers": browser_pool.max_browsers,
            }
        else:
            status["dependencies"]["browser_pool"] = "not_initialized"
    except Exception as e:
        status["dependencies"]["browser_pool"] = f"error: {str(e)}"
    
    # Проверка circuit breaker для Serper
    try:
        cb = get_serper_circuit_breaker()
        status["dependencies"]["serper_circuit_breaker"] = {
            "state": cb.state.value,
            "failure_count": cb.failure_count,
            "threshold": cb.failure_threshold,
        }
    except Exception as e:
        status["dependencies"]["serper_circuit_breaker"] = f"error: {str(e)}"
    
    return status


@app.get("/metrics", summary="Metrics Endpoint")
async def metrics_endpoint():
    """
    Эндпоинт для получения метрик приложения.
    """
    metrics = get_metrics_collector()
    stats = metrics.get_stats()
    return stats


@app.post("/metrics/reset", summary="Reset Metrics")
async def reset_metrics_endpoint():
    """
    Сброс метрик (для тестирования).
    """
    metrics = get_metrics_collector()
    metrics.reset()
    logger.info("metrics_reset")
    return {"status": "ok", "message": "Metrics reset"}


@app.post(
    "/collect_mirrors_all_async",
    summary="Collect Mirrors All Async",
)
async def collect_mirrors_all_async_endpoint(
    req: CollectAllRequest,
    background_tasks: BackgroundTasks,
):
    """
    Запускает сбор зеркал для всех мерчантов в фоне.
    """
    background_tasks.add_task(
        run_background_task,
        collect_mirrors_for_all(limit=req.limit)
    )
    logger.info("background_task_scheduled", task="collect_mirrors_for_all", limit=req.limit)
    return {"ok": True, "message": "Task scheduled"}


@app.post(
    "/collect_mirrors_batch",
    summary="Collect Mirrors Batch (async background)",
)
async def collect_mirrors_batch_endpoint(
    req: CollectBatchRequest,
    background_tasks: BackgroundTasks,
):
    """
    Запускает сбор зеркал для батча мерчантов в фоне.
    """
    max_limit = max((item.limit for item in req.items), default=10)
    
    background_tasks.add_task(
        run_background_task,
        collect_mirrors_for_batch(
            items=req.items,
            limit=max_limit,
            follow_redirects=True,
        ),
    )
    logger.info("background_task_scheduled", task="collect_mirrors_for_batch", items_count=len(req.items))
    return {"ok": True, "message": "Task scheduled"}


@app.post(
    "/collect_mirrors_batch_sync",
    summary="Collect Mirrors Batch (wait for result)",
)
async def collect_mirrors_batch_sync_endpoint(req: CollectBatchRequest):
    """
    Синхронный сбор зеркал для батча мерчантов.
    Ждет завершения и возвращает результат.
    """
    max_limit = max((item.limit for item in req.items), default=10)
    result = await collect_mirrors_for_batch(
        items=req.items,
        limit=max_limit,
        follow_redirects=True,
    )
    return result


# =======================================
#  /mirrors: фильтры + сортировка по свежести
# =======================================

@app.get(
    "/mirrors",
    summary="List Mirrors",
)
def list_mirrors(
    limit: int = Query(default=100, ge=1, le=1000, description="Max 1000 results"),
    offset: int = Query(default=0, ge=0),
    country: Optional[str] = Query(default=None),
    merchant: Optional[str] = Query(default=None),
    db=Depends(get_db),
):
    """
    Примеры:
      /mirrors?limit=100
      /mirrors?country=in&limit=100
      /mirrors?country=ar&merchant=stake&limit=100
      /mirrors?country=ar&limit=100&offset=100
    """
    query = db.query(Mirror)

    if country:
        query = query.filter(Mirror.country == country)

    if merchant:
        query = query.filter(Mirror.merchant == merchant)

    mirrors = (
        query.order_by(Mirror.last_seen_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return mirrors


# =======================================
#  GOOGLE SHEETS EXPORT
# =======================================

class ExportToSheetsRequest(BaseModel):
    spreadsheet_url: str = Field(..., description="Google Sheets URL")
    range_name: str = Field(default="Sheet1!A2:Z", description="Range to write (e.g., Sheet1!A2:Z)")
    clear_first: bool = Field(default=False, description="Clear range before writing")
    country: Optional[str] = None
    merchant: Optional[str] = None
    limit: int = Field(default=1000, ge=1, le=10000)
    access_token: Optional[str] = Field(default=None, description="Google OAuth2 access token (optional if set in .env)")


@app.post(
    "/export_to_sheets",
    summary="Export Mirrors to Google Sheets",
)
async def export_to_sheets_endpoint(
    req: ExportToSheetsRequest,
    db=Depends(get_db),
):
    """
    Экспортирует зеркала из БД в Google Sheets.
    Поддерживает фильтры по country и merchant.
    """
    from services.google_sheets import export_mirrors_to_sheets, extract_spreadsheet_id
    
    try:
        # Получаем зеркала из БД
        query = db.query(Mirror)

        if req.country:
            query = query.filter(Mirror.country == req.country)

        if req.merchant:
            query = query.filter(Mirror.merchant == req.merchant)

        mirrors = (
            query.order_by(Mirror.last_seen_at.desc())
            .limit(req.limit)
            .all()
        )

        if not mirrors:
            return {
                "ok": False,
                "message": "No mirrors found",
                "rows_exported": 0,
            }

        # Экспортируем в Google Sheets
        spreadsheet_id = extract_spreadsheet_id(req.spreadsheet_url)
        result = await export_mirrors_to_sheets(
            mirrors=mirrors,
            spreadsheet_id=spreadsheet_id,
            range_name=req.range_name,
            clear_first=req.clear_first,
            access_token=req.access_token,
        )

        return {
            "ok": True,
            "message": "Export successful",
            "spreadsheet_id": spreadsheet_id,
            "rows_exported": len(mirrors),
            "updated_cells": result.get("updatedCells", 0),
            "updated_rows": result.get("updatedRows", 0),
        }

    except ValueError as e:
        logger.error("export_sheets_validation_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("export_sheets_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")


# =======================================
#  N8N INTEGRATION: Collect + Export
# =======================================

class N8NCollectAndExportRequest(BaseModel):
    """
    Запрос для n8n: собирает зеркала и сразу экспортирует в Google Sheets.
    """
    # Параметры сбора
    items: List[BatchItem] = Field(..., description="Merchants to collect")
    limit: int = Field(default=10, ge=1, le=100)
    follow_redirects: bool = Field(default=True)
    
    # Параметры экспорта
    spreadsheet_url: str = Field(..., description="Google Sheets URL")
    range_name: str = Field(default="Sheet1!A2:Z")
    clear_first: bool = Field(default=False)
    access_token: Optional[str] = Field(default=None)


@app.post(
    "/n8n_collect_and_export",
    summary="N8N Integration: Collect Mirrors and Export to Google Sheets",
)
async def n8n_collect_and_export_endpoint(
    req: N8NCollectAndExportRequest,
    background_tasks: BackgroundTasks,
):
    """
    Эндпоинт для n8n workflow:
    1. Собирает зеркала для указанных merchants
    2. Экспортирует результаты в Google Sheets
    
    Можно запустить синхронно или в фоне.
    """
    from services.google_sheets import extract_spreadsheet_id
    
    try:
        # Собираем зеркала
        max_limit = max((item.limit for item in req.items), default=req.limit)
        
        result = await collect_mirrors_for_batch(
            items=req.items,
            limit=max_limit,
            follow_redirects=req.follow_redirects,
        )

        # Экспортируем в Google Sheets в фоне
        async def export_task():
            from db import SessionLocal
            from services.google_sheets import export_mirrors_to_sheets
            
            db = SessionLocal()
            try:
                # Получаем свежесобранные зеркала
                query = db.query(Mirror)
                
                # Фильтруем по merchants из запроса
                merchants = [item.merchant for item in req.items]
                query = query.filter(Mirror.merchant.in_(merchants))
                
                mirrors = (
                    query.order_by(Mirror.last_seen_at.desc())
                    .limit(1000)
                    .all()
                )
                
                spreadsheet_id = extract_spreadsheet_id(req.spreadsheet_url)
                export_result = await export_mirrors_to_sheets(
                    mirrors=mirrors,
                    spreadsheet_id=spreadsheet_id,
                    range_name=req.range_name,
                    clear_first=req.clear_first,
                    access_token=req.access_token,
                )
                
                logger.info(
                    "n8n_export_completed",
                    rows_exported=len(mirrors),
                    spreadsheet_id=spreadsheet_id[:20],
                )
            finally:
                db.close()

        background_tasks.add_task(run_background_task, export_task())

        return {
            "ok": True,
            "message": "Collection started, export scheduled",
            "collection_result": result,
            "spreadsheet_id": extract_spreadsheet_id(req.spreadsheet_url),
        }

    except Exception as e:
        logger.error("n8n_collect_export_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post(
    "/n8n_collect_and_export_sync",
    summary="N8N Integration: Collect and Export (Synchronous)",
)
async def n8n_collect_and_export_sync_endpoint(
    req: N8NCollectAndExportRequest,
    db=Depends(get_db),
):
    """
    Синхронная версия: собирает и экспортирует, ждет завершения.
    """
    from services.google_sheets import export_mirrors_to_sheets, extract_spreadsheet_id
    
    try:
        # Собираем зеркала
        max_limit = max((item.limit for item in req.items), default=req.limit)
        
        collection_result = await collect_mirrors_for_batch(
            items=req.items,
            limit=max_limit,
            follow_redirects=req.follow_redirects,
        )

        # Получаем собранные зеркала
        merchants = [item.merchant for item in req.items]
        query = db.query(Mirror).filter(Mirror.merchant.in_(merchants))
        
        mirrors = (
            query.order_by(Mirror.last_seen_at.desc())
            .limit(1000)
            .all()
        )

        # Экспортируем
        spreadsheet_id = extract_spreadsheet_id(req.spreadsheet_url)
        export_result = await export_mirrors_to_sheets(
            mirrors=mirrors,
            spreadsheet_id=spreadsheet_id,
            range_name=req.range_name,
            clear_first=req.clear_first,
            access_token=req.access_token,
        )

        return {
            "ok": True,
            "message": "Collection and export completed",
            "collection": collection_result,
            "export": {
                "spreadsheet_id": spreadsheet_id,
                "rows_exported": len(mirrors),
                "updated_cells": export_result.get("updatedCells", 0),
                "updated_rows": export_result.get("updatedRows", 0),
            },
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("n8n_sync_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# =======================================
#  PAYMENT PARSER FOR ARGENTINA
# =======================================

class ParsePaymentDataRequest(BaseModel):
    """
    Запрос для парсинга платежных данных с 1win.lat для Аргентины.
    """
    email: str = Field(..., description="Email для входа на сайт")
    password: str = Field(..., description="Пароль для входа на сайт")
    base_url: str = Field(default="https://1win.lat/", description="Базовый URL сайта")
    spreadsheet_url: str = Field(..., description="URL Google Sheets для экспорта данных")
    sheet_name: Optional[str] = Field(default=None, description="Имя вкладки (если не указано, будет получено по gid)")
    clear_first: bool = Field(default=False, description="Очистить данные перед записью")
    access_token: Optional[str] = Field(default=None, description="Google OAuth2 access token")
    wait_seconds: int = Field(default=15, ge=5, le=60, description="Время ожидания для загрузки страниц")
    use_persistent_context: bool = Field(default=True, description="Использовать persistent context для сохранения cookies/session (позволяет сохранить авторизацию)")
    skip_login: bool = Field(default=False, description="Пропустить логин (если уже авторизован через persistent context)")


@app.post(
    "/parse_payment_data_ar",
    summary="Parse Payment Data for Argentina (1win.lat)",
)
async def parse_payment_data_ar_endpoint(req: ParsePaymentDataRequest):
    """
    Парсит платежные данные с сайта 1win.lat для Аргентины.
    
    Процесс:
    1. Логинится на сайт с указанными учетными данными
    2. Переходит на страницу депозита
    3. Выбирает метод оплаты Claro Pay (Fiat)
    4. Извлекает данные платежной формы (CVU, Recipient, Bank, Amount)
    5. Экспортирует данные в Google Sheets
    
    Возвращает результат парсинга и информацию об экспорте.
    """
    from services.payment_parser_ar import parse_payment_data_1win
    from services.google_sheets import export_payment_data_to_sheets, extract_gid_from_url
    
    try:
        # Парсим платежные данные
        logger.info("payment_parser_starting", email=req.email, base_url=req.base_url)
        payment_data = await parse_payment_data_1win(
            email=req.email,
            password=req.password,
            base_url=req.base_url,
            wait_seconds=req.wait_seconds,
            use_persistent_context=req.use_persistent_context,
            skip_login=req.skip_login,
        )
        
        if not payment_data.get("success"):
            logger.warning(
                "payment_parser_failed",
                error=payment_data.get("error"),
                cvu_found=payment_data.get("cvu") is not None,
            )
            return {
                "ok": False,
                "message": "Payment data parsing failed",
                "payment_data": payment_data,
                "export": None,
            }
        
        # Экспортируем в Google Sheets (опционально - если есть токен)
        export_result = None
        if req.spreadsheet_url and (req.access_token or os.getenv("GOOGLE_SHEETS_ACCESS_TOKEN")):
            try:
                logger.info("payment_parser_exporting_to_sheets", spreadsheet_url=req.spreadsheet_url[:50])
                
                # Извлекаем gid из URL если есть
                gid = extract_gid_from_url(req.spreadsheet_url)
                
                export_result = await export_payment_data_to_sheets(
                    payment_data=payment_data,
                    spreadsheet_id_or_url=req.spreadsheet_url,
                    sheet_name=req.sheet_name,
                    clear_first=req.clear_first,
                    access_token=req.access_token,
                    gid=gid,
                )
                
                logger.info(
                    "payment_parser_export_completed",
                    rows_added=export_result.get("updates", {}).get("updatedRows", 0),
                )
            except ValueError as e:
                logger.warning("payment_parser_export_skipped", error=str(e))
                export_result = {"error": str(e)}
            except Exception as e:
                logger.warning("payment_parser_export_failed", error=str(e))
                export_result = {"error": str(e)}
        else:
            logger.info("payment_parser_export_skipped_no_token", 
                       has_url=bool(req.spreadsheet_url),
                       has_token=bool(req.access_token or os.getenv("GOOGLE_SHEETS_ACCESS_TOKEN")))
        
        logger.info(
            "payment_parser_completed",
            success=True,
            domain=payment_data.get("domain"),
            method=payment_data.get("method"),
            url=payment_data.get("url"),
            export_success=export_result is not None and "error" not in export_result if export_result else False,
        )
        
        return {
            "ok": True,
            "message": "Payment data parsed successfully" + (" and exported" if export_result and "error" not in export_result else ""),
            "payment_data": {
                "domain": payment_data.get("domain"),
                "method": payment_data.get("method"),
                "payment_type": payment_data.get("payment_type"),
                "bank": payment_data.get("bank"),
                "cvu": payment_data.get("cvu"),
                "recipient": payment_data.get("recipient"),
                "amount": payment_data.get("amount"),
                "url": payment_data.get("url"),
                "provider_screenshot": payment_data.get("provider_screenshot"),
                "provider_screenshot_path": payment_data.get("provider_screenshot_path"),
                "screenshot": payment_data.get("screenshot"),
                "screenshot_path": payment_data.get("screenshot_path"),
                "success": payment_data.get("success"),
            },
            "export": {
                "spreadsheet_id": export_result.get("spreadsheetId", "") if export_result and "error" not in export_result else None,
                "updated_range": export_result.get("updates", {}).get("updatedRange", "") if export_result and "error" not in export_result else None,
                "updated_rows": export_result.get("updates", {}).get("updatedRows", 0) if export_result and "error" not in export_result else 0,
                "error": export_result.get("error") if export_result and "error" in export_result else None,
            } if export_result else None,
        }
        
    except ValueError as e:
        logger.error("payment_parser_validation_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("payment_parser_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Payment parser error: {str(e)}")
