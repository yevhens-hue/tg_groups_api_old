# Исправление ошибки 404 в n8n

## ❌ Проблема

Ошибка: "The resource you are requesting could not be found"

## 🔍 Причины

### 1. Неправильный домен
На скриншоте видно: `https://mirrors-api-prod.onrender.cc`
- ❌ `.cc` - неправильный домен
- ✅ Должно быть: `https://mirrors-api.onrender.com`

### 2. Неполный URL (нет эндпоинта)
- ❌ `https://mirrors-api.onrender.com`
- ✅ `https://mirrors-api.onrender.com/n8n_collect_and_export_sync`

### 3. Неполный JSON body
JSON должен содержать все обязательные поля.

## ✅ Правильная настройка

### HTTP Request Node в n8n:

**Method:** `POST`

**URL (ПРАВИЛЬНЫЙ):**
```
https://mirrors-api.onrender.com/n8n_collect_and_export_sync
```

⚠️ **ВАЖНО:** 
- Домен: `.com` (не `.cc`)
- Должен быть эндпоинт: `/n8n_collect_and_export_sync`

**Body (JSON) - ПОЛНЫЙ:**
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

## 🔧 Проверка перед использованием

### 1. Проверьте доступность API:
```bash
curl https://mirrors-api.onrender.com/health
```

Должен вернуть:
```json
{"status":"ok","version":"0.9.0",...}
```

### 2. Проверьте эндпоинт:
```bash
curl -X POST https://mirrors-api.onrender.com/n8n_collect_and_export_sync \
  -H "Content-Type: application/json" \
  -d '{"items":[],"spreadsheet_url":"..."}'
```

## 📋 Чеклист для n8n

- [ ] URL правильный: `https://mirrors-api.onrender.com/n8n_collect_and_export_sync`
- [ ] Method: `POST`
- [ ] Body Content Type: `JSON`
- [ ] JSON содержит все поля: `items`, `spreadsheet_url`
- [ ] `spreadsheet_url` - полный URL Google Таблицы
- [ ] Если нужен `access_token` - добавлен в JSON или в `.env` на сервере

## 🚀 Если сервер на Render.com спит

Free инстансы на Render.com засыпают после 15 минут бездействия.

**Решения:**
1. Включите keep-alive в `.env`:
   ```bash
   KEEPALIVE_ENABLED=true
   KEEPALIVE_INTERVAL=60
   ```

2. Или используйте n8n для периодических health checks

3. Или upgrade на платный план

## ✅ Исправленный пример

См. файл: `N8N_FIXED.json`


