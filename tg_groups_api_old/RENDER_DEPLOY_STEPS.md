# 🚀 Пошаговая инструкция: Деплой на Render

## Ваш Render сервис
- **URL Dashboard:** https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug
- **Service ID:** srv-d4qq4224d50c73cfqvug

---

## ШАГ 1: Подготовка GitHub репозитория

### 1.1. Создайте репозиторий на GitHub (если еще нет)

1. Откройте https://github.com/yevhens-hue
2. Нажмите **"New repository"** (зеленая кнопка)
3. Название: `tg_groups_api_old` (или любое другое)
4. Выберите **Public** или **Private**
5. **НЕ** добавляйте README, .gitignore, license (у нас уже есть)
6. Нажмите **"Create repository"**

### 1.2. Подключите локальный репозиторий к GitHub

Выполните в терминале (замените `YOUR_USERNAME` на `yevhens-hue`):

```bash
# Если git еще не инициализирован
git init

# Добавьте все файлы
git add .

# Создайте первый коммит
git commit -m "Production ready: Circuit breaker, metrics, auto-reconnect"

# Добавьте remote (замените REPO_NAME на название вашего репозитория)
git remote add origin https://github.com/yevhens-hue/REPO_NAME.git

# Запушьте код
git branch -M main
git push -u origin main
```

**Или если репозиторий уже существует:**

```bash
git add .
git commit -m "Production ready: Circuit breaker, metrics, auto-reconnect"
git push
```

---

## ШАГ 2: Настройка Render сервиса

### 2.1. Откройте ваш Render сервис

Перейдите: https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug

### 2.2. Подключите GitHub репозиторий

1. В левом меню нажмите **"Settings"**
2. Прокрутите до секции **"Source"**
3. Нажмите **"Connect GitHub"** (если еще не подключено)
4. Выберите репозиторий `tg_groups_api_old` (или ваш репозиторий)
5. Выберите **Branch:** `main` (или `master`)
6. Нажмите **"Save"**

### 2.3. Настройте Build & Start команды

1. В **Settings** → **Build & Deploy**
2. Установите:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `./start.sh`
3. Нажмите **"Save Changes"**

**Примечание:** Если в репозитории есть `render.yaml`, Render может использовать его автоматически.

### 2.4. Установите Environment Variables

1. В **Settings** → **Environment**
2. Нажмите **"Add Environment Variable"**
3. Добавьте следующие переменные:

#### Обязательные:
```
TG_API_ID
Значение: ваш_telegram_api_id

TG_API_HASH
Значение: ваш_telegram_api_hash

TG_SESSION_STRING
Значение: ваша_telegram_сессия
```

**Как получить TG_SESSION_STRING:**
```bash
# Локально на вашем компьютере
python login.py
# Скопируйте выведенную сессию
```

#### Рекомендуемые (опционально):
```
REDIS_URL
Значение: redis://... (если используете Redis)

LOG_LEVEL
Значение: INFO

HTTP_RATE_LIMIT_RPM
Значение: 60

CIRCUIT_BREAKER_FAILURE_THRESHOLD
Значение: 5
```

4. После добавления всех переменных нажмите **"Save Changes"**

---

## ШАГ 3: Деплой

### Вариант A: Автоматический деплой (рекомендуется)

1. После подключения GitHub, Render автоматически задеплоит при каждом `git push`
2. Просто выполните:
   ```bash
   git push
   ```
3. Render начнет деплой автоматически

### Вариант B: Ручной деплой

1. В Render Dashboard нажмите **"Manual Deploy"**
2. Выберите **"Deploy latest commit"**
3. Нажмите **"Deploy"**
4. Дождитесь завершения деплоя (обычно 2-5 минут)

---

## ШАГ 4: Проверка деплоя

### 4.1. Проверьте логи

1. В Render Dashboard нажмите **"Logs"**
2. Или перейдите: https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug/logs
3. Убедитесь, что нет ошибок
4. Должны увидеть: `startup ok` и `INFO: Application startup complete`

### 4.2. Проверьте endpoints

Найдите ваш URL сервиса (обычно `https://your-service-name.onrender.com`)

```bash
# Health check
curl https://your-service-name.onrender.com/health

# Должен вернуть:
# {"ok": true, "telegram": "ok", "me_id": ..., "redis": "ok"}

# Metrics
curl https://your-service-name.onrender.com/metrics

# Root
curl https://your-service-name.onrender.com/
```

---

## ШАГ 5: Обновление кода в будущем

После любых изменений в коде:

```bash
git add .
git commit -m "Описание изменений"
git push
```

Render автоматически задеплоит новую версию!

---

## ❌ Troubleshooting

### Ошибка: "Module not found"
- Проверьте, что `requirements.txt` содержит все зависимости
- Проверьте Build Command: `pip install -r requirements.txt`

### Ошибка: "Telegram not authorized"
- Проверьте `TG_SESSION_STRING` - должен быть валидным
- Сгенерируйте новую сессию: `python login.py`

### Ошибка: "Port already in use"
- Убедитесь, что `start.sh` использует `$PORT` (Render автоматически устанавливает)
- Проверьте Start Command: `./start.sh`

### Деплой не запускается
- Проверьте, что GitHub репозиторий подключен
- Проверьте, что branch правильный (`main` или `master`)
- Проверьте логи в Render Dashboard

---

## ✅ Чеклист перед деплоем

- [ ] Код закоммичен и запушен в GitHub
- [ ] GitHub репозиторий подключен к Render
- [ ] Build Command установлен: `pip install -r requirements.txt`
- [ ] Start Command установлен: `./start.sh`
- [ ] Все Environment Variables установлены (TG_API_ID, TG_API_HASH, TG_SESSION_STRING)
- [ ] Деплой запущен
- [ ] Логи проверены (нет ошибок)
- [ ] `/health` endpoint отвечает

---

## 🎉 Готово!

После успешного деплоя ваш сервис будет доступен по URL, который Render предоставит.

Мониторинг:
- **Logs:** https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug/logs
- **Metrics:** `/metrics` endpoint
- **Health:** `/health` endpoint



