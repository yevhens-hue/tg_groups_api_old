# Быстрый старт для продакшена

## Команды запуска

### 1. Простой запуск (для тестирования)

```bash
./start_production.sh
```

### 2. С Gunicorn (рекомендуется)

```bash
./start_production_gunicorn.sh
```

### 3. Прямой запуск uvicorn

```bash
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8011 --workers 4 --log-level info --proxy-headers
```

### 4. Прямой запуск gunicorn

```bash
source .venv/bin/activate
gunicorn app:app \
    --bind 0.0.0.0:8011 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --log-level info \
    --timeout 120 \
    --preload
```

## Systemd (Linux)

```bash
# Установить service
sudo cp mirrors-api.service /etc/systemd/system/
sudo systemctl daemon-reload

# Управление
sudo systemctl start mirrors-api      # Запустить
sudo systemctl stop mirrors-api       # Остановить
sudo systemctl restart mirrors-api    # Перезапустить
sudo systemctl enable mirrors-api     # Автозапуск
sudo systemctl status mirrors-api     # Статус
sudo journalctl -u mirrors-api -f     # Логи
```

## Переменные окружения

Создайте `.env` файл:

```bash
cp .env.example .env
nano .env
```

Обязательно укажите:
- `SERPER_API_KEY` - ваш API ключ Serper.dev

Опционально:
- `DATABASE_URL` - URL базы данных (по умолчанию SQLite)
- `HOST` - хост (по умолчанию 0.0.0.0)
- `PORT` - порт (по умолчанию 8011)
- `WORKERS` - количество workers (по умолчанию 4)
- `LOG_LEVEL` - уровень логирования (по умолчанию info)

## Проверка работы

```bash
# Health check
curl http://localhost:8011/health

# Метрики
curl http://localhost:8011/metrics
```

## Рекомендации

- **Workers**: `(2 × CPU cores) + 1`
- **Для высоких нагрузок**: используйте Gunicorn
- **Для продакшена**: настройте Nginx как reverse proxy
- **Мониторинг**: используйте `/health` и `/metrics` endpoints

Подробнее: см. `DEPLOYMENT.md`


