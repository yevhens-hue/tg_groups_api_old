# 🚀 Настройка GitHub репозитория

## Шаг 1: Настройка Git (если ещё не настроено)

```bash
# Установите ваше имя и email для Git
git config --global user.name "Yevhen"
git config --global user.email "ваш-email@example.com"

# Проверьте настройки
git config --global --list
```

## Шаг 2: Инициализация Git репозитория

```bash
cd /Users/yevhen.shaforostov

# Инициализируем Git репозиторий
git init

# Проверяем статус
git status
```

## Шаг 3: Создание репозитория на GitHub

1. Перейдите на https://github.com/new
2. Войдите в аккаунт **Yevhen (yevhens-hue)**
3. Заполните форму:
   - **Repository name**: `mirror_finder` (или другое имя)
   - **Description**: (опционально) "Indian gambling parser and mirror finder"
   - **Visibility**: 
     - ⚠️ **Private** (рекомендуется, так как могут быть секреты)
     - или **Public** (если уверены, что нет секретов)
   - **НЕ** добавляйте README, .gitignore, license (у нас уже есть)
4. Нажмите **Create repository**

## Шаг 4: Добавление файлов и первый коммит

```bash
cd /Users/yevhen.shaforostov

# Добавляем все файлы (кроме тех, что в .gitignore)
git add .

# Проверяем, что credential файлы НЕ добавлены
git status | grep -i credential
git status | grep -i "\.env"

# Если видите credential файлы в статусе - ОСТАНОВИТЕСЬ!
# Проверьте .gitignore и убедитесь, что они исключены

# Создаём первый коммит
git commit -m "Initial commit: mirror_finder projects"

# Проверяем, что в коммите нет credential файлов
git show --name-only HEAD | grep -i credential
git show --name-only HEAD | grep -i "\.env"
```

## Шаг 5: Подключение к GitHub

```bash
# Замените YOUR_USERNAME и REPO_NAME на ваши значения
# Например: git@github.com:yevhens-hue/mirror_finder.git

git remote add origin git@github.com:YOUR_USERNAME/REPO_NAME.git

# Или через HTTPS (если SSH не настроен):
# git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# Проверяем подключение
git remote -v
```

## Шаг 6: Push на GitHub

```bash
# Отправляем код на GitHub
git branch -M main
git push -u origin main
```

Если используете HTTPS, GitHub попросит ввести логин и пароль (или Personal Access Token).

## ⚠️ ВАЖНО: Проверка безопасности перед push

### Перед первым push обязательно проверьте:

```bash
# 1. Проверьте, что credential файлы НЕ в индексе
git ls-files | grep -i credential
git ls-files | grep -i "\.env"

# 2. Проверьте содержимое .gitignore
cat .gitignore | grep -i credential

# 3. Если нашли credential файлы в git ls-files:
#    Удалите их из индекса:
#    git rm --cached path/to/credential/file
#    git commit -m "Remove credential files"
```

## 🔐 Настройка SSH ключа (рекомендуется)

Если хотите использовать SSH вместо HTTPS:

```bash
# Проверьте, есть ли уже SSH ключ
ls -la ~/.ssh/id_*.pub

# Если нет - создайте новый
ssh-keygen -t ed25519 -C "ваш-email@example.com"

# Скопируйте публичный ключ
cat ~/.ssh/id_ed25519.pub

# Добавьте ключ на GitHub:
# 1. Перейдите: https://github.com/settings/keys
# 2. Нажмите "New SSH key"
# 3. Вставьте содержимое ~/.ssh/id_ed25519.pub
# 4. Сохраните
```

## 📋 Структура репозитория

После push на GitHub будет загружено:

✅ **Включено:**
- Весь исходный код Python
- Конфигурационные файлы (без секретов)
- Документация (.md, .txt)
- requirements.txt
- .gitignore

❌ **Исключено (через .gitignore):**
- `google_credentials.json`
- `*.credentials*.json`
- `.env` файлы
- `__pycache__/`
- `venv/`, `env/`
- `*.db`, `*.xlsx`
- `screenshots/`, `traces/`
- `storage_states/`
- Логи и уведомления

## 🔄 Обновление репозитория

После изменений:

```bash
git add .
git commit -m "Описание изменений"
git push
```

## 🛡️ Если случайно закоммитили credential файлы

Если вы случайно закоммитили credential файлы:

```bash
# 1. Удалите из Git истории (но оставьте локально)
git rm --cached google_credentials.json
git rm --cached .env

# 2. Добавьте в .gitignore (если ещё нет)
echo "google_credentials.json" >> .gitignore
echo ".env" >> .gitignore

# 3. Закоммитьте изменения
git add .gitignore
git commit -m "Remove credentials and update .gitignore"

# 4. Если уже запушили - нужно переписать историю
# ⚠️ Осторожно! Это изменит историю Git
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch google_credentials.json .env" \
  --prune-empty --tag-name-filter cat -- --all

# 5. Force push (только если уверены!)
# git push --force
```

## 📝 Рекомендации

1. **Используйте Private репозиторий** - если есть credential файлы
2. **Проверяйте .gitignore** перед каждым коммитом
3. **Используйте SSH** для удобства работы
4. **Делайте регулярные коммиты** с понятными сообщениями
