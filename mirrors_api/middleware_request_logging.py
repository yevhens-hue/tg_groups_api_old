# middleware_request_logging.py
import time
from typing import Callable
import json

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware для детального логирования запросов и ответов.
    Полезно для отладки и мониторинга.
    """

    def __init__(self, app, log_request_body: bool = False, log_response_body: bool = False):
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        request_id = getattr(request.state, "request_id", None)

        # Логируем входящий запрос
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "request_id": request_id,
        }

        # Логируем тело запроса если нужно (только для POST/PUT/PATCH)
        if self.log_request_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    try:
                        log_data["request_body"] = json.loads(body.decode())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        log_data["request_body"] = body.decode("utf-8", errors="replace")[:500]
            except Exception as e:
                log_data["request_body_error"] = str(e)

        logger.info("request_received", **log_data)

        # Выполняем запрос
        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Логируем ответ
            response_log = {
                "status_code": response.status_code,
                "process_time": round(process_time, 3),
                "request_id": request_id,
            }

            # Логируем тело ответа если нужно
            if self.log_response_body:
                try:
                    # Читаем тело ответа
                    response_body = b""
                    async for chunk in response.body_iterator:
                        response_body += chunk

                    # Парсим если JSON
                    try:
                        response_log["response_body"] = json.loads(response_body.decode())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        response_log["response_body"] = response_body.decode("utf-8", errors="replace")[:500]

                    # Создаем новый response с телом
                    from starlette.responses import Response as StarletteResponse
                    response = StarletteResponse(
                        content=response_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                    )
                except Exception as e:
                    response_log["response_body_error"] = str(e)

            # Логируем в зависимости от статуса
            if response.status_code >= 500:
                logger.error("request_completed_error", **response_log)
            elif response.status_code >= 400:
                logger.warning("request_completed_client_error", **response_log)
            else:
                logger.info("request_completed_success", **response_log)

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "request_exception",
                error=str(e),
                process_time=round(process_time, 3),
                request_id=request_id,
                exc_info=True,
            )
            raise


