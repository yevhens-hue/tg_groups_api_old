#!/bin/bash
# Скрипт для автоматической установки всех проектов на новом компьютере

set -e

echo "🚀 Установка Mirror Finder проектов"
echo "===================================="
echo ""

# Проверка Python
echo "📋 Проверка Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден! Установите Python 3.8 или выше"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python найден: $PYTHON_VERSION"
echo ""

# Проверка pip
echo "📋 Проверка pip..."
if ! command -v pip3 &> /dev/null; then
    echo "⚠️  pip3 не найден, устанавливаем..."
    python3 -m ensurepip --upgrade
fi
echo "✓ pip установлен"
echo ""

# Определяем директорию проекта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "📁 Рабочая директория: $SCRIPT_DIR"
echo ""

# Список проектов для установки
PROJECTS=(
    "indian_gambling_parser"
    "mirror_finder"
    "mirrors_api"
)

# Установка зависимостей для каждого проекта
for project in "${PROJECTS[@]}"; do
    if [ -d "$project" ]; then
        echo "📦 Установка зависимостей: $project"
        
        if [ -f "$project/requirements.txt" ]; then
            cd "$project"
            echo "   → Установка пакетов из requirements.txt..."
            pip3 install -r requirements.txt --quiet
            echo "   ✓ Зависимости установлены"
            
            # Специальная обработка для indian_gambling_parser
            if [ "$project" == "indian_gambling_parser" ]; then
                echo "   → Установка Playwright браузеров..."
                python3 -m playwright install chromium 2>&1 | grep -v "Downloading" || true
                echo "   ✓ Playwright браузеры установлены"
            fi
            
            cd ..
        else
            echo "   ⚠️  requirements.txt не найден, пропускаем"
        fi
        echo ""
    else
        echo "⚠️  Проект не найден: $project"
        echo ""
    fi
done

# Создание необходимых директорий
echo "📁 Создание директорий..."
for project in "${PROJECTS[@]}"; do
    if [ -d "$project" ]; then
        mkdir -p "$project/screenshots"
        mkdir -p "$project/storage_states"
        mkdir -p "$project/traces"
        echo "✓ Директории созданы для $project"
    fi
done
echo ""

# Проверка установки
echo "🔍 Проверка установки..."
echo ""

# Проверка импортов
for project in "${PROJECTS[@]}"; do
    if [ -d "$project" ]; then
        echo "   Проверка $project..."
        cd "$project"
        
        # Проверяем основные модули
        if python3 -c "import sys; sys.path.insert(0, '.'); import storage" 2>/dev/null; then
            echo "   ✓ storage модуль работает"
        fi
        
        if [ "$project" == "indian_gambling_parser" ]; then
            if python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
                echo "   ✓ Playwright работает"
            fi
        fi
        
        cd ..
    fi
done

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo ""
echo "1. Настройте Google Sheets (опционально):"
echo "   - Создайте Service Account в Google Cloud"
echo "   - Сохраните JSON как: indian_gambling_parser/google_credentials.json"
echo "   - См. indian_gambling_parser/GOOGLE_SHEETS_SETUP.md"
echo ""
echo "2. Запустите парсер:"
echo "   cd indian_gambling_parser"
echo "   python3 main_parser_playwright.py --merchant 1xbet --url https://indian.1xbet.com"
echo ""
echo "3. Или используйте другие проекты:"
echo "   cd mirror_finder"
echo "   python3 main_parser.py --help"
echo ""
