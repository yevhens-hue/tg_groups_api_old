# middleware.py
import uuid
import time
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware для генерации и передачи request_id через весь запрос.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Генерируем или получаем request_id из заголовка
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Устанавливаем в state для доступа в эндпоинтах
        request.state.request_id = request_id
        
        # Настраиваем logger с request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Добавляем request_id в заголовок ответа
            response.headers["X-Request-ID"] = request_id
            
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                process_time=round(process_time, 3),
            )
            
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                process_time=round(process_time, 3),
                exc_info=True,
            )
            # Пробрасываем исключение дальше для обработки exception handlers
            raise

