# Подходы из 1winSTD-bot для нажатия кнопки Deposit

## 🔍 Анализ подходов из 1winSTD-bot

В проекте 1winSTD-bot используются следующие рабочие подходы для нажатия кнопки Deposit:

### 1. Простой подход - `:text()` селектор Playwright

**Код из 1winSTD-bot:**
```python
page.locator('div:text("Deposit")').first.click()
```

**Преимущества:**
- Самый простой и надежный способ
- Playwright автоматически находит элемент с текстом
- Не требует проверки видимости (но можно добавить)

**Применено в текущем проекте:**
- ✅ Добавлено как Метод 0 (самый первый)
- Проверка видимости: `is_visible(timeout=5000)`
- Таймаут клика: `click(timeout=5000)`

### 2. Wait for visible перед кликом

**Код из 1winSTD-bot:**
```python
deposit_button = page.locator('div:text("Deposit")').first
deposit_button.wait_for(state="visible", timeout=20000)
deposit_button.click()
```

**Преимущества:**
- Ждет появления элемента перед кликом
- Таймаут 20 секунд (достаточно долго)
- Более надежно, чем просто `is_visible()`

**Применено в текущем проекте:**
- ✅ Добавлено как Метод 0.25
- Таймаут: 10 секунд (можно увеличить)

### 3. Множественные селекторы с проверкой видимости

**Код из 1winSTD-bot:**
```python
deposit_selectors = [
    'div:text("Deposit")',
    'button:text("Deposit")',
    'a:text("Deposit")',
    '[data-testid*="deposit"]',
    'div:has-text("Deposit")',
    'button:has-text("Deposit")'
]

deposit_clicked = False
for selector in deposit_selectors:
    try:
        deposit_btn = page.locator(selector).first
        if deposit_btn.is_visible(timeout=3000):
            deposit_btn.click(timeout=3000)
            deposit_clicked = True
            break
    except:
        continue
```

**Преимущества:**
- Пробует разные селекторы
- Проверяет видимость перед кликом
- Если один не работает, пробует следующий

**Применено в текущем проекте:**
- ✅ Добавлено как Метод 0.5
- Те же селекторы из 1winSTD-bot

### 4. Поиск через `button:has-text()` с wait_for

**Код из 1winSTD-bot:**
```python
deposit_btn = main_page.locator('button:has-text("Deposit"), button:has-text("deposit")').first
deposit_btn.wait_for(state="visible", timeout=8000)
deposit_btn.click()
```

**Преимущества:**
- Специфично для кнопок
- Учитывает регистр
- Ждет появления перед кликом

**Применено в текущем проекте:**
- ✅ Добавлено как Метод 0.75

### 5. Использование `data-testid="deposit-button"`

**Код из 1winSTD-bot:**
```python
page.locator('button[data-testid="deposit-button"]').click()
```

**Преимущества:**
- Самый надежный селектор (используется внутри модального окна)
- Точное соответствие элемента
- Используется в критических местах (после выбора метода оплаты)

**Применено в текущем проекте:**
- ✅ Добавлено как Метод 1 (первый после ранних методов)
- Используется перед сложными поисками

### 6. JavaScript поиск (fallback)

**Код из 1winSTD-bot:**
```python
clicked = main_page.evaluate("""
    () => {
        const searchTexts = ['Deposit', 'deposit', 'Пополнить', 'пополнить', 'Top up'];
        for (let text of searchTexts) {
            const allElements = Array.from(document.querySelectorAll('*'));
            const matches = allElements.filter(el => {
                const elText = el.textContent || '';
                const hasText = elText.includes(text);
                const isClickable = el.tagName === 'BUTTON' || el.tagName === 'A' || ...
                return hasText && isClickable && ...
            });
            if (matches.length > 0) {
                matches[0].click();
                return true;
            }
        }
        return false;
    }
""")
```

**Преимущества:**
- Поиск через JavaScript напрямую
- Не зависит от селекторов Playwright
- Работает как последний fallback

**Применено в текущем проекте:**
- ✅ Уже есть как Метод 0.8 (агрессивный JS поиск)

## 📊 Порядок применения методов

В текущем проекте методы применяются в следующем порядке:

1. **Метод 0** (из 1winSTD): `div:text("Deposit")` - простой подход
2. **Метод 0.25** (из 1winSTD): `div:text("Deposit")` с `wait_for(state="visible")`
3. **Метод 0.5** (из 1winSTD): Множественные селекторы с проверкой видимости
4. **Метод 0.75** (из 1winSTD): `button:has-text("Deposit")` с `wait_for`
5. **Метод 0.8**: Агрессивный JS поиск (уже был)
6. **Метод 1** (из 1winSTD): `button[data-testid="deposit-button"]` - самый надежный
7. Остальные методы (уже существующие)

## ✅ Результат

Теперь код использует проверенные подходы из рабочего проекта 1winSTD-bot, что должно значительно повысить надежность поиска и клика по кнопке Deposit.

## 🧪 Тестирование

Для проверки работы:
```bash
python3 test_prod.py
```

Или:
```bash
python3 first_login.py
```

Проверьте логи на наличие:
- `payment_parser_deposit_clicked_via_text_selector_std`
- `payment_parser_deposit_clicked_via_wait_for_visible_std`
- `payment_parser_deposit_clicked_via_std_selector`
- `payment_parser_deposit_clicked_via_data_testid_std`
