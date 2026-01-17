# Настройка n8n для работы с API

## Быстрая настройка

### 1. HTTP Request Node в n8n

**Настройки:**
- **Method:** `POST`
- **URL:** `https://your-api-domain.com/n8n_collect_and_export_sync`
- **Authentication:** None (или Basic если настроено)
- **Send Body:** ✅ ON
- **Body Content Type:** `JSON`

### 2. Body (JSON)

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

### 3. Google OAuth2 Token

**Вариант A: Передать в запросе**
```json
{
  ...,
  "access_token": "ya29.a0AfH6SMC..."
}
```

**Вариант B: Установить в .env на сервере**
```bash
GOOGLE_SHEETS_ACCESS_TOKEN=ya29.a0AfH6SMC...
```

**Вариант C: Использовать n8n Google OAuth2 node**
1. Добавьте Google OAuth2 node перед HTTP Request
2. Получите access token
3. Используйте `{{ $json.access_token }}` в HTTP Request body

## Получение Google OAuth2 Token

### Через n8n Google OAuth2 Node:

1. Добавьте **Google OAuth2 API** node
2. Настройте OAuth2 credentials:
   - Client ID
   - Client Secret
   - Scope: `https://www.googleapis.com/auth/spreadsheets`
3. Выполните node для получения токена
4. Используйте токен в HTTP Request

### Через Google Cloud Console:

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте проект (или выберите существующий)
3. Включите **Google Sheets API**
4. Создайте **OAuth 2.0 Client ID**
5. Используйте токен в запросах

## Пример полного workflow в n8n

```
1. Google OAuth2 API
   └─> Получить access_token

2. HTTP Request
   ├─ Method: POST
   ├─ URL: https://your-api.com/n8n_collect_and_export_sync
   ├─ Body: {
        "items": [...],
        "spreadsheet_url": "...",
        "access_token": "{{ $json.access_token }}"
      }
   └─> Результат экспорта

3. (Опционально) Google Sheets
   └─> Проверить данные в таблице
```

## Эндпоинты

### `/n8n_collect_and_export_sync` (рекомендуется)
- Синхронный: ждет завершения сбора и экспорта
- Возвращает полный результат
- Подходит для n8n workflows

### `/n8n_collect_and_export`
- Асинхронный: запускает в фоне
- Возвращает статус сразу
- Подходит для долгих операций

### `/export_to_sheets`
- Только экспорт существующих данных
- Не собирает новые зеркала
- Полезно для обновления таблицы

## Формат ответа

**Успешный ответ:**
```json
{
  "ok": true,
  "message": "Collection and export completed",
  "collection": {
    "status": "ok",
    "created": 15,
    "updated": 5,
    "merchants_count": 2
  },
  "export": {
    "spreadsheet_id": "1ubWNiixJEzQxu9kLO1GAosbdiXw1-kIGnsJjdwzFDJQ",
    "rows_exported": 20,
    "updated_cells": 240,
    "updated_rows": 20
  }
}
```

**Ошибка:**
```json
{
  "detail": "Error message here"
}
```

## Troubleshooting

### "The connection cannot be established"
- Проверьте URL API
- Убедитесь, что сервер запущен
- Проверьте firewall/network

### "Google Sheets access token is required"
- Установите токен в `.env` или передайте в запросе
- Проверьте, что токен не истек

### "Could not extract spreadsheet ID"
- Убедитесь, что URL правильный
- Формат: `https://docs.google.com/spreadsheets/d/ID/edit`

## Тестирование

Проверьте эндпоинт локально:
```bash
curl -X POST http://localhost:8011/n8n_collect_and_export_sync \
  -H "Content-Type: application/json" \
  -d '{
    "items": [{"merchant": "1xbet", "keywords": ["test"], "country": "ar", "limit": 5}],
    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1ubWNiixJEzQxu9kLO1GAosbdiXw1-kIGnsJjdwzFDJQ/edit"
  }'
```


