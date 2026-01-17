# ✅ Чеклист: Проверка работы полей в n8n

## Критически важно для работы:

### 1. В HTTP Request node в n8n

**URL:** `https://tg-groups-api-old.onrender.com/search_groups`

**Method:** POST

**Body (JSON):**
```json
{
  "query": "india",
  "limit": 10,
  "include_admins": true
}
```

**⚠️ КРИТИЧЕСКИ ВАЖНО:**
- `include_admins` должен быть **boolean `true`**, НЕ строка `"true"`
- В n8n используйте Expression: `{{ true }}` или просто `true` в JSON

### 2. Проверка ответа

После HTTP Request добавьте **Code node** для проверки:

```javascript
const response = $input.item.json;

// Проверяем что include_admins был передан
console.log("Response items count:", response.items?.length);

if (response.items && response.items.length > 0) {
  const firstItem = response.items[0];
  console.log("First item keys:", Object.keys(firstItem));
  console.log("admin_id:", firstItem.admin_id);
  console.log("created_at:", firstItem.created_at);
  console.log("is_megagroup:", firstItem.is_megagroup);
  console.log("description:", firstItem.description);
  
  // Если все null - проблема в запросе или доступе
  if (firstItem.admin_id === null && firstItem.created_at === null) {
    console.error("⚠️ Поля пустые! Проверьте include_admins в запросе");
  }
}

return { json: response };
```

### 3. Проверка логов на Render

Откройте: https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug/logs

**Ищите в логах:**

✅ **Хорошие признаки:**
```
search_groups request include_admins=true
search_groups result admins_found=5 created_at_found=5
```

❌ **Плохие признаки:**
```
search_groups request include_admins=false  # ← Проблема!
search_groups result admins_found=0  # ← Админы не найдены
failed to get admin info  # ← Ошибки доступа
```

### 4. Типичные ошибки

#### Ошибка: `include_admins` передается как строка
**В n8n HTTP Request:**
```json
{
  "include_admins": "true"  // ❌ НЕПРАВИЛЬНО - это строка!
}
```

**Правильно:**
```json
{
  "include_admins": true  // ✅ ПРАВИЛЬНО - это boolean
}
```

Или в Expression mode:
```javascript
{
  "include_admins": {{ true }}
}
```

#### Ошибка: Поля не передаются в Google Sheets
**Проблема:** n8n не извлекает вложенные поля из `items`

**Решение:** Используйте **Split In Batches** node:
1. HTTP Request → получаем `{ok: true, items: [...]}`
2. **Code node** → извлекаем items:
   ```javascript
   return $input.item.json.items.map(item => ({ json: item }));
   ```
3. **Split In Batches** → обрабатываем по одному
4. **Google Sheets** → записываем каждый item

### 5. Тестовый запрос напрямую

Проверьте API напрямую (минуя n8n):

```bash
curl -X POST https://tg-groups-api-old.onrender.com/search_groups \
  -H "Content-Type: application/json" \
  -d '{
    "query": "india",
    "limit": 1,
    "include_admins": true
  }' | jq '.items[0] | {
    id,
    title,
    admin_id,
    admin_username,
    created_at,
    is_megagroup,
    is_broadcast,
    description
  }'
```

Если здесь поля заполнены, проблема в n8n конфигурации.
Если здесь поля пустые, проблема в API или доступе.

### 6. Если ничего не помогает

Используйте альтернативный подход - получайте админов отдельно:

```javascript
// После получения списка групп
for (const group of items) {
  try {
    const adminResponse = await $http.post(
      'https://tg-groups-api-old.onrender.com/get_group_admins',
      { chat_id: group.id, limit: 1 }
    );
    
    if (adminResponse.items && adminResponse.items.length > 0) {
      const admin = adminResponse.items[0];
      group.admin_id = admin.admin_id;
      group.admin_username = admin.username;
      group.admin_last_seen_at = admin.last_seen_at;
      group.admin_last_seen_status = admin.status;
    }
  } catch (e) {
    console.log(`Failed to get admin for ${group.id}:`, e.message);
  }
}
```

Но это будет медленнее (отдельный запрос для каждой группы).



