# Changelog

## [0.8.0] - Production Improvements Phase 2

### Added
- ✅ Глобальные exception handlers для единообразной обработки ошибок
- ✅ CORS middleware для кросс-доменных запросов
- ✅ Rate limiting (100 req/min по умолчанию, настраиваемо)
- ✅ Метрики и мониторинг (`/metrics` endpoint)
- ✅ Улучшенный graceful shutdown
- ✅ Timeout утилита для долгих операций
- ✅ Детальная информация в health check

### Changed
- Версия обновлена до 0.8.0
- Health check теперь возвращает детальную информацию о browser pool
- Улучшена обработка ошибок при shutdown

### Files Added
- `exception_handlers.py` - глобальные обработчики исключений
- `rate_limiter.py` - rate limiting middleware
- `metrics.py` - коллектор метрик
- `middleware_metrics.py` - middleware для сбора метрик
- `services/timeout.py` - утилита для таймаутов

## [0.7.0] - Production Improvements Phase 1

### Added
- ✅ Исправлен `run_async()` в BackgroundTasks
- ✅ Connection pooling для SQLite
- ✅ Browser pool для Playwright
- ✅ Structured logging + request-id
- ✅ Retry + Circuit Breaker для Serper
- ✅ Валидация входных параметров
- ✅ Кэширование результатов Serper
- ✅ Лимит на фоновые задачи
- ✅ Улучшен health check
- ✅ Унифицирована обработка ошибок Serper

### Files Added
- `middleware.py` - request-id middleware
- `logging_config.py` - настройка structured logging
- `services/browser_pool.py` - пул браузеров
- `services/cache.py` - TTL кэш
- `services/circuit_breaker.py` - circuit breaker

### Dependencies Added
- `tenacity==9.0.0` - retry логика
- `pybreaker==1.0.1` - circuit breaker
- `structlog==24.1.0` - structured logging

## [0.6.0] - Initial Production Version

### Features
- FastAPI приложение
- Интерактивные эндпоинты с Playwright
- Сбор зеркал через Serper.dev
- SQLite база данных
- Background tasks для асинхронной обработки


