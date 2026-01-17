# Использование Persistent Context для сохранения авторизации

## Описание

Парсер теперь поддерживает **persistent context** - это позволяет сохранять cookies и session между запусками. Это означает, что вы можете один раз залогиниться вручную, и парсер будет автоматически использовать сохраненную авторизацию в последующих запусках.

## Как это работает

1. **Первый запуск с логином** - вы указываете email/password, парсер логинится и сохраняет cookies в профиль браузера
2. **Последующие запуски** - парсер автоматически обнаруживает сохраненную авторизацию и пропускает логин

## Настройка

### Вариант 1: Автоматический (рекомендуется)

Просто включите `use_persistent_context=true` (по умолчанию включено):

```bash
curl -X POST "http://localhost:8011/parse_payment_data_ar" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "perymury78@gmail.com",
    "password": "%m^%G5\"}4m",
    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit?gid=516142479#gid=516142479",
    "use_persistent_context": true,
    "skip_login": false
  }'
```

При первом запуске парсер:
- Залогинится с указанными данными
- Сохранит cookies в `~/.cache/mirrors_api/1win_ar_profile/`

При последующих запусках парсер:
- Автоматически проверит, авторизован ли пользователь
- Если да - пропустит логин (`skip_login` будет установлен автоматически)
- Если нет - выполнит логин снова

### Вариант 2: Ручной логин (для первого раза)

Если вы хотите вручную залогиниться первый раз:

1. Установите переменную окружения для пути к профилю:
```bash
export PAYMENT_PARSER_USER_DATA_DIR="$HOME/.cache/mirrors_api/1win_ar_profile"
```

2. Запустите браузер с persistent context в headless=false режиме:
```bash
python3 -c "
from playwright.async_api import async_playwright
import asyncio
import os

async def login():
    user_data_dir = os.path.expanduser('~/.cache/mirrors_api/1win_ar_profile')
    os.makedirs(user_data_dir, exist_ok=True)
    
    playwright = await async_playwright().start()
    context = await playwright.chromium.launch_persistent_context(
        user_data_dir,
        headless=False,  # Видимый браузер для ручного логина
        viewport={'width': 1920, 'height': 1080}
    )
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto('https://1win.lat/')
    print('Браузер открыт. Войдите вручную и нажмите Enter после входа...')
    input()
    await context.close()
    await playwright.stop()
    print('Авторизация сохранена!')

asyncio.run(login())
"
```

3. Теперь запускайте парсер с `skip_login=true`:
```bash
curl -X POST "http://localhost:8011/parse_payment_data_ar" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "perymury78@gmail.com",
    "password": "%m^%G5\"}4m",
    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit?gid=516142479#gid=516142479",
    "use_persistent_context": true,
    "skip_login": true
  }'
```

## Параметры API

- `use_persistent_context` (bool, default: `true`) - Использовать persistent context для сохранения cookies/session
- `skip_login` (bool, default: `false`) - Пропустить логин (если уже авторизован)

## Где хранятся данные

Профиль браузера сохраняется в:
```
~/.cache/mirrors_api/1win_ar_profile/
```

Или можно задать другой путь через переменную окружения:
```bash
export PAYMENT_PARSER_USER_DATA_DIR="/path/to/your/profile"
```

## Преимущества

1. ✅ Не нужно вводить логин/пароль каждый раз
2. ✅ Сохраняется сессия между запусками
3. ✅ Быстрее работает (пропускает логин)
4. ✅ Меньше вероятность блокировки (меньше попыток логина)

## Важные замечания

- Профиль браузера хранит cookies, session storage и другие данные авторизации
- Если вы выйдете из аккаунта вручную, парсер не сможет использовать сохраненную сессию
- Для обновления авторизации просто запустите парсер с `skip_login=false`
- Профиль браузера можно удалить для сброса авторизации: `rm -rf ~/.cache/mirrors_api/1win_ar_profile/`
