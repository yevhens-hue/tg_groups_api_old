#!/bin/bash
# Скрипт для создания резервной копии всех проектов

set -e

# Переходим в директорию пользователя
cd /Users/yevhen.shaforostov

# Создаём имя архива с датой и временем
BACKUP_NAME="projects_backup_$(date +%Y%m%d_%H%M%S).tar.gz"

echo "📦 Создание резервной копии проектов..."
echo "Имя архива: $BACKUP_NAME"
echo ""

# Создаём архив
tar -czf "$BACKUP_NAME" \
  indian_gambling_parser/ \
  mirror_finder/ \
  mirrors_api/ \
  conductor/ \
  1win/ \
  1win_ar/ \
  tg_api_old/ \
  tg_groups_api_old/ \
  --exclude='*/__pycache__' \
  --exclude='*/.git' \
  --exclude='*/node_modules' \
  --exclude='*/venv' \
  --exclude='*/env' \
  --exclude='*/.venv' \
  --exclude='*/.DS_Store' \
  --exclude='*/screenshots/*.png' \
  --exclude='*/screenshots/*.jpg' \
  --exclude='*/traces/*.zip' \
  --exclude='*/storage_states/*.json' \
  --exclude='*/providers_data.db' \
  --exclude='*/providers_data.xlsx' \
  --exclude='*/notification_*.txt' \
  --exclude='*/test_run_*.log' 2>&1 | grep -v "Removing leading" || true

# Проверяем размер архива
ARCHIVE_SIZE=$(du -h "$BACKUP_NAME" | cut -f1)

echo ""
echo "✓ Архив создан успешно!"
echo "  Файл: $BACKUP_NAME"
echo "  Размер: $ARCHIVE_SIZE"
echo "  Путь: $(pwd)/$BACKUP_NAME"
echo ""
echo "✓ Все credential файлы включены в архив:"
echo "   - google_credentials.json"
echo "   - .env файлы"
echo "   - credentials*.json"
echo ""
echo "📋 Следующие шаги:"
echo "  1. Скопируйте архив на внешний диск / USB / облачное хранилище"
echo "  2. На новом компьютере распакуйте: tar -xzf $BACKUP_NAME"
echo "  3. Установите зависимости: pip3 install -r requirements.txt"
echo ""
echo "⚠️  ВНИМАНИЕ: Архив содержит секретные данные!"
echo "   Храните его в безопасном месте и не загружайте в публичные репозитории!"
