# Интеграция с n8n и Google Sheets

## Новые поля для выгрузки в Google Таблицы

Добавлены следующие поля в ответ `/search_groups`:
- `created_at` - Дата создания группы (ISO format)
- `admin_id` - ID первого админа группы
- `admin_username` - Username первого админа
- `admin_last_seen_at` - Когда админ был в сети последний раз (ISO format)
- `admin_last_seen_status` - Статус админа (online, offline, recently, last_week, last_month, unknown)

## Использование

### API Request

```json
POST /search_groups
{
  "query": "python",
  "limit": 10,
  "include_admins": true
}
```

**Важно:** Установите `include_admins: true` чтобы получить дополнительные поля.

### API Response

```json
{
  "ok": true,
  "query": "python",
  "items": [
    {
      "id": 123456789,
      "title": "Python Community",
      "username": "python",
      "members_count": 10000,
      "type": "channel",
      "status": "ok",
      "reason": null,
      "created_at": "2020-01-15T10:30:00+00:00",
      "admin_id": 987654321,
      "admin_username": "admin_user",
      "admin_last_seen_at": "2024-12-28T14:30:00+00:00",
      "admin_last_seen_status": "offline"
    }
  ]
}
```

## Настройка n8n Workflow

### 1. HTTP Request Node

**Method:** POST  
**URL:** `https://tg-groups-api-old.onrender.com/search_groups`  
**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
  "query": "{{ $json.query }}",
  "limit": 10,
  "include_admins": true
}
```

### 2. Google Sheets Node

**Operation:** Append  
**Spreadsheet:** Ваша Google Таблица  
**Sheet:** Имя листа

**Columns Mapping:**
```
id → A
title → B
username → C
members_count → D
type → E
status → F
created_at → G
admin_id → H
admin_username → I
admin_last_seen_at → J
admin_last_seen_status → K
```

**Data Format:**
```javascript
// В Google Sheets node используйте:
{{ $json.items }}
```

### 3. Пример полного Workflow

```
1. Manual Trigger (или Schedule Trigger)
   ↓
2. HTTP Request → POST /search_groups
   Body: {
     "query": "python",
     "limit": 10,
     "include_admins": true
   }
   ↓
3. Split In Batches (если нужно обработать по частям)
   ↓
4. Google Sheets → Append
   Spreadsheet: "Telegram Groups"
   Sheet: "Groups"
   Columns: A-K (все поля)
```

## Структура Google Таблицы

Рекомендуемые заголовки столбцов:

| A | B | C | D | E | F | G | H | I | J | K |
|---|---|---|---|---|---|---|---|---|---|---|
| id | title | username | members_count | type | status | created_at | admin_id | admin_username | admin_last_seen_at | admin_last_seen_status |

## Важные замечания

1. **Производительность:** При `include_admins: true` запросы будут медленнее, так как для каждой группы делается дополнительный запрос к Telegram API.

2. **Rate Limiting:** Telegram API имеет лимиты. При большом количестве групп может быть flood wait.

3. **Кэширование:** Результаты кэшируются на 10 минут (600 секунд). Для обновления данных подождите или очистите кэш.

4. **Обратная совместимость:** Если `include_admins: false` или не указан, API работает как раньше, без дополнительных полей.

## Пример использования в n8n

### Code Node (для форматирования данных)

```javascript
// Преобразуем items в формат для Google Sheets
const items = $input.item.json.items;

return items.map(item => ({
  json: {
    id: item.id,
    title: item.title,
    username: item.username || '',
    members_count: item.members_count || 0,
    type: item.type,
    status: item.status,
    created_at: item.created_at || '',
    admin_id: item.admin_id || '',
    admin_username: item.admin_username || '',
    admin_last_seen_at: item.admin_last_seen_at || '',
    admin_last_seen_status: item.admin_last_seen_status || ''
  }
}));
```

### Schedule Trigger (автоматический запуск)

Настройте Schedule Trigger для автоматического обновления данных:
- **Every:** 1 hour (или по необходимости)
- **At:** конкретное время (например, каждый день в 9:00)

## Troubleshooting

### Поля пустые (null)
- Убедитесь что `include_admins: true` в запросе
- Проверьте что группа имеет админов (некоторые группы могут не иметь публичных админов)
- Проверьте права доступа к группе

### Ошибка "rate_limited"
- Telegram API ограничивает количество запросов
- Уменьшите `limit` или добавьте задержку между запросами в n8n

### Ошибка "not_participant"
- Бот должен быть участником группы для получения информации об админах
- Для публичных каналов это обычно не проблема



