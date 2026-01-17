# middleware_metrics.py
import time
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from metrics import get_metrics_collector

logger = structlog.get_logger()


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware для сбора метрик запросов.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        endpoint = f"{request.method} {request.url.path}"
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        
        # Записываем метрику
        metrics = get_metrics_collector()
        metrics.record_request(endpoint, response.status_code, duration)
        
        # Добавляем заголовок времени обработки
        response.headers["X-Process-Time"] = f"{duration:.3f}"
        
        return response


