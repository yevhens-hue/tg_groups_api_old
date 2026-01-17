# Инструкция по деплою в продакшен

## Быстрый старт

### 1. Подготовка окружения

```bash
# Клонировать репозиторий
git clone <repository_url>
cd mirrors_api

# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install --upgrade pip
pip install -r requirements.txt

# Установить Playwright браузеры
playwright install chromium
```

### 2. Настройка переменных окружения

```bash
# Создать .env файл из примера
cp .env.example .env

# Отредактировать .env
nano .env
```

Обязательные переменные:
- `SERPER_API_KEY` - ключ API Serper.dev
- `DATABASE_URL` - URL базы данных (по умолчанию SQLite)

### 3. Запуск приложения

#### Вариант A: Простой запуск (для тестирования)

```bash
chmod +x start_production.sh
./start_production.sh
```

#### Вариант B: С Gunicorn (рекомендуется для продакшена)

```bash
# Установить gunicorn
pip install gunicorn

# Запустить
chmod +x start_production_gunicorn.sh
./start_production_gunicorn.sh
```

#### Вариант C: Прямой запуск uvicorn

```bash
source .venv/bin/activate
uvicorn app:app \
    --host 0.0.0.0 \
    --port 8011 \
    --workers 4 \
    --log-level info \
    --proxy-headers
```

#### Вариант D: С Gunicorn напрямую

```bash
source .venv/bin/activate
pip install gunicorn
gunicorn app:app \
    --bind 0.0.0.0:8011 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --log-level info \
    --timeout 120 \
    --preload
```

## Systemd Service (Linux)

### 1. Установить service файл

```bash
# Скопировать service файл
sudo cp mirrors-api.service /etc/systemd/system/

# Отредактировать пути в файле (если нужно)
sudo nano /etc/systemd/system/mirrors-api.service

# Обновить systemd
sudo systemctl daemon-reload
```

### 2. Управление сервисом

```bash
# Запустить
sudo systemctl start mirrors-api

# Остановить
sudo systemctl stop mirrors-api

# Перезапустить
sudo systemctl restart mirrors-api

# Включить автозапуск
sudo systemctl enable mirrors-api

# Проверить статус
sudo systemctl status mirrors-api

# Посмотреть логи
sudo journalctl -u mirrors-api -f
```

## Nginx Reverse Proxy (рекомендуется)

### Конфигурация Nginx

```nginx
upstream mirrors_api {
    server 127.0.0.1:8011;
    keepalive 32;
}

server {
    listen 80;
    server_name api.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/mirrors_api_access.log;
    error_log /var/log/nginx/mirrors_api_error.log;

    # Client settings
    client_max_body_size 10M;
    client_body_timeout 60s;

    location / {
        proxy_pass http://mirrors_api;
        proxy_http_version 1.1;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Health check endpoint (можно сделать без авторизации)
    location /health {
        proxy_pass http://mirrors_api/health;
        access_log off;
    }
}
```

## Docker (опционально)

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Установка Playwright
RUN pip install --no-cache-dir playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose порт
EXPOSE 8011

# Запуск
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8011", "--workers", "4"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  mirrors_api:
    build: .
    ports:
      - "8011:8011"
    environment:
      - SERPER_API_KEY=${SERPER_API_KEY}
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - ./mirrors.db:/app/mirrors.db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8011/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Мониторинг

### Health Check

```bash
curl http://localhost:8011/health
```

### Метрики

```bash
curl http://localhost:8011/metrics
```

### Логи

Логи в JSON формате выводятся в stdout/stderr. Для продакшена рекомендуется:
- Настроить централизованное логирование (ELK, Loki, CloudWatch)
- Использовать log rotation
- Настроить алерты на ошибки

## Рекомендации по производительности

### Количество workers

Формула: `(2 × CPU cores) + 1`

Примеры:
- 2 CPU cores → 5 workers
- 4 CPU cores → 9 workers
- 8 CPU cores → 17 workers

### Настройки для высоких нагрузок

```bash
# Увеличить лимиты системы
ulimit -n 65536

# Запуск с большим количеством workers
uvicorn app:app \
    --host 0.0.0.0 \
    --port 8011 \
    --workers 8 \
    --log-level warning \
    --limit-concurrency 1000 \
    --timeout-keep-alive 5
```

## Безопасность

### Перед деплоем:

1. ✅ Изменить CORS настройки в `app.py`:
   ```python
   allow_origins=["https://yourdomain.com"]  # вместо ["*"]
   ```

2. ✅ Настроить rate limiting под вашу нагрузку

3. ✅ Использовать HTTPS (через Nginx/Cloudflare)

4. ✅ Ограничить доступ к `/metrics` endpoint

5. ✅ Использовать firewall для ограничения доступа

6. ✅ Регулярно обновлять зависимости

## Troubleshooting

### Приложение не запускается

```bash
# Проверить логи
journalctl -u mirrors-api -n 50

# Проверить переменные окружения
systemctl show mirrors-api --property=Environment

# Проверить порт
netstat -tulpn | grep 8011
```

### Высокое потребление памяти

- Уменьшить количество workers
- Уменьшить размер browser pool
- Использовать PostgreSQL вместо SQLite

### Медленные запросы

- Проверить метрики: `curl /metrics`
- Проверить circuit breaker статус в `/health`
- Увеличить timeout настройки


