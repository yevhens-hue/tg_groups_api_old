# 🔧 Решение проблемы с git push

## Проблема
```
Missing or invalid credentials.
Authentication failed for 'https://github.com/yevhens-hue/tg_groups_api_old.git/'
```

## ✅ Коммит создан успешно
```
[main 64c33bf] Change date format to YYYY-MM-DD H:MM:SS
```

## Решения

### Вариант 1: Использовать SSH (рекомендуется)

```bash
# Изменить remote на SSH
git remote set-url origin git@github.com:yevhens-hue/tg_groups_api_old.git

# Push
git push
```

**Требования:**
- Настроен SSH ключ на GitHub
- Если нет - создайте: `ssh-keygen -t ed25519 -C "your_email@example.com"`

### Вариант 2: Personal Access Token

1. Создайте токен на GitHub:
   - Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate new token (classic)
   - Выберите scope: `repo`
   - Скопируйте токен

2. При push используйте:
   - Username: `yevhens-hue`
   - Password: `ваш_токен` (не пароль от GitHub!)

### Вариант 3: GitHub CLI

```bash
# Установите GitHub CLI (если нет)
# brew install gh  # на macOS

# Авторизуйтесь
gh auth login

# Push
git push
```

### Вариант 4: Ручной push через терминал

Откройте обычный терминал (не в Cursor) и выполните:
```bash
cd /Users/yevhen.shaforostov/tg_groups_api_old
git push
```

### Вариант 5: Деплой через Render Dashboard

Если не получается push, можно задеплоить через Render Dashboard:
1. Откройте: https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug
2. Settings → Manual Deploy → Deploy latest commit
3. Или загрузите файлы через Render Dashboard

## Проверка после push

После успешного push:
1. Проверьте что изменения на GitHub
2. Render автоматически задеплоит (если подключен auto-deploy)
3. Или запустите Manual Deploy в Render

## Текущий статус

✅ Коммит создан: `64c33bf Change date format to YYYY-MM-DD H:MM:SS`
⏳ Ожидает push в GitHub

