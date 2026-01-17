# 🔍 Отладка пустых полей в Google Sheets

## Проблема
Поля `admin_id`, `admin_username`, `admin_last_seen_at`, `admin_last_seen_status`, `created_at` остаются пустыми (null).

## Диагностика

### 1. Проверьте что передается `include_admins: true`

В n8n добавьте **Debug node** после HTTP Request:

```javascript
// Code node для проверки запроса
const requestBody = {
  query: "india",
  limit: 10,
  include_admins: true  // ← Проверьте что это boolean true
};

console.log("Request body:", JSON.stringify(requestBody));
console.log("include_admins type:", typeof requestBody.include_admins);
console.log("include_admins value:", requestBody.include_admins);

return { json: requestBody };
```

### 2. Проверьте ответ API

После HTTP Request node добавьте еще один Debug node:

```javascript
// Code node для проверки ответа
const response = $input.item.json;
console.log("Response ok:", response.ok);
console.log("Items count:", response.items?.length);
console.log("First item:", JSON.stringify(response.items?.[0], null, 2));
console.log("First item admin_id:", response.items?.[0]?.admin_id);
console.log("First item created_at:", response.items?.[0]?.created_at);

return { json: response };
```

### 3. Проверьте логи на Render

Откройте: https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug/logs

Ищите строки:
- `search_groups request` - должен показывать `include_admins: true`
- `search_groups result` - должен показывать `admins_found` и `created_at_found`
- `failed to get admin info` - ошибки получения админов
- `failed to get full chat` - ошибки получения полной информации

### 4. Типичные проблемы

#### Проблема: `include_admins` передается как строка
**Симптом:** В логах `include_admins: "true"` (строка) вместо `include_admins: true` (boolean)

**Решение:** В n8n HTTP Request node используйте:
```json
{
  "query": "india",
  "limit": 10,
  "include_admins": true
}
```

НЕ используйте:
```json
{
  "include_admins": "true"  // ❌ Строка
}
```

#### Проблема: Ошибки доступа к группам
**Симптом:** В логах `failed to get admin info` или `not_participant`

**Решение:** 
- Бот должен быть участником группы для получения админов
- Для публичных каналов это обычно не проблема
- Проверьте права доступа бота

#### Проблема: Кэш содержит старые данные
**Симптом:** Данные не обновляются после исправлений

**Решение:**
- Подождите 10 минут (TTL кэша)
- Или измените query в запросе
- Или добавьте timestamp в query

### 5. Тестовый запрос

Проверьте API напрямую:

```bash
curl -X POST https://tg-groups-api-old.onrender.com/search_groups \
  -H "Content-Type: application/json" \
  -d '{
    "query": "india",
    "limit": 1,
    "include_admins": true
  }' | jq '.items[0] | {admin_id, admin_username, created_at}'
```

Если поля все еще `null`, проверьте логи на Render.

### 6. Альтернативное решение

Если проблема сохраняется, можно получить админов отдельным запросом для каждой группы:

```javascript
// В n8n после получения списка групп
for (const group of items) {
  const adminsResponse = await $http.post('https://tg-groups-api-old.onrender.com/get_group_admins', {
    chat_id: group.id,
    limit: 1
  });
  
  if (adminsResponse.items && adminsResponse.items.length > 0) {
    const admin = adminsResponse.items[0];
    group.admin_id = admin.admin_id;
    group.admin_username = admin.username;
    group.admin_last_seen_at = admin.last_seen_at;
    group.admin_last_seen_status = admin.status;
  }
}
```

Но это будет медленнее, так как делает отдельный запрос для каждой группы.



