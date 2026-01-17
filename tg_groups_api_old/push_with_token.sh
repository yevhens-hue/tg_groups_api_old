#!/bin/bash
# Скрипт для push с токеном (обходит проблему с Cursor askpass)

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     🔧 PUSH С ТОКЕНОМ                                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Проверяем что есть коммит для push
if ! git log origin/main..HEAD --oneline | grep -q .; then
    echo "❌ Нет коммитов для push"
    exit 1
fi

echo "📋 Коммиты для push:"
git log origin/main..HEAD --oneline
echo ""

# Запрашиваем токен
read -sp "Введите ваш GitHub Personal Access Token: " TOKEN
echo ""

if [ -z "$TOKEN" ]; then
    echo "❌ Токен не введен"
    exit 1
fi

# Выполняем push с токеном в URL
echo "🚀 Выполняю push..."
GIT_ASKPASS=echo git push https://${TOKEN}@github.com/yevhens-hue/tg_groups_api_old.git main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Push выполнен успешно!"
    echo "💡 Render автоматически задеплоит изменения"
else
    echo ""
    echo "❌ Ошибка при push. Проверьте токен и права доступа."
    exit 1
fi

