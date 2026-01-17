# 1win AR Payment Parser

Парсер платежных данных для сайта 1win.lat (Аргентина). Извлекает информацию о методах оплаты (CVU, банк, получатель и т.д.) и экспортирует данные в Google Sheets.

## Возможности

- Автоматический вход на сайт 1win.lat
- Парсинг платежных данных (CVU, банк, получатель, сумма)
- Сохранение сессии браузера (persistent context)
- Экспорт данных в Google Sheets
- Скриншоты для отладки
- REST API для интеграции

## Установка

1. Клонируйте репозиторий или скопируйте проект:
```bash
cd 1win_ar
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Установите браузеры для Playwright:
```bash
playwright install chromium
```

4. (Опционально) Настройте переменные окружения:
```bash
export GOOGLE_SHEETS_ACCESS_TOKEN=your_token_here
export PAYMENT_PARSER_USER_DATA_DIR=~/.cache/1win_ar/profile
```

## Использование

### 1. Ручной логин (для сохранения сессии)

Перед первым использованием рекомендуется выполнить ручной логин для сохранения сессии:

```bash
python login_manually_1win_ar.py
```

Это откроет браузер, где вы сможете войти в аккаунт. Сессия будет сохранена для последующих запусков.

### 2. Запуск API сервера

```bash
python app.py
```

Или с uvicorn:
```bash
uvicorn app:app --host 0.0.0.0 --port 8011
```

### 3. Использование API

#### Парсинг платежных данных:

```bash
curl -X POST "http://localhost:8011/parse_payment_data_ar" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your_email@example.com",
    "password": "your_password",
    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit",
    "use_persistent_context": true,
    "skip_login": false
  }'
```

#### Параметры запроса:

- `email` (обязательно) - Email для входа на сайт
- `password` (обязательно) - Пароль для входа
- `base_url` (опционально, по умолчанию: "https://1win.lat/") - Базовый URL сайта
- `spreadsheet_url` (опционально) - URL Google Sheets для экспорта данных
- `sheet_name` (опционально) - Имя вкладки в таблице
- `clear_first` (опционально, по умолчанию: false) - Очистить данные перед записью
- `access_token` (опционально) - Google OAuth2 access token (можно также через переменную окружения)
- `wait_seconds` (опционально, по умолчанию: 15) - Время ожидания для загрузки страниц (5-60 секунд)
- `use_persistent_context` (опционально, по умолчанию: true) - Использовать сохраненную сессию
- `skip_login` (опционально, по умолчанию: false) - Пропустить логин (если уже авторизован)

### 4. Тестирование

Запустите тестовый скрипт:

```bash
python test_payment_parser.py
```

## Структура проекта

```
1win_ar/
├── app.py                      # FastAPI приложение
├── login_manually_1win_ar.py   # Скрипт для ручного логина
├── test_payment_parser.py      # Тестовый скрипт
├── requirements.txt            # Зависимости Python
├── README.md                   # Документация
└── services/
    ├── __init__.py
    ├── payment_parser_ar.py    # Основной парсер
    ├── browser_pool.py         # Пул браузеров
    └── google_sheets.py       # Интеграция с Google Sheets
```

## Формат данных

Парсер извлекает следующие данные:

- `cvu` - CVU номер (20-25 цифр)
- `recipient` - Имя получателя
- `bank` - Название банка (обычно "Claro Pay")
- `amount` - Сумма платежа
- `method` - Метод оплаты (обычно "Claro Pay")
- `payment_type` - Тип оплаты ("Fiat" или "Crypto")
- `url` - URL страницы с данными
- `domain` - Домен сайта
- `screenshot_path` - Путь к скриншоту
- `provider_screenshot_path` - Путь к скриншоту провайдера

## Экспорт в Google Sheets

Данные экспортируются в следующий формат:

| Method | Type | Account | Date | Links | Screenshot | QR | Status | Bank | CVU |
|--------|------|---------|------|-------|------------|----|----|------|-----|
| Claro Pay | Fiat | ... | ... | ... | ... | | Success | ... | ... |

## Переменные окружения

- `GOOGLE_SHEETS_ACCESS_TOKEN` - OAuth2 токен для доступа к Google Sheets API
- `PAYMENT_PARSER_USER_DATA_DIR` - Путь к директории профиля браузера (по умолчанию: `~/.cache/1win_ar/profile`)

## Логирование

Приложение использует структурированное логирование через `structlog`. Логи выводятся в формате JSON.

## Troubleshooting

### Проблемы с логином

Если парсер не может войти на сайт:

1. Выполните ручной логин через `login_manually_1win_ar.py`
2. Используйте `skip_login=true` в запросах API
3. Проверьте правильность учетных данных

### Проблемы с блокировкой профиля

Если возникают ошибки с блокировкой профиля браузера:

```bash
rm -rf ~/.cache/1win_ar/profile/SingletonLock
rm -rf ~/.cache/1win_ar/profile/SingletonSocket
```

### Проблемы с Google Sheets

Убедитесь, что:
- Установлен `GOOGLE_SHEETS_ACCESS_TOKEN`
- Токен имеет права на запись в таблицу
- URL таблицы корректный

## Лицензия

Проект для внутреннего использования.
