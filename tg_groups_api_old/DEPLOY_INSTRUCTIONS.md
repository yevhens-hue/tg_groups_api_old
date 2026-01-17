# 🚀 Deployment Instructions for Render

## Ваш Render Service
- Service ID: `srv-d4qq4224d50c73cfqvug`
- Dashboard: https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug

## Ваш GitHub
- Username: `yevhens-hue`
- Profile: https://github.com/yevhens-hue

## Шаги для деплоя:

### 1. Подготовка репозитория

Если репозиторий еще не создан на GitHub:

```bash
# Инициализируйте git (если еще не сделано)
git init

# Добавьте все файлы
git add .

# Создайте коммит
git commit -m "Production ready: Circuit breaker, metrics, auto-reconnect"

# Добавьте remote (замените YOUR_REPO на ваш репозиторий)
git remote add origin https://github.com/yevhens-hue/tg_groups_api_old.git

# Запушьте
git push -u origin main
```

### 2. Настройка Render Service

В Render Dashboard (https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug):

#### A. Подключение к GitHub (если еще не подключено)
1. Settings → Connect GitHub
2. Выберите репозиторий `tg_groups_api_old`
3. Выберите branch (обычно `main` или `master`)

#### B. Build & Start Commands
В разделе **Settings** → **Build & Deploy**:

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `./start.sh`

Или Render автоматически обнаружит `render.yaml` если он в репозитории.

#### C. Environment Variables
В разделе **Environment** добавьте:

**Обязательные:**
```
TG_API_ID=ваш_api_id
TG_API_HASH=ваш_api_hash
TG_SESSION_STRING=ваша_сессия
```

**Рекомендуемые:**
```
REDIS_URL=redis://... (если используете Redis)
LOG_LEVEL=INFO
HTTP_RATE_LIMIT_RPM=60
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
```

### 3. Деплой

1. Нажмите **Manual Deploy** → **Deploy latest commit**
2. Или просто запушьте изменения в GitHub - Render автоматически задеплоит

### 4. Проверка после деплоя

После успешного деплоя проверьте:

```bash
# Health check
curl https://your-service.onrender.com/health

# Metrics
curl https://your-service.onrender.com/metrics

# Root endpoint
curl https://your-service.onrender.com/
```

### 5. Мониторинг

- **Logs:** https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug/logs
- **Metrics:** `/metrics` endpoint
- **Health:** `/health` endpoint

## Troubleshooting

### Если деплой падает:

1. **Проверьте логи** в Render Dashboard
2. **Проверьте переменные окружения** - все ли установлены
3. **Проверьте Build Command** - должен быть `pip install -r requirements.txt`
4. **Проверьте Start Command** - должен быть `./start.sh`

### Частые ошибки:

- **"Module not found"** → Проверьте `requirements.txt`
- **"Telegram not authorized"** → Проверьте `TG_SESSION_STRING`
- **"Port already in use"** → Render автоматически устанавливает PORT, убедитесь что `start.sh` использует `$PORT`

## Обновление после изменений

Просто запушьте изменения:
```bash
git add .
git commit -m "Update: ..."
git push
```

Render автоматически задеплоит новую версию.



