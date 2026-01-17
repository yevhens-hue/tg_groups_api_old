# Быстрый старт для n8n

## ✅ Готово к использованию!

### Эндпоинты созданы:
- ✅ `/n8n_collect_and_export_sync` - сбор + экспорт (синхронно)
- ✅ `/n8n_collect_and_export` - сбор + экспорт (асинхронно)
- ✅ `/export_to_sheets` - только экспорт

## 🚀 Настройка в n8n

### 1. HTTP Request Node

**URL:** 
```
POST https://your-api-domain.com/n8n_collect_and_export_sync
```

**Body (JSON):**
```json
{
  "items": [
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

### 2. Google OAuth2 Token

**Вариант A:** Передать в запросе
```json
{
  ...,
  "access_token": "ya29.a0AfH6SMC..."
}
```

**Вариант B:** Установить на сервере в `.env`
```bash
GOOGLE_SHEETS_ACCESS_TOKEN=ya29.a0AfH6SMC...
```

## 📋 Формат данных в Google Sheets

Данные экспортируются в колонки:
1. merchant
2. country  
3. keyword
4. source_url
5. source_domain
6. final_url
7. final_domain
8. is_redirector (TRUE/FALSE)
9. is_mirror (TRUE/FALSE)
10. cta_found (TRUE/FALSE)
11. first_seen_at
12. last_seen_at

## 🔧 Получение Google OAuth2 Token

### Через n8n:
1. Добавьте **Google OAuth2 API** node
2. Scope: `https://www.googleapis.com/auth/spreadsheets`
3. Используйте `{{ $json.access_token }}` в HTTP Request

### Через Google Cloud Console:
1. [Google Cloud Console](https://console.cloud.google.com/)
2. Включите **Google Sheets API**
3. Создайте **OAuth 2.0 Client ID**
4. Используйте токен в запросах

## ✅ Тестирование

Все компоненты протестированы и готовы!

Подробнее: см. `N8N_INTEGRATION.md`


