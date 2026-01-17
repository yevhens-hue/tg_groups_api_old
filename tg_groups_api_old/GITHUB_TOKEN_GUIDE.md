# 🔑 Как создать и использовать GitHub Personal Access Token

## Где показывается токен

**⚠️ ВАЖНО:** Токен показывается **ТОЛЬКО ОДИН РАЗ** - сразу после создания!

### После создания токена:

1. GitHub покажет токен в **зеленой рамке** на странице
2. Токен будет выглядеть примерно так: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
3. **Скопируйте его сразу** - после закрытия страницы он больше не будет виден!

### Где найти токен после создания:

- Токен появляется **на той же странице** где вы его создали
- Это страница: `https://github.com/settings/tokens`
- После создания вы увидите зеленую рамку с текстом типа:
  ```
  Make sure to copy your personal access token now. 
  You won't be able to see it again!
  
  ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  ```

## У вас уже есть токены

На скриншоте видно что у вас есть:
- **"tg-api-push"** - expires Jan 29 2026, scope: repo
- **"Render Deploy"** - expires Apr 4 2026, scope: repo, workflow, etc.

### Можно использовать существующий токен

Если вы помните значение токена "tg-api-push" - используйте его:
```bash
git push
# Username: yevhens-hue
# Password: [ваш токен tg-api-push]
```

### Если токен не помните

Создайте новый токен:

1. На странице `https://github.com/settings/tokens`
2. Нажмите **"Generate new token"** → **"Generate new token (classic)"**
3. Заполните:
   - **Note:** "tg-api-push-2" (или любое название)
   - **Expiration:** 90 days (или No expiration)
   - **Scopes:** отметьте `repo` (все права репозитория)
4. Нажмите **"Generate token"**
5. **⚠️ СКОПИРУЙТЕ ТОКЕН СРАЗУ** - он появится в зеленой рамке
6. Используйте токен при `git push`

## Использование токена

```bash
git push
```

При запросе credentials:
- **Username:** `yevhens-hue`
- **Password:** `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` (ваш токен, НЕ пароль!)

## Альтернатива: Сохранить токен в git credential helper

Чтобы не вводить токен каждый раз:

```bash
# macOS
git config --global credential.helper osxkeychain

# Linux
git config --global credential.helper store
```

После первого push с токеном, git запомнит credentials.

## Если токен потерян

Если вы не скопировали токен при создании:
1. **Удалите старый токен** (кнопка "Delete")
2. **Создайте новый токен**
3. **Скопируйте его сразу** при создании

## Альтернатива: Деплой через Render Dashboard

Если не получается push, можно задеплоить вручную:
1. Откройте: https://dashboard.render.com/web/srv-d4qq4224d50c73cfqvug
2. Settings → Manual Deploy → Deploy latest commit
3. Или загрузите файлы через Render Dashboard

