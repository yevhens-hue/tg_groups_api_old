# 🚀 Перенос проекта на GitHub

## Текущая ситуация

- **Текущий remote:** `https://github.com/yevhens-hue/mirror_finder.git`
- **Проект:** `tg_groups_api_old`
- **Нужно:** Создать новый репозиторий или использовать существующий

## Вариант 1: Создать новый репозиторий (рекомендуется)

### Шаг 1: Создайте репозиторий на GitHub

1. Перейдите на https://github.com/new
2. Название: `tg_groups_api_old` (или `tg-groups-api`)
3. Описание: "FastAPI service for Telegram groups search with Telethon"
4. **НЕ** добавляйте README, .gitignore, license (они уже есть)
5. Нажмите "Create repository"

### Шаг 2: Измените remote и запушьте

```bash
# Удалите старый remote (если нужно)
git remote remove origin

# Добавьте новый remote
git remote add origin https://github.com/yevhens-hue/tg_groups_api_old.git

# Или если используете SSH:
git remote add origin git@github.com:yevhens-hue/tg_groups_api_old.git

# Добавьте все новые файлы
git add .

# Закоммитьте изменения
git commit -m "Add transfer scripts and n8n integration docs"

# Запушьте на GitHub
git push -u origin main
```

## Вариант 2: Использовать существующий репозиторий

Если хотите использовать существующий `mirror_finder`:

```bash
# Добавьте все новые файлы
git add .

# Закоммитьте
git commit -m "Add transfer scripts and n8n integration docs"

# Запушьте
git push origin main
```

## Вариант 3: Создать репозиторий через GitHub CLI (если установлен)

```bash
# Создайте репозиторий
gh repo create tg_groups_api_old --public --description "FastAPI service for Telegram groups search with Telethon"

# Измените remote
git remote set-url origin https://github.com/yevhens-hue/tg_groups_api_old.git

# Запушьте
git add .
git commit -m "Add transfer scripts and n8n integration docs"
git push -u origin main
```

## 🔐 Важно: Секретные файлы

**Проверьте что секретные файлы НЕ попадут в Git:**

```bash
# Проверьте что они в .gitignore
grep -E "(\.env|\.session)" .gitignore

# Проверьте что они не в Git
git ls-files | grep -E "(\.env|\.session)" || echo "✅ Секретные файлы не в Git"
```

Если секретные файлы уже в Git (не должно быть):
```bash
# Удалите их из Git (но оставьте локально)
git rm --cached .env *.session
git commit -m "Remove secret files from Git"
```

## 📋 Файлы для добавления

Новые файлы которые нужно добавить:
- `create_transfer_archive.sh` - скрипт для создания архива
- `TRANSFER_INSTRUCTIONS.md` - инструкция по переносу
- `N8N_ITEMS_EXTRACT.md` - инструкция по n8n
- Все остальные .md файлы (если еще не добавлены)

## ✅ После пуша

1. Проверьте репозиторий на GitHub
2. Убедитесь что секретные файлы отсутствуют
3. Обновите README если нужно
4. Настройте GitHub Actions (если нужно)

## 🆘 Проблемы с аутентификацией

Если возникнут проблемы с push (401, 403):

1. **Используйте Personal Access Token:**
   ```bash
   git remote set-url origin https://YOUR_TOKEN@github.com/yevhens-hue/tg_groups_api_old.git
   ```

2. **Или используйте SSH:**
   ```bash
   git remote set-url origin git@github.com:yevhens-hue/tg_groups_api_old.git
   ```

3. **Или используйте скрипт:**
   ```bash
   ./push_with_token.sh
   ```

См. `GITHUB_TOKEN_GUIDE.md` для подробностей.
