# 🚀 Установка и запуск на новом компьютере

Полная инструкция по установке и запуску проекта на новом компьютере.

## 📋 Требования

- Python 3.8+ (проверьте: `python3 --version`)
- Git (проверьте: `git --version`)
- Telegram API credentials (TG_API_ID, TG_API_HASH)

## 🔧 Шаг 1: Клонирование репозитория

```bash
# Клонируйте репозиторий
git clone https://github.com/yevhens-hue/tg_groups_api_old.git
cd tg_groups_api_old
```

## 🔧 Шаг 2: Создание виртуального окружения

```bash
# Создайте виртуальное окружение
python3 -m venv .venv

# Активируйте его
# На Linux/Mac:
source .venv/bin/activate

# На Windows:
.venv\Scripts\activate
```

## 🔧 Шаг 3: Установка зависимостей

```bash
# Установите все зависимости
pip install -r requirements.txt
```

## 🔐 Шаг 4: Настройка секретных файлов

### Вариант A: Использовать .env файл (рекомендуется)

Создайте файл `.env` в корне проекта:

```bash
nano .env
```

Добавьте следующие переменные:

```env
# Обязательные
TG_API_ID=ваш_api_id
TG_API_HASH=ваш_api_hash

# Telegram сессия (один из вариантов)
TG_SESSION_STRING=ваша_сессия_строка

# Или используйте файл сессии (альтернатива)
# TG_SESSION_NAME=tg_groups_session

# Опционально: Redis для масштабирования
REDIS_URL=redis://localhost:6379/0

# Опционально: Настройки rate limiting
HTTP_RATE_LIMIT_RPM=60
RATE_LIMITER_MAX_ITEMS=10000

# Опционально: Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SEC=60

# Опционально: Кэширование
CACHE_SEARCH_TTL_SEC=600
CACHE_ADMINS_TTL_SEC=1800

# Опционально: Таймауты
TG_RPC_TIMEOUT_SEC=25
TG_RPC_MAX_RETRIES=2
HTTP_TIMEOUT_SEC=30

# Опционально: Логирование
LOG_LEVEL=INFO
```

### Вариант B: Создать Telegram сессию

Если у вас нет `TG_SESSION_STRING`, создайте сессию:

```bash
# Запустите скрипт для создания сессии
python login.py
```

Это создаст файл `tg_groups_session.session` и выведет строку сессии.

**Важно:** Сохраните строку сессии в `.env` как `TG_SESSION_STRING`.

## 🚀 Шаг 5: Запуск сервиса

### Локальный запуск

```bash
# Убедитесь что виртуальное окружение активировано
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows

# Запустите сервис
./start.sh

# Или напрямую:
uvicorn app:app --host 0.0.0.0 --port 8010
```

Сервис будет доступен по адресу: `http://localhost:8010`

### Проверка работоспособности

```bash
# Проверьте health endpoint
curl http://localhost:8010/health

# Должен вернуть:
# {
#   "ok": true,
#   "telegram": "ok",
#   "me_id": ...,
#   "redis": "ok" или "not_configured"
# }
```

## 📡 Шаг 6: Тестирование API

### Поиск групп

```bash
curl -X POST http://localhost:8010/search_groups \
  -H "Content-Type: application/json" \
  -d '{
    "query": "python",
    "limit": 10,
    "types_only": "channel,megagroup,group",
    "min_members": 0,
    "include_admins": true
  }'
```

### Получение админов группы

```bash
curl -X POST http://localhost:8010/get_group_admins \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": -1001234567890,
    "limit": 100
  }'
```

## 🔧 Дополнительная настройка

### Redis (опционально, для масштабирования)

Если хотите использовать Redis для распределенного rate limiting:

```bash
# Установите Redis (пример для Ubuntu/Debian)
sudo apt-get update
sudo apt-get install redis-server

# Запустите Redis
redis-server

# Добавьте в .env:
REDIS_URL=redis://localhost:6379/0
```

### Prometheus метрики

Метрики доступны по адресу: `http://localhost:8010/metrics`

## ❓ Решение проблем

### Ошибка "TG_API_ID / TG_API_HASH отсутствуют"

**Решение:** Проверьте файл `.env` и убедитесь что переменные установлены:
```bash
cat .env | grep TG_API
```

### Ошибка "Session not found"

**Решение:** Создайте сессию:
```bash
python login.py
```

Или установите `TG_SESSION_STRING` в `.env`.

### Ошибка "Module not found"

**Решение:** Убедитесь что виртуальное окружение активировано и зависимости установлены:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Ошибка при подключении к Telegram

**Решение:**
1. Проверьте что `TG_API_ID` и `TG_API_HASH` правильные
2. Проверьте что сессия валидна (запустите `python login.py` заново)
3. Проверьте интернет соединение

### Порт уже занят

**Решение:** Измените порт:
```bash
PORT=8011 ./start.sh
```

## 📚 Дополнительная документация

- `README.md` - Основная документация
- `DEPLOY.md` - Полное руководство по деплою
- `QUICK_DEPLOY.md` - Быстрый деплой
- `AGENTS.md` - Все настройки и переменные окружения
- `CHANGELOG.md` - История изменений

## ✅ Чеклист готовности

- [ ] Репозиторий склонирован
- [ ] Виртуальное окружение создано и активировано
- [ ] Зависимости установлены (`pip install -r requirements.txt`)
- [ ] Файл `.env` создан с `TG_API_ID` и `TG_API_HASH`
- [ ] Telegram сессия создана (`python login.py`) или `TG_SESSION_STRING` установлен
- [ ] Сервис запускается (`./start.sh`)
- [ ] Health endpoint отвечает (`curl http://localhost:8010/health`)
- [ ] API работает (тестовый запрос к `/search_groups`)

## 🎉 Готово!

После выполнения всех шагов сервис должен работать на новом компьютере.

Для деплоя на продакшн (Render.com) см. `DEPLOY.md`.
