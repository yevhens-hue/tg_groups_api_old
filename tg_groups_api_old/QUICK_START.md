# ⚡ Быстрый старт на новом компьютере

## 1. Клонирование
```bash
git clone https://github.com/yevhens-hue/tg_groups_api_old.git
cd tg_groups_api_old
```

## 2. Установка
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## 3. Настройка
```bash
# Создайте .env файл
nano .env
```

Добавьте:
```env
TG_API_ID=ваш_api_id
TG_API_HASH=ваш_api_hash
```

## 4. Создание сессии
```bash
python login.py
# Скопируйте TG_SESSION_STRING в .env
```

## 5. Запуск
```bash
./start.sh
```

## 6. Проверка
```bash
curl http://localhost:8010/health
```

---

📖 **Полная инструкция:** `SETUP_NEW_COMPUTER.md`
