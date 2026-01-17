# 📦 Инструкция по переносу проекта на другой компьютер

## ✅ Архив создан успешно!

**Файл архива:** `tg_groups_api_transfer_20260117_130723.tar.gz`  
**Размер:** ~172KB  
**Включает все необходимые файлы, включая секретные**

## 📋 Что включено в архив:

✅ **Код проекта:**
- Все Python файлы (*.py)
- Конфигурация (requirements.txt, render.yaml, start.sh, .gitignore)

✅ **Секретные файлы:**
- `.env` - переменные окружения
- `tg_groups_session.session` - Telegram сессия

✅ **Тесты:**
- Вся директория tests/

✅ **Документация:**
- Все .md файлы (DEPLOY.md, README.md, и т.д.)
- Скрипты (*.sh)

---

## 🚀 На новом компьютере:

### Шаг 1: Перенесите архив
Скопируйте `tg_groups_api_transfer_*.tar.gz` на новый компьютер:
- USB флешка
- Облачное хранилище (Dropbox, Google Drive)
- SSH: `scp tg_groups_api_transfer_*.tar.gz user@new-computer:/path/`

### Шаг 2: Распакуйте архив
```bash
tar -xzf tg_groups_api_transfer_*.tar.gz
cd tg_groups_api
```

### Шаг 3: Создайте виртуальное окружение
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или на Windows:
.venv\Scripts\activate
```

### Шаг 4: Установите зависимости
```bash
pip install -r requirements.txt
```

### Шаг 5: Проверьте секретные файлы
```bash
# Проверьте что .env файл на месте
ls -la .env

# Проверьте что session файл на месте
ls -la *.session
```

Если файлы отсутствуют, создайте их:
```bash
# Создайте .env (скопируйте из старого проекта или создайте вручную)
nano .env
# Добавьте: TG_API_ID, TG_API_HASH, TG_SESSION_STRING

# Если session файла нет, создайте его:
python login.py
```

### Шаг 6: Запустите локально
```bash
./start.sh
# или
uvicorn app:app --host 0.0.0.0 --port 8010
```

### Шаг 7: Проверьте работоспособность
```bash
curl http://localhost:8010/health
```

---

## 🔐 Безопасность

**ВАЖНО:** Архив содержит секретные файлы!

✅ **Безопасные способы переноса:**
- USB флешка (зашифрованная)
- Облачное хранилище с шифрованием
- SSH/SCP напрямую между компьютерами
- Зашифрованный архив (7z, zip с паролем)

❌ **НЕ ДЕЛАЙТЕ:**
- Не публикуйте архив в публичных местах
- Не отправляйте по незашифрованной почте
- Не загружайте в публичный Git репозиторий

---

## 📖 Подробная инструкция

Полная инструкция находится в архиве: `TRANSFER_README.md`

---

## ❓ Проблемы?

### Ошибка "Module not found"
```bash
pip install -r requirements.txt
```

### Ошибка "Session not found"
```bash
python login.py
```

### Ошибка "TG_API_ID отсутствуют"
Проверьте `.env` файл:
```bash
cat .env
```

### Ошибка при запуске
Проверьте логи:
```bash
./start.sh
# или
python app.py
```

---

## ✨ После переноса

1. ✅ Проверьте что все работает локально
2. ✅ Настройте Git (если нужно):
   ```bash
   git remote -v
   git pull
   ```
3. ✅ Задеплойте на Render (если нужно):
   - См. `DEPLOY.md` или `QUICK_DEPLOY.md`
