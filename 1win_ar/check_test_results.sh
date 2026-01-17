#!/bin/bash
# Скрипт для проверки результатов теста

PID_FILE="/tmp/test_prod_pid.txt"
LOG_FILE="/tmp/test_prod_output.log"

echo "🔍 Проверка результатов теста..."
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Лог файл не найден: $LOG_FILE"
    exit 1
fi

# Проверяем статус процесса
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⏳ Тест еще выполняется (PID: $PID)"
        echo ""
        echo "📋 Последние строки лога:"
        tail -30 "$LOG_FILE"
        echo ""
        echo "Для мониторинга: ./monitor_test.sh"
        echo "Для остановки: kill $PID"
    else
        echo "✅ Тест завершен"
        echo ""
    fi
fi

# Показываем результаты
echo "=" 
echo "📊 РЕЗУЛЬТАТЫ ТЕСТА:"
echo "=" 
echo ""

# Ищем ключевые сообщения
if grep -q "РЕЗУЛЬТАТЫ ТЕСТА" "$LOG_FILE"; then
    echo "✅ Найдены итоговые результаты:"
    echo ""
    grep -A 20 "РЕЗУЛЬТАТЫ ТЕСТА" "$LOG_FILE" | head -25
    echo ""
fi

# Проверяем успешность
if grep -qi "ТЕСТ ПРОЙДЕН" "$LOG_FILE"; then
    echo "✅ ТЕСТ ПРОЙДЕН!"
elif grep -qi "ТЕСТ НЕ ПРОЙДЕН" "$LOG_FILE"; then
    echo "❌ ТЕСТ НЕ ПРОЙДЕН"
elif grep -qi "ЧАСТИЧНО УСПЕШЕН" "$LOG_FILE"; then
    echo "⚠️  ТЕСТ ЧАСТИЧНО УСПЕШЕН"
fi

# Проверяем Deposit кнопку
echo ""
echo "🔍 КЛЮЧЕВЫЕ СОБЫТИЯ:"
echo ""

if grep -qi "deposit.*found\|deposit.*clicked" "$LOG_FILE"; then
    echo "✅ Кнопка Deposit найдена/кликнута:"
    grep -i "deposit.*found\|deposit.*clicked\|deposit.*success" "$LOG_FILE" | tail -5
else
    echo "⚠️  Информация о кнопке Deposit не найдена в логах"
fi

# Проверяем скриншоты
echo ""
echo "📸 СКРИНШОТЫ:"
echo ""

SCREENSHOTS_DIR="$HOME/.cache/1win_ar/screenshots"
if [ -d "$SCREENSHOTS_DIR" ]; then
    RECENT_SCREENSHOTS=$(ls -t "$SCREENSHOTS_DIR"/*.png 2>/dev/null | head -5)
    if [ -n "$RECENT_SCREENSHOTS" ]; then
        echo "Последние скриншоты:"
        ls -lt "$SCREENSHOTS_DIR"/*.png 2>/dev/null | head -5 | awk '{print "  -", $9}' | xargs -I {} basename {}
        
        # Проверяем специфичные скриншоты
        if [ -f "$SCREENSHOTS_DIR/before_deposit_search.png" ]; then
            echo "  ✅ before_deposit_search.png создан"
        fi
        
        if [ -f "$SCREENSHOTS_DIR/deposit_button_not_found.png" ]; then
            echo "  ⚠️  deposit_button_not_found.png - кнопка не найдена"
        fi
    else
        echo "  ⚠️  Скриншоты не найдены"
    fi
fi

# Показываем ошибки если есть
echo ""
if grep -qi "error\|Error\|ERROR\|failed\|Failed\|FAILED" "$LOG_FILE"; then
    echo "⚠️  ОШИБКИ В ЛОГЕ:"
    grep -i "error\|failed" "$LOG_FILE" | tail -10
fi

# Показываем последние строки
echo ""
echo "=" 
echo "📋 ПОСЛЕДНИЕ СТРОКИ ЛОГА:"
echo "=" 
tail -40 "$LOG_FILE"
