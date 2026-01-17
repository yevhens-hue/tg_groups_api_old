# exception_handlers.py
from typing import Union

import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger()


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации Pydantic."""
    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "details": exc.errors(),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


async def http_exception_handler(request: Request, exc: Union[StarletteHTTPException, Exception]):
    """Обработчик HTTP исключений."""
    if isinstance(exc, StarletteHTTPException):
        status_code = exc.status_code
        detail = exc.detail
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = str(exc)

    logger.error(
        "http_exception",
        path=request.url.path,
        status_code=status_code,
        detail=detail,
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "error": detail,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик всех необработанных исключений."""
    request_id = getattr(request.state, "request_id", None)
    
    # Собираем контекст ошибки
    error_context = {
        "path": request.url.path,
        "method": request.method,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "request_id": request_id,
        "client_ip": request.client.host if request.client else None,
    }
    
    logger.error(
        "unhandled_exception",
        **error_context,
        exc_info=True,
    )

    # В production не показываем детали ошибки
    from config import get_settings
    settings = get_settings()
    
    error_detail = "Internal server error"
    if settings.ENVIRONMENT == "development":
        error_detail = f"{type(exc).__name__}: {str(exc)}"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": error_detail,
            "request_id": request_id,
        },
    )

