# 🔧 Решение: Данные об админах в колонке items

## Проблема
Все данные об админах попадают в одну колонку `items` как JSON, а не разбиты по отдельным колонкам в Google Sheets.

## Причина
n8n маппит весь ответ API в Google Sheets, включая поле `items` как одну колонку с JSON.

## Решение: Извлечь items и разбить на строки

### Шаг 1: Добавьте Code Node после HTTP Request

После HTTP Request node добавьте **Code node** для извлечения items:

```javascript
// Получаем ответ от API
const response = $input.item.json;

// Проверяем что ответ успешный
if (!response.ok) {
  throw new Error(`API error: ${response.reason || 'Unknown error'}`);
}

// Извлекаем items из ответа
const items = response.items || [];

if (items.length === 0) {
  console.log("No items found in response");
  return [];
}

// Для каждого item создаем отдельную запись
const result = items.map((item, index) => {
  return {
    json: {
      // Основные поля группы
      id: item.id || null,
      title: item.title || '',
      username: item.username || null,
      members_count: item.members_count || null,
      type: item.type || 'unknown',
      status: item.status || 'ok',
      
      // Дата создания
      created_at: item.created_at || null,
      
      // Данные об админе
      admin_id: item.admin_id || null,
      admin_username: item.admin_username || null,
      admin_last_seen_at: item.admin_last_seen_at || null,
      admin_last_seen_status: item.admin_last_seen_status || null,
      
      // Дополнительные поля
      is_megagroup: item.is_megagroup || null,
      is_broadcast: item.is_broadcast || null,
      description: item.description || null,
      
      // Метаданные для отладки
      query: response.query || '',
      item_index: index,
      total_items: items.length,
      
      // Для отладки (можно удалить после проверки)
      _debug: {
        has_admin_id: item.admin_id !== null && item.admin_id !== undefined,
        has_admin_username: item.admin_username !== null && item.admin_username !== undefined,
        has_created_at: item.created_at !== null && item.created_at !== undefined,
      }
    }
  };
});

console.log(`Extracted ${result.length} items`);
console.log(`Items with admin_id: ${result.filter(r => r.json.admin_id).length}`);
console.log(`Items with created_at: ${result.filter(r => r.json.created_at).length}`);

return result;
```

### Шаг 2: Настройте Google Sheets Append

После Code node добавьте **Google Sheets → Append Row**:

**Spreadsheet:** Ваша таблица  
**Sheet:** Ваш лист (например, "Tab")

**Columns to Send:**
```
id, title, username, members_count, type, status, created_at, admin_id, admin_username, admin_last_seen_at, admin_last_seen_status, is_megagroup, is_broadcast, description
```

**Или маппинг вручную:**
- `id` → Колонка F (или нужная вам)
- `title` → Колонка B
- `username` → Колонка C
- `members_count` → Колонка I
- `type` → Колонка J
- `created_at` → Колонка H
- `admin_id` → Колонка L
- `admin_username` → Колонка M
- `admin_last_seen_at` → Колонка N
- `admin_last_seen_status` → Колонка O
- `is_megagroup` → Новая колонка
- `is_broadcast` → Новая колонка
- `description` → Новая колонка

### Шаг 3: Полный workflow

```
1. Manual Trigger (или Schedule)
   ↓
2. HTTP Request
   POST https://tg-groups-api-old.onrender.com/search_groups
   Body: {
     "query": "india",
     "limit": 100,
     "include_admins": true,
     "min_members": 5,
     "types_only": "channel,megagroup,group",
     "no_cache": true
   }
   ↓
3. Code Node (извлечение items)
   [Код выше]
   ↓
4. Google Sheets → Append Row
   Spreadsheet: "Telegram Groups Monitor"
   Sheet: "Tab"
   Columns: [маппинг выше]
```

## Альтернатива: Использовать Split In Batches

Если у вас много items, можно использовать **Split In Batches** node:

```
HTTP Request
  ↓
Code Node (извлечение items)
  ↓
Split In Batches (batch size: 10)
  ↓
Google Sheets → Append Row
```

## Проверка результата

После настройки:

1. Запустите workflow
2. Проверьте Google Sheets - каждая группа должна быть в отдельной строке
3. Данные об админах должны быть в отдельных колонках (L, M, N, O)
4. Проверьте Debug node если добавили - там будет видно сколько items с админами

## Отладка

Если данные все еще не появляются:

1. **Добавьте Debug node** после Code node:
   ```javascript
   const items = $input.all();
   console.log("Total items:", items.length);
   console.log("First item:", JSON.stringify(items[0].json, null, 2));
   return items;
   ```

2. **Проверьте логи n8n** - должны быть сообщения:
   - "Extracted X items"
   - "Items with admin_id: X"
   - "Items with created_at: X"

3. **Проверьте маппинг в Google Sheets** - убедитесь что колонки правильно маппятся

## Пример результата в Google Sheets

После правильной настройки:

| A | B (title) | C (username) | ... | H (created_at) | ... | L (admin_id) | M (admin_username) | N (admin_last_seen_at) | O (admin_last_seen_status) |
|---|-----------|--------------|-----|----------------|-----|--------------|-------------------|------------------------|----------------------------|
| 1 | Group 1 | group1 | ... | 2025-10-22 9:33:53 | ... | 7357164577 | tony_paym | null | recently |
| 2 | Group 2 | group2 | ... | 2024-08-20 8:16:07 | ... | 7898005853 | Annabel_Williams | 2025-12-23 10:34:07 | offline |

Каждая группа в отдельной строке, данные об админах в отдельных колонках!

