#!/bin/bash

# Скрипт для переноса проекта на GitHub
# Автоматически создает репозиторий и пушит код

set -e

GITHUB_USER="yevhens-hue"
REPO_NAME="tg_groups_api_old"
GITHUB_URL="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

echo "🚀 Перенос проекта на GitHub"
echo "================================"
echo ""
echo "Пользователь: ${GITHUB_USER}"
echo "Репозиторий: ${REPO_NAME}"
echo "URL: ${GITHUB_URL}"
echo ""

# Проверяем что секретные файлы не в Git
echo "🔐 Проверка секретных файлов..."
if git ls-files | grep -qE "(\.env|\.session)"; then
    echo "❌ ОШИБКА: Секретные файлы найдены в Git!"
    echo "Удалите их перед пушем:"
    echo "  git rm --cached .env *.session"
    exit 1
else
    echo "✅ Секретные файлы не в Git - хорошо!"
fi

# Проверяем текущий remote
CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
echo ""
echo "📡 Текущий remote: ${CURRENT_REMOTE:-не установлен}"

# Предлагаем варианты
echo ""
echo "Выберите действие:"
echo "1) Создать новый репозиторий ${REPO_NAME} (рекомендуется)"
echo "2) Использовать существующий репозиторий"
echo "3) Изменить remote на ${GITHUB_URL}"
echo "4) Просто запушить в текущий remote"
read -p "Ваш выбор (1-4): " choice

case $choice in
    1)
        echo ""
        echo "📦 Создание нового репозитория..."
        echo ""
        echo "⚠️  ВАЖНО: Сначала создайте репозиторий на GitHub:"
        echo "   1. Перейдите на https://github.com/new"
        echo "   2. Название: ${REPO_NAME}"
        echo "   3. Описание: FastAPI service for Telegram groups search"
        echo "   4. НЕ добавляйте README, .gitignore, license"
        echo "   5. Нажмите 'Create repository'"
        echo ""
        read -p "Нажмите Enter когда репозиторий создан..."
        
        # Удаляем старый remote если есть
        if [ -n "$CURRENT_REMOTE" ]; then
            echo "🗑️  Удаляю старый remote..."
            git remote remove origin
        fi
        
        # Добавляем новый remote
        echo "➕ Добавляю новый remote..."
        git remote add origin "${GITHUB_URL}"
        ;;
    2)
        read -p "Введите URL репозитория: " repo_url
        if [ -n "$CURRENT_REMOTE" ]; then
            git remote set-url origin "$repo_url"
        else
            git remote add origin "$repo_url"
        fi
        ;;
    3)
        if [ -n "$CURRENT_REMOTE" ]; then
            git remote set-url origin "${GITHUB_URL}"
        else
            git remote add origin "${GITHUB_URL}"
        fi
        echo "✅ Remote изменен на ${GITHUB_URL}"
        ;;
    4)
        if [ -z "$CURRENT_REMOTE" ]; then
            echo "❌ Remote не установлен! Используйте вариант 1 или 3."
            exit 1
        fi
        echo "✅ Используем текущий remote: ${CURRENT_REMOTE}"
        ;;
    *)
        echo "❌ Неверный выбор"
        exit 1
        ;;
esac

# Добавляем все файлы
echo ""
echo "📋 Добавляю файлы..."
git add .

# Проверяем есть ли что коммитить
if git diff --staged --quiet; then
    echo "ℹ️  Нет изменений для коммита"
else
    echo "💾 Коммичу изменения..."
    git commit -m "Add transfer scripts, n8n integration docs, and deployment guides"
fi

# Показываем статус
echo ""
echo "📊 Статус перед пушем:"
git status --short

# Пушим
echo ""
echo "🚀 Пушим на GitHub..."
echo ""
read -p "Продолжить? (y/n): " confirm

if [ "$confirm" != "y" ]; then
    echo "❌ Отменено"
    exit 0
fi

# Пробуем запушить
if git push -u origin main 2>&1; then
    echo ""
    echo "✅ Успешно запушено на GitHub!"
    echo ""
    echo "🔗 Репозиторий: ${GITHUB_URL}"
    echo ""
    echo "📋 Следующие шаги:"
    echo "   1. Проверьте репозиторий на GitHub"
    echo "   2. Убедитесь что секретные файлы отсутствуют"
    echo "   3. Настройте GitHub Actions (если нужно)"
else
    echo ""
    echo "❌ Ошибка при пуше!"
    echo ""
    echo "Возможные причины:"
    echo "  1. Репозиторий не создан на GitHub"
    echo "  2. Проблемы с аутентификацией"
    echo ""
    echo "Решения:"
    echo "  1. Создайте репозиторий на https://github.com/new"
    echo "  2. Используйте Personal Access Token:"
    echo "     git remote set-url origin https://YOUR_TOKEN@github.com/${GITHUB_USER}/${REPO_NAME}.git"
    echo "  3. Или используйте SSH:"
    echo "     git remote set-url origin git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
    echo ""
    echo "См. PUSH_TO_GITHUB.md или GITHUB_TOKEN_GUIDE.md для подробностей"
    exit 1
fi
