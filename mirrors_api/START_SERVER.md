# Инструкция по запуску сервера

## Быстрый старт

### 1. Остановить старый процесс (если запущен)
```bash
./stop_server.sh
```

### 2. Запустить сервер

**Вариант A: Простой запуск**
```bash
./start_production.sh
```

**Вариант B: В фоне (с nohup)**
```bash
nohup ./start_production.sh > server.log 2>&1 &
```

**Вариант C: С Gunicorn**
```bash
./start_production_gunicorn.sh
```

### 3. Проверить работу
```bash
curl http://localhost:8011/health
```

## Если порт занят

### Найти процесс на порту 8011:
```bash
lsof -i :8011
```

### Остановить процесс:
```bash
./stop_server.sh
# или вручную:
kill $(lsof -ti :8011)
```

### Использовать другой порт:
```bash
PORT=8012 ./start_production.sh
```

## Полезные команды

### Проверить статус:
```bash
lsof -i :8011
curl http://localhost:8011/health
```

### Посмотреть логи (если запущен с nohup):
```bash
tail -f server.log
```

### Остановить сервер:
```bash
./stop_server.sh
```

## Troubleshooting

### "Address already in use"
- Запустите `./stop_server.sh`
- Или используйте другой порт: `PORT=8012 ./start_production.sh`

### "Module not found"
- Убедитесь, что виртуальное окружение активировано
- Установите зависимости: `pip install -r requirements.txt`

### Сервер не отвечает
- Проверьте логи
- Убедитесь, что `.env` файл настроен правильно
- Проверьте, что `SERPER_API_KEY` установлен


