# Mirror Finder & Indian Gambling Parser

Проекты для парсинга провайдеров платежных систем и поиска зеркал.

## 📁 Структура проектов

- **`indian_gambling_parser/`** - Парсер провайдеров для индийских гемблинг-сайтов
- **`mirror_finder/`** - Поиск зеркал сайтов
- **`mirrors_api/`** - API для работы с зеркалами
- **`conductor/`** - Оркестрация задач
- Другие проекты...

## 🚀 Быстрая установка на новом компьютере

### Требования

- Python 3.8 или выше
- Git
- Доступ к интернету

### Шаг 1: Клонирование репозитория

```bash
# Клонируйте репозиторий
git clone https://github.com/yevhens-hue/mirror_finder.git
cd mirror_finder
```

### Шаг 2: Автоматическая установка

```bash
# Запустите скрипт установки
./setup_new_computer.sh
```

Скрипт автоматически:
- Проверит версию Python
- Установит все зависимости
- Установит Playwright браузеры
- Создаст необходимые директории

### Шаг 3: Ручная установка (если скрипт не работает)

```bash
# Установите зависимости для каждого проекта
cd indian_gambling_parser
pip3 install -r requirements.txt
python3 -m playwright install chromium

cd ../mirror_finder
pip3 install -r requirements.txt

cd ../mirrors_api
pip3 install -r requirements.txt
```

### Шаг 4: Настройка Google Sheets (опционально)

Если нужен экспорт в Google Sheets:

1. Создайте Service Account в Google Cloud Console
2. Скачайте JSON ключ
3. Сохраните как `indian_gambling_parser/google_credentials.json`
4. Предоставьте доступ к Google Таблице (email из JSON)

Подробная инструкция: `indian_gambling_parser/GOOGLE_SHEETS_SETUP.md`

## 📖 Документация по проектам

### Indian Gambling Parser

**Основной проект для парсинга провайдеров**

```bash
cd indian_gambling_parser
python3 main_parser_playwright.py --merchant 1xbet --url https://indian.1xbet.com
```

**Документация:**
- `indian_gambling_parser/README.md` - Общее описание
- `indian_gambling_parser/ЗАПУСК.md` - Инструкция по запуску
- `indian_gambling_parser/QUICKSTART.md` - Быстрый старт

**Основные возможности:**
- Автоматический парсинг провайдеров платежных систем
- Заполнение форм с личными данными
- Обнаружение редиректов на домены провайдеров
- Сохранение скриншотов
- Экспорт в SQLite, Excel, Google Sheets

### Mirror Finder

**Поиск и проверка зеркал сайтов**

```bash
cd mirror_finder
python3 main_parser.py --help
```

**Документация:**
- `mirror_finder/README_PARSER.md` - Описание парсера
- `mirror_finder/README_PLAYWRIGHT.md` - Playwright версия

### Mirrors API

**REST API для работы с зеркалами**

```bash
cd mirrors_api
python3 api.py
```

## 🔧 Настройка окружения

### Переменные окружения (опционально)

Создайте `.env` файл в корне проекта:

```bash
# Google Sheets
GOOGLE_CREDENTIALS_PATH=/path/to/google_credentials.json
GOOGLE_SHEET_ID=your_sheet_id

# Другие настройки
DEBUG=true
```

## 📋 Зависимости

Основные зависимости (устанавливаются автоматически):

- **Playwright** - Автоматизация браузера
- **BeautifulSoup4** - Парсинг HTML
- **Requests** - HTTP запросы
- **Pandas** - Работа с данными
- **FastAPI** - REST API
- **gspread** - Google Sheets API

Полный список в `requirements.txt` каждого проекта.

## 🛠️ Разработка

### Структура репозитория

```
mirror_finder/
├── indian_gambling_parser/    # Парсер провайдеров
├── mirror_finder/             # Поиск зеркал
├── mirrors_api/                # API для зеркал
├── conductor/                  # Оркестрация
├── README.md                   # Этот файл
├── setup_new_computer.sh       # Скрипт установки
└── .gitignore                  # Исключения Git
```

### Добавление изменений

```bash
git add .
git commit -m "Описание изменений"
git push
```

## ⚠️ Важные замечания

1. **Credential файлы** не включены в репозиторий (безопасность)
2. **Базы данных** и временные файлы исключены из Git
3. Используйте **Private репозиторий** если есть секреты
4. **Playwright** требует установки браузеров после установки пакетов

## 📞 Поддержка

- GitHub Issues: https://github.com/yevhens-hue/mirror_finder/issues
- Документация в папках проектов

## 📄 Лицензия

[Укажите лицензию если нужно]

---

**Последнее обновление:** 2025-01-17
