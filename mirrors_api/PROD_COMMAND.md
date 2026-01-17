# Команда для продакшена

## ✅ Тестирование пройдено

Все компоненты проверены и готовы к работе.

## 🚀 Команда запуска в продакшене

### Вариант 1: Простой запуск (рекомендуется)
```bash
./start_prod.sh
```

### Вариант 2: С Gunicorn (для высоких нагрузок)
```bash
./start_production_gunicorn.sh
```

### Вариант 3: Прямая команда uvicorn
```bash
source .venv/bin/activate
uvicorn app:app \
    --host 0.0.0.0 \
    --port 8011 \
    --workers 4 \
    --log-level info \
    --no-access-log \
    --proxy-headers \
    --forwarded-allow-ips "*" \
    --timeout-keep-alive 300 \
    --timeout-graceful-shutdown 60
```

### Вариант 4: С Gunicorn (прямая команда)
```bash
source .venv/bin/activate
gunicorn app:app \
    --bind 0.0.0.0:8011 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --log-level info \
    --timeout 120 \
    --keep-alive 30 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --preload
```

## 📋 Перед запуском

1. **Проверьте .env файл:**
   ```bash
   cat .env | grep SERPER_API_KEY
   ```

2. **Убедитесь что порт свободен:**
   ```bash
   ./stop_server.sh
   ```

3. **Для production включите keep-alive:**
   ```bash
   # В .env добавьте:
   ENVIRONMENT=production
   KEEPALIVE_ENABLED=true
   KEEPALIVE_INTERVAL=60
   ```

## 🔍 Проверка работы

После запуска проверьте:

```bash
# Health check
curl http://localhost:8011/health

# Метрики
curl http://localhost:8011/metrics

# Документация API
open http://localhost:8011/docs
```

## 🛑 Остановка

```bash
./stop_server.sh
```

## 📊 Мониторинг

```bash
# Логи (если запущен с nohup)
tail -f server.log

# Процессы
ps aux | grep uvicorn

# Порт
lsof -i :8011
```

## ⚙️ Настройки для продакшена

Рекомендуемые настройки в `.env`:

```bash
# Окружение
ENVIRONMENT=production

# Keep-alive (предотвращает таймауты)
KEEPALIVE_ENABLED=true
KEEPALIVE_INTERVAL=60

# Сервер
HOST=0.0.0.0
PORT=8011
WORKERS=4  # (2 × CPU cores) + 1
LOG_LEVEL=info

# API ключ (обязательно)
SERPER_API_KEY=your_key_here
```

## 🎯 Готово к продакшену!

Версия: **0.9.0**
Все улучшения: **22/22** ✅


