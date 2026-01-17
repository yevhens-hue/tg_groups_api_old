# Парсер платежных данных для Аргентины (1win.lat)

## Описание

Парсер для извлечения платежных данных с сайта 1win.lat для Аргентины. Парсер:
1. Автоматически логинится на сайт
2. Переходит на страницу депозита
3. Выбирает метод оплаты Claro Pay (Fiat)
4. Извлекает данные платежной формы:
   - CVU (номер CVU)
   - Recipient (получатель)
   - Bank (банк)
   - Amount (сумма)
5. Экспортирует данные в Google Sheets

## Эндпоинт

### POST `/parse_payment_data_ar`

**Описание:** Парсит платежные данные с 1win.lat и экспортирует в Google Sheets.

**Тело запроса (JSON):**

```json
{
  "email": "perymury78@gmail.com",
  "password": "%m^%G5\"}4m",
  "base_url": "https://1win.lat/",
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit?gid=516142479#gid=516142479",
  "sheet_name": null,
  "clear_first": false,
  "access_token": null,
  "wait_seconds": 15
}
```

**Параметры:**

- `email` (обязательно) - Email для входа на сайт
- `password` (обязательно) - Пароль для входа на сайт
- `base_url` (опционально, по умолчанию: "https://1win.lat/") - Базовый URL сайта
- `spreadsheet_url` (обязательно) - URL Google Sheets для экспорта данных
- `sheet_name` (опционально) - Имя вкладки. Если не указано, будет попытка определить по gid из URL или используется первая доступная вкладка
- `clear_first` (опционально, по умолчанию: false) - Очистить данные перед записью
- `access_token` (опционально) - Google OAuth2 access token. Если не указан, используется из переменной окружения `GOOGLE_SHEETS_ACCESS_TOKEN`
- `wait_seconds` (опционально, по умолчанию: 15) - Время ожидания для загрузки страниц (5-60 секунд)

**Пример ответа (успех):**

```json
{
  "ok": true,
  "message": "Payment data parsed and exported successfully",
  "payment_data": {
    "method": "Claro Pay",
    "payment_type": "Fiat",
    "bank": "Claro Pay",
    "cvu": "0000085700202965723316",
    "recipient": "Oscar Oscar Daniel Heredia",
    "amount": "$6,000",
    "url": "https://1win.lat/...",
    "success": true
  },
  "export": {
    "spreadsheet_id": "1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE",
    "updated_range": "Sheet1!A2:J2",
    "updated_rows": 1
  }
}
```

**Пример ответа (ошибка):**

```json
{
  "ok": false,
  "message": "Payment data parsing failed",
  "payment_data": {
    "cvu": null,
    "recipient": null,
    "bank": null,
    "amount": null,
    "success": false,
    "error": "CVU not found"
  },
  "export": null
}
```

## Формат данных в Google Sheets

Данные экспортируются в следующие колонки:

| Колонка | Описание | Пример |
|---------|----------|--------|
| A - Method | Метод оплаты | Claro Pay |
| B - Type | Тип оплаты | Fiat |
| C - Account | Получатель (Account) | Oscar Oscar Daniel Heredia |
| D - Date | Дата и время | 2025-01-15 10:30:45 |
| E - Links | URL страницы | https://1win.lat/... |
| F - Screenshot | Скриншот (пока пусто) | |
| G - QR | QR код (пока пусто) | |
| H - Status | Статус | Success / Failed |
| I - Bank | Банк | Claro Pay |
| J - CVU | CVU номер | 0000085700202965723316 |

## Использование

### Через curl

```bash
curl -X POST "http://localhost:8000/parse_payment_data_ar" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "perymury78@gmail.com",
    "password": "%m^%G5\"}4m",
    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit?gid=516142479#gid=516142479"
  }'
```

### Через Python

```python
import requests

response = requests.post(
    "http://localhost:8000/parse_payment_data_ar",
    json={
        "email": "perymury78@gmail.com",
        "password": "%m^%G5\"}4m",
        "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit?gid=516142479#gid=516142479"
    }
)

print(response.json())
```

### Настройка Google OAuth2 Token

**Вариант 1:** Установить в переменную окружения

```bash
export GOOGLE_SHEETS_ACCESS_TOKEN=ya29.a0AfH6SMC...
```

**Вариант 2:** Передать в запросе

```json
{
  "email": "...",
  "password": "...",
  "spreadsheet_url": "...",
  "access_token": "ya29.a0AfH6SMC..."
}
```

## Извлечение данных

Парсер использует различные стратегии для извлечения данных:

1. **CVU**: Поиск через regex-паттерны в содержимом страницы и в DOM-элементах
2. **Recipient**: Поиск элемента с текстом "Recipient" и извлечение значения рядом
3. **Bank**: Поиск элемента с текстом "Bank" или "Claro Pay"
4. **Amount**: Поиск элемента с текстом "Amount" и извлечение суммы в формате $X,XXX

## Особенности

- Парсер автоматически определяет имя вкладки по gid из URL Google Sheets
- Если gid не найден или вкладка не найдена, используется первая доступная вкладка
- Парсер делает скриншот страницы с платежными данными (в base64 формате в ответе)
- Все данные логируются для отладки

## Устранение неполадок

### CVU не найден

**Причины:**
- Страница не загрузилась полностью
- Структура страницы изменилась
- Данные загружаются динамически и требуется больше времени ожидания

**Решение:**
- Увеличить `wait_seconds` (например, до 30)
- Проверить, что учетные данные правильные
- Проверить логи для детальной информации

### Не удается найти вкладку в Google Sheets

**Причины:**
- gid из URL не совпадает с sheetId в API
- Вкладка с таким gid не существует

**Решение:**
- Указать `sheet_name` явно в запросе
- Проверить, что URL правильный и вкладка существует

### Ошибка авторизации Google Sheets

**Причины:**
- Access token недействителен или истек
- Access token не имеет прав на запись в таблицу

**Решение:**
- Обновить access token
- Убедиться, что токен имеет scope `https://www.googleapis.com/auth/spreadsheets`

## Логирование

Все действия парсера логируются с помощью structlog. Для просмотра логов:

```bash
# Если используется uvicorn
uvicorn app:app --log-level debug
```

Ключевые события в логах:
- `payment_parser_starting` - Начало парсинга
- `payment_parser_login_clicked` - Кнопка входа найдена и нажата
- `payment_parser_cvu_found` - CVU успешно извлечен
- `payment_parser_success` - Парсинг завершен успешно
- `payment_data_exported` - Данные экспортированы в Google Sheets
