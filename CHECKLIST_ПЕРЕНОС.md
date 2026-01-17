# ✅ Чеклист для переноса проектов на новый компьютер

## 📦 Подготовка к переносу

- [ ] Создать резервную копию всех проектов
  ```bash
  cd /Users/yevhen.shaforostov
  ./create_projects_backup.sh
  ```
- [ ] Проверить размер архива (должен быть ~500MB - 1GB)
- [ ] Убедиться, что `google_credentials.json` включён в архив (теперь включён автоматически)

## 🚚 Перенос архива

Выберите один из способов:

- [ ] **Вариант A**: Скопировать на USB/внешний диск
  ```bash
  cp projects_backup_*.tar.gz /Volumes/YourUSB/
  ```

- [ ] **Вариант B**: Загрузить в облачное хранилище (Google Drive / Dropbox / iCloud)

- [ ] **Вариант C**: Передать через сеть (rsync / scp)
  ```bash
  scp projects_backup_*.tar.gz user@new-computer:/path/to/
  ```

## 💻 Установка на новом компьютере

### 1. Распаковка

- [ ] Распаковать архив
  ```bash
  tar -xzf projects_backup_*.tar.gz
  ```

- [ ] Переместить проекты в нужную директорию
  ```bash
  mv indian_gambling_parser ~/
  mv mirror_finder ~/
  mv mirrors_api ~/
  # и т.д.
  ```

### 2. Установка Python и зависимостей

- [ ] Убедиться, что Python 3 установлен
  ```bash
  python3 --version
  ```

- [ ] Установить pip (если не установлен)
  ```bash
  python3 -m ensurepip --upgrade
  ```

- [ ] Установить зависимости для каждого проекта:
  ```bash
  # indian_gambling_parser
  cd ~/indian_gambling_parser
  pip3 install -r requirements.txt
  
  # mirror_finder
  cd ~/mirror_finder
  pip3 install -r requirements.txt
  
  # mirrors_api
  cd ~/mirrors_api
  pip3 install -r requirements.txt
  ```

### 3. Установка Playwright браузеров

- [ ] Установить Chromium для Playwright
  ```bash
  cd ~/indian_gambling_parser
  python3 -m playwright install chromium
  ```

### 4. Проверка конфигурационных файлов

- [ ] Проверить наличие `google_credentials.json` в проектах (должен быть в архиве)
  ```bash
  # На новом компьютере после распаковки
  ls ~/indian_gambling_parser/google_credentials.json
  ```

- [ ] Проверить наличие `.env` файлов (должны быть в архиве)
- [ ] Проверить пути в конфигурационных файлах

### 5. Проверка работоспособности

- [ ] Проверить импорты Python
  ```bash
  cd ~/indian_gambling_parser
  python3 -c "from storage import Storage; print('OK')"
  ```

- [ ] Проверить синтаксис файлов
  ```bash
  python3 -m py_compile *.py
  ```

- [ ] Запустить тестовую команду парсера (если нужно)
  ```bash
  cd ~/indian_gambling_parser
  python3 main_parser_playwright.py --list-merchants
  ```

## 🔐 Безопасность

- [ ] Удалить архив после успешного переноса (если содержит секреты)
- [ ] Проверить `.gitignore` перед коммитом в Git (если используете)
- [ ] Не загружать `google_credentials.json` в публичные репозитории

## 📝 Документация

- [ ] Проверить пути в документации (если изменилась структура)
- [ ] Обновить пути в `.md` и `.txt` файлах при необходимости

## ✅ Итоговая проверка

- [ ] Все проекты распакованы и работают
- [ ] Все зависимости установлены
- [ ] Playwright браузеры установлены
- [ ] Конфигурационные файлы перенесены
- [ ] Тестовые запуски прошли успешно

---

## 🆘 Если что-то не работает

1. Проверьте версию Python (`python3 --version` должен быть 3.8+)
2. Проверьте, что все зависимости установлены (`pip3 list`)
3. Проверьте пути к файлам в коде
4. Проверьте наличие `google_credentials.json` (если нужен для Google Sheets)
