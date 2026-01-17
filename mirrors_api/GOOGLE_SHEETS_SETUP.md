# Настройка Google Sheets API для парсера платежных данных

## Шаг 1: Получение Access Token

### Вариант A: Автоматический (рекомендуется)

Запустите скрипт для получения токена:

```bash
cd /Users/yevhen.shaforostov/mirrors_api
python3 get_google_token.py
```

Скрипт:
1. Откроет браузер для авторизации
2. Попросит разрешить доступ к Google Sheets
3. Сохранит токен в `token.json`
4. Выведет токен для использования

### Вариант B: Вручную через Google Cloud Console

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Выберите проект `scraper-483621`
3. Перейдите в **APIs & Services** > **Credentials**
4. Создайте OAuth 2.0 Client ID (если еще не создан)
5. Используйте полученный токен

## Шаг 2: Сохранение токена

После получения токена, добавьте его в `.env` файл:

```bash
# В .env файле
GOOGLE_SHEETS_ACCESS_TOKEN=ya29.a0AfH6SMC...
```

Или используйте переменную окружения:

```bash
export GOOGLE_SHEETS_ACCESS_TOKEN=ya29.a0AfH6SMC...
```

## Шаг 3: Проверка работы

Токен будет автоматически использоваться при экспорте в Google Sheets.

## Структура таблицы

Таблица должна иметь следующие колонки:

| A | B | C | D | E | F | G | H | I | J |
|---|---|---|---|---|---|---|---|---|---|
| Method | Type | Account | Date | Links | Screenshot | QR | Status | Bank | CVU |

## Что сохраняется в таблицу

- **Method**: Метод оплаты (Claro Pay)
- **Type**: Тип платежа (Fiat)
- **Account**: Получатель (Recipient)
- **Date**: Дата и время парсинга
- **Links**: Domain + URL (формат: "Domain: 1win.lat | https://...")
- **Screenshot**: Путь к файлу скриншота (`~/.cache/mirrors_api/screenshots/provider_claro_...png`)
- **QR**: QR код (если есть)
- **Status**: Success/Failed
- **Bank**: Название банка (Claro Pay)
- **CVU**: CVU номер (если найден)

## Где сохраняются скриншоты

Скриншоты сохраняются в:
```
~/.cache/mirrors_api/screenshots/
├── provider_claro_YYYYMMDD_HHMMSS.png  # Скриншот после выбора Claro Pay
└── payment_form_YYYYMMDD_HHMMSS.png    # Общий скриншот формы оплаты
```

## Обновление токена

Access token истекает через определенное время. Для автоматического обновления:

1. Скрипт `get_google_token.py` сохраняет refresh_token в `token.json`
2. При необходимости можно создать утилиту для автоматического обновления токена

## Troubleshooting

### Ошибка: "Google Sheets access token is required"
- Убедитесь, что токен установлен в `.env` или передан в запросе
- Проверьте, что токен не истек

### Ошибка: "Invalid credentials"
- Перезапустите `get_google_token.py` для получения нового токена
- Убедитесь, что credentials.json находится в корне проекта

### Токен истек
- Запустите `get_google_token.py` снова для получения нового токена
- Refresh token автоматически используется для обновления
