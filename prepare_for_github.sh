#!/bin/bash
# Скрипт для подготовки проекта к загрузке на GitHub

set -e

cd /Users/yevhen.shaforostov

echo "🔍 Проверка credential файлов..."

# Проверяем, что credential файлы не попадут в репозиторий
if git ls-files | grep -qi credential; then
    echo "❌ ОШИБКА: Найдены credential файлы в Git индексе!"
    echo "   Удалите их перед push на GitHub:"
    git ls-files | grep -i credential
    exit 1
fi

if git ls-files | grep -q "\.env"; then
    echo "❌ ОШИБКА: Найдены .env файлы в Git индексе!"
    echo "   Удалите их перед push на GitHub:"
    git ls-files | grep "\.env"
    exit 1
fi

echo "✓ Credential файлы не в индексе"

echo ""
echo "📋 Статус Git репозитория:"
git status --short | head -20

echo ""
echo "📊 Статистика файлов:"
echo "   Всего файлов в индексе: $(git ls-files | wc -l)"
echo "   Python файлов: $(git ls-files | grep '\.py$' | wc -l)"
echo "   Markdown файлов: $(git ls-files | grep '\.md$' | wc -l)"

echo ""
echo "✅ Проект готов к коммиту!"
echo ""
echo "📝 Следующие шаги:"
echo "   1. git commit -m 'Initial commit: mirror_finder projects'"
echo "   2. Создайте репозиторий на GitHub: https://github.com/new"
echo "   3. git remote add origin git@github.com:YOUR_USERNAME/REPO_NAME.git"
echo "   4. git push -u origin main"
echo ""
echo "📖 Подробная инструкция: см. НАСТРОЙКА_GITHUB.md"
