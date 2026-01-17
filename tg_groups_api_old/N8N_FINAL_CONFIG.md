# ✅ Финальная конфигурация n8n для Google Sheets

## Рабочий JSON запрос

```json
{
  "query": "india",
  "limit": 100,
  "include_admins": true,
  "min_members": 500,
  "types_only": "channel,megagroup,group"
}
```

## Параметры

### Обязательные:
- `query` - Поисковый запрос (строка, минимум 1 символ)

### Опциональные (с значениями по умолчанию):
- `limit` - Максимум результатов (1-100, по умолчанию: 10)
- `include_admins` - Включить данные об админах и дате создания (boolean, по умолчанию: false)
- `min_members` - Минимальное количество участников (число, по умолчанию: 0)
- `types_only` - Типы групп для поиска (строка, по умолчанию: "channel,megagroup,group")

## Настройка в n8n

### HTTP Request Node

**URL:** `https://tg-groups-api-old.onrender.com/search_groups`

**Method:** POST

**Body Type:** JSON

**Body (JSON):**
```json
{
  "query": "{{ $json.query }}",
  "limit": 100,
  "include_admins": true,
  "min_members": 500,
  "types_only": "channel,megagroup,group"
}
```

**Или с переменными из предыдущего node:**
```json
{
  "query": "{{ $json.keyword }}",
  "limit": {{ $json.limit || 100 }},
  "include_admins": true,
  "min_members": {{ $json.min_members || 500 }},
  "types_only": "{{ $json.types_only || 'channel,megagroup,group' }}"
}
```

## Пример полного workflow

```
1. Manual Trigger (или Schedule)
   ↓
2. Set Node (опционально - для настройки параметров)
   {
     "query": "india",
     "limit": 100,
     "min_members": 500,
     "types_only": "channel,megagroup,group"
   }
   ↓
3. HTTP Request
   POST https://tg-groups-api-old.onrender.com/search_groups
   Body: {
     "query": "{{ $json.query }}",
     "limit": {{ $json.limit }},
     "include_admins": true,
     "min_members": {{ $json.min_members }},
     "types_only": "{{ $json.types_only }}"
   }
   ↓
4. Code Node (извлечение items)
   return $input.item.json.items.map(item => ({ json: item }));
   ↓
5. Google Sheets → Append
   Spreadsheet: "Telegram Groups Monitor"
   Sheet: "Tab"
   Columns: A-U (все поля)
```

## Поля в ответе

Каждый item содержит:

```json
{
  "id": 123456789,
  "title": "Group Name",
  "username": "group_username",
  "members_count": 1000,
  "type": "channel",
  "status": "ok",
  "reason": null,
  "created_at": "2024-01-15T10:30:00+00:00",
  "admin_id": 987654321,
  "admin_username": "admin_user",
  "admin_last_seen_at": "2024-12-28T14:30:00+00:00",
  "admin_last_seen_status": "offline",
  "is_megagroup": false,
  "is_broadcast": true,
  "description": "Group description"
}
```

## Маппинг для Google Sheets

| Колонка | Поле API | Описание |
|---------|----------|----------|
| A | added_at | Время добавления (из n8n) |
| B | title | Название группы |
| C | username | Username группы |
| F | id | ID группы |
| G | link | Ссылка (https://t.me/username) |
| H | created_at | Дата создания |
| I | members | Количество участников |
| J | type | Тип (channel/megagroup/group) |
| K | keyword | Ключевое слово поиска |
| L | admin_id | ID админа |
| M | admin_username | Username админа |
| N | admin_last_seen_at | Когда админ был в сети |
| O | admin_last_seen_status | Статус админа |
| S | ok | Статус ответа |
| T | query | Поисковый запрос |
| U | items | JSON всех items |

## Важные замечания

1. **`include_admins: true`** - обязательно для получения данных об админах
2. **`min_members: 500`** - фильтрует группы с менее чем 500 участниками
3. **`types_only`** - можно указать только нужные типы:
   - `"channel"` - только каналы
   - `"megagroup"` - только мегагруппы
   - `"group"` - только обычные группы
   - `"channel,megagroup"` - каналы и мегагруппы

## Производительность

- При `include_admins: true` запросы медленнее (дополнительные запросы к Telegram API)
- При `limit: 100` и `include_admins: true` может занять 30-60 секунд
- Рекомендуется использовать `limit: 10-20` для быстрых запросов

## Troubleshooting

### Поля все еще пустые
1. Проверьте логи на Render - должно быть `include_admins=true`
2. Проверьте что `include_admins` boolean, не строка
3. Проверьте права доступа бота к группам

### Слишком мало результатов
- Уменьшите `min_members` (например, до 100)
- Проверьте `types_only` - возможно фильтрует нужные типы

### Слишком много результатов
- Увеличьте `min_members`
- Уменьшите `limit`
- Уточните `query`

