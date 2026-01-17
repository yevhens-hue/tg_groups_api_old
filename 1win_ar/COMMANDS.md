# 📋 КОМАНДЫ ДЛЯ РАБОТЫ С ПАРСЕРОМ 1WIN AR

## 🚀 Основные команды

### 1. ПЕРВЫЙ ЗАПУСК (С ЛОГИНОМ)
```bash
python3 first_login.py
```
Создаст сессию и сохранит cookies для последующих запусков.

### 2. ЗАПУСК ПАРСЕРА В ПРОДАКШНЕ
```bash
python3 run_parser_ar.py
```
Использует сохраненную сессию, парсит данные, загружает скриншоты в Drive и добавляет данные в Google Sheets.

### 3. ОБНОВИТЬ GOOGLE TOKEN
```bash
python3 get_google_token.py
```
Получает новый токен с правами для Google Sheets и Drive API.

---

## 📸 Проверка скриншотов

### Посмотреть последние скриншоты провайдера:
```bash
ls -lht ~/.cache/1win_ar/screenshots/provider/ | head -5
```

### Посмотреть скриншоты форм:
```bash
ls -lht ~/.cache/1win_ar/screenshots/payment_form_*.png 2>/dev/null | head -5
```

### Открыть папку со скриншотами:
```bash
open ~/.cache/1win_ar/screenshots/provider/
```

---

## 🔍 Проверка статуса

### Проверить, есть ли сохраненная сессия:
```bash
test -d ~/.cache/1win_ar/profile && echo "✅ Сессия найдена" || echo "❌ Сессия не найдена"
```

### Проверить токен Google:
```bash
python3 << 'PYEOF'
import json
try:
    with open('token.json', 'r') as f:
        token = json.load(f)
    scopes = token.get('scopes', [])
    has_drive = any('drive' in s for s in scopes)
    print(f"✅ Токен найден")
    print(f"   Scopes: {scopes}")
    print(f"   Имеет Drive API: {'✅ Да' if has_drive else '❌ Нет'}")
except FileNotFoundError:
    print("❌ Токен не найден. Запустите: python3 get_google_token.py")
PYEOF
```

---

## 🗑️ Очистка

### Удалить сессию (для перелогина):
```bash
rm -rf ~/.cache/1win_ar/profile
```

### Удалить все скриншоты:
```bash
rm -rf ~/.cache/1win_ar/screenshots/*
```

---

## 🌐 FastAPI сервер (опционально)

### Запустить API сервер:
```bash
uvicorn app:app --host 0.0.0.0 --port 8011
```

### Тестовый запрос к API:
```bash
curl -X POST "http://localhost:8011/parse_payment_data_ar" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "perymury78@gmail.com",
    "password": "пароль",
    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit#gid=516142479",
    "access_token": "ваш_токен"
  }'
```

---

## 📁 Полезные ссылки

### Папка со скриншотами в Google Drive (общая папка, как в проекте 1win_STD):
```bash
open "https://drive.google.com/drive/u/1/folders/1wZeGXBkEoud0blwl06J7DEAHPTVAFaL4"
```

### Google Sheets таблица:
```bash
open "https://docs.google.com/spreadsheets/d/1kw74QoJGHKlaLOD-FGEPRU0DXKOAh4S-8_1Bz6burFE/edit#gid=516142479"
```

---

## 📂 Пути и директории

- **Скриншоты провайдера (локально)**: `~/.cache/1win_ar/screenshots/provider/`
- **Скриншоты форм (локально)**: `~/.cache/1win_ar/screenshots/payment_form_*.png`
- **Браузерная сессия**: `~/.cache/1win_ar/profile/`
- **Google Drive папка (общая, как в проекте 1win_STD)**: `1wZeGXBkEoud0blwl06J7DEAHPTVAFaL4`

---

## ⚙️ Переменные окружения (опционально)

```bash
# Переопределить путь к профилю браузера
export PAYMENT_PARSER_USER_DATA_DIR=~/.cache/1win_ar/profile

# Переопределить ID папки Drive для всех скриншотов (общая папка, как в проекте 1win_STD)
export DRIVE_SCREENSHOTS_FOLDER_ID=1wZeGXBkEoud0blwl06J7DEAHPTVAFaL4

# Установить Google Sheets токен
export GOOGLE_SHEETS_ACCESS_TOKEN=ваш_токен
```
