#!/bin/bash

# Скрипт для создания архива проекта для переноса на другой компьютер
# Включает все файлы, включая секретные (session, .env если есть)

set -e

PROJECT_NAME="tg_groups_api"
ARCHIVE_NAME="${PROJECT_NAME}_transfer_$(date +%Y%m%d_%H%M%S).tar.gz"
TEMP_DIR=$(mktemp -d)
ARCHIVE_DIR="${TEMP_DIR}/${PROJECT_NAME}"

echo "📦 Создание архива для переноса проекта..."
echo "Архив: ${ARCHIVE_NAME}"
echo ""

# Создаем директорию для архива
mkdir -p "${ARCHIVE_DIR}"

# Копируем все Python файлы
echo "📄 Копирую Python файлы..."
cp -v *.py "${ARCHIVE_DIR}/" 2>/dev/null || true

# Копируем конфигурационные файлы
echo "⚙️  Копирую конфигурационные файлы..."
cp -v requirements*.txt "${ARCHIVE_DIR}/" 2>/dev/null || true
cp -v render.yaml "${ARCHIVE_DIR}/" 2>/dev/null || true
cp -v start.sh "${ARCHIVE_DIR}/" 2>/dev/null || true
cp -v .gitignore "${ARCHIVE_DIR}/" 2>/dev/null || true

# Копируем секретные файлы (важно для переноса!)
echo "🔐 Копирую секретные файлы..."
cp -v .env "${ARCHIVE_DIR}/" 2>/dev/null || echo "⚠️  .env не найден (будет создан на новом компьютере)"
cp -v *.session "${ARCHIVE_DIR}/" 2>/dev/null || true
cp -v *.session-journal "${ARCHIVE_DIR}/" 2>/dev/null || true

# Копируем тесты
echo "🧪 Копирую тесты..."
mkdir -p "${ARCHIVE_DIR}/tests"
cp -rv tests/* "${ARCHIVE_DIR}/tests/" 2>/dev/null || true

# Копируем документацию
echo "📚 Копирую документацию..."
cp -v *.md "${ARCHIVE_DIR}/" 2>/dev/null || true
cp -v *.sh "${ARCHIVE_DIR}/" 2>/dev/null || true

# Копируем другие важные файлы
echo "📋 Копирую другие файлы..."
cp -v context.py "${ARCHIVE_DIR}/" 2>/dev/null || true

# Исключаем ненужное
echo "🗑️  Исключаю ненужные файлы..."
rm -rf "${ARCHIVE_DIR}/__pycache__" 2>/dev/null || true
rm -rf "${ARCHIVE_DIR}/tests/__pycache__" 2>/dev/null || true
rm -rf "${ARCHIVE_DIR}/tests/tests/__pycache__" 2>/dev/null || true
find "${ARCHIVE_DIR}" -name "*.pyc" -delete 2>/dev/null || true
find "${ARCHIVE_DIR}" -name ".DS_Store" -delete 2>/dev/null || true

# Создаем README для переноса
cat > "${ARCHIVE_DIR}/TRANSFER_README.md" << 'EOF'
# 📦 Инструкция по переносу проекта

## На новом компьютере выполните:

### 1. Распакуйте архив
```bash
tar -xzf tg_groups_api_transfer_*.tar.gz
cd tg_groups_api
```

### 2. Создайте виртуальное окружение
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows
```

### 3. Установите зависимости
```bash
pip install -r requirements.txt
```

### 4. Настройте секретные файлы

#### Если .env не было в архиве, создайте его:
```bash
# Скопируйте .env.example или создайте вручную
nano .env
```

Добавьте необходимые переменные окружения:
```
TG_API_ID=ваш_api_id
TG_API_HASH=ваш_api_hash
TG_SESSION_STRING=ваша_сессия
# И другие переменные если нужны
```

#### Проверьте session файл:
```bash
ls -la *.session
```

Если session файл отсутствует, создайте его:
```bash
python login.py
```

### 5. Запустите локально
```bash
./start.sh
# или
uvicorn app:app --host 0.0.0.0 --port 8010
```

### 6. Проверьте работоспособность
```bash
curl http://localhost:8010/health
```

## Важные файлы

- `*.session` - Telegram сессия (важно сохранить!)
- `.env` - Переменные окружения (если был в архиве)
- `requirements.txt` - Зависимости Python
- `app.py` - Главный файл приложения
- `tg_service.py` - Telegram сервис

## Деплой на Render

Если нужно задеплоить на Render, см. `DEPLOY.md` или `QUICK_DEPLOY.md`

## Проблемы?

- Если не работает сессия - запустите `python login.py`
- Если не работает .env - проверьте переменные окружения
- Если ошибки импорта - проверьте `pip install -r requirements.txt`
EOF

# Создаем список файлов в архиве
echo "📋 Создаю список файлов..."
find "${ARCHIVE_DIR}" -type f | sort > "${ARCHIVE_DIR}/FILES_LIST.txt"

# Создаем архив
echo ""
echo "🗜️  Создаю архив..."
cd "${TEMP_DIR}"
tar -czf "${OLDPWD}/${ARCHIVE_NAME}" "${PROJECT_NAME}/"

# Подсчитываем размер
ARCHIVE_SIZE=$(du -h "${OLDPWD}/${ARCHIVE_NAME}" | cut -f1)

# Очищаем временную директорию
rm -rf "${TEMP_DIR}"

echo ""
echo "✅ Архив создан успешно!"
echo ""
echo "📦 Файл: ${ARCHIVE_NAME}"
echo "📊 Размер: ${ARCHIVE_SIZE}"
echo ""
echo "📋 Включенные файлы:"
echo "   ✅ Все Python файлы (*.py)"
echo "   ✅ Конфигурация (requirements.txt, render.yaml, start.sh)"
echo "   ✅ Секретные файлы (.env, *.session)"
echo "   ✅ Тесты (tests/)"
echo "   ✅ Документация (*.md)"
echo ""
echo "📖 Инструкция по переносу находится в архиве: TRANSFER_README.md"
echo ""
echo "🔐 ВАЖНО: Архив содержит секретные файлы!"
echo "   • Не публикуйте архив в публичных местах"
echo "   • Передайте архив безопасным способом (USB, шифрование, и т.д.)"
echo ""
echo "🚀 Для переноса на новый компьютер:"
echo "   tar -xzf ${ARCHIVE_NAME}"
echo "   cd ${PROJECT_NAME}"
echo "   # Следуйте инструкциям в TRANSFER_README.md"
