# Где взять URL для n8n

## 🔗 URL API

### Если API запущен локально:
```
http://localhost:8011/n8n_collect_and_export_sync
```

### Если API на Render.com (как на скриншоте):
```
https://mirrors-api-prod.onrender.com/n8n_collect_and_export_sync
```

### Если API на другом домене:
```
https://your-domain.com/n8n_collect_and_export_sync
```

## ⚠️ Важно!

URL должен быть **полным**, включая:
- Протокол (`https://` или `http://`)
- Домен
- **Эндпоинт** (`/n8n_collect_and_export_sync`)

❌ Неправильно:
```
https://mirrors-api-prod.onrender.com
```

✅ Правильно:
```
https://mirrors-api-prod.onrender.com/n8n_collect_and_export_sync
```

## 📋 Полный пример для n8n

### HTTP Request Node:

**Method:** `POST`

**URL:** 
```
https://mirrors-api-prod.onrender.com/n8n_collect_and_export_sync
```

**Body (JSON):**
```json
{
  "items": [
    {
      "merchant": "stake",
      "keywords": [
        "stake argentina",
        "stake mirror argentina",
        "stake enlace argentina",
        "stake ingresar argentina"
      ],
      "country": "ar",
      "lang": "es",
      "limit": 20
    },
    {
      "merchant": "1xbet",
      "keywords": [
        "1xbet argentina",
        "1xbet mirror argentina",
        "1xbet enlace argentina",
        "1xbet ingresar"
      ],
      "country": "ar",
      "lang": "es",
      "limit": 20
    },
    {
      "merchant": "1win",
      "keywords": [
        "1win argentina",
        "1win espejo",
        "1win enlace argentina",
        "1win ingresar"
      ],
      "country": "ar",
      "lang": "es",
      "limit": 20
    }
  ],
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1ubWNiixJEzQxu9kLO1GAosbdiXw1-kIGnsJjdwzFDJQ/edit?gid=465762212#gid=465762212",
  "range_name": "Sheet1!A2:Z",
  "clear_first": false,
  "follow_redirects": true
}
```

## 🔍 Проверка доступности API

Перед использованием в n8n проверьте:

```bash
# Health check
curl https://mirrors-api-prod.onrender.com/health

# Должен вернуть:
# {"status":"ok","version":"0.9.0",...}
```

## 🐛 Ошибка "Service unavailable"

Если видите ошибку "Service unavailable":

1. **Проверьте, что сервер запущен:**
   ```bash
   curl https://mirrors-api-prod.onrender.com/health
   ```

2. **Проверьте URL:**
   - Должен быть полный URL с эндпоинтом
   - Должен быть правильный метод (POST)

3. **Проверьте timeout в n8n:**
   - Увеличьте timeout до 300 секунд (сбор может занять время)

4. **Проверьте логи сервера:**
   - Если сервер на Render, проверьте логи в панели

## 📝 Где взять spreadsheet_url?

Это URL вашей Google Таблицы:
```
https://docs.google.com/spreadsheets/d/1ubWNiixJEzQxu9kLO1GAosbdiXw1-kIGnsJjdwzFDJQ/edit?gid=465762212#gid=465762212
```

Просто скопируйте URL из браузера когда открыта таблица.


