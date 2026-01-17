# Troubleshooting Guide

## Проблема: Сервер останавливается через некоторое время

### Возможные причины:

1. **Таймаут бездействия в облачной платформе**
   - Многие облачные платформы останавливают инстансы после периода бездействия
   - **Решение**: Настроить keep-alive или health checks

2. **Автоматический перезапуск**
   - Платформа может перезапускать контейнеры/инстансы
   - **Решение**: Проверить настройки платформы

3. **Нехватка ресурсов**
   - OOM (Out of Memory) убивает процесс
   - **Решение**: Увеличить лимиты памяти или уменьшить workers

4. **Graceful shutdown по сигналу**
   - Платформа отправляет SIGTERM для перезапуска
   - **Решение**: Это нормальное поведение, сервер корректно завершается

### Решения:

#### 1. Настроить keep-alive для предотвращения таймаутов

Добавьте в `.env`:
```bash
# Увеличить таймауты
TIMEOUT_KEEP_ALIVE=300
TIMEOUT_GRACEFUL_SHUTDOWN=60
```

#### 2. Использовать health checks

Настройте платформу на периодические запросы к `/health`:
```bash
# Каждые 30 секунд
curl http://localhost:8011/health
```

#### 3. Уменьшить потребление памяти

Если проблема в памяти, уменьшите workers:
```bash
WORKERS=2 ./start_production.sh
```

#### 4. Использовать Gunicorn с max-requests

Gunicorn автоматически перезапускает workers после N запросов:
```bash
./start_production_gunicorn.sh
```

#### 5. Настроить systemd для автоперезапуска

Если используете systemd, он автоматически перезапустит сервис:
```bash
sudo systemctl enable mirrors-api
sudo systemctl start mirrors-api
```

### Мониторинг

Проверьте логи для понимания причины shutdown:
```bash
# Если используете nohup
tail -f server.log

# Если используете systemd
sudo journalctl -u mirrors-api -f

# Проверьте метрики
curl http://localhost:8011/metrics
```

### Проверка ресурсов

```bash
# Память
free -h

# CPU
top

# Процессы
ps aux | grep uvicorn
```

## Проблема: "Address already in use"

См. `START_SERVER.md` - используйте `./stop_server.sh`

## Проблема: "Module not found"

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Проблема: Сервер не отвечает

1. Проверьте логи
2. Проверьте `.env` файл
3. Проверьте `SERPER_API_KEY`
4. Проверьте порт: `lsof -i :8011`


