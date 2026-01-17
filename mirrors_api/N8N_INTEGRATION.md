# Интеграция с n8n и Google Sheets

## Настройка

### 1. Получить Google OAuth2 Access Token

Для работы с Google Sheets API нужен OAuth2 access token.

**Вариант A: Через Google Cloud Console**
1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com/)
2. Включите Google Sheets API
3. Создайте OAuth2 credentials
4. Получите access token

**Вариант B: Через n8n**
1. Используйте n8n Google Sheets node для получения токена
2. Передайте токен в запросе или установите в `.env`

### 2. Настроить .env

```bash
# Google Sheets OAuth2 token (опционально, можно передавать в запросе)
GOOGLE_SHEETS_ACCESS_TOKEN=your_access_token_here
```

## Эндпоинты для n8n

### 1. `/n8n_collect_and_export_sync` (рекомендуется)

Собирает зеркала и экспортирует в Google Sheets синхронно.

**POST запрос:**
```json
{
  "items": [
    {
      "merchant": "1xbet",
      "keywords": ["1xbet argentina", "1xbet mirror argentina"],
      "country": "ar",
      "lang": "es",
      "limit": 20
    },
    {
      "merchant": "1win",
      "keywords": ["1win argentina", "1win espejo"],
      "country": "ar",
      "lang": "es",
      "limit": 20
    }
  ],
  "limit": 20,
  "follow_redirects": true,
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1ubWNiixJEzQxu9kLO1GAosbdiXw1-kIGnsJjdwzFDJQ/edit",
  "range_name": "Sheet1!A2:Z",
  "clear_first": false,
  "access_token": "optional_if_set_in_env"
}
```

**Ответ:**
```json
{
  "ok": true,
  "message": "Collection and export completed",
  "collection": {
    "status": "ok",
    "created": 15,
    "updated": 5
  },
  "export": {
    "spreadsheet_id": "1ubWNiixJEzQxu9kLO1GAosbdiXw1-kIGnsJjdwzFDJQ",
    "rows_exported": 20,
    "updated_cells": 240,
    "updated_rows": 20
  }
}
```

### 2. `/n8n_collect_and_export` (асинхронный)

Запускает сбор в фоне, экспорт выполняется после сбора.

**POST запрос:** (тот же формат)

**Ответ:**
```json
{
  "ok": true,
  "message": "Collection started, export scheduled",
  "collection_result": {...},
  "spreadsheet_id": "..."
}
```

### 3. `/export_to_sheets` (только экспорт)

Экспортирует существующие данные из БД в Google Sheets.

**POST запрос:**
```json
{
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1ubWNiixJEzQxu9kLO1GAosbdiXw1-kIGnsJjdwzFDJQ/edit",
  "range_name": "Sheet1!A2:Z",
  "clear_first": false,
  "country": "ar",
  "merchant": "1xbet",
  "limit": 1000,
  "access_token": "optional"
}
```

## Настройка n8n

### HTTP Request Node

**Method:** POST  
**URL:** `https://your-api-domain.com/n8n_collect_and_export_sync`

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "items": [
    {
      "merchant": "1xbet",
      "keywords": ["1xbet argentina", "1xbet mirror argentina"],
      "country": "ar",
      "lang": "es",
      "limit": 20
    }
  ],
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1ubWNiixJEzQxu9kLO1GAosbdiXw1-kIGnsJjdwzFDJQ/edit",
  "range_name": "Sheet1!A2:Z",
  "clear_first": false
}
```

## Формат данных в Google Sheets

Данные экспортируются в следующем порядке колонок:

1. `merchant` - мерчант
2. `country` - страна
3. `keyword` - ключевое слово
4. `source_url` - исходный URL
5. `source_domain` - исходный домен
6. `final_url` - финальный URL
7. `final_domain` - финальный домен
8. `is_redirector` - TRUE/FALSE
9. `is_mirror` - TRUE/FALSE
10. `cta_found` - TRUE/FALSE
11. `first_seen_at` - дата первого обнаружения
12. `last_seen_at` - дата последнего обновления

## Примеры использования

### Пример 1: Сбор для одного мерчанта

```json
{
  "items": [
    {
      "merchant": "1xbet",
      "keywords": ["1xbet argentina", "1xbet mirror"],
      "country": "ar",
      "lang": "es",
      "limit": 20
    }
  ],
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit",
  "range_name": "Sheet1!A2:Z"
}
```

### Пример 2: Сбор для нескольких мерчантов

```json
{
  "items": [
    {
      "merchant": "1xbet",
      "keywords": ["1xbet argentina"],
      "country": "ar",
      "limit": 20
    },
    {
      "merchant": "1win",
      "keywords": ["1win argentina"],
      "country": "ar",
      "limit": 20
    }
  ],
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit",
  "clear_first": true
}
```

## Troubleshooting

### Ошибка: "Google Sheets access token is required"

**Решение:** Установите `GOOGLE_SHEETS_ACCESS_TOKEN` в `.env` или передайте в запросе.

### Ошибка: "Could not extract spreadsheet ID"

**Решение:** Убедитесь, что URL правильный. Должен быть формат:
```
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
```

### Ошибка: "The connection cannot be established"

**Решение:** 
1. Проверьте, что API доступен
2. Проверьте URL в n8n
3. Убедитесь, что сервер запущен

## Получение Access Token через n8n

1. Используйте n8n Google OAuth2 node
2. Настройте OAuth2 credentials
3. Получите access token
4. Передайте токен в запросе или сохраните в переменных окружения


