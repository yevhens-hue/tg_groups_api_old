# Production Deployment Guide

## Быстрый старт

### 1. Установка зависимостей
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Настройка конфигурации
```bash
cp .env.example .env
nano .env  # Укажите SERPER_API_KEY
```

### 3. Запуск
```bash
./start_production.sh
```

## Конфигурация для разных окружений

### Development
```bash
ENVIRONMENT=development
KEEPALIVE_ENABLED=false
LOG_LEVEL=debug
```

### Production
```bash
ENVIRONMENT=production
KEEPALIVE_ENABLED=true
KEEPALIVE_INTERVAL=60
LOG_LEVEL=info
```

## Keep-Alive для предотвращения таймаутов

Если сервер останавливается из-за таймаутов бездействия:

```bash
# В .env
KEEPALIVE_ENABLED=true
KEEPALIVE_INTERVAL=60  # Проверка каждые 60 секунд
KEEPALIVE_URL=http://localhost:8011/health
```

## Мониторинг

### Health Check
```bash
curl http://localhost:8011/health
```

### Метрики
```bash
curl http://localhost:8011/metrics | jq
```

### Логи
```bash
# Если запущен с nohup
tail -f server.log

# Если через systemd
sudo journalctl -u mirrors-api -f
```

## Версия

**Текущая версия: 0.9.0**

Все улучшения реализованы и готовы к продакшену.


