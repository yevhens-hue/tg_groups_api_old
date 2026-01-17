# services/payment_parser_ar.py
from typing import Dict, Any, Optional
from datetime import datetime
import re
import base64
import os
from pathlib import Path

import structlog
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from .browser_pool import get_browser_pool

logger = structlog.get_logger()

# Директория для сохранения скриншотов
SCREENSHOTS_DIR = Path(os.path.expanduser("~/.cache/mirrors_api/screenshots"))
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Путь к профилю браузера для persistent context (сохранение cookies/session)
# Если путь указан, парсер будет использовать сохраненную сессию
PAYMENT_PARSER_USER_DATA_DIR = os.environ.get(
    "PAYMENT_PARSER_USER_DATA_DIR",
    os.path.join(os.path.expanduser("~"), ".cache", "mirrors_api", "1win_ar_profile")
)


async def parse_payment_data_1win(
    email: str,
    password: str,
    base_url: str = "https://1win.lat/",
    wait_seconds: int = 15,
    use_persistent_context: bool = True,
    skip_login: bool = False,
) -> Dict[str, Any]:
    """
    Парсит платежные данные с сайта 1win.lat для Аргентины.
    
    Args:
        email: Email для входа
        password: Пароль для входа
        base_url: Базовый URL сайта
        wait_seconds: Время ожидания для загрузки страниц
        
    Returns:
        Словарь с извлеченными данными:
        - cvu: CVU номер
        - recipient: Имя получателя
        - bank: Название банка
        - amount: Сумма
        - method: Метод оплаты
        - payment_type: Тип оплаты (Fiat/Crypto)
        - url: URL страницы с данными
        - screenshot_path: Путь к скриншоту (если сохранен)
    """
    result: Dict[str, Any] = {
        "cvu": None,
        "recipient": None,
        "bank": None,
        "amount": None,
        "method": None,
        "payment_type": None,
        "url": None,
        "domain": None,
        "screenshot_path": None,
        "provider_screenshot": None,
        "provider_screenshot_path": None,
        "success": False,
        "error": None,
    }

    # Инициализация переменных для cleanup
    playwright = None
    context = None
    page = None
    browser_pool_context = None
    browser_context_manager = None

    # Используем persistent context для сохранения cookies/session
    if use_persistent_context:
        # Создаем директорию для профиля, если не существует
        user_data_dir = Path(PAYMENT_PARSER_USER_DATA_DIR)
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("payment_parser_using_persistent_context", user_data_dir=str(user_data_dir))
        
        playwright = await async_playwright().start()
        try:
            # Используем persistent context для сохранения cookies
            # Настройки для обхода детекции автоматизации
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=True,
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                # Отключаем признаки автоматизации
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                ],
                ignore_https_errors=False,
                locale="en-US",
                timezone_id="America/New_York",
            )
            page = context.pages[0] if context.pages else await context.new_page()
            
            # Удаляем признаки автоматизации из page
            await page.add_init_script("""
                // Удаляем webdriver флаг
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Маскируем permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Маскируем plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Маскируем languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Переопределяем Chrome runtime
                window.chrome = {
                    runtime: {}
                };
            """)
        except Exception as e:
            logger.error("payment_parser_persistent_context_failed", error=str(e))
            await playwright.stop()
            playwright = None
            # Fallback к обычному browser pool
            browser_pool = get_browser_pool()
            async with browser_pool.acquire() as browser:
                browser_pool_context = browser
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                page = await context.new_page()
    else:
        # Используем обычный browser pool
        browser_pool = get_browser_pool()
        browser_context_manager = browser_pool.acquire()
        browser = await browser_context_manager.__aenter__()
        browser_pool_context = browser
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
    
    # Основной код парсинга (выполняется для обоих вариантов)
    try:
        # Шаг 1: Переход на главную страницу
        logger.info("payment_parser_navigating", url=base_url)
        try:
            # Пробуем сначала с domcontentloaded (быстрее)
            await page.goto(base_url, wait_until="domcontentloaded", timeout=wait_seconds * 1000)
            await page.wait_for_timeout(3000)  # Даем время на загрузку динамического контента
        except Exception as e:
            logger.debug("payment_parser_goto_domcontentloaded_failed", error=str(e))
            # Если не получилось, пробуем с load
            try:
                await page.goto(base_url, wait_until="load", timeout=wait_seconds * 1000)
                await page.wait_for_timeout(3000)
            except Exception as e2:
                logger.debug("payment_parser_goto_load_failed", error=str(e2))
                # В последнюю очередь пробуем networkidle
                await page.goto(base_url, wait_until="networkidle", timeout=wait_seconds * 1000)
                await page.wait_for_timeout(2000)

        # Шаг 1.5: Проверка, авторизован ли уже пользователь (если используется persistent context)
        if skip_login or use_persistent_context:
            try:
                # Проверяем наличие элементов, которые появляются только для авторизованных пользователей
                deposit_button = page.locator('div:text("Deposit"), button:text("Deposit"), a:text("Deposit")').first
                is_deposit_visible = await deposit_button.is_visible(timeout=3000)
                if is_deposit_visible:
                    logger.info("payment_parser_already_logged_in", message="User already logged in, skipping login")
                    skip_login = True  # Пользователь уже авторизован
            except Exception as e:
                logger.debug("payment_parser_auth_check_failed", error=str(e))
                skip_login = False  # Не удалось проверить, пытаемся войти

        # Шаг 2: Поиск и клик на кнопку входа (если не пропускаем логин)
        if not skip_login:
            logger.info("payment_parser_looking_for_login")
            await page.wait_for_timeout(3000)  # Дополнительное ожидание для загрузки
            
            # Попробуем разные способы найти кнопку входа
            login_clicked = False
            
            # Стратегия 0: Ожидание появления модального окна логина (может открыться автоматически)
            try:
                # Проверяем, не открыто ли уже модальное окно с формой входа
                modal_login = page.locator('[class*="modal" i], [class*="login" i], [id*="login" i]').first
                if await modal_login.count() > 0:
                    # Проверяем наличие input полей в модальном окне
                    email_in_modal = await modal_login.locator('input[type="email"], input[placeholder*="email" i]').count()
                    if email_in_modal > 0:
                        logger.info("payment_parser_login_modal_already_open")
                        login_clicked = True  # Модальное окно уже открыто
            except Exception as e:
                logger.debug("payment_parser_modal_check_failed", error=str(e))
        
            # Стратегия 1: Поиск кнопки логина (как в рабочем парсере 1win STD)
            login_indicators = [
                'button:has-text("Войти")',
                'button:has-text("Log in")',
                'button:has-text("Login")',
                'button:has-text("Ingresar")',
                'button:has-text("Entrar")',
                'a:has-text("Войти")',
                'a:has-text("Log in")',
                'a:has-text("Login")',
                'a:has-text("Ingresar")',
                'a:has-text("Entrar")',
                '[data-testid*="login"]',
                '[data-testid*="signin"]',
                '*:has-text("Войти")',
                '*:has-text("Login")',
                '*:has-text("Ingresar")'
            ]
        
            for selector in login_indicators:
                try:
                    login_btn = page.locator(selector).first
                    is_visible = await login_btn.is_visible(timeout=3000)
                    if is_visible:
                        logger.info("payment_parser_login_button_found", selector=selector)
                        await login_btn.scroll_into_view_if_needed()
                        await login_btn.click(timeout=5000)
                        await page.wait_for_timeout(3000)  # Даем время на открытие формы
                        login_clicked = True
                        logger.info("payment_parser_login_clicked", selector=selector)
                        break
                except Exception as e:
                    logger.debug("payment_parser_login_selector_failed", selector=selector, error=str(e)[:50])
                    continue
        
            # Стратегия 2: Поиск по role и тексту
            if not login_clicked:
                try:
                    login_button = page.get_by_role("button", name=re.compile("(login|ingresar|entrar|вход)", re.I))
                    count = await login_button.count()
                    if count > 0:
                        await login_button.first.click(timeout=5000)
                        await page.wait_for_timeout(3000)
                        login_clicked = True
                        logger.info("payment_parser_login_clicked", method="role_button")
                except Exception as e:
                    logger.debug("payment_parser_login_role_failed", error=str(e))
        
            # Стратегия 3: Поиск ссылок с login
            if not login_clicked:
                try:
                    login_link = page.get_by_role("link", name=re.compile("(login|ingresar|entrar|вход)", re.I))
                    count = await login_link.count()
                    if count > 0:
                        await login_link.first.click(timeout=5000)
                        await page.wait_for_timeout(3000)
                        login_clicked = True
                        logger.info("payment_parser_login_clicked", method="role_link")
                except Exception as e:
                    logger.debug("payment_parser_login_link_failed", error=str(e))
        
            # Стратегия 4: CSS селекторы
            if not login_clicked:
                login_selectors = [
                    '[data-testid*="login" i]',
                    '[class*="login" i]',
                    '[id*="login" i]',
                    'button[class*="btn" i]',
                    'a[href*="login" i]',
                    'a[href*="auth" i]',
                    'button[type="button"]',
                    '.button',
                    '[role="button"]',
                ]
                for selector in login_selectors:
                    try:
                        login_btn = await page.query_selector(selector)
                        if login_btn:
                            # Проверяем, что это действительно кнопка входа по тексту
                            btn_text = await login_btn.inner_text()
                            if any(word.lower() in btn_text.lower() for word in ["login", "ingresar", "entrar", "вход", "sign"]):
                                await login_btn.click()
                                await page.wait_for_timeout(3000)
                                login_clicked = True
                                logger.info("payment_parser_login_clicked", selector=selector, text=btn_text[:50])
                                break
                    except Exception as e:
                        logger.debug("payment_parser_login_selector_failed", selector=selector, error=str(e))
                        continue

            if not login_clicked and not skip_login:
                # Если кнопка не найдена, может быть форма уже видна или нужен другой подход
                logger.warning("payment_parser_login_button_not_found", url=page.url)
                # Пробуем перейти напрямую на страницу логина
                try:
                    login_urls = [
                        f"{base_url.rstrip('/')}/login",
                        f"{base_url.rstrip('/')}/auth/login",
                        f"{base_url.rstrip('/')}/signin",
                        f"{base_url.rstrip('/')}/account/login",
                    ]
                    for login_url in login_urls:
                        try:
                            # Используем domcontentloaded для быстрой загрузки
                            await page.goto(login_url, wait_until="domcontentloaded", timeout=15000)
                            await page.wait_for_timeout(5000)  # Увеличиваем ожидание для динамической загрузки
                            logger.info("payment_parser_direct_login_navigation", url=login_url)
                            # Проверяем, появились ли поля формы после перехода
                            try:
                                inputs = await page.query_selector_all('input[type="email"], input[type="text"], input')
                                if inputs:
                                    logger.info("payment_parser_inputs_found_after_navigation", count=len(inputs))
                            except:
                                pass
                            break
                        except Exception as e:
                            logger.debug("payment_parser_navigation_url_failed", url=login_url, error=str(e)[:100])
                            continue
                except Exception as e:
                    logger.debug("payment_parser_direct_login_failed", error=str(e))

            # Шаг 3: Ожидание появления формы логина (если не пропускаем логин)
            if not skip_login:
                logger.info("payment_parser_waiting_for_login_form")
                await page.wait_for_timeout(3000)
                
                # Ждем появления полей формы (модальное окно ИЛИ обычная страница логина)
                form_appeared = False
                if not login_clicked:
                    try:
                        # Ожидаем появления любых input полей (модальное окно или обычная страница)
                        await page.wait_for_selector(
                            'input[type="email"], input[placeholder*="Email" i], input[placeholder*="email" i], '
                            'input[type="text"], input[name*="email" i], input[name*="login" i]',
                            timeout=15000,
                            state="visible"
                        )
                        logger.info("payment_parser_login_form_appeared")
                        form_appeared = True
                    except Exception as e:
                        logger.warning("payment_parser_form_not_appeared", error=str(e))
                        # Пробуем подождать еще немного и проверить снова
                        try:
                            await page.wait_for_timeout(3000)
                            # Проверяем наличие любых input полей
                            all_inputs = await page.query_selector_all('input[type="email"], input[type="text"], input')
                            if all_inputs:
                                logger.info("payment_parser_form_appeared_after_wait", inputs_count=len(all_inputs))
                                form_appeared = True
                        except:
                            pass
                else:
                    form_appeared = True
                
                # Если форма появилась, ждем полной загрузки полей
                if form_appeared:
                    await page.wait_for_timeout(2000)  # Дополнительное ожидание для динамической загрузки полей
            
            # Шаг 3.1: Выбор вкладки Email (если есть выбор между Phone/Email)
            try:
                # Ищем вкладку Email и кликаем на нее
                email_tab_selectors = [
                    'button:has-text("Email")',
                    'div:has-text("Email")',
                    '[class*="tab" i]:has-text("Email")',
                    '[role="tab"]:has-text("Email")',
                ]
                
                for selector in email_tab_selectors:
                    try:
                        email_tab = page.locator(selector).first
                        if await email_tab.count() > 0:
                            # Проверяем, активна ли уже вкладка Email
                            is_active = await email_tab.get_attribute("class")
                            if not is_active or "active" not in is_active.lower():
                                await email_tab.click(timeout=3000)
                                await page.wait_for_timeout(1000)
                                logger.info("payment_parser_email_tab_selected", selector=selector)
                            else:
                                logger.info("payment_parser_email_tab_already_active")
                            break
                    except Exception:
                        continue
            except Exception as e:
                logger.debug("payment_parser_email_tab_selection_failed", error=str(e))
            
            # Шаг 3.2: Заполнение формы входа
            logger.info("payment_parser_filling_login_form")
            await page.wait_for_timeout(2000)

            # Стратегия 1: Поиск поля email через различные методы
            email_filled = False
            
            # Метод 1: Ожидание появления поля Email и поиск по placeholder (приоритетный метод)
            try:
                # Сначала ждем появления поля с placeholder "Email"
                await page.wait_for_selector(
                    'input[placeholder*="Email" i], input[placeholder*="email" i]',
                    timeout=10000,
                    state="visible"
                )
                # Даем время на полную загрузку
                await page.wait_for_timeout(1000)
                
                # Ищем поле с placeholder содержащим "Email"
                email_input = page.locator('input[placeholder*="Email" i], input[placeholder*="email" i]').first
                if await email_input.count() > 0:
                    await email_input.wait_for(state="visible", timeout=5000)
                    # Скроллим к элементу на случай, если он не виден
                    await email_input.scroll_into_view_if_needed()
                    await page.wait_for_timeout(500)
                    await email_input.click(timeout=5000)
                    await page.wait_for_timeout(500)
                    await email_input.fill(email, timeout=10000)
                    await page.wait_for_timeout(500)
                    email_filled = True
                    logger.info("payment_parser_email_filled", method="placeholder_email")
            except Exception as e:
                logger.debug("payment_parser_email_placeholder_failed", error=str(e))
            
            # Метод 1.5: Поиск по типу input[type="email"] с ожиданием
            if not email_filled:
                try:
                    await page.wait_for_selector('input[type="email"]', timeout=5000)
                    email_input = page.locator('input[type="email"]').first
                    if await email_input.count() > 0:
                        await email_input.wait_for(state="visible", timeout=5000)
                        await email_input.click(timeout=3000)
                        await email_input.fill(email, timeout=5000)
                        email_filled = True
                        logger.info("payment_parser_email_filled", method="type_email")
                except Exception as e:
                    logger.debug("payment_parser_email_type_failed", error=str(e))
            
            # Метод 2: Поиск по name атрибутам
            if not email_filled:
                email_selectors = [
                    'input[name="email"]',
                    'input[name="login"]',
                    'input[name="username"]',
                    'input[name="user"]',
                    'input[name="mail"]',
                ]
                for selector in email_selectors:
                    try:
                        email_input = page.locator(selector).first
                        if await email_input.count() > 0:
                            await email_input.fill(email, timeout=5000)
                            email_filled = True
                            logger.info("payment_parser_email_filled", selector=selector)
                            break
                    except Exception as e:
                        logger.debug("payment_parser_email_selector_failed", selector=selector, error=str(e))
                        continue
            
            # Метод 3: Поиск по placeholder
            if not email_filled:
                try:
                    # Ищем все input поля и проверяем placeholder
                    all_inputs = await page.query_selector_all('input[type="text"], input[type="email"], input:not([type])')
                    for inp in all_inputs[:10]:  # Ограничиваем количество проверок
                        try:
                            placeholder = await inp.get_attribute("placeholder")
                            id_attr = await inp.get_attribute("id")
                            name_attr = await inp.get_attribute("name")
                            
                            if placeholder and any(word in placeholder.lower() for word in ["email", "correo", "e-mail", "mail"]):
                                await inp.fill(email)
                                email_filled = True
                                logger.info("payment_parser_email_filled", method="placeholder", placeholder=placeholder)
                                break
                            elif id_attr and any(word in id_attr.lower() for word in ["email", "login", "user"]):
                                await inp.fill(email)
                                email_filled = True
                                logger.info("payment_parser_email_filled", method="id", id=id_attr)
                                break
                            elif name_attr and any(word in name_attr.lower() for word in ["email", "login", "user"]):
                                await inp.fill(email)
                                email_filled = True
                                logger.info("payment_parser_email_filled", method="name", name=name_attr)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug("payment_parser_email_placeholder_failed", error=str(e))
            
            # Метод 4: Поиск по label и связанному input
            if not email_filled:
                try:
                    # Ищем label с текстом email и связанный input
                    labels = await page.query_selector_all('label')
                    for label in labels[:10]:
                        try:
                            label_text = await label.inner_text()
                            if any(word in label_text.lower() for word in ["email", "correo", "e-mail", "mail", "login"]):
                                # Ищем связанный input через for атрибут или следующий input
                                for_attr = await label.get_attribute("for")
                                if for_attr:
                                    email_input = await page.query_selector(f'#{for_attr}')
                                    if email_input:
                                        await email_input.fill(email)
                                        email_filled = True
                                        logger.info("payment_parser_email_filled", method="label_for", for_attr=for_attr)
                                        break
                                # Если не нашли по for, ищем следующий input
                                if not email_filled:
                                    email_input = await label.query_selector('input')
                                    if email_input:
                                        await email_input.fill(email)
                                        email_filled = True
                                        logger.info("payment_parser_email_filled", method="label_input")
                                        break
                            if email_filled:
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug("payment_parser_email_label_failed", error=str(e))
            
            # Метод 5: Поиск первого текстового input как последняя попытка
            if not email_filled:
                try:
                    # Ждем появления любого текстового input
                    await page.wait_for_selector('input[type="text"], input:not([type]), input', timeout=5000)
                    # Ищем все input поля
                    all_inputs = await page.query_selector_all('input:not([type="hidden"]):not([type="password"]):not([type="submit"]):not([type="button"])')
                    
                    for inp in all_inputs[:5]:  # Проверяем первые 5 input полей
                        try:
                            inp_type = await inp.get_attribute("type")
                            inp_name = await inp.get_attribute("name") or ""
                            inp_id = await inp.get_attribute("id") or ""
                            inp_placeholder = await inp.get_attribute("placeholder") or ""
                            
                            # Если это не password, не submit, не button - вероятно это поле для email
                            if inp_type not in ["password", "submit", "button", "hidden"]:
                                # Пробуем заполнить первое найденное текстовое поле
                                await inp.fill(email, timeout=3000)
                                email_filled = True
                                logger.info(
                                    "payment_parser_email_filled", 
                                    method="first_text_input", 
                                    type=inp_type,
                                    name=inp_name[:30],
                                    id=inp_id[:30],
                                    placeholder=inp_placeholder[:30]
                                )
                                break
                        except Exception as e:
                            logger.debug("payment_parser_email_input_fill_failed", error=str(e))
                            continue
                except Exception as e:
                    logger.debug("payment_parser_email_first_input_failed", error=str(e))
            
            if not email_filled:
                # Делаем скриншот для отладки перед ошибкой
                try:
                    screenshot = await page.screenshot(full_page=True)
                    result["debug_screenshot"] = base64.b64encode(screenshot).decode('utf-8')
                    logger.warning("payment_parser_email_not_found_screenshot_taken")
                    
                    # Сохраняем HTML страницы для отладки
                    html_content = await page.content()
                    # Логируем первые 2000 символов HTML для отладки
                    logger.warning("payment_parser_page_html_sample", html_sample=html_content[:2000])
                    
                    # Логируем все найденные input элементы
                    all_inputs_info = []
                    try:
                        all_inputs = await page.query_selector_all('input')
                        for inp in all_inputs[:10]:
                            try:
                                inp_info = {
                                    "type": await inp.get_attribute("type") or "text",
                                    "name": await inp.get_attribute("name") or "",
                                    "id": await inp.get_attribute("id") or "",
                                    "placeholder": await inp.get_attribute("placeholder") or "",
                                    "class": await inp.get_attribute("class") or "",
                                }
                                all_inputs_info.append(inp_info)
                            except:
                                pass
                        logger.warning("payment_parser_inputs_found", inputs=all_inputs_info)
                    except Exception:
                        pass
                except:
                    pass
                raise Exception("Email field not found after trying all methods")

            await page.wait_for_timeout(1000)

            # Ищем поле password
            password_filled = False
            
            # Поиск поля password (как в рабочем парсере 1win STD)
            password_filled = False
            password_selectors = [
                'input[type="password"]',
                'input[name*="password" i]',
                'input[name*="Password" i]',
                'input[placeholder*="password" i]',
                'input[placeholder*="Password" i]',
                'input[placeholder*="Пароль" i]',
                'input[data-testid*="password" i]',
                'input[id*="password" i]'
            ]
            
            password_input = None
            if email_filled:  # Ищем password только если email заполнен
                for selector in password_selectors:
                    try:
                        password_input = page.locator(selector).first
                        if await password_input.count() > 0:
                            is_visible = await password_input.is_visible(timeout=2000)
                            if is_visible:
                                logger.info("payment_parser_password_found", selector=selector)
                                password_filled = True
                                break
                    except:
                        continue
            
            # Заполнение password если найдено
            if password_input and password_filled:
                try:
                    logger.info("payment_parser_filling_password")
                    await password_input.scroll_into_view_if_needed()
                    await page.wait_for_timeout(500)
                    await password_input.click(timeout=5000)
                    await page.wait_for_timeout(500)
                    await password_input.fill(password, timeout=10000)
                    await page.wait_for_timeout(500)
                    logger.info("payment_parser_password_filled", method="multiple_selectors")
                except Exception as e:
                    logger.debug("payment_parser_password_fill_failed", error=str(e))
                    password_filled = False
            
            # Метод 2: Поиск по типу input[type="password"]
            if not password_filled:
                try:
                    password_input = page.locator('input[type="password"]').first
                    if await password_input.count() > 0:
                        await password_input.wait_for(state="visible", timeout=5000)
                        await password_input.click(timeout=3000)
                        await password_input.fill(password, timeout=5000)
                        password_filled = True
                        logger.info("payment_parser_password_filled", method="type_password")
                except Exception as e:
                    logger.debug("payment_parser_password_type_failed", error=str(e))
            
            # Метод 3: Поиск по name и другим атрибутам
            if not password_filled:
                password_selectors = [
                    'input[name="password"]',
                    'input[name="pass"]',
                    'input[placeholder*="contraseña" i]',
                    'input[id*="password" i]',
                    'input[id*="pass" i]',
                ]

                for selector in password_selectors:
                    try:
                        password_input = page.locator(selector).first
                        if await password_input.count() > 0:
                            await password_input.wait_for(state="visible", timeout=5000)
                            await password_input.click(timeout=3000)
                            await password_input.fill(password, timeout=5000)
                            password_filled = True
                            logger.info("payment_parser_password_filled", selector=selector)
                            break
                    except Exception as e:
                        logger.debug("payment_parser_password_selector_failed", selector=selector, error=str(e))
                        continue

            if not password_filled:
                raise Exception("Password field not found")

            await page.wait_for_timeout(500)

            # Шаг 4: Отправка формы входа
            logger.info("payment_parser_submitting_login_form")
            await page.wait_for_timeout(1000)

            # Пробуем найти кнопку отправки формы
            form_submitted = False
            
            # Метод 1: Поиск по тексту кнопки "Log in" (приоритетный для модального окна)
            login_button_texts = ["Log in", "Login", "Войти", "Ingresar", "Entrar", "Sign in"]
            for text in login_button_texts:
                try:
                    submit_btn = page.get_by_role("button", name=text, exact=False).first
                    if await submit_btn.count() > 0:
                        await submit_btn.wait_for(state="visible", timeout=3000)
                        await submit_btn.click(timeout=5000)
                        await page.wait_for_timeout(3000)
                        form_submitted = True
                        logger.info("payment_parser_form_submitted", method="button_text", text=text)
                        break
                except Exception as e:
                    logger.debug("payment_parser_submit_button_text_failed", text=text, error=str(e))
                    continue
            
            # Метод 2: Поиск по типу submit
            if not form_submitted:
                try:
                    submit_btn = page.locator('button[type="submit"]').first
                    if await submit_btn.count() > 0:
                        await submit_btn.wait_for(state="visible", timeout=3000)
                        await submit_btn.click(timeout=5000)
                        await page.wait_for_timeout(3000)
                        form_submitted = True
                        logger.info("payment_parser_form_submitted", method="submit_button")
                except Exception as e:
                    logger.debug("payment_parser_submit_button_failed", error=str(e))
            
            # Метод 3: Поиск по другим селекторам (старый метод как fallback)
            if not form_submitted:
                submit_selectors = [
                    'input[type="submit"]',
                    '[data-testid*="submit" i]',
                    '[class*="submit" i]',
                    '[class*="login" i] button',
                    'button[class*="btn" i]',
                ]
                
                for selector in submit_selectors:
                    try:
                        submit_btn = page.locator(selector).first
                        if await submit_btn.count() > 0:
                            # Проверяем текст кнопки
                            btn_text = await submit_btn.inner_text()
                            if any(word.lower() in btn_text.lower() for word in ["login", "log in", "ingresar", "entrar", "вход"]):
                                await submit_btn.wait_for(state="visible", timeout=3000)
                                await submit_btn.click(timeout=5000)
                                await page.wait_for_timeout(3000)
                                form_submitted = True
                                logger.info("payment_parser_form_submitted", selector=selector, text=btn_text[:50])
                                break
                    except Exception as e:
                        logger.debug("payment_parser_submit_selector_failed", selector=selector, error=str(e))
                        continue

            if not form_submitted:
                # Пробуем нажать Enter на поле пароля
                try:
                    password_input = page.locator('input[type="password"]').first
                    if await password_input.count() > 0:
                        await password_input.press("Enter")
                        await page.wait_for_timeout(3000)
                        form_submitted = True
                        logger.info("payment_parser_form_submitted_via_enter")
                except Exception as e:
                    logger.warning("payment_parser_submit_failed", error=str(e))

            # Шаг 5: Ожидание загрузки после входа
            logger.info("payment_parser_waiting_after_login")
            await page.wait_for_timeout(3000)
        
        # Шаг 6: Переход на страницу депозита (выполняется всегда, даже при skip_login)
        logger.info("payment_parser_navigating_to_deposit")
        await page.wait_for_timeout(2000)  # Даем время на загрузку главной страницы
        
        # Проверяем текущий URL - может быть мы уже на странице депозита
        current_url = page.url.lower()
        deposit_clicked = False
        
        if "deposit" not in current_url and "depositar" not in current_url:
            # Пробуем разные способы найти кнопку депозита
            # Пробуем найти по тексту
            deposit_texts = ["Deposit", "Depositar", "Depósito", "Пополнить"]
            for text in deposit_texts:
                try:
                    deposit_locator = page.get_by_text(text, exact=False)
                    if await deposit_locator.count() > 0:
                        await deposit_locator.first.click()
                        await page.wait_for_timeout(3000)
                        deposit_clicked = True
                        logger.info("payment_parser_deposit_clicked", text=text)
                        break
                except Exception as e:
                    logger.debug("payment_parser_deposit_text_failed", text=text, error=str(e))
                    continue
            
            # Если не нашли по тексту, пробуем CSS селекторы
            if not deposit_clicked:
                deposit_selectors = [
                    '[href*="deposit" i]',
                    '[href*="depositar" i]',
                    '[data-testid="deposit"]',
                    'a[href*="/deposit"]',
                    'button[data-action="deposit"]',
                ]
                for selector in deposit_selectors:
                    try:
                        deposit_btn = await page.query_selector(selector)
                        if deposit_btn:
                            await deposit_btn.click()
                            await page.wait_for_timeout(3000)
                            deposit_clicked = True
                            logger.info("payment_parser_deposit_clicked", selector=selector)
                            break
                    except Exception as e:
                        logger.debug("payment_parser_deposit_selector_failed", selector=selector, error=str(e))
                        continue

            if not deposit_clicked:
                # Пробуем прямой переход
                deposit_url = f"{base_url.rstrip('/')}/deposit"
                try:
                    await page.goto(deposit_url, wait_until="domcontentloaded", timeout=wait_seconds * 1000)
                    await page.wait_for_timeout(2000)
                    logger.info("payment_parser_direct_deposit_navigation")
                except Exception as e:
                    logger.debug("payment_parser_deposit_goto_failed", error=str(e))

        # Шаг 7: Выбор метода оплаты Claro Pay
        logger.info("payment_parser_selecting_payment_method")
        logger.debug("payment_parser_current_url", url=page.url)
        await page.wait_for_timeout(3000)  # Увеличиваем ожидание после перехода на депозит

        # Ищем Claro Pay
        claro_clicked = False
        
        # Пробуем найти по тексту
        try:
            claro_locator = page.get_by_text("Claro Pay", exact=False)
            count = await claro_locator.count()
            logger.debug("payment_parser_claro_text_count", count=count)
            if count > 0:
                await claro_locator.first.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                await claro_locator.first.click()
                await page.wait_for_timeout(3000)
                claro_clicked = True
                logger.info("payment_parser_claro_pay_clicked", method="text", url_after=page.url)
        except Exception as e:
            logger.debug("payment_parser_claro_text_failed", error=str(e))
        
        # Если не нашли по тексту, пробуем CSS селекторы
        if not claro_clicked:
            claro_pay_selectors = [
                '[data-method*="claro" i]',
                '[data-payment*="claro" i]',
                '[class*="claro" i]',
                '[id*="claro" i]',
                'button:has-text("Claro")',
                'a:has-text("Claro")',
                'div:has-text("Claro Pay")',
            ]
            for selector in claro_pay_selectors:
                try:
                    claro_elem = await page.query_selector(selector)
                    if claro_elem:
                        await claro_elem.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        await claro_elem.click()
                        await page.wait_for_timeout(3000)
                        claro_clicked = True
                        logger.info("payment_parser_claro_pay_clicked", selector=selector, url_after=page.url)
                        break
                except Exception as e:
                    logger.debug("payment_parser_claro_selector_failed", selector=selector, error=str(e))
                    continue
        
        # Делаем скриншот провайдера всегда (после попытки выбора Claro Pay)
        try:
            screenshot_bytes = await page.screenshot(full_page=True)
            # Сохраняем в base64 для ответа
            result["provider_screenshot"] = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            # Сохраняем в файл
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_filename = f"provider_claro_{timestamp}.png"
            screenshot_path = SCREENSHOTS_DIR / screenshot_filename
            screenshot_path.write_bytes(screenshot_bytes)
            result["provider_screenshot_path"] = str(screenshot_path)
            
            if claro_clicked:
                logger.info("payment_parser_provider_screenshot_taken", 
                           provider="Claro Pay", 
                           status="found",
                           path=str(screenshot_path))
            else:
                logger.info("payment_parser_provider_screenshot_taken", 
                           provider="Claro Pay", 
                           status="not_found", 
                           current_url=page.url,
                           path=str(screenshot_path))
        except Exception as e:
            logger.warning("payment_parser_provider_screenshot_failed", error=str(e))
        
        if not claro_clicked:
            logger.warning("payment_parser_claro_pay_not_found", current_url=page.url)

        # Шаг 8: Выбор типа Fiat (если есть выбор)
        logger.info("payment_parser_selecting_fiat_type")
        await page.wait_for_timeout(2000)  # Увеличиваем ожидание

        fiat_selected = False
        # Пробуем найти Fiat по тексту
        try:
            fiat_locator = page.get_by_text("Fiat", exact=False)
            count = await fiat_locator.count()
            logger.debug("payment_parser_fiat_text_count", count=count)
            if count > 0:
                await fiat_locator.first.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                await fiat_locator.first.click()
                await page.wait_for_timeout(2000)
                fiat_selected = True
                logger.info("payment_parser_fiat_selected", method="text", url_after=page.url)
        except Exception as e:
            logger.debug("payment_parser_fiat_text_failed", error=str(e))
        
        # Если не нашли по тексту, пробуем CSS селекторы
        if not fiat_selected:
            fiat_selectors = [
                '[data-type="fiat"]',
                '.fiat-tab',
                '#fiat-tab',
                '[class*="fiat" i]',
                'button:has-text("Fiat")',
                'a:has-text("Fiat")',
            ]
            for selector in fiat_selectors:
                try:
                    fiat_elem = await page.query_selector(selector)
                    if fiat_elem:
                        await fiat_elem.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        await fiat_elem.click()
                        await page.wait_for_timeout(2000)
                        fiat_selected = True
                        logger.info("payment_parser_fiat_selected", selector=selector, url_after=page.url)
                        break
                except Exception as e:
                    logger.debug("payment_parser_fiat_selector_failed", selector=selector, error=str(e))
                    continue
        
        if not fiat_selected:
            logger.debug("payment_parser_fiat_not_found", current_url=page.url)
        
        # Дополнительное ожидание после выбора метода и типа
        await page.wait_for_timeout(3000)
        logger.debug("payment_parser_final_url_before_extraction", url=page.url)

        # Шаг 9: Извлечение данных платежной формы
        logger.info("payment_parser_extracting_data")
        await page.wait_for_timeout(5000)  # Увеличиваем ожидание для динамической загрузки

        result["url"] = page.url

        # Сохраняем скриншот для отладки
        try:
            screenshot = await page.screenshot(full_page=True)
            result["debug_screenshot"] = base64.b64encode(screenshot).decode('utf-8')
            logger.info("payment_parser_screenshot_taken")
        except:
            pass

        # Извлекаем CVU - улучшенная логика поиска
        cvu_patterns = [
            r'CVU[:\s]*([0-9]{20,25})',
            r'CVU[:\s]*([\d\s\-]{20,30})',  # С учетом возможных дефисов/пробелов
            r'(?:CVU|Alias)[:\s]*([0-9]{20,25})',
            r'([0-9]{20,25})',  # Fallback: просто ищем длинное число
        ]

        page_content = await page.content()
        page_text = await page.inner_text('body')  # Получаем весь видимый текст
        cvu_found = None

        # Метод 1: Поиск в HTML контенте
        logger.debug("payment_parser_searching_cvu_in_html")
        for pattern in cvu_patterns:
            matches = re.findall(pattern, page_content, re.IGNORECASE)
            if matches:
                for match in matches:
                    cvu_found = re.sub(r'[\s\-]+', '', str(match))
                    if len(cvu_found) >= 20 and len(cvu_found) <= 25:
                        result["cvu"] = cvu_found
                        logger.info("payment_parser_cvu_found_via_regex_html", cvu=cvu_found[:10] + "...", pattern=pattern[:30])
                        break
                if result["cvu"]:
                    break

        # Метод 2: Поиск в видимом тексте страницы
        if not result["cvu"]:
            logger.debug("payment_parser_searching_cvu_in_text")
            for pattern in cvu_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    for match in matches:
                        cvu_found = re.sub(r'[\s\-]+', '', str(match))
                        if len(cvu_found) >= 20 and len(cvu_found) <= 25:
                            result["cvu"] = cvu_found
                            logger.info("payment_parser_cvu_found_via_regex_text", cvu=cvu_found[:10] + "...")
                            break
                    if result["cvu"]:
                        break

        # Метод 3: Поиск через DOM селекторы
        if not result["cvu"]:
            logger.debug("payment_parser_searching_cvu_via_dom")
            cvu_selectors = [
                '*:has-text("CVU")',
                '*:has-text("CVU") + *',  # Следующий элемент после CVU
                '*:has-text("CVU") ~ *',  # Соседние элементы
                '[data-field*="cvu" i]',
                '[name*="cvu" i]',
                '[id*="cvu" i]',
                '[class*="cvu" i]',
                '.cvu-value',
                '.cv-code',
                '[data-testid*="cvu" i]',
                'input[value*="CVU" i]',
                'input[placeholder*="CVU" i]',
            ]

            for selector in cvu_selectors:
                try:
                    # Ищем элемент с CVU
                    cvu_elem = await page.locator(selector).first
                    if await cvu_elem.count() > 0:
                        # Пробуем получить текст из элемента
                        cvu_text = await cvu_elem.inner_text()
                        # Также пробуем получить текст из родителя
                        try:
                            parent = await cvu_elem.evaluate_handle('el => el.closest("div, span, td, li")')
                            if parent:
                                parent_elem = parent.as_element() if hasattr(parent, 'as_element') else None
                                if parent_elem:
                                    parent_text = await parent_elem.inner_text()
                                    cvu_text = parent_text if len(parent_text) > len(cvu_text) else cvu_text
                        except:
                            pass
                        
                        # Ищем число в тексте
                        numbers = re.findall(r'\d+', cvu_text)
                        for num in numbers:
                            if len(num) >= 20 and len(num) <= 25:
                                result["cvu"] = num
                                logger.info("payment_parser_cvu_found_via_dom", cvu=num[:10] + "...", selector=selector[:50])
                                break
                        if result["cvu"]:
                            break
                except Exception as e:
                    logger.debug("payment_parser_cvu_selector_failed", selector=selector[:50], error=str(e)[:100])
                    continue

        # Метод 4: Поиск всех input полей и их значений
        if not result["cvu"]:
            logger.debug("payment_parser_searching_cvu_in_inputs")
            try:
                all_inputs = await page.query_selector_all('input, textarea, [contenteditable]')
                for inp in all_inputs[:20]:  # Проверяем первые 20 элементов
                    try:
                        value = await inp.get_attribute('value') or await inp.inner_text()
                        if value:
                            # Ищем длинное число в значении
                            numbers = re.findall(r'\d{20,25}', value)
                            if numbers:
                                result["cvu"] = numbers[0]
                                logger.info("payment_parser_cvu_found_in_input", cvu=numbers[0][:10] + "...")
                                break
                    except:
                        continue
            except Exception as e:
                logger.debug("payment_parser_cvu_inputs_search_failed", error=str(e)[:100])

        # Метод 5: Поиск через evaluate - ищем все элементы с длинными числами
        if not result["cvu"]:
            logger.debug("payment_parser_searching_cvu_via_evaluate")
            try:
                # Ищем все текстовые узлы с длинными числами
                cvu_candidates = await page.evaluate("""
                    () => {
                        const walker = document.createTreeWalker(
                            document.body,
                            NodeFilter.SHOW_TEXT,
                            null,
                            false
                        );
                        const candidates = [];
                        let node;
                        while (node = walker.nextNode()) {
                            const text = node.textContent.trim();
                            // Ищем паттерн CVU или длинное число (20-25 цифр)
                            if (text.match(/CVU[\\s:]*[0-9]{20,25}/i) || text.match(/[0-9]{20,25}/)) {
                                const match = text.match(/([0-9]{20,25})/);
                                if (match) {
                                    candidates.push({
                                        text: text.substring(0, 100),
                                        cvu: match[1].replace(/[\\s\\-]/g, '')
                                    });
                                }
                            }
                        }
                        return candidates.slice(0, 10); // Возвращаем первые 10 кандидатов
                    }
                """)
                
                if cvu_candidates:
                    for candidate in cvu_candidates:
                        cvu_value = candidate['cvu']
                        if len(cvu_value) >= 20 and len(cvu_value) <= 25:
                            result["cvu"] = cvu_value
                            logger.info("payment_parser_cvu_found_via_evaluate", cvu=cvu_value[:10] + "...")
                            break
            except Exception as e:
                logger.debug("payment_parser_cvu_evaluate_failed", error=str(e)[:100])

        # Извлекаем Recipient
        recipient_selectors = [
            '*:has-text("Recipient")',
            '*:has-text("Recipient"):not(:has-text("CVU"))',
            '[data-field="recipient"]',
            '[name="recipient"]',
            '[id*="recipient" i]',
        ]

        for selector in recipient_selectors:
            try:
                recipient_elem = await page.query_selector(selector)
                if recipient_elem:
                    # Пробуем найти значение рядом
                    parent = await recipient_elem.evaluate_handle('el => el.closest("div, li, tr")')
                    if parent:
                        parent_text = await parent.as_element().inner_text() if hasattr(parent, 'as_element') else None
                        if parent_text:
                            # Ищем значение после "Recipient"
                            match = re.search(r'Recipient[:\s]+(.+?)(?:\n|$)', parent_text, re.IGNORECASE)
                            if match:
                                result["recipient"] = match.group(1).strip()
                                logger.info("payment_parser_recipient_found", recipient=result["recipient"][:20])
                                break
            except Exception as e:
                logger.debug("payment_parser_recipient_selector_failed", selector=selector, error=str(e))
                continue

        # Извлекаем Bank
        bank_selectors = [
            '*:has-text("Bank")',
            '*:has-text("Claro Pay")',
            '[data-field="bank"]',
            '[name="bank"]',
        ]

        for selector in bank_selectors:
            try:
                bank_elem = await page.query_selector(selector)
                if bank_elem:
                    bank_text = await bank_elem.inner_text()
                    if "Claro Pay" in bank_text:
                        # Пробуем извлечь значение Bank
                        match = re.search(r'Bank[:\s]+(.+?)(?:\n|$)', bank_text, re.IGNORECASE)
                        if match:
                            result["bank"] = match.group(1).strip()
                        else:
                            result["bank"] = "Claro Pay"
                        logger.info("payment_parser_bank_found", bank=result["bank"])
                        break
            except Exception as e:
                logger.debug("payment_parser_bank_selector_failed", selector=selector, error=str(e))
                continue

        if not result["bank"]:
            result["bank"] = "Claro Pay"  # По умолчанию

        # Извлекаем Amount
        amount_selectors = [
            '*:has-text("Amount")',
            '[data-field="amount"]',
            '[name="amount"]',
            '*:has-text("$")',
        ]

        for selector in amount_selectors:
            try:
                amount_elem = await page.query_selector(selector)
                if amount_elem:
                    amount_text = await amount_elem.inner_text()
                    # Ищем сумму в формате $X,XXX или $XXXX
                    match = re.search(r'\$\s*([\d,]+\.?\d*)', amount_text)
                    if match:
                        result["amount"] = match.group(0)  # Сохраняем с символом $
                        logger.info("payment_parser_amount_found", amount=result["amount"])
                        break
            except Exception as e:
                logger.debug("payment_parser_amount_selector_failed", selector=selector, error=str(e))
                continue

        # Устанавливаем method и payment_type
        result["method"] = "Claro Pay"
        result["payment_type"] = "Fiat"
        
        # Извлекаем домен из URL
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(page.url)
            result["domain"] = parsed_url.netloc
            logger.info("payment_parser_domain_extracted", domain=result["domain"])
        except Exception as e:
            logger.warning("payment_parser_domain_extraction_failed", error=str(e))
            result["domain"] = None

        # Делаем финальный скриншот (если еще не сделан)
        if "screenshot" not in result or not result["screenshot"]:
            try:
                screenshot_bytes = await page.screenshot(full_page=True)
                # Сохраняем в base64 для ответа
                result["screenshot"] = base64.b64encode(screenshot_bytes).decode('utf-8')
                
                # Сохраняем в файл
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_filename = f"payment_form_{timestamp}.png"
                screenshot_path = SCREENSHOTS_DIR / screenshot_filename
                screenshot_path.write_bytes(screenshot_bytes)
                result["screenshot_path"] = str(screenshot_path)
                
                logger.info("payment_parser_screenshot_taken", path=str(screenshot_path))
            except Exception as e:
                logger.warning("payment_parser_screenshot_failed", error=str(e))

        # Проверяем успешность - теперь без требования CVU
        # Успех определяется тем, что мы дошли до страницы депозита и выбрали метод оплаты
        if result.get("method") == "Claro Pay" and result.get("url"):
            result["success"] = True
            logger.info("payment_parser_success", 
                       domain=result.get("domain"), 
                       method=result.get("method"),
                       url=result.get("url"))
        else:
            result["success"] = False
            result["error"] = "Failed to select payment method or navigate to deposit page"
            logger.warning("payment_parser_failed", 
                          method=result.get("method"), 
                          url=result.get("url"))

    except PlaywrightTimeoutError as e:
        result["error"] = f"Timeout: {str(e)}"
        logger.error("payment_parser_timeout", error=str(e))
    except Exception as e:
        result["error"] = str(e)
        logger.error("payment_parser_error", error=str(e), exc_info=True)
    finally:
            try:
                if page:
                    await page.close()
                if context:
                    if playwright:
                        # Для persistent context закрываем context и playwright
                        await context.close()
                        await playwright.stop()
                    elif browser_pool_context:
                        # Для обычного browser pool просто закрываем context
                        # browser pool сам вернет браузер в очередь
                        await context.close()
            except Exception as e:
                logger.debug("payment_parser_cleanup_failed", error=str(e))
            
            # Если использовали browser pool, возвращаем браузер в пул
            if browser_pool_context and not playwright:
                try:
                    await browser_pool_context_manager.__aexit__(None, None, None)
                except:
                    pass

    return result
