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
SCREENSHOTS_DIR = Path(os.path.expanduser("~/.cache/1win_ar/screenshots"))
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Отдельная папка для скриншотов провайдера
PROVIDER_SCREENSHOTS_DIR = Path(os.path.expanduser("~/.cache/1win_ar/screenshots/provider"))
PROVIDER_SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Путь к профилю браузера для persistent context (сохранение cookies/session)
# Если путь указан, парсер будет использовать сохраненную сессию
PAYMENT_PARSER_USER_DATA_DIR = os.environ.get(
    "PAYMENT_PARSER_USER_DATA_DIR",
    os.path.join(os.path.expanduser("~"), ".cache", "1win_ar", "profile")
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
                headless=False,  # Включаем визуальный режим для отладки
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
                ignore_https_errors=True,  # Разрешаем ошибки HTTPS для быстрой загрузки
                locale="en-US",
                timezone_id="America/New_York",
            )
            page = context.pages[0] if context.pages else await context.new_page()
            
            # НЕ блокируем ресурсы через route - это замедляет загрузку страницы
            # Вместо этого будем перехватывать только навигацию после кликов (если нужно)
            # async def handle_route(route):
            #     url = route.request.url
            #     # Блокируем промо-редиректы
            #     if "trid=" in url or "banner" in url:
            #         logger.debug("payment_parser_blocking_promo_redirect", url=url)
            #         await route.abort()
            #     else:
            #         await route.continue_()
            # 
            # # Включаем перехват навигации
            # await context.route("**/*promotions*trid=**", handle_route)
            # await context.route("**/*banner**", handle_route)
            
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
                
                // Перехватываем window.location для предотвращения промо-редиректов
                const originalLocation = window.location;
                let locationProxy = new Proxy(originalLocation, {
                    set: function(target, property, value) {
                        if (property === 'href' && (value.includes('trid=') || value.includes('banner'))) {
                            console.log('Blocked promo redirect:', value);
                            return false;
                        }
                        target[property] = value;
                        return true;
                    }
                });
                
                // Переопределяем history.pushState и replaceState
                const originalPushState = history.pushState;
                const originalReplaceState = history.replaceState;
                
                history.pushState = function(...args) {
                    const url = args[2];
                    if (url && (url.includes('trid=') || url.includes('banner'))) {
                        console.log('Blocked promo pushState:', url);
                        return;
                    }
                    return originalPushState.apply(history, args);
                };
                
                history.replaceState = function(...args) {
                    const url = args[2];
                    if (url && (url.includes('trid=') || url.includes('banner'))) {
                        console.log('Blocked promo replaceState:', url);
                        return;
                    }
                    return originalReplaceState.apply(history, args);
                };
                
                // Агрессивный перехват window.location
                let locationBlocked = false;
                const originalLocationSetter = Object.getOwnPropertyDescriptor(window, 'location').set;
                Object.defineProperty(window, 'location', {
                    set: function(value) {
                        if (locationBlocked) return;
                        if (value && (value.includes('trid=') || value.includes('banner'))) {
                            console.log('Blocked promo location set:', value);
                            locationBlocked = true;
                            setTimeout(() => { locationBlocked = false; }, 1000);
                            return;
                        }
                        originalLocationSetter.call(window, value);
                    },
                    get: function() {
                        return window.location;
                    }
                });
                
                // Перехватываем все события клика для предотвращения промо-редиректов
                document.addEventListener('click', function(e) {
                    const target = e.target;
                    const href = target.href || target.closest('a')?.href || '';
                    if (href && (href.includes('trid=') || href.includes('banner'))) {
                        e.preventDefault();
                        e.stopPropagation();
                        e.stopImmediatePropagation();
                        console.log('Blocked promo click:', href);
                        return false;
                    }
                }, true);
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
    
    # Перехватываем навигацию для предотвращения промо-редиректов
    navigation_blocked = False
    async def handle_navigation(frame):
        nonlocal navigation_blocked
        url = frame.url
        if (url and ("trid=" in url or "banner" in url)) and not navigation_blocked:
            navigation_blocked = True
            logger.warning("payment_parser_blocking_promo_navigation", url=url)
            try:
                # Возвращаемся на предыдущую страницу или главную
                await page.go_back(timeout=2000)
            except:
                try:
                    await page.goto(base_url, timeout=5000)
                except:
                    pass
            navigation_blocked = False
    
    page.on("framenavigated", handle_navigation)
    
    # Основной код парсинга (выполняется для обоих вариантов)
    try:
        # Шаг 1: Переход на главную страницу с полной загрузкой (как при ручном вводе)
        logger.info("payment_parser_navigating", url=base_url, skip_login=skip_login)
        try:
            # Используем networkidle для полной загрузки страницы (как при ручном вводе)
            logger.info("payment_parser_waiting_for_full_page_load")
            await page.goto(base_url, wait_until="networkidle", timeout=30000)  # Увеличиваем таймаут до 30 секунд
            logger.info("payment_parser_page_loaded_networkidle")
            # Дополнительное ожидание для динамического контента (как при ручном вводе)
            await page.wait_for_timeout(5000)  # Даем 5 секунд на загрузку динамического контента
            
            # Проверяем, что страница действительно загрузилась
            page_ready = await page.evaluate("""
                () => {
                    return {
                        readyState: document.readyState,
                        bodyTextLength: document.body?.innerText?.length || 0,
                        hasContent: document.body && document.body.innerText.length > 100
                    };
                }
            """)
            logger.info("payment_parser_page_ready_check", 
                       ready_state=page_ready.get('readyState'),
                       body_text_length=page_ready.get('bodyTextLength'),
                       has_content=page_ready.get('hasContent'))
        except Exception as e:
            logger.warning("payment_parser_goto_networkidle_failed", error=str(e)[:200])
            # Fallback: пробуем с load
            try:
                await page.goto(base_url, wait_until="load", timeout=30000)
                await page.wait_for_timeout(5000)
                logger.info("payment_parser_page_loaded_with_load")
            except Exception as e2:
                logger.warning("payment_parser_goto_load_failed", error=str(e2)[:200])
                # Последняя попытка с domcontentloaded
                try:
                    await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(10000)  # Увеличиваем ожидание до 10 секунд
                    logger.info("payment_parser_page_loaded_with_domcontentloaded")
                except Exception as e3:
                    logger.error("payment_parser_all_navigation_methods_failed", error=str(e3)[:200])

        # Шаг 1.5: Проверка, авторизован ли уже пользователь (если используется persistent context)
        # Улучшенная проверка с ожиданием полной загрузки страницы
        # Дополнительное ожидание для загрузки динамического контента
        logger.info("payment_parser_waiting_for_page_content", skip_login=skip_login, use_persistent_context=use_persistent_context)
        await page.wait_for_timeout(5000)  # Ждем дополнительное время на загрузку страницы
        
        # Проверяем, что страница загрузилась достаточно - до 5 попыток по 2 секунды
        page_text_length = 0
        for wait_attempt in range(5):  # До 5 попыток по 2 секунды = 10 секунд максимум
            page_text_check = await page.inner_text('body')
            page_text_length = len(page_text_check)
            if page_text_length > 500:  # Если страница загрузилась достаточно
                logger.info("payment_parser_page_content_loaded", attempt=wait_attempt+1, text_length=page_text_length)
                break
            else:
                logger.debug("payment_parser_waiting_for_content", attempt=wait_attempt+1, text_length=page_text_length)
                await page.wait_for_timeout(2000)
        
        if skip_login or use_persistent_context:
            logger.info("payment_parser_checking_auth_status", skip_login=skip_login, use_persistent_context=use_persistent_context, page_text_length=page_text_length)
            
            # Проверяем, что страница загрузилась полностью
            page_content_check = await page.evaluate("""
                () => {
                    const bodyText = document.body?.innerText || '';
                    const bodyLength = bodyText.length;
                    const hasSubstantialContent = bodyLength > 500; // Минимум 500 символов для загруженной страницы
                    
                    // Ищем индикаторы авторизации
                    const hasBalance = bodyText.includes('balance') || bodyText.includes('Balance') || bodyText.includes('Balance');
                    const hasDeposit = bodyText.includes('Deposit') || bodyText.includes('Depositar') || bodyText.includes('Depósito');
                    const hasUserMenu = document.querySelector('[class*="user"], [class*="profile"], [class*="account"], [id*="user"], [id*="profile"]');
                    const hasLoginButton = bodyText.includes('Войти') || bodyText.includes('Login') || bodyText.includes('Ingresar') || bodyText.includes('Entrar');
                    
                    return {
                        bodyLength: bodyLength,
                        hasSubstantialContent: hasSubstantialContent,
                        hasBalance: hasBalance,
                        hasDeposit: hasDeposit,
                        hasUserMenu: !!hasUserMenu,
                        hasLoginButton: hasLoginButton,
                        isLoggedIn: hasSubstantialContent && (hasBalance || hasDeposit || hasUserMenu) && !hasLoginButton
                    };
                }
            """)
            
            logger.info("payment_parser_auth_check_result",
                       body_length=page_content_check.get('bodyLength'),
                       has_substantial_content=page_content_check.get('hasSubstantialContent'),
                       has_balance=page_content_check.get('hasBalance'),
                       has_deposit=page_content_check.get('hasDeposit'),
                       has_user_menu=page_content_check.get('hasUserMenu'),
                       has_login_button=page_content_check.get('hasLoginButton'),
                       is_logged_in=page_content_check.get('isLoggedIn'))
            
            # Если страница не загрузилась полностью или нет индикаторов авторизации - требуем логин
            if not page_content_check.get('hasSubstantialContent') or not page_content_check.get('isLoggedIn'):
                logger.warning("payment_parser_auth_check_failed_or_page_not_loaded",
                             body_length=page_content_check.get('bodyLength'),
                             has_substantial_content=page_content_check.get('hasSubstantialContent'),
                             is_logged_in=page_content_check.get('isLoggedIn'))
                skip_login = False  # Требуем логин, если страница не загружена или нет признаков авторизации
            else:
                logger.info("payment_parser_already_logged_in", 
                           message="User already logged in, skipping login",
                           body_length=page_content_check.get('bodyLength'))
                skip_login = True  # Пользователь уже авторизован

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
        
        # Убеждаемся, что страница полностью загружена перед поиском кнопки Deposit
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)  # Увеличиваем таймаут
            logger.info("payment_parser_page_loaded_networkidle_before_deposit")
        except:
            logger.debug("payment_parser_networkidle_timeout_before_deposit")
            # Fallback: ждем load
            try:
                await page.wait_for_load_state("load", timeout=10000)
                logger.info("payment_parser_page_loaded_load_before_deposit")
            except:
                logger.debug("payment_parser_load_timeout_before_deposit")
        
        # Дополнительное ожидание для динамических элементов
        await page.wait_for_timeout(7000)  # Увеличиваем до 7 секунд для полной загрузки
        
        # Проверяем, что страница загружена и есть контент
        page_content_check = await page.evaluate("""
            () => {
                return {
                    bodyText: document.body?.innerText?.length || 0,
                    hasElements: document.querySelectorAll('*').length,
                    readyState: document.readyState,
                    hasButtons: document.querySelectorAll('button').length
                };
            }
        """)
        logger.info("payment_parser_page_content_check", 
                   body_text_length=page_content_check.get('bodyText'),
                   elements_count=page_content_check.get('hasElements'),
                   ready_state=page_content_check.get('readyState'),
                   buttons_count=page_content_check.get('hasButtons'))
        
        # Если элементов мало, ждем еще
        if page_content_check.get('hasElements', 0) < 500:
            logger.warning("payment_parser_page_not_fully_loaded", elements=page_content_check.get('hasElements'))
            await page.wait_for_timeout(5000)
            # Пробуем обновить страницу, если она не загрузилась
            try:
                await page.reload(wait_until="load", timeout=15000)
                await page.wait_for_timeout(5000)
                logger.info("payment_parser_page_reloaded")
            except:
                logger.debug("payment_parser_page_reload_failed")
        
        # Проверяем промо-ссылки и сбрасываем (как в STD боте)
        is_promo = "trid=" in page.url or "banner" in page.url
        is_wrong_site = "1win.lat" not in page.url
        if is_wrong_site or is_promo:
            logger.info("payment_parser_promo_url_detected", url=page.url, action="resetting")
            await page.goto("about:blank")
            await page.wait_for_timeout(500)
            await page.goto(base_url, timeout=wait_seconds * 1000)
            await page.wait_for_timeout(3000)
            if "trid=" in page.url:
                logger.warning("payment_parser_still_promo_after_reset", action="clicking_logo")
                try:
                    await page.locator('a[href="/"]').first.click(timeout=3000)
                    await page.wait_for_timeout(2000)
                except:
                    pass
        
        # Проверяем текущий URL - может быть мы уже на странице депозита
        current_url = page.url.lower()
        deposit_clicked = False
        
        # Метод 1: НЕ используем JS для клика, так как селектор :has-text() не работает в JS
        # Вместо этого сразу ищем кнопку Deposit через Playwright и кликаем на неё
        # Модальное окно должно открыться на той же странице без редиректа
        
        # Метод 2: Ищем кнопку Deposit на главной странице и кликаем на неё
        if not deposit_clicked:
            # Сначала снова проверяем и закрываем промо-баннеры
            try:
                await page.evaluate("""
                    () => {
                        const closeButtons = document.querySelectorAll(
                            'button[aria-label*="close" i], ' +
                            '[class*="close"][class*="promo" i], ' +
                            '[class*="dismiss"][class*="banner" i]'
                        );
                        for (const btn of closeButtons) {
                            const style = window.getComputedStyle(btn);
                            if (style.display !== 'none' && style.visibility !== 'hidden') {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                await page.wait_for_timeout(1000)
            except:
                pass
            
            # Делаем скриншот перед анализом DOM
            try:
                await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "before_deposit_search.png"))
                logger.info("payment_parser_screenshot_before_deposit_search")
            except:
                pass
            
            # Анализ DOM для поиска точного селектора кнопки Deposit
            logger.info("payment_parser_analyzing_dom_for_deposit_button", url=page.url[:80])
            try:
                # Сначала ждем, пока все элементы загрузятся
                await page.wait_for_timeout(2000)
                
                dom_analysis = await page.evaluate("""
                    () => {
                        const results = {
                            buttons: [],
                            links: [],
                            elements_with_deposit_text: []
                        };
                        
                        // Ищем все кнопки, ссылки и кликабельные элементы
                        const allClickable = document.querySelectorAll('button, [role="button"], a, [onclick], [class*="button"], [class*="btn"], [class*="deposit"]');
                        allClickable.forEach((el, idx) => {
                            const text = (el.innerText || el.textContent || '').toLowerCase().trim();
                            const href = el.getAttribute('href') || '';
                            const dataTestId = el.getAttribute('data-testid') || '';
                            const className = (el.className || '').toString();
                            const ariaLabel = (el.getAttribute('aria-label') || '').toString();
                            const title = (el.getAttribute('title') || '').toString();
                            
                            // Расширенный поиск: deposit, depositar, пополнить, пополнение, депозит
                            if (text.includes('deposit') || text.includes('depositar') || text.includes('пополнить') || 
                                text.includes('пополнение') || text.includes('депозит') ||
                                href.toLowerCase().includes('deposit') || 
                                dataTestId.toLowerCase().includes('deposit') ||
                                (className && typeof className === 'string' && className.toLowerCase().includes('deposit')) ||
                                (ariaLabel && ariaLabel.toLowerCase().includes('deposit')) ||
                                (title && title.toLowerCase().includes('deposit'))) {
                                const style = window.getComputedStyle(el);
                                const isVisible = style.display !== 'none' && style.visibility !== 'hidden' && 
                                                 style.opacity !== '0' && el.offsetWidth > 0 && el.offsetHeight > 0;
                                
                                let selector = null;
                                if (el.id) {
                                    selector = `#${el.id}`;
                                } else if (dataTestId) {
                                    selector = `[data-testid="${dataTestId}"]`;
                                } else if (className) {
                                    const firstClass = className.split(' ').filter(c => c && !c.includes(' '))[0];
                                    if (firstClass) selector = `.${firstClass}`;
                                }
                                
                                results.buttons.push({
                                    index: idx,
                                    tag: el.tagName.toLowerCase(),
                                    text: (el.innerText || el.textContent || '').substring(0, 50),
                                    href: href.substring(0, 100),
                                    dataTestId: dataTestId,
                                    className: className.substring(0, 100),
                                    visible: isVisible,
                                    position: style.position,
                                    zIndex: style.zIndex,
                                    selector: selector
                                });
                            }
                        });
                        
                        // Ищем элементы с текстом Deposit в видимом тексте (более широкий поиск)
                        const allElements = document.querySelectorAll('*');
                        allElements.forEach((el) => {
                            const text = (el.innerText || el.textContent || '').toLowerCase().trim();
                            // Ищем короткие тексты, которые могут быть кнопками
                            if ((text === 'deposit' || text === 'depositar' || text === 'пополнить' ||
                                 text.includes('deposit') || text.includes('depositar') || text.includes('пополнить')) && 
                                text.length < 50 && text.length > 0) { // Только короткие тексты (названия кнопок)
                                const style = window.getComputedStyle(el);
                                const isVisible = style.display !== 'none' && style.visibility !== 'hidden';
                                
                                if (isVisible) {
                                    let selector = null;
                                    if (el.id) {
                                        selector = `#${el.id}`;
                                    } else if (el.getAttribute('data-testid')) {
                                        selector = `[data-testid="${el.getAttribute('data-testid')}"]`;
                                    } else if (el.className) {
                                        const firstClass = el.className.split(' ').filter(c => c && !c.includes(' '))[0];
                                        if (firstClass) selector = `.${firstClass}`;
                                    }
                                    
                                    results.elements_with_deposit_text.push({
                                        text: (el.innerText || el.textContent || '').substring(0, 50),
                                        tag: el.tagName.toLowerCase(),
                                        className: el.className?.substring(0, 100),
                                        id: el.id,
                                        dataTestId: el.getAttribute('data-testid'),
                                        visible: true,
                                        selector: selector
                                    });
                                }
                            }
                        });
                        
                        return results;
                    }
                """)
                logger.info("payment_parser_dom_analysis_result", 
                           buttons_found=len(dom_analysis.get('buttons', [])),
                           elements_with_text=len(dom_analysis.get('elements_with_deposit_text', [])))
                
                if dom_analysis.get('buttons'):
                    visible_buttons = [b for b in dom_analysis['buttons'] if b.get('visible')]
                    logger.info("payment_parser_deposit_buttons_in_dom", 
                               total=len(dom_analysis['buttons']),
                               visible=len(visible_buttons),
                               buttons=visible_buttons[:3])
                
                if dom_analysis.get('elements_with_deposit_text'):
                    logger.info("payment_parser_deposit_text_elements_in_dom", 
                               elements=dom_analysis['elements_with_deposit_text'][:3])
                
                # Пробуем использовать найденные селекторы
                if dom_analysis.get('buttons'):
                    for btn_info in dom_analysis['buttons']:
                        if btn_info.get('visible') and btn_info.get('selector'):
                            try:
                                logger.info("payment_parser_trying_selector_from_dom", selector=btn_info['selector'])
                                btn = page.locator(btn_info['selector']).first
                                if await btn.is_visible(timeout=2000):
                                    await btn.scroll_into_view_if_needed()
                                    await page.wait_for_timeout(500)
                                    await btn.click()
                                    await page.wait_for_timeout(3000)
                                    # Проверяем модальное окно
                                    try:
                                        modal = page.locator('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"]').first
                                        if await modal.is_visible(timeout=3000):
                                            deposit_clicked = True
                                            logger.info("payment_parser_deposit_clicked_via_dom_selector", selector=btn_info['selector'])
                                            break
                                    except:
                                        pass
                            except Exception as e:
                                logger.debug("payment_parser_dom_selector_failed", selector=btn_info.get('selector'), error=str(e)[:100])
                                continue
            except Exception as e:
                logger.debug("payment_parser_dom_analysis_failed", error=str(e)[:100])
            
            # Пробуем разные способы найти кнопку депозита
            # Метод 0: Сначала пробуем найти по data-testid (самый надежный способ)
            try:
                deposit_by_testid = page.locator('[data-testid="header-balance-deposit-button"]')
                count = await deposit_by_testid.count()
                logger.info("payment_parser_deposit_by_testid_search", count=count, testid="header-balance-deposit-button")
                if count > 0:
                    is_visible = await deposit_by_testid.first.is_visible(timeout=2000)
                    if is_visible:
                        await deposit_by_testid.first.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        try:
                            await deposit_by_testid.first.click(timeout=5000)
                            deposit_clicked = True
                            logger.info("payment_parser_deposit_clicked_via_testid")
                        except Exception as e:
                            logger.debug("payment_parser_deposit_testid_click_failed", error=str(e)[:100])
                            # Fallback: клик через JavaScript
                            try:
                                await deposit_by_testid.first.evaluate("(el) => el.click()")
                                deposit_clicked = True
                                logger.info("payment_parser_deposit_clicked_via_testid_js")
                            except:
                                pass
            except Exception as e:
                logger.debug("payment_parser_deposit_testid_search_failed", error=str(e)[:100])
            
            # Пробуем разные способы найти кнопку депозита
            # Пробуем найти по тексту
            if not deposit_clicked:
                deposit_texts = ["Deposit", "Depositar", "Depósito", "Пополнить"]
                logger.info("payment_parser_searching_deposit_button", texts=deposit_texts, url=page.url[:80])
                for text in deposit_texts:
                    try:
                        deposit_locator = page.get_by_text(text, exact=False)
                        count = await deposit_locator.count()
                        logger.debug("payment_parser_deposit_text_search", text=text, count=count)
                        if count > 0:
                            logger.info("payment_parser_found_deposit_button", text=text, count=count)
                            
                            # Ждем, пока элемент станет видимым и кликабельным
                            try:
                                await deposit_locator.first.wait_for(state="visible", timeout=5000)
                                logger.info("payment_parser_deposit_button_visible")
                            except Exception as e:
                                logger.warning("payment_parser_deposit_button_not_visible", error=str(e)[:100])
                            
                            # Скроллим к элементу
                            try:
                                await deposit_locator.first.scroll_into_view_if_needed(timeout=3000)
                                await page.wait_for_timeout(1000)
                                logger.info("payment_parser_deposit_button_scrolled_into_view")
                            except Exception as e:
                                logger.debug("payment_parser_deposit_scroll_failed", error=str(e)[:100])
                            
                            # Делаем скриншот перед кликом
                            try:
                                await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "before_deposit_click.png"))
                                logger.info("payment_parser_screenshot_before_deposit_click")
                            except:
                                pass
                            
                            # Пробуем кликнуть через координаты (более надежно)
                            try:
                                # Проверяем, что элемент действительно видим
                                is_visible = await deposit_locator.first.is_visible(timeout=2000)
                                logger.info("payment_parser_deposit_button_is_visible_check", visible=is_visible)
                                
                                if not is_visible:
                                    logger.warning("payment_parser_deposit_button_not_visible_for_click")
                                    continue
                                
                                # Получаем bounding_box с несколькими попытками
                                box = None
                                for attempt in range(3):
                                    try:
                                        box = await deposit_locator.first.bounding_box(timeout=2000)
                                        if box and box.get('x') is not None and box.get('y') is not None:
                                            logger.info("payment_parser_bounding_box_success", attempt=attempt+1, box=box)
                                            break
                                        logger.debug("payment_parser_bounding_box_attempt", attempt=attempt+1, box=box)
                                        await page.wait_for_timeout(500)
                                    except Exception as e:
                                        logger.debug("payment_parser_bounding_box_error", attempt=attempt+1, error=str(e)[:100])
                                        await page.wait_for_timeout(500)
                                
                                logger.info("payment_parser_deposit_button_bounding_box_final", 
                                           box=box if box else None,
                                           has_coords=box and box.get('x') is not None if box else False)
                                
                                if box and box.get('x') is not None:
                                    logger.info("payment_parser_deposit_button_box", 
                                              x=box['x'], y=box['y'], width=box['width'], height=box['height'])
                                    
                                    # Кликаем через координаты
                                    logger.info("payment_parser_clicking_deposit_via_coordinates")
                                    await page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                                else:
                                    # Fallback: клик через JavaScript напрямую по элементу
                                    logger.warning("payment_parser_bounding_box_none_using_js_click")
                                    try:
                                        await deposit_locator.first.evaluate("(element) => { element.click(); }")
                                        logger.info("payment_parser_deposit_clicked_via_js_evaluate")
                                    except Exception as js_e:
                                        logger.debug("payment_parser_js_click_failed", error=str(js_e)[:100])
                                        # Последняя попытка: обычный клик Playwright
                                        try:
                                            await deposit_locator.first.click(timeout=3000)
                                            logger.info("payment_parser_deposit_clicked_via_normal_click")
                                        except Exception as click_e:
                                            logger.warning("payment_parser_all_click_methods_failed", error=str(click_e)[:100])
                                            continue
                                
                                # После любого успешного клика проверяем результат
                                # Ждем и проверяем URL каждые 500мс
                                for check in range(10):  # Проверяем 10 раз (5 секунд)
                                    await page.wait_for_timeout(500)
                                    current_url = page.url
                                    logger.info("payment_parser_url_check_after_click", 
                                              check=check+1, url=current_url[:80])
                                    
                                    # Проверяем модальное окно
                                    try:
                                        modal = page.locator('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"]').first
                                        if await modal.is_visible(timeout=500):
                                            logger.info("payment_parser_modal_found_after_click", check=check+1)
                                            deposit_clicked = True
                                            break
                                    except:
                                        pass
                                    
                                    # Если произошел редирект на промо
                                    if "promotions" in current_url or "trid=" in current_url:
                                        logger.warning("payment_parser_redirected_to_promo_after_click", 
                                                     check=check+1, url=current_url)
                                        # Делаем скриншот промо-страницы
                                        try:
                                            await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "promo_page_after_deposit.png"))
                                            logger.info("payment_parser_screenshot_promo_page")
                                        except:
                                            pass
                                        break
                                
                                if deposit_clicked:
                                    logger.info("payment_parser_deposit_clicked_modal_appeared", text=text, method="js_or_coordinates")
                                    break
                                elif "promotions" not in page.url and "trid=" not in page.url:
                                    deposit_clicked = True
                                    logger.info("payment_parser_deposit_clicked_no_redirect", text=text, method="js_or_coordinates")
                                    break
                            except Exception as e:
                                logger.debug("payment_parser_coordinates_click_failed", error=str(e))
                                # Fallback на обычный клик
                                try:
                                    logger.info("payment_parser_trying_normal_click")
                                    await deposit_locator.first.click()
                                    await page.wait_for_timeout(2000)
                                    logger.info("payment_parser_url_after_normal_click", url=page.url[:80])
                                    
                                    # Проверяем, появилось ли модальное окно
                                    modal_check = await page.locator('div.paywidget-app, [class*="paywidget"]').first.is_visible(timeout=3000)
                                    if modal_check or "promotions" not in page.url:
                                        deposit_clicked = True
                                        logger.info("payment_parser_deposit_clicked", text=text, method="click")
                                        break
                                except Exception as e2:
                                    logger.debug("payment_parser_normal_click_failed", error=str(e2))
                                    pass
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
                logger.warning("payment_parser_deposit_button_not_found_after_all_attempts")
        
        # После клика на Deposit ждем появления модального окна (БЕЗ редиректа)
        if deposit_clicked:
            logger.info("payment_parser_waiting_for_modal_after_deposit_click", url=page.url[:80])
            await page.wait_for_timeout(3000)  # Даем время на открытие модального окна
            
            # Проверяем, появилось ли модальное окно
            try:
                modal_check = await page.locator('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"]').first.is_visible(timeout=5000)
                if modal_check:
                    logger.info("payment_parser_modal_appeared_after_deposit_click")
                else:
                    logger.warning("payment_parser_modal_not_visible_after_deposit_click")
            except:
                logger.warning("payment_parser_modal_not_found_after_deposit_click")
        
        # Шаг 7: Выбор метода оплаты Claro Pay (логика как в 1winSTD-bot)
        logger.info("payment_parser_selecting_payment_method")
        logger.debug("payment_parser_current_url", url=page.url)
        
        # Агрессивное ожидание модального окна с перехватом редиректов
        logger.info("payment_parser_aggressive_modal_wait")
        modal_appeared = False
        
        # Используем wait_for_function для более надежного ожидания
        try:
            await page.wait_for_function("""
                () => {
                    const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"]');
                    if (modal) {
                        const style = window.getComputedStyle(modal);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            return true;
                        }
                    }
                    return false;
                }
            """, timeout=15000)
            modal_appeared = True
            logger.info("payment_parser_modal_appeared_via_wait_for_function")
        except Exception as e:
            logger.debug("payment_parser_wait_for_function_failed", error=str(e))
            # Fallback: пробуем найти модальное окно вручную с перехватом редиректов
            for attempt in range(10):  # Пробуем 10 раз с интервалом
                try:
                    modal = page.locator('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"]').first
                    if await modal.is_visible(timeout=1500):
                        modal_appeared = True
                        logger.info("payment_parser_modal_appeared_after_deposit", attempt=attempt+1)
                        break
                except:
                    pass
                
                # Проверяем, не произошел ли редирект
                current_url = page.url
                if "promotions" in current_url or "trid=" in current_url:
                    logger.warning("payment_parser_redirected_during_wait", attempt=attempt+1, url=current_url)
                    # Пробуем вернуться назад и найти модальное окно
                    try:
                        await page.go_back(timeout=2000)
                        await page.wait_for_timeout(1000)
                        # Пробуем открыть модальное окно через JS
                        modal_opened = await page.evaluate("""
                            () => {
                                const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"]');
                                if (modal) {
                                    modal.style.display = 'block';
                                    modal.style.visibility = 'visible';
                                    modal.style.zIndex = '99999';
                                    modal.style.position = 'fixed';
                                    modal.style.top = '0';
                                    modal.style.left = '0';
                                    modal.style.width = '100%';
                                    modal.style.height = '100%';
                                    return true;
                                }
                                return false;
                            }
                        """)
                        if modal_opened:
                            logger.info("payment_parser_modal_opened_after_go_back")
                            modal_appeared = True
                            break
                    except:
                        pass
                
                await page.wait_for_timeout(1000)
        
        # Проверяем промо-редирект после перехода на Deposit
        await page.wait_for_timeout(2000)
        current_url_after_deposit = page.url
        is_promo_after_deposit = "trid=" in current_url_after_deposit or "banner" in current_url_after_deposit
        
        if is_promo_after_deposit:
            logger.warning("payment_parser_promo_redirect_after_deposit", url=current_url_after_deposit)
            
            # Пробуем закрыть промо-баннер (если есть кнопка закрытия)
            try:
                logger.info("payment_parser_trying_to_close_promo_banner")
                close_selectors = [
                    'button[aria-label*="close" i]',
                    'button[aria-label*="закрыть" i]',
                    '[class*="close" i]',
                    '[class*="dismiss" i]',
                    'button:has-text("×")',
                    'button:has-text("✕")',
                    '[data-testid*="close" i]',
                    'svg[class*="close"]',
                    '[role="button"][aria-label*="close" i]',
                ]
                for selector in close_selectors:
                    try:
                        close_btn = page.locator(selector).first
                        if await close_btn.is_visible(timeout=2000):
                            await close_btn.click()
                            await page.wait_for_timeout(2000)
                            logger.info("payment_parser_promo_banner_closed", selector=selector)
                            # Проверяем, не произошел ли редирект обратно
                            if "trid=" not in page.url and "banner" not in page.url:
                                logger.info("payment_parser_redirected_away_from_promo_after_close")
                            break
                    except:
                        continue
                
                # Пробуем закрыть через JavaScript (если кнопка не видна)
                try:
                    closed_via_js = await page.evaluate("""
                        () => {
                            // Ищем все возможные кнопки закрытия
                            const closeButtons = document.querySelectorAll(
                                'button[aria-label*="close" i], ' +
                                '[class*="close" i], ' +
                                '[class*="dismiss" i], ' +
                                'svg[class*="close"]'
                            );
                            for (const btn of closeButtons) {
                                const style = window.getComputedStyle(btn);
                                if (style.display !== 'none' && style.visibility !== 'hidden') {
                                    btn.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    if closed_via_js:
                        logger.info("payment_parser_promo_banner_closed_via_js")
                        await page.wait_for_timeout(2000)
                except Exception as e:
                    logger.debug("payment_parser_js_close_failed", error=str(e))
                    
            except Exception as e:
                logger.debug("payment_parser_close_promo_failed", error=str(e))
            
            # Пробуем открыть модальное окно через JavaScript (если оно есть в DOM)
            try:
                logger.info("payment_parser_trying_js_modal_open")
                modal_opened = await page.evaluate("""
                    () => {
                        // Пробуем найти модальное окно и открыть его
                        const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], [class*="deposit-modal"]');
                        if (modal) {
                            if (modal.style.display === 'none' || modal.style.visibility === 'hidden') {
                                modal.style.display = 'block';
                                modal.style.visibility = 'visible';
                                return true;
                            }
                            // Модальное окно уже видно
                            return true;
                        }
                        // Пробуем вызвать событие открытия депозита через кнопку
                        const depositBtn = document.querySelector('[data-testid*="deposit" i], a[href*="deposit" i], button[data-action*="deposit" i], button:has-text("Deposit")');
                        if (depositBtn) {
                            depositBtn.click();
                            return true;
                        }
                        return false;
                    }
                """)
                if modal_opened:
                    logger.info("payment_parser_js_modal_opened")
                    await page.wait_for_timeout(3000)
            except Exception as e:
                logger.debug("payment_parser_js_modal_failed", error=str(e))
            
            # Если JS не помог, пробуем вернуться на главную и кликнуть на Deposit
            if is_promo_after_deposit:
                try:
                    logger.info("payment_parser_resetting_to_homepage")
                    await page.goto(base_url, timeout=wait_seconds * 1000)
                    await page.wait_for_timeout(3000)
                    # Пробуем снова кликнуть на Deposit
                    deposit_texts = ["Deposit", "Depositar", "Depósito"]
                    for text in deposit_texts:
                        try:
                            deposit_locator = page.get_by_text(text, exact=False)
                            if await deposit_locator.count() > 0:
                                await deposit_locator.first.click()
                                await page.wait_for_timeout(5000)  # Увеличиваем ожидание
                                # Проверяем, не произошел ли снова редирект
                                if "trid=" not in page.url and "banner" not in page.url:
                                    logger.info("payment_parser_deposit_clicked_after_promo_reset", text=text, url=page.url)
                                    break
                        except:
                            continue
                except Exception as e:
                    logger.warning("payment_parser_promo_reset_failed", error=str(e))
        
        await page.wait_for_timeout(5000)  # Увеличиваем ожидание после перехода на депозит

        # Проверяем, не произошел ли редирект на промо-страницу
        current_url_check = page.url
        is_promo_check = "trid=" in current_url_check or "banner" in current_url_check
        
        if is_promo_check:
            logger.warning("payment_parser_promo_redirect_before_modal_search", url=current_url_check)
            
            # Попытка 1: Вернуться назад и попробовать снова
            try:
                logger.info("payment_parser_trying_go_back_from_promo")
                await page.go_back(timeout=3000)
                await page.wait_for_timeout(2000)
                logger.info("payment_parser_went_back_from_promo", new_url=page.url)
            except:
                pass
            
            # Попытка 2: Найти модальное окно через JavaScript (может быть в DOM, но скрыто)
            try:
                modal_in_dom = await page.evaluate("""
                    () => {
                        const selectors = [
                            'div.paywidget-app',
                            '[class*="paywidget"]',
                            '[class*="payment-modal"]',
                            '[class*="deposit-modal"]',
                            'div[role="dialog"]'
                        ];
                        for (const sel of selectors) {
                            const el = document.querySelector(sel);
                            if (el) {
                                return {found: true, selector: sel, visible: window.getComputedStyle(el).display !== 'none'};
                            }
                        }
                        return {found: false};
                    }
                """)
                if modal_in_dom.get('found'):
                    logger.info("payment_parser_modal_found_in_dom_via_js", 
                              selector=modal_in_dom.get('selector'),
                              visible=modal_in_dom.get('visible'))
                    # Пробуем сделать модальное окно видимым
                    if not modal_in_dom.get('visible'):
                        await page.evaluate(f"""
                            () => {{
                                const el = document.querySelector('{modal_in_dom.get('selector')}');
                                if (el) {{
                                    el.style.display = 'block';
                                    el.style.visibility = 'visible';
                                    el.style.zIndex = '99999';
                                    el.style.position = 'fixed';
                                    el.style.top = '0';
                                    el.style.left = '0';
                                    el.style.width = '100%';
                                    el.style.height = '100%';
                                }}
                            }}
                        """)
                        await page.wait_for_timeout(2000)
            except Exception as e:
                logger.debug("payment_parser_js_modal_check_failed", error=str(e))
            
            # Попытка 3: Попробовать вызвать функцию открытия модального окна
            try:
                logger.info("payment_parser_trying_call_modal_function_on_promo")
                function_called = await page.evaluate("""
                    () => {
                        const funcs = ['openDepositModal', 'openDeposit', 'showDeposit', 'openPaymentModal', 'showPaymentModal'];
                        for (const f of funcs) {
                            if (typeof window[f] === 'function') {
                                try {
                                    window[f]();
                                    return {called: true, func: f};
                                } catch (e) {
                                    console.log('Function call failed:', f, e);
                                }
                            }
                        }
                        // Пробуем найти функцию в других объектах
                        const objects = [window, document, window.React, window.__REACT_DEVTOOLS_GLOBAL_HOOK__];
                        for (const obj of objects) {
                            if (obj) {
                                for (const f of funcs) {
                                    if (typeof obj[f] === 'function') {
                                        try {
                                            obj[f]();
                                            return {called: true, func: f, obj: obj.constructor.name};
                                        } catch (e) {
                                            console.log('Object function call failed:', f, e);
                                        }
                                    }
                                }
                            }
                        }
                        return {called: false};
                    }
                """)
                if function_called.get('called'):
                    logger.info("payment_parser_modal_function_called", 
                              func=function_called.get('func'),
                              obj=function_called.get('obj'))
                    await page.wait_for_timeout(2000)
            except Exception as e:
                logger.debug("payment_parser_function_call_failed", error=str(e))

        # Ищем модальное окно оплаты - пробуем разные селекторы
        payment_modal = None
        modal_found = False
        
        # Список селекторов для модального окна (в порядке приоритета)
        modal_selectors = [
            "div.paywidget-app",
            "[class*='paywidget']",
            "[class*='payment-modal']",
            "[class*='deposit-modal']",
            "div[role='dialog']",
            "[class*='modal'][class*='payment']",
            "[class*='modal'][class*='deposit']",
            "[class*='payment']",
            "[class*='deposit']",
        ]
        
        # Пробуем найти модальное окно
        for selector in modal_selectors:
            try:
                test_modal = page.locator(selector).first
                if await test_modal.is_visible(timeout=3000):
                    payment_modal = test_modal
                    modal_found = True
                    logger.info("payment_parser_payment_modal_found", selector=selector)
                    break
            except:
                continue
        
        # Если не нашли сразу, ждем появления
        if not modal_found:
            logger.info("payment_parser_waiting_for_modal_appearance")
            for selector in modal_selectors:
                try:
                    test_modal = page.locator(selector).first
                    await test_modal.wait_for(state="visible", timeout=15000)
                    payment_modal = test_modal
                    modal_found = True
                    logger.info("payment_parser_payment_modal_appeared", selector=selector)
                    break
                except:
                    continue
        
        # Если все еще не нашли, пробуем найти через текст "Deposit" в модальном окне
        if not modal_found:
            logger.warning("payment_parser_modal_not_found_trying_text_search")
            try:
                # Ищем элемент с текстом "Deposit" или "Fiat" / "Crypto" (признаки модального окна)
                deposit_text = page.get_by_text("Deposit", exact=False)
                if await deposit_text.count() > 0:
                    # Пробуем найти родительское модальное окно
                    modal_parent = await deposit_text.first.evaluate_handle("""
                        (el) => {
                            let current = el;
                            for (let i = 0; i < 15; i++) {
                                if (!current) break;
                                const tag = current.tagName.toLowerCase();
                                const style = window.getComputedStyle(current);
                                if (tag === 'div' && (
                                    style.position === 'fixed' || 
                                    style.position === 'absolute' ||
                                    current.getAttribute('role') === 'dialog' ||
                                    current.classList.toString().toLowerCase().includes('modal') ||
                                    current.classList.toString().toLowerCase().includes('payment') ||
                                    current.classList.toString().toLowerCase().includes('deposit')
                                )) {
                                    return current;
                                }
                                current = current.parentElement;
                            }
                            return null;
                        }
                    """)
                    if modal_parent:
                        payment_modal = page.locator('body')  # Используем body как fallback
                        modal_found = True
                        logger.info("payment_parser_modal_found_via_text_search")
            except Exception as e:
                logger.debug("payment_parser_text_search_failed", error=str(e))
        
        if not modal_found:
            logger.error("payment_parser_payment_modal_not_found_after_all_attempts")
            # Делаем скриншот для диагностики
            try:
                await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "modal_not_found.png"))
                logger.info("payment_parser_modal_not_found_screenshot_saved")
            except:
                pass
            # Используем body как fallback для поиска элементов
            payment_modal = page.locator('body')

        # Ищем Claro Pay - обновленная логика для карточек методов оплаты
        claro_clicked = False
        
        # Если модальное окно не найдено, пробуем найти его через JavaScript
        if not modal_found:
            logger.warning("payment_parser_modal_not_found_trying_js_search")
            try:
                modal_info = await page.evaluate("""
                    () => {
                        const selectors = [
                            'div.paywidget-app',
                            '[class*="paywidget"]',
                            '[class*="payment-modal"]',
                            '[class*="deposit-modal"]',
                            'div[role="dialog"]'
                        ];
                        for (const sel of selectors) {
                            const el = document.querySelector(sel);
                            if (el) {
                                const style = window.getComputedStyle(el);
                                return {
                                    found: true,
                                    selector: sel,
                                    visible: style.display !== 'none' && style.visibility !== 'hidden',
                                    zIndex: style.zIndex
                                };
                            }
                        }
                        return {found: false};
                    }
                """)
                if modal_info.get('found'):
                    logger.info("payment_parser_modal_found_via_js", 
                              selector=modal_info.get('selector'),
                              visible=modal_info.get('visible'))
                    # Если модальное окно скрыто, делаем его видимым
                    if not modal_info.get('visible'):
                        await page.evaluate(f"""
                            () => {{
                                const el = document.querySelector('{modal_info.get('selector')}');
                                if (el) {{
                                    el.style.display = 'block';
                                    el.style.visibility = 'visible';
                                    el.style.zIndex = '99999';
                                }}
                            }}
                        """)
                        await page.wait_for_timeout(2000)
                        modal_found = True
                        payment_modal = page.locator(modal_info.get('selector'))
                        logger.info("payment_parser_modal_made_visible_via_js")
            except Exception as e:
                logger.debug("payment_parser_js_modal_search_failed", error=str(e))
        
        if not modal_found:
            logger.warning("payment_parser_modal_not_found_cannot_find_claro")
            # Используем body как fallback для поиска элементов
            payment_modal = page.locator('body')
        else:
            # Метод 1: Ищем карточки методов оплаты через data-testid (как в STD боте)
            try:
                logger.info("payment_parser_searching_payment_method_cards")
                
                # Пробуем разные селекторы для карточек методов оплаты
                card_selectors = [
                    'button[data-testid^="payment-method-"]',
                    'div[data-testid^="payment-method-"]',
                    'button[class*="payment-method"]',
                    'div[class*="payment-method"]',
                    'button[class*="payment"]',
                    'div[class*="payment"]',
                    # Селекторы для карточек с текстом
                    '*:has-text("Claro Pay")',
                    '*:has-text("Airtm")',  # Для проверки наличия карточек
                ]
                
                buttons_locator = None
                for selector in card_selectors:
                    try:
                        test_locator = payment_modal.locator(selector)
                        count = await test_locator.count()
                        if count > 0:
                            buttons_locator = test_locator
                            logger.info("payment_parser_payment_cards_found", selector=selector, count=count)
                            break
                    except:
                        continue
                
                # Если не нашли через селекторы, ищем все кликабельные элементы с текстом "Claro Pay"
                if not buttons_locator:
                    logger.info("payment_parser_searching_claro_pay_directly")
                    # Ищем элемент с текстом "Claro Pay" в модальном окне
                    claro_elements = payment_modal.locator('*:has-text("Claro Pay")')
                    count = await claro_elements.count()
                    if count > 0:
                        logger.info("payment_parser_claro_pay_elements_found", count=count)
                        # Берем первый элемент и ищем его родительскую карточку
                        try:
                            claro_element = claro_elements.first
                            # Пробуем найти кликабельный родитель (button, div с cursor: pointer)
                            parent_card = await claro_element.evaluate_handle("""
                                (el) => {
                                    let current = el;
                                    for (let i = 0; i < 5; i++) {
                                        if (!current) break;
                                        const tag = current.tagName.toLowerCase();
                                        const style = window.getComputedStyle(current);
                                        if (tag === 'button' || 
                                            style.cursor === 'pointer' || 
                                            current.onclick || 
                                            current.getAttribute('role') === 'button' ||
                                            current.classList.toString().includes('payment') ||
                                            current.classList.toString().includes('method')) {
                                            return current;
                                        }
                                        current = current.parentElement;
                                    }
                                    return el.closest('button, div[role="button"], [class*="card"], [class*="payment"]');
                                }
                            """)
                            if parent_card:
                                # Создаем локатор для родительской карточки
                                buttons_locator = page.locator(f'xpath=//*[contains(text(), "Claro Pay")]/ancestor::*[self::button or self::div[@role="button"] or contains(@class, "payment") or contains(@class, "card")][1]')
                                logger.info("payment_parser_claro_pay_parent_card_found")
                        except Exception as e:
                            logger.debug("payment_parser_parent_card_search_failed", error=str(e))
                
                if buttons_locator:
                    # Ждем появления карточек
                    try:
                        await buttons_locator.first.wait_for(state="visible", timeout=15000)
                        logger.info("payment_parser_payment_cards_visible")
                    except Exception as e:
                        logger.warning("payment_parser_cards_not_visible", error=str(e))
                    
                    await page.wait_for_timeout(2000)  # Даем время на загрузку
                    
                    # Получаем все карточки методов
                    buttons = await buttons_locator.all()
                    logger.info("payment_parser_payment_methods_found", count=len(buttons))
                    
                    # Ищем карточку с текстом "Claro Pay"
                    for btn in buttons:
                        try:
                            # Пропускаем криптовалютные методы
                            tid = await btn.get_attribute("data-testid")
                            if tid and 'crypto' in tid.lower():
                                logger.debug("payment_parser_skipping_crypto", testid=tid)
                                continue
                            
                            # Получаем весь текст карточки
                            card_text = await btn.inner_text()
                            card_text_lower = card_text.lower()
                            logger.debug("payment_parser_checking_card", text=card_text[:50])
                            
                            # Проверяем, содержит ли карточка "Claro Pay"
                            if "claro pay" in card_text_lower or "claro-pay" in card_text_lower:
                                logger.info("payment_parser_claro_pay_card_found", text=card_text[:50], testid=tid)
                                
                                # Прокручиваем к элементу и ждем
                                await btn.scroll_into_view_if_needed()
                                await page.wait_for_timeout(800)
                                
                                # Проверяем видимость перед кликом
                                is_visible = await btn.is_visible()
                                logger.info("payment_parser_claro_card_visible_check", visible=is_visible, testid=tid)
                                
                                if is_visible:
                                    try:
                                        # Пробуем обычный клик
                                        await btn.click(timeout=5000)
                                        claro_clicked = True
                                        logger.info("payment_parser_claro_pay_clicked", method="card_click_normal", url_after=page.url[:80])
                                    except Exception as click_e:
                                        logger.debug("payment_parser_claro_normal_click_failed", error=str(click_e)[:100])
                                        # Fallback: клик через JavaScript
                                        try:
                                            await btn.evaluate("(el) => { el.scrollIntoView({block: 'center'}); el.click(); }")
                                            await page.wait_for_timeout(1000)
                                            claro_clicked = True
                                            logger.info("payment_parser_claro_pay_clicked", method="card_click_js", url_after=page.url[:80])
                                        except Exception as js_e:
                                            logger.warning("payment_parser_claro_js_click_failed", error=str(js_e)[:100])
                                
                                if claro_clicked:
                                    # Ждем появления следующего модального окна или изменений
                                    await page.wait_for_timeout(2000)
                                    logger.info("payment_parser_waiting_after_claro_click")
                                    break
                        except Exception as e:
                            logger.debug("payment_parser_card_check_failed", error=str(e)[:50])
                            continue
                else:
                    logger.warning("payment_parser_no_payment_cards_found")
                    
            except Exception as e:
                logger.warning("payment_parser_method_cards_search_failed", error=str(e))
        
        # Метод 2: Если не нашли через карточки, пробуем найти по тексту "Claro Pay" и кликнуть на родительский элемент
        if not claro_clicked and modal_found:
            try:
                logger.info("payment_parser_searching_claro_pay_by_text")
                # Ищем элемент с текстом "Claro Pay" в модальном окне
                claro_text_locator = payment_modal.get_by_text("Claro Pay", exact=False)
                count = await claro_text_locator.count()
                if count > 0:
                    logger.info("payment_parser_claro_pay_text_found", count=count)
                    # Пробуем кликнуть на элемент с текстом
                    try:
                        await claro_text_locator.first.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        await claro_text_locator.first.click()
                        await page.wait_for_timeout(3000)
                        claro_clicked = True
                        logger.info("payment_parser_claro_pay_clicked_by_text", url_after=page.url)
                    except Exception as e:
                        logger.debug("payment_parser_claro_pay_text_click_failed", error=str(e))
                        # Пробуем найти родительский кликабельный элемент
                        try:
                            parent_clickable = await claro_text_locator.first.evaluate_handle("""
                                (el) => {
                                    let current = el;
                                    for (let i = 0; i < 10; i++) {
                                        if (!current) break;
                                        const tag = current.tagName.toLowerCase();
                                        const style = window.getComputedStyle(current);
                                        if (tag === 'button' || 
                                            style.cursor === 'pointer' || 
                                            current.onclick || 
                                            current.getAttribute('role') === 'button' ||
                                            current.classList.toString().toLowerCase().includes('payment') ||
                                            current.classList.toString().toLowerCase().includes('method') ||
                                            current.classList.toString().toLowerCase().includes('card')) {
                                            return current;
                                        }
                                        current = current.parentElement;
                                    }
                                    return el.closest('button, div[role="button"], [class*="card"], [class*="payment"], [class*="method"]');
                                }
                            """)
                            if parent_clickable:
                                # Используем JavaScript для клика
                                await page.evaluate("""
                                    (el) => {
                                        if (el) {
                                            el.click();
                                        }
                                    }
                                """, parent_clickable)
                                await page.wait_for_timeout(3000)
                                claro_clicked = True
                                logger.info("payment_parser_claro_pay_clicked_via_parent", url_after=page.url)
                        except Exception as e2:
                            logger.debug("payment_parser_parent_click_failed", error=str(e2))
            except Exception as e:
                logger.debug("payment_parser_text_search_failed", error=str(e))
        
        # Метод 3: Если не нашли через модальное окно, пробуем найти по тексту на всей странице
        if not claro_clicked:
            try:
                logger.info("payment_parser_searching_claro_pay_on_entire_page")
                # Ищем на всей странице
                claro_locator = page.get_by_text("Claro Pay", exact=False)
                count = await claro_locator.count()
                logger.info("payment_parser_claro_text_count_on_page", count=count)
                if count > 0:
                    # Пробуем найти кликабельный родительский элемент
                    for i in range(min(count, 5)):  # Проверяем первые 5 элементов
                        try:
                            claro_elem = claro_locator.nth(i)
                            # Пробуем найти родительскую карточку через JS
                            parent_card = await claro_elem.evaluate_handle("""
                                (el) => {
                                    let current = el;
                                    for (let i = 0; i < 10; i++) {
                                        if (!current) break;
                                        const tag = current.tagName.toLowerCase();
                                        const style = window.getComputedStyle(current);
                                        if (tag === 'button' || 
                                            tag === 'div' && (
                                                style.cursor === 'pointer' || 
                                                current.onclick ||
                                                current.classList.toString().toLowerCase().includes('card') ||
                                                current.classList.toString().toLowerCase().includes('payment') ||
                                                current.classList.toString().toLowerCase().includes('method')
                                            )) {
                                            return current;
                                        }
                                        current = current.parentElement;
                                    }
                                    return el.closest('button, div[role="button"], [class*="card"], [class*="payment"], [class*="method"]');
                                }
                            """)
                            if parent_card:
                                # Кликаем через JS
                                await page.evaluate("""
                                    (el) => {
                                        if (el) {
                                            el.scrollIntoView({behavior: 'smooth', block: 'center'});
                                            setTimeout(() => el.click(), 100);
                                        }
                                    }
                                """, parent_card)
                                await page.wait_for_timeout(3000)
                                claro_clicked = True
                                logger.info("payment_parser_claro_pay_clicked", method="page_text_with_parent", index=i, url_after=page.url[:80])
                                break
                        except Exception as e:
                            logger.debug("payment_parser_claro_parent_search_failed", index=i, error=str(e))
                            continue
                    
                    # Если не нашли родитель, пробуем кликнуть напрямую
                    if not claro_clicked:
                        try:
                            await claro_locator.first.scroll_into_view_if_needed()
                            await page.wait_for_timeout(500)
                            await claro_locator.first.click()
                            await page.wait_for_timeout(3000)
                            claro_clicked = True
                            logger.info("payment_parser_claro_pay_clicked", method="page_text_direct", url_after=page.url[:80])
                        except Exception as e:
                            logger.debug("payment_parser_claro_direct_click_failed", error=str(e))
            except Exception as e:
                logger.debug("payment_parser_claro_text_failed", error=str(e))
        
        # Метод 3: Если все еще не нашли, пробуем CSS селекторы (последний fallback)
        if not claro_clicked:
            claro_pay_selectors = [
                'button[data-testid*="claro" i]',
                '[data-method*="claro" i]',
                '[data-payment*="claro" i]',
                'button:has-text("Claro Pay")',
                'button:has-text("Claro")',
            ]
            for selector in claro_pay_selectors:
                try:
                    claro_elem = payment_modal.locator(selector).first
                    if await claro_elem.count() > 0:
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
        
        # Метод 5: Поиск через JavaScript на всей странице (включая скрытые элементы)
        if not claro_clicked:
            logger.info("payment_parser_searching_claro_pay_via_js_on_entire_page")
            try:
                claro_element_info = await page.evaluate("""
                    () => {
                        // Ищем все элементы с текстом "Claro Pay"
                        const allElements = document.querySelectorAll('*');
                        const claroElements = [];
                        
                        for (const el of allElements) {
                            const text = el.textContent || el.innerText || '';
                            if (text.includes('Claro Pay') || text.includes('Claro-Pay')) {
                                const style = window.getComputedStyle(el);
                                const rect = el.getBoundingClientRect();
                                claroElements.push({
                                    element: el,
                                    tag: el.tagName.toLowerCase(),
                                    visible: style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0,
                                    clickable: el.tagName.toLowerCase() === 'button' || 
                                              style.cursor === 'pointer' || 
                                              el.onclick !== null ||
                                              el.getAttribute('role') === 'button',
                                    hasParent: el.closest('button, div[role="button"], [class*="card"], [class*="payment"], [class*="method"]') !== null
                                });
                            }
                        }
                        
                        // Выбираем лучший элемент для клика
                        for (const item of claroElements) {
                            if (item.clickable && item.visible) {
                                return {found: true, element: item.element, method: 'clickable_visible'};
                            }
                        }
                        for (const item of claroElements) {
                            if (item.hasParent && item.visible) {
                                const parent = item.element.closest('button, div[role="button"], [class*="card"], [class*="payment"], [class*="method"]');
                                if (parent) {
                                    return {found: true, element: parent, method: 'parent_visible'};
                                }
                            }
                        }
                        for (const item of claroElements) {
                            if (item.clickable) {
                                return {found: true, element: item.element, method: 'clickable'};
                            }
                        }
                        if (claroElements.length > 0) {
                            const parent = claroElements[0].element.closest('button, div, a');
                            return {found: true, element: parent || claroElements[0].element, method: 'first_found'};
                        }
                        return {found: false};
                    }
                """)
                
                if claro_element_info.get('found'):
                    logger.info("payment_parser_claro_pay_found_via_js", method=claro_element_info.get('method'))
                    # Кликаем через JavaScript
                    await page.evaluate("""
                        (el) => {
                            if (el) {
                                el.scrollIntoView({behavior: 'smooth', block: 'center'});
                                setTimeout(() => {
                                    el.click();
                                }, 200);
                            }
                        }
                    """, claro_element_info.get('element'))
                    await page.wait_for_timeout(3000)
                    claro_clicked = True
                    logger.info("payment_parser_claro_pay_clicked_via_js", method=claro_element_info.get('method'), url_after=page.url)
            except Exception as e:
                logger.debug("payment_parser_js_claro_search_failed", error=str(e))
        
        if not claro_clicked:
            logger.warning("payment_parser_claro_pay_not_found", current_url=page.url)
        
        # Делаем скриншот провайдера после клика на Claro Pay (до дальнейших действий)
        if claro_clicked:
            try:
                await page.wait_for_timeout(2000)  # Даем время на загрузку после клика
                screenshot_bytes = await page.screenshot(full_page=True)
                # Сохраняем в base64 для ответа
                result["provider_screenshot"] = base64.b64encode(screenshot_bytes).decode('utf-8')
                
                # Сохраняем в файл в отдельную папку для провайдера
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_filename = f"provider_claro_{timestamp}.png"
                screenshot_path = PROVIDER_SCREENSHOTS_DIR / screenshot_filename
                screenshot_path.write_bytes(screenshot_bytes)
                result["provider_screenshot_path"] = str(screenshot_path)
                
                logger.info("payment_parser_provider_screenshot_taken", 
                           provider="Claro Pay", 
                           status="found",
                           path=str(screenshot_path))
            except Exception as e:
                logger.warning("payment_parser_provider_screenshot_failed", error=str(e))
        
        # Шаг 8: Логика после клика на Claro Pay - ожидание модального окна с кнопкой Deposit
        # Инициализируем form_appeared заранее, чтобы она была доступна везде, независимо от claro_clicked
        form_appeared = False
        logger.info("payment_parser_before_claro_clicked_check", claro_clicked=claro_clicked)
        if claro_clicked:
            logger.info("payment_parser_waiting_for_deposit_modal_after_claro_click")
            logger.info("payment_parser_url_after_claro_click", url=page.url[:80])
            
            # Делаем скриншот после клика на Claro Pay
            try:
                await page.wait_for_timeout(2000)
                await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "after_claro_click.png"))
                logger.info("payment_parser_screenshot_after_claro_click")
            except:
                pass
            
            # Ждем появления второго модального окна с полем Amount и кнопкой Deposit
            logger.info("payment_parser_waiting_for_amount_form_modal")
            await page.wait_for_timeout(3000)  # Ждем появления модального окна
            
            # ВАЖНО: После клика на Claro Pay ждем появления формы с полем Amount и кнопкой Deposit
            # Проверяем несколько раз с ожиданием, так как форма может загружаться динамически
            logger.info("payment_parser_checking_if_payment_form_appeared_after_claro")
            payment_form_ready = False
            deposit_button_clicked_early = False
            
            # Ждем до 10 секунд появления формы с Amount и Deposit
            for attempt in range(5):
                try:
                    await page.wait_for_timeout(2000)  # Ждем 2 секунды перед каждой проверкой
                    # Проверяем наличие поля Amount
                    amount_field_exists = await page.locator('input[placeholder*="Amount" i], input[name*="amount" i], label:has-text("Amount"), *:has-text("Amount")').first.is_visible(timeout=1000)
                    
                    # Более агрессивный поиск кнопки Deposit - пробуем разные методы
                    deposit_button_exists = False
                    deposit_button = None
                    
                    # Метод 1: Поиск по тексту через locator
                    try:
                        deposit_locator = page.locator('button:has-text("Deposit"), button:has-text("Depositar")').first
                        if await deposit_locator.count() > 0:
                            deposit_button_exists = await deposit_locator.is_visible(timeout=1000)
                            if deposit_button_exists:
                                deposit_button = deposit_locator
                    except:
                        pass
                    
                    # Метод 2: Поиск через get_by_role (более надежный)
                    if not deposit_button_exists:
                        try:
                            deposit_role = page.get_by_role("button", name=re.compile("^deposit$|^depositar$", re.I))
                            if await deposit_role.count() > 0:
                                # Проверяем, находится ли кнопка внутри модального окна
                                for i in range(min(await deposit_role.count(), 5)):
                                    try:
                                        btn = deposit_role.nth(i)
                                        is_in_modal = await btn.evaluate("""
                                            (el) => {
                                                const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], div[role="dialog"]');
                                                if (!modal) return false;
                                                return modal.contains(el);
                                            }
                                        """)
                                        if is_in_modal:
                                            deposit_button_exists = await btn.is_visible(timeout=1000)
                                            if deposit_button_exists:
                                                deposit_button = btn
                                                break
                                    except:
                                        continue
                        except:
                            pass
                    
                    # Метод 3: Поиск через JavaScript внутри модального окна
                    if not deposit_button_exists:
                        try:
                            deposit_info = await page.evaluate("""
                                () => {
                                    const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], div[role="dialog"]');
                                    if (!modal) return {found: false};
                                    
                                    const buttons = Array.from(modal.querySelectorAll('button, [role="button"]'));
                                    for (const btn of buttons) {
                                        const text = (btn.innerText || btn.textContent || '').toLowerCase().trim();
                                        if (text === 'deposit' || text === 'depositar') {
                                            const style = window.getComputedStyle(btn);
                                            const rect = btn.getBoundingClientRect();
                                            const isVisible = style.display !== 'none' && 
                                                             style.visibility !== 'hidden' && 
                                                             style.opacity !== '0' &&
                                                             rect.width > 0 && 
                                                             rect.height > 0;
                                            if (isVisible) {
                                                return {found: true, text: text, large: rect.width > 100 && rect.height > 30};
                                            }
                                        }
                                    }
                                    return {found: false};
                                }
                            """)
                            if deposit_info.get('found'):
                                deposit_button_exists = True
                                logger.info("payment_parser_deposit_button_found_via_js_early", 
                                          text=deposit_info.get('text'),
                                          large=deposit_info.get('large'))
                        except Exception as e:
                            logger.debug("payment_parser_js_deposit_search_early_failed", error=str(e)[:100])
                    
                    logger.debug("payment_parser_form_check_attempt", 
                               attempt=attempt+1, 
                               has_amount=amount_field_exists, 
                               has_deposit=deposit_button_exists,
                               deposit_button_found=deposit_button is not None)
                    
                    if amount_field_exists and deposit_button_exists:
                        logger.info("payment_parser_payment_form_ready_after_claro", has_amount=True, has_deposit=True, attempt=attempt+1)
                        payment_form_ready = True
                        
                        # Пытаемся кликнуть на кнопку Deposit сразу, если нашли её
                        if deposit_button and not deposit_button_clicked_early:
                            try:
                                logger.info("payment_parser_trying_to_click_deposit_early")
                                await deposit_button.scroll_into_view_if_needed()
                                await page.wait_for_timeout(500)
                                await deposit_button.click(timeout=5000)
                                deposit_button_clicked_early = True
                                logger.info("payment_parser_deposit_clicked_early_success")
                                # Увеличиваем ожидание после клика на Deposit
                                await page.wait_for_timeout(5000)
                                # Делаем скриншот после клика для диагностики
                                try:
                                    await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "after_deposit_click_early.png"))
                                    logger.info("payment_parser_screenshot_after_deposit_click_early")
                                except:
                                    pass
                                break
                            except Exception as e:
                                logger.debug("payment_parser_deposit_early_click_failed", error=str(e)[:100])
                                # Fallback: клик через JavaScript
                                try:
                                    await deposit_button.evaluate("(el) => el.click()")
                                    deposit_button_clicked_early = True
                                    logger.info("payment_parser_deposit_clicked_early_via_js")
                                    # Увеличиваем ожидание после клика
                                    await page.wait_for_timeout(5000)
                                    # Делаем скриншот после клика
                                    try:
                                        await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "after_deposit_click_early_js.png"))
                                        logger.info("payment_parser_screenshot_after_deposit_click_early_js")
                                    except:
                                        pass
                                    break
                                except Exception as e2:
                                    logger.debug("payment_parser_deposit_early_js_click_failed", error=str(e2)[:100])
                        
                        await page.wait_for_timeout(2000)  # Дополнительное ожидание для полной загрузки
                        break
                    elif amount_field_exists:
                        logger.info("payment_parser_amount_field_found_after_claro", has_deposit=deposit_button_exists, attempt=attempt+1)
                        # Есть поле Amount, но кнопки Deposit еще нет - продолжаем ждать
                    else:
                        logger.debug("payment_parser_form_not_ready_yet", attempt=attempt+1)
                except Exception as e:
                    logger.debug("payment_parser_payment_form_check_failed_after_claro", attempt=attempt+1, error=str(e)[:100])
                    continue
            
            if not payment_form_ready:
                logger.info("payment_parser_form_not_ready_after_claro_wait_proceeding_with_fiat")
            
            # Если кнопка Deposit уже была кликнута, пропускаем дальнейшие шаги
            if deposit_button_clicked_early:
                logger.info("payment_parser_deposit_already_clicked_early_skipping_fiat_and_deposit_steps")
                fiat_selected = True
            else:
                fiat_selected = False
            
            # Шаг 8.1: Выбор типа Fiat (только если форма еще не готова)
            if not payment_form_ready:
                logger.info("payment_parser_selecting_fiat_type_in_modal")
                await page.wait_for_timeout(2000)
                # Пробуем найти Fiat по тексту в модальном окне
                try:
                    fiat_locator = page.get_by_text("Fiat", exact=False)
                    count = await fiat_locator.count()
                    logger.debug("payment_parser_fiat_text_count", count=count)
                    if count > 0:
                        # Проверяем, не выбран ли уже Fiat (зеленый фон)
                        fiat_elem = fiat_locator.first
                        # Если не выбран, кликаем
                        try:
                            await fiat_elem.scroll_into_view_if_needed()
                            await page.wait_for_timeout(500)
                            await fiat_elem.click()
                            await page.wait_for_timeout(4000)  # Увеличиваем ожидание после выбора Fiat
                            fiat_selected = True
                            logger.info("payment_parser_fiat_selected", method="text", url_after=page.url[:80])
                            
                            # После выбора Fiat ждем появления формы с полем Amount и кнопкой Deposit
                            logger.info("payment_parser_waiting_for_amount_form_after_fiat")
                            await page.wait_for_timeout(3000)  # Ждем загрузки формы
                            
                            # Проверяем, появилось ли поле Amount (признак того, что форма загрузилась)
                            try:
                                amount_field = await page.locator('input[placeholder*="Amount" i], input[name*="amount" i], label:has-text("Amount")').first.is_visible(timeout=5000)
                                if amount_field:
                                    logger.info("payment_parser_amount_field_appeared_after_fiat")
                                    await page.wait_for_timeout(2000)  # Дополнительное ожидание для кнопки Deposit
                                else:
                                    logger.warning("payment_parser_amount_field_not_found_after_fiat")
                                    await page.wait_for_timeout(3000)  # Ждем еще, может появится
                            except:
                                logger.debug("payment_parser_amount_field_check_failed")
                                await page.wait_for_timeout(3000)
                        except Exception as fiat_click_error:
                            # Возможно, Fiat уже выбран
                            logger.debug("payment_parser_fiat_already_selected_or_click_failed", error=str(fiat_click_error)[:100])
                            fiat_selected = True
                            await page.wait_for_timeout(5000)  # Увеличиваем ожидание
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
                                logger.info("payment_parser_fiat_selected", selector=selector, url_after=page.url[:80])
                                break
                        except Exception as e:
                            logger.debug("payment_parser_fiat_selector_failed", selector=selector, error=str(e))
                            continue
                    
                    if not fiat_selected:
                        logger.debug("payment_parser_fiat_not_found_or_already_selected", current_url=page.url[:80])
            else:
                logger.info("payment_parser_skipping_fiat_selection_form_already_ready")
                fiat_selected = True
            
            # Шаг 8.2: Нажимаем кнопку "Deposit" в модальном окне (большая зеленая кнопка внизу)
            # Пропускаем, если кнопка уже была кликнута ранее
            if deposit_button_clicked_early:
                logger.info("payment_parser_deposit_already_clicked_skipping_deposit_search")
                deposit_button_clicked = True
            else:
                logger.info("payment_parser_clicking_deposit_button_in_modal_START")
                logger.info("payment_parser_current_url_before_deposit_click", url=page.url[:80])
                logger.info("payment_parser_fiat_selected_status", fiat_selected=fiat_selected)
                deposit_button_clicked = False
            
            # Продолжаем поиск кнопки Deposit только если она еще не была кликнута
            if not deposit_button_clicked:
                # ВАЖНО: После выбора Fiat может появиться новое модальное окно с формой
                # Ждем появления формы с полем Amount и кнопкой Deposit до 15 секунд
                logger.info("payment_parser_waiting_for_form_after_fiat_selection")
                form_ready_after_fiat = False
                for wait_attempt in range(7):  # До 14 секунд (7 * 2 секунды)
                    await page.wait_for_timeout(2000)
                    try:
                        # Проверяем наличие поля Amount
                        amount_field = page.locator('input[placeholder*="Amount" i], input[name*="amount" i], label:has-text("Amount"), *:has-text("Amount")').first
                        amount_exists = await amount_field.is_visible(timeout=1000)
                        
                        # Проверяем наличие кнопки Deposit
                        deposit_btn = page.locator('button:has-text("Deposit"), button:has-text("Depositar")').first
                        deposit_exists = await deposit_btn.is_visible(timeout=1000)
                        
                        logger.debug("payment_parser_form_check_after_fiat", attempt=wait_attempt+1, has_amount=amount_exists, has_deposit=deposit_exists)
                        
                        if amount_exists and deposit_exists:
                            logger.info("payment_parser_form_ready_after_fiat", attempt=wait_attempt+1)
                            form_ready_after_fiat = True
                            await page.wait_for_timeout(2000)  # Дополнительное ожидание
                            break
                    except:
                        logger.debug("payment_parser_form_check_failed_after_fiat", attempt=wait_attempt+1)
                        continue
                
                if not form_ready_after_fiat:
                    logger.warning("payment_parser_form_not_ready_after_fiat_wait", waited_seconds=14)
            else:
                logger.info("payment_parser_deposit_already_clicked_skipping_form_wait")
                form_ready_after_fiat = True
            
            # Продолжаем поиск только если кнопка еще не была кликнута
            if not deposit_button_clicked:
                # ВАЖНО: Ищем кнопку Deposit ВНУТРИ модального окна, а не на всей странице
                # Кнопка в header перекрыта backdrop-ом модального окна
                # После выбора Fiat появляется новое модальное окно с полем Amount и кнопкой Deposit
                try:
                    # Пробуем найти текущее открытое модальное окно (может быть новое после выбора Fiat)
                    # Ищем модальное окно, которое содержит поле Amount - это и есть нужное окно
                    current_modal = page.locator('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], div[role="dialog"]').first
                    modal_visible = await current_modal.is_visible(timeout=5000)
                    if modal_visible:
                        logger.info("payment_parser_current_modal_found_after_fiat")
                        # Проверяем, что в модальном окне есть поле Amount или кнопка Deposit
                        has_amount = await current_modal.locator('input[placeholder*="Amount" i], input[name*="amount" i], *:has-text("Amount")').count() > 0
                        has_deposit = await current_modal.locator('button:has-text("Deposit"), button:has-text("Depositar")').count() > 0
                        logger.info("payment_parser_modal_content_check", has_amount=has_amount, has_deposit=has_deposit)
                        modal_container = current_modal
                    else:
                        logger.warning("payment_parser_current_modal_not_visible_using_payment_modal")
                        modal_container = payment_modal  # Используем уже найденное модальное окно
                except:
                    logger.warning("payment_parser_current_modal_not_found_using_payment_modal")
                    modal_container = payment_modal  # Используем уже найденное модальное окно
                
                # Дополнительное ожидание для загрузки кнопки Deposit
                await page.wait_for_timeout(2000)
            else:
                logger.info("payment_parser_deposit_already_clicked_skipping_modal_search")
                modal_container = payment_modal  # Используем уже найденное модальное окно
            
            # Делаем скриншот перед поиском кнопки Deposit для диагностики
            if not deposit_button_clicked:
                try:
                    await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "before_deposit_search.png"))
                    logger.info("payment_parser_screenshot_before_deposit_search")
                except:
                    pass
            
            # Метод 0 (из 1winSTD): Простой поиск через :text() селектор Playwright (самый надежный)
            if not deposit_button_clicked:
                try:
                    logger.info("payment_parser_searching_deposit_via_text_selector_std_approach")
                    # Используем подход из 1winSTD-bot: простое использование :text() селектора
                    deposit_text_selector = page.locator('div:text("Deposit")').first
                    if await deposit_text_selector.is_visible(timeout=5000):
                        logger.info("payment_parser_deposit_found_via_text_selector")
                        deposit_text_selector.click(timeout=5000)
                        deposit_button_clicked = True
                        logger.info("payment_parser_deposit_clicked_via_text_selector_std")
                        await page.wait_for_timeout(2000)
                except Exception as e:
                    logger.debug("payment_parser_deposit_text_selector_failed", error=str(e)[:100])
            
            # Метод 0.25 (из 1winSTD): Wait for visible перед кликом
            if not deposit_button_clicked:
                try:
                    logger.info("payment_parser_searching_deposit_via_wait_for_visible_std")
                    deposit_wait_visible = page.locator('div:text("Deposit")').first
                    await deposit_wait_visible.wait_for(state="visible", timeout=10000)
                    await deposit_wait_visible.click()
                    deposit_button_clicked = True
                    logger.info("payment_parser_deposit_clicked_via_wait_for_visible_std")
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    logger.debug("payment_parser_deposit_wait_for_visible_failed", error=str(e)[:100])
            
            # Метод 0.5 (из 1winSTD): Множественные селекторы с проверкой видимости
            if not deposit_button_clicked:
                try:
                    logger.info("payment_parser_searching_deposit_via_multiple_selectors_std")
                    # Селекторы из 1winSTD-bot
                    deposit_selectors_std = [
                        'div:text("Deposit")',
                        'button:text("Deposit")',
                        'a:text("Deposit")',
                        '[data-testid*="deposit"]',
                        'div:has-text("Deposit")',
                        'button:has-text("Deposit")'
                    ]
                    
                    for selector in deposit_selectors_std:
                        try:
                            deposit_btn = page.locator(selector).first
                            if await deposit_btn.is_visible(timeout=3000):
                                logger.info("payment_parser_deposit_found_via_std_selector", selector=selector)
                                await deposit_btn.click(timeout=3000)
                                deposit_button_clicked = True
                                logger.info("payment_parser_deposit_clicked_via_std_selector", selector=selector)
                                await page.wait_for_timeout(2000)
                                break
                        except Exception as e:
                            logger.debug("payment_parser_deposit_std_selector_failed", selector=selector, error=str(e)[:100])
                            continue
                except Exception as e:
                    logger.debug("payment_parser_deposit_multiple_selectors_std_failed", error=str(e)[:100])
            
            # Метод 0.75 (из 1winSTD): Поиск через button:has-text() с wait_for
            if not deposit_button_clicked:
                try:
                    logger.info("payment_parser_searching_deposit_via_button_has_text_std")
                    deposit_btn_has_text = page.locator('button:has-text("Deposit"), button:has-text("deposit")').first
                    await deposit_btn_has_text.wait_for(state="visible", timeout=8000)
                    await deposit_btn_has_text.click()
                    deposit_button_clicked = True
                    logger.info("payment_parser_deposit_clicked_via_button_has_text_std")
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    logger.debug("payment_parser_deposit_button_has_text_failed", error=str(e)[:100])
            
            # Метод 0.8: Агрессивный поиск кнопки Deposit через JavaScript (находит все элементы)
            if not deposit_button_clicked:
                try:
                    logger.info("payment_parser_searching_deposit_via_js_aggressive")
                    deposit_button_info = await page.evaluate("""
                        () => {
                            // Ищем все элементы с текстом Deposit
                            const allElements = Array.from(document.querySelectorAll('*'));
                            const depositElements = [];
                            
                            for (const el of allElements) {
                                const text = (el.innerText || el.textContent || '').toLowerCase().trim();
                                const tagName = el.tagName.toLowerCase();
                                
                                // Ищем элементы с текстом "deposit" или "depositar"
                                if ((text === 'deposit' || text === 'depositar' || 
                                     (text.includes('deposit') && text.length < 20)) && 
                                    text.length > 0) {
                                    
                                    const style = window.getComputedStyle(el);
                                    const rect = el.getBoundingClientRect();
                                    
                                    // Проверяем видимость
                                    const isVisible = style.display !== 'none' && 
                                                     style.visibility !== 'hidden' && 
                                                     style.opacity !== '0' &&
                                                     rect.width > 0 && 
                                                     rect.height > 0 &&
                                                     rect.top >= 0 &&
                                                     rect.left >= 0;
                                    
                                    if (isVisible) {
                                        // Проверяем, находится ли в модальном окне
                                        const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], div[role="dialog"]');
                                        const isInModal = modal && modal.contains(el);
                                        
                                        // Ищем родительскую кнопку, если это не кнопка
                                        let clickableElement = el;
                                        if (tagName !== 'button' && tagName !== 'a') {
                                            const parentButton = el.closest('button, [role="button"], [onclick]');
                                            if (parentButton) {
                                                clickableElement = parentButton;
                                            }
                                        }
                                        
                                        depositElements.push({
                                            element: clickableElement,
                                            tag: tagName,
                                            text: text.substring(0, 30),
                                            isButton: tagName === 'button' || clickableElement.tagName.toLowerCase() === 'button',
                                            isInModal: isInModal,
                                            width: rect.width,
                                            height: rect.height,
                                            isLarge: rect.width > 100 && rect.height > 30,
                                            bgColor: style.backgroundColor,
                                            x: rect.x + rect.width / 2,
                                            y: rect.y + rect.height / 2,
                                            hasOnClick: !!clickableElement.onclick || clickableElement.getAttribute('onclick')
                                        });
                                    }
                                }
                            }
                            
                            // Сортируем: сначала кнопки в модальном окне, потом большие, потом по размеру
                            depositElements.sort((a, b) => {
                                if (a.isInModal && !b.isInModal) return -1;
                                if (!a.isInModal && b.isInModal) return 1;
                                if (a.isButton && !b.isButton) return -1;
                                if (!a.isButton && b.isButton) return 1;
                                if (a.isLarge && !b.isLarge) return -1;
                                if (!a.isLarge && b.isLarge) return 1;
                                return (b.width * b.height) - (a.width * a.height);
                            });
                            
                            if (depositElements.length > 0) {
                                const best = depositElements[0];
                                return {
                                    found: true,
                                    count: depositElements.length,
                                    text: best.text,
                                    tag: best.tag,
                                    isButton: best.isButton,
                                    isInModal: best.isInModal,
                                    width: best.width,
                                    height: best.height,
                                    x: best.x,
                                    y: best.y,
                                    element: best.element
                                };
                            }
                            
                            return {found: false, count: 0};
                        }
                    """)
                    
                    if deposit_button_info.get('found'):
                        logger.info("payment_parser_deposit_found_via_js_aggressive", 
                                  count=deposit_button_info.get('count'),
                                  text=deposit_button_info.get('text'),
                                  tag=deposit_button_info.get('tag'),
                                  isButton=deposit_button_info.get('isButton'),
                                  isInModal=deposit_button_info.get('isInModal'),
                                  width=deposit_button_info.get('width'),
                                  height=deposit_button_info.get('height'),
                                  x=deposit_button_info.get('x'),
                                  y=deposit_button_info.get('y'))
                        
                        # Пробуем кликнуть через координаты (самый надежный способ)
                        try:
                            x = deposit_button_info.get('x')
                            y = deposit_button_info.get('y')
                            if x and y:
                                logger.info("payment_parser_clicking_deposit_via_coordinates", x=x, y=y)
                                await page.mouse.click(x, y)
                                await page.wait_for_timeout(3000)
                                deposit_button_clicked = True
                                logger.info("payment_parser_deposit_clicked_via_coordinates_success")
                        except Exception as e:
                            logger.debug("payment_parser_deposit_coordinates_click_failed", error=str(e)[:100])
                            # Fallback: клик через JavaScript на элемент
                            try:
                                await page.evaluate("""
                                    (el) => {
                                        if (el) {
                                            el.scrollIntoView({behavior: 'smooth', block: 'center'});
                                            setTimeout(() => {
                                                if (el.click) {
                                                    el.click();
                                                } else if (el.dispatchEvent) {
                                                    const event = new MouseEvent('click', {
                                                        bubbles: true,
                                                        cancelable: true,
                                                        view: window
                                                    });
                                                    el.dispatchEvent(event);
                                                }
                                            }, 200);
                                        }
                                    }
                                """, deposit_button_info.get('element'))
                                await page.wait_for_timeout(3000)
                                deposit_button_clicked = True
                                logger.info("payment_parser_deposit_clicked_via_js_element")
                            except Exception as e2:
                                logger.debug("payment_parser_deposit_js_element_click_failed", error=str(e2)[:100])
                    else:
                        logger.warning("payment_parser_deposit_not_found_via_js_aggressive")
                except Exception as e:
                    logger.debug("payment_parser_deposit_js_aggressive_failed", error=str(e)[:100])
            
            # Метод 0.5: Простой поиск кнопки Deposit через get_by_text (fallback)
            if not deposit_button_clicked:
                try:
                    logger.info("payment_parser_searching_deposit_via_get_by_text")
                    # Ищем все элементы с текстом "Deposit" или "Depositar"
                    deposit_text_buttons = page.get_by_text("Deposit", exact=False)
                    deposit_text_count = await deposit_text_buttons.count()
                    logger.info("payment_parser_deposit_get_by_text_count", count=deposit_text_count)
                    
                    # Проверяем каждую кнопку, находится ли она в модальном окне и видна ли она
                    for i in range(min(deposit_text_count, 10)):
                        try:
                            btn = deposit_text_buttons.nth(i)
                            
                            # Проверяем, находится ли элемент в модальном окне и виден ли он
                            btn_info = await btn.evaluate("""
                                (el) => {
                                    const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], div[role="dialog"]');
                                    const isInModal = modal && modal.contains(el);
                                    const style = window.getComputedStyle(el);
                                    const rect = el.getBoundingClientRect();
                                    const isVisible = style.display !== 'none' && 
                                                     style.visibility !== 'hidden' && 
                                                     style.opacity !== '0' &&
                                                     rect.width > 0 && 
                                                     rect.height > 0;
                                    
                                    // Ищем родительскую кнопку
                                    let clickable = el;
                                    if (el.tagName.toLowerCase() !== 'button') {
                                        const parentButton = el.closest('button, [role="button"]');
                                        if (parentButton) clickable = parentButton;
                                    }
                                    
                                    return {
                                        isInModal: isInModal,
                                        isVisible: isVisible,
                                        tag: el.tagName.toLowerCase(),
                                        isButton: clickable.tagName.toLowerCase() === 'button',
                                        x: rect.x + rect.width / 2,
                                        y: rect.y + rect.height / 2,
                                        width: rect.width,
                                        height: rect.height,
                                        clickable: clickable
                                    };
                                }
                            """)
                            
                            if btn_info.get('isInModal') and btn_info.get('isVisible'):
                                logger.info("payment_parser_deposit_button_candidate_get_by_text", 
                                          index=i, 
                                          isButton=btn_info.get('isButton'),
                                          width=btn_info.get('width'),
                                          height=btn_info.get('height'))
                                
                                # Пробуем кликнуть через координаты
                                try:
                                    x = btn_info.get('x')
                                    y = btn_info.get('y')
                                    if x and y:
                                        logger.info("payment_parser_clicking_deposit_get_by_text_coords", x=x, y=y)
                                        await page.mouse.click(x, y)
                                        await page.wait_for_timeout(3000)
                                        deposit_button_clicked = True
                                        logger.info("payment_parser_deposit_clicked_via_get_by_text_coords", index=i)
                                        break
                                except Exception as e:
                                    logger.debug("payment_parser_deposit_get_by_text_coords_failed", index=i, error=str(e)[:100])
                                    # Fallback: обычный клик
                                    try:
                                        await btn.scroll_into_view_if_needed()
                                        await page.wait_for_timeout(500)
                                        
                                        # Если это не кнопка, находим родительскую кнопку
                                        if not btn_info.get('isButton'):
                                            clickable_el = btn_info.get('clickable')
                                            if clickable_el:
                                                await page.evaluate("(el) => el.click()", clickable_el)
                                        else:
                                            await btn.click(timeout=5000)
                                        
                                        deposit_button_clicked = True
                                        logger.info("payment_parser_deposit_clicked_via_get_by_text", index=i)
                                        await page.wait_for_timeout(3000)
                                        break
                                    except Exception as e2:
                                        logger.debug("payment_parser_deposit_get_by_text_click_failed", index=i, error=str(e2)[:100])
                                        continue
                        except Exception as e:
                            logger.debug("payment_parser_deposit_get_by_text_check_failed", index=i, error=str(e)[:100])
                            continue
                except Exception as e:
                    logger.debug("payment_parser_deposit_get_by_text_failed", error=str(e)[:100])
            
            # Метод 0.75: Поиск всех больших кнопок на странице и фильтрация по тексту Deposit
            if not deposit_button_clicked:
                try:
                    logger.info("payment_parser_searching_all_large_buttons")
                    all_buttons_info = await page.evaluate("""
                        () => {
                            const buttons = Array.from(document.querySelectorAll('button, [role="button"], div[onclick], a[href*="deposit" i]'));
                            const largeButtons = [];
                            
                            for (const btn of buttons) {
                                const style = window.getComputedStyle(btn);
                                const rect = btn.getBoundingClientRect();
                                const text = (btn.innerText || btn.textContent || '').toLowerCase().trim();
                                
                                // Проверяем видимость и размер
                                const isVisible = style.display !== 'none' && 
                                                 style.visibility !== 'hidden' && 
                                                 style.opacity !== '0' &&
                                                 rect.width > 0 && 
                                                 rect.height > 0;
                                
                                const isLarge = rect.width > 100 && rect.height > 30;
                                const hasDepositText = text === 'deposit' || text === 'depositar' || 
                                                       (text.includes('deposit') && text.length < 30);
                                
                                // Проверяем, находится ли в модальном окне
                                const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], div[role="dialog"]');
                                const isInModal = modal && modal.contains(btn);
                                
                                // Исключаем header кнопки
                                const testid = btn.getAttribute('data-testid') || '';
                                const isNotHeader = !testid.includes('header-balance') && !testid.includes('header');
                                
                                if (isVisible && isLarge && isNotHeader && (hasDepositText || isInModal)) {
                                    largeButtons.push({
                                        element: btn,
                                        text: text.substring(0, 50),
                                        isInModal: isInModal,
                                        hasDepositText: hasDepositText,
                                        width: rect.width,
                                        height: rect.height,
                                        x: rect.x + rect.width / 2,
                                        y: rect.y + rect.height / 2,
                                        bgColor: style.backgroundColor,
                                        className: btn.className || ''
                                    });
                                }
                            }
                            
                            // Сортируем: сначала с текстом Deposit в модальном окне
                            largeButtons.sort((a, b) => {
                                if (a.hasDepositText && a.isInModal && !(b.hasDepositText && b.isInModal)) return -1;
                                if (b.hasDepositText && b.isInModal && !(a.hasDepositText && a.isInModal)) return 1;
                                if (a.hasDepositText && !b.hasDepositText) return -1;
                                if (b.hasDepositText && !a.hasDepositText) return 1;
                                if (a.isInModal && !b.isInModal) return -1;
                                if (b.isInModal && !a.isInModal) return 1;
                                return (b.width * b.height) - (a.width * a.height);
                            });
                            
                            if (largeButtons.length > 0) {
                                const best = largeButtons[0];
                                return {
                                    found: true,
                                    count: largeButtons.length,
                                    text: best.text,
                                    isInModal: best.isInModal,
                                    hasDepositText: best.hasDepositText,
                                    width: best.width,
                                    height: best.height,
                                    x: best.x,
                                    y: best.y,
                                    element: best.element,
                                    allButtons: largeButtons.slice(0, 5).map(b => ({
                                        text: b.text,
                                        isInModal: b.isInModal,
                                        hasDepositText: b.hasDepositText
                                    }))
                                };
                            }
                            
                            return {found: false, count: 0};
                        }
                    """)
                    
                    if all_buttons_info.get('found'):
                        logger.info("payment_parser_large_buttons_found", 
                                  count=all_buttons_info.get('count'),
                                  text=all_buttons_info.get('text'),
                                  isInModal=all_buttons_info.get('isInModal'),
                                  hasDepositText=all_buttons_info.get('hasDepositText'),
                                  width=all_buttons_info.get('width'),
                                  height=all_buttons_info.get('height'),
                                  x=all_buttons_info.get('x'),
                                  y=all_buttons_info.get('y'),
                                  allButtons=all_buttons_info.get('allButtons'))
                        
                        # Пробуем кликнуть через координаты
                        try:
                            x = all_buttons_info.get('x')
                            y = all_buttons_info.get('y')
                            if x and y:
                                logger.info("payment_parser_clicking_large_button_via_coordinates", x=x, y=y)
                                await page.mouse.click(x, y)
                                await page.wait_for_timeout(3000)
                                deposit_button_clicked = True
                                logger.info("payment_parser_deposit_clicked_via_large_button_coords")
                        except Exception as e:
                            logger.debug("payment_parser_large_button_coords_click_failed", error=str(e)[:100])
                            # Fallback: клик через JavaScript
                            try:
                                await page.evaluate("""
                                    (el) => {
                                        if (el) {
                                            el.scrollIntoView({behavior: 'smooth', block: 'center'});
                                            setTimeout(() => {
                                                if (el.click) el.click();
                                                else if (el.dispatchEvent) {
                                                    el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                                                }
                                            }, 200);
                                        }
                                    }
                                """, all_buttons_info.get('element'))
                                await page.wait_for_timeout(3000)
                                deposit_button_clicked = True
                                logger.info("payment_parser_deposit_clicked_via_large_button_js")
                            except Exception as e2:
                                logger.debug("payment_parser_large_button_js_click_failed", error=str(e2)[:100])
                    else:
                        logger.warning("payment_parser_no_large_buttons_found")
                except Exception as e:
                    logger.debug("payment_parser_large_buttons_search_failed", error=str(e)[:100])
            
            # Метод 1 (из 1winSTD): Использование data-testid="deposit-button" - самый надежный способ
            if not deposit_button_clicked:
                try:
                    logger.info("payment_parser_searching_deposit_via_data_testid_std")
                    # Из 1winSTD-bot: page.locator('button[data-testid="deposit-button"]').click()
                    deposit_testid = page.locator('button[data-testid="deposit-button"]')
                    if await deposit_testid.count() > 0:
                        if await deposit_testid.first.is_visible(timeout=5000):
                            logger.info("payment_parser_deposit_found_via_data_testid_std")
                            await deposit_testid.first.click(timeout=5000)
                            deposit_button_clicked = True
                            logger.info("payment_parser_deposit_clicked_via_data_testid_std")
                            await page.wait_for_timeout(3000)
                except Exception as e:
                    logger.debug("payment_parser_deposit_data_testid_std_failed", error=str(e)[:100])
            
            # Метод 1.5: Ищем большую зеленую кнопку "Deposit" ВНУТРИ модального окна по тексту
            # Это должна быть большая зеленая кнопка с белым текстом "Deposit"
            # ВАЖНО: После клика на Claro Pay открывается НОВОЕ модальное окно, нужно искать в нем
            # Продолжаем только если кнопка еще не была кликнута
            if not deposit_button_clicked:
                try:
                    # Сначала убеждаемся, что модальное окно с полем Amount появилось
                    try:
                        amount_field_exists = await page.locator('input[placeholder*="Amount" i], input[name*="amount" i], label:has-text("Amount")').first.is_visible(timeout=5000)
                        if amount_field_exists:
                            logger.info("payment_parser_amount_field_confirmed_visible")
                            await page.wait_for_timeout(2000)  # Даем время на полную загрузку формы
                    except:
                        logger.debug("payment_parser_amount_field_not_confirmed")
                    
                    # Ищем кнопку с текстом "Deposit" ВНУТРИ модального окна
                    # Пробуем искать в текущем модальном окне и на всей странице (так как модальное окно может быть новым)
                    deposit_button_text = modal_container.get_by_role("button", name=re.compile("^deposit$|^depositar$", re.I))
                    count_in_modal = await deposit_button_text.count()
                    
                    # Если не нашли в modal_container, ищем на всей странице, но внутри модального окна
                    if count_in_modal == 0:
                        logger.debug("payment_parser_deposit_not_found_in_modal_container_searching_on_page")
                        # Ищем все кнопки с текстом Deposit на странице, но внутри модального окна
                        all_deposit_buttons = page.get_by_role("button", name=re.compile("^deposit$|^depositar$", re.I))
                        count_all = await all_deposit_buttons.count()
                        logger.info("payment_parser_deposit_button_count_on_page", count=count_all)
                        
                        # Проверяем каждую кнопку, находится ли она внутри модального окна
                        for i in range(min(count_all, 5)):
                            try:
                                btn = all_deposit_buttons.nth(i)
                                # Проверяем через JavaScript, находится ли кнопка внутри модального окна
                                is_in_modal = await btn.evaluate("""
                                    (el) => {
                                        const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], div[role="dialog"]');
                                        if (!modal) return false;
                                        return modal.contains(el);
                                    }
                                """)
                                if is_in_modal:
                                    deposit_button_text = btn
                                    count_in_modal = 1
                                    logger.info("payment_parser_deposit_found_in_modal_via_page_search", index=i)
                                    break
                            except:
                                continue
                    
                    logger.info("payment_parser_deposit_button_text_count_in_modal", count=count_in_modal)
                    if count_in_modal > 0:
                        # Проверяем, что это действительно большая зеленая кнопка
                        # Проверяем до 3 кнопок, если их несколько
                        buttons_to_check = min(count_in_modal, 3)
                        for i in range(buttons_to_check):
                            try:
                                btn = deposit_button_text.nth(i) if count_in_modal > 1 else deposit_button_text.first
                                # Проверяем стиль кнопки через JavaScript
                                btn_info = await btn.evaluate("""
                                    (el) => {
                                        const style = window.getComputedStyle(el);
                                        const rect = el.getBoundingClientRect();
                                        return {
                                            text: (el.innerText || el.textContent || '').trim(),
                                            backgroundColor: style.backgroundColor,
                                            color: style.color,
                                            width: rect.width,
                                            height: rect.height,
                                            isLarge: rect.width > 150 && rect.height > 40,
                                            isGreen: style.backgroundColor.includes('rgb') && 
                                                    (style.backgroundColor.includes('0,') || style.backgroundColor.includes('green'))
                                        };
                                    }
                                """)
                                logger.info("payment_parser_deposit_button_info", index=i, **btn_info)
                                
                                # Приоритет большой зеленой кнопке
                                if btn_info.get('isLarge') or btn_info.get('isGreen') or i == 0:
                                    await btn.scroll_into_view_if_needed()
                                    await page.wait_for_timeout(500)
                                    try:
                                        await btn.click(timeout=5000)
                                        deposit_button_clicked = True
                                        logger.info("payment_parser_deposit_button_clicked", method="text_inside_modal", index=i)
                                        # После клика на Deposit ждем появления формы оплаты
                                        await page.wait_for_timeout(5000)  # Даем время на загрузку формы после клика
                                        break
                                    except Exception as e:
                                        logger.debug("payment_parser_deposit_button_text_click_failed", index=i, error=str(e)[:100])
                                        # Fallback: клик через JavaScript
                                        try:
                                            await btn.evaluate("(el) => el.click()")
                                            deposit_button_clicked = True
                                            logger.info("payment_parser_deposit_button_clicked", method="text_inside_modal_js", index=i)
                                            # После клика на Deposit ждем появления формы оплаты
                                            await page.wait_for_timeout(5000)  # Даем время на загрузку формы после клика
                                            break
                                        except Exception as e2:
                                            logger.debug("payment_parser_deposit_button_text_js_failed", index=i, error=str(e2)[:100])
                            except Exception as e:
                                logger.debug("payment_parser_deposit_button_check_failed", index=i, error=str(e)[:100])
                                continue
                except Exception as e:
                    logger.debug("payment_parser_deposit_button_text_failed", error=str(e)[:100])
            
            # Метод 2: Ищем через data-testid ВНУТРИ модального окна (исключаем header-balance-deposit-button)
            if not deposit_button_clicked:
                try:
                    # Ищем кнопки с deposit в data-testid, но НЕ header-balance-deposit-button
                    deposit_button = modal_container.locator('button[data-testid*="deposit" i]:not([data-testid*="header-balance" i])')
                    count = await deposit_button.count()
                    if count > 0:
                        logger.info("payment_parser_deposit_button_found_in_modal", count=count)
                        await deposit_button.first.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        try:
                            await deposit_button.first.click(timeout=5000)
                            deposit_button_clicked = True
                            logger.info("payment_parser_deposit_button_clicked", method="data-testid_inside_modal")
                        except Exception as e:
                            logger.debug("payment_parser_deposit_button_testid_click_failed", error=str(e)[:100])
                            # Fallback: клик через JavaScript
                            try:
                                await deposit_button.first.evaluate("(el) => el.click()")
                                deposit_button_clicked = True
                                logger.info("payment_parser_deposit_button_clicked", method="data-testid_inside_modal_js")
                            except Exception as e2:
                                logger.debug("payment_parser_deposit_button_testid_js_failed", error=str(e2)[:100])
                    else:
                        logger.debug("payment_parser_no_deposit_button_in_modal_via_testid")
                except Exception as e:
                    logger.debug("payment_parser_deposit_button_testid_failed", error=str(e)[:100])
            
            # Метод 3: Ищем через JavaScript ВНУТРИ модального окна
            if not deposit_button_clicked:
                try:
                    logger.info("payment_parser_searching_deposit_via_js_in_modal")
                    deposit_found = await page.evaluate("""
                        () => {
                            // Ищем модальное окно
                            const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], div[role="dialog"]');
                            if (!modal) return {found: false, reason: 'no_modal'};
                            
                            // Ищем все кнопки внутри модального окна
                            const buttons = Array.from(modal.querySelectorAll('button, [role="button"], div[onclick], a[href]'));
                            
                            // Фильтруем кнопки, которые находятся внутри модального окна
                            const depositButtons = buttons.filter(btn => {
                                const text = (btn.innerText || btn.textContent || '').toLowerCase().trim();
                                const testid = btn.getAttribute('data-testid') || '';
                                const className = btn.className || '';
                                
                                // Проверяем текст
                                const hasDepositText = text === 'deposit' || text === 'depositar' || 
                                                      text.includes('deposit') || text.includes('depositar');
                                
                                // Проверяем, что это не кнопка в header
                                const isNotHeader = !testid.includes('header-balance') && 
                                                   !testid.includes('header') &&
                                                   !className.includes('header');
                                
                                // Исключаем currency selector и другие не-депозитные кнопки
                                const isNotCurrencySelector = !testid.includes('currency-selector') &&
                                                             !testid.includes('currency') &&
                                                             !className.includes('currency-selector');
                                
                                // Исключаем карточки методов оплаты
                                const isNotPaymentMethodCard = !testid.includes('payment-method-') &&
                                                              !className.includes('payment-method') &&
                                                              !className.includes('_tile_') &&
                                                              !text.includes('astro') &&
                                                              !text.includes('airtm') &&
                                                              !text.includes('binance') &&
                                                              !text.includes('claro') &&
                                                              !text.includes('nely');
                                
                                // Проверяем видимость, размер и цвет
                                const style = window.getComputedStyle(btn);
                                const rect = btn.getBoundingClientRect();
                                const isVisible = style.display !== 'none' && 
                                                 style.visibility !== 'hidden' && 
                                                 style.opacity !== '0' &&
                                                 btn.offsetWidth > 0 && 
                                                 btn.offsetHeight > 0;
                                
                                // Проверяем размер и цвет для большой зеленой кнопки
                                const isLarge = rect.width > 150 && rect.height > 40;
                                const isGreen = style.backgroundColor.includes('rgb') && 
                                               (style.backgroundColor.includes('0,') || 
                                                style.backgroundColor.includes('green') ||
                                                style.backgroundColor.includes('76,') ||
                                                btn.className.toLowerCase().includes('green') ||
                                                btn.className.toLowerCase().includes('accent') ||
                                                btn.className.toLowerCase().includes('primary'));
                                
                                // Приоритет большой зеленой кнопке с текстом Deposit
                                const isLargeGreenDeposit = hasDepositText && isLarge && isGreen;
                                
                                // Приоритет большой зеленой кнопке
                                if (isLargeGreenDeposit) {
                                    return true;
                                }
                                // Или обычная кнопка с текстом Deposit
                                return hasDepositText && isNotHeader && isNotCurrencySelector && isNotPaymentMethodCard && isVisible;
                            });
                            
                            // Логирование будет в Python коде
                            
                            if (depositButtons.length > 0) {
                                // Сортируем: сначала большие зеленые кнопки
                                depositButtons.sort((a, b) => {
                                    const aStyle = window.getComputedStyle(a);
                                    const bStyle = window.getComputedStyle(b);
                                    const aRect = a.getBoundingClientRect();
                                    const bRect = b.getBoundingClientRect();
                                    const aIsLarge = aRect.width > 150 && aRect.height > 40;
                                    const bIsLarge = bRect.width > 150 && bRect.height > 40;
                                    const aIsGreen = aStyle.backgroundColor.includes('green') || aStyle.backgroundColor.includes('76,');
                                    const bIsGreen = bStyle.backgroundColor.includes('green') || bStyle.backgroundColor.includes('76,');
                                    
                                    if (aIsLarge && aIsGreen && !(bIsLarge && bIsGreen)) return -1;
                                    if (bIsLarge && bIsGreen && !(aIsLarge && aIsGreen)) return 1;
                                    return 0;
                                });
                                
                                const btn = depositButtons[0];
                                btn.scrollIntoView({behavior: 'smooth', block: 'center'});
                                setTimeout(() => {
                                    btn.click();
                                }, 200);
                                return {
                                    found: true, 
                                    text: (btn.innerText || btn.textContent || '').trim().substring(0, 50),
                                    testid: btn.getAttribute('data-testid') || '',
                                    className: btn.className || ''
                                };
                            }
                            
                            // Если не нашли по тексту, ищем большую зеленую/акцентную кнопку внизу модального окна
                            // НО исключаем currency selector и другие служебные кнопки
                            const allButtons = Array.from(modal.querySelectorAll('button, [role="button"]'));
                            const largeButtons = allButtons.filter(btn => {
                                const testid = btn.getAttribute('data-testid') || '';
                                const className = btn.className || '';
                                const text = (btn.innerText || btn.textContent || '').toLowerCase();
                                
                                // Исключаем currency selector и другие служебные элементы
                                const isNotCurrencySelector = !testid.includes('currency-selector') &&
                                                             !testid.includes('currency') &&
                                                             !className.includes('currency-selector') &&
                                                             !text.includes('peso') &&
                                                             !text.includes('currency');
                                
                                // Исключаем карточки методов оплаты
                                // Но разрешаем кнопку Deposit
                                const isDepositButton = text === 'deposit' || text === 'depositar';
                                const isNotPaymentMethodCard = isDepositButton || (
                                                              !testid.includes('payment-method-') &&
                                                              !className.includes('payment-method') &&
                                                              !className.includes('_tile_') &&
                                                              !className.includes('_root_38ag8_') &&
                                                              !text.includes('astro') &&
                                                              !text.includes('airtm') &&
                                                              !text.includes('binance') &&
                                                              !text.includes('claro') &&
                                                              !text.includes('nely') &&
                                                              !(text.includes('pay') && !isDepositButton)
                                                              );
                                
                                // Исключаем header кнопки
                                const isNotHeader = !testid.includes('header') && !className.includes('header');
                                
                                const style = window.getComputedStyle(btn);
                                const isVisible = style.display !== 'none' && style.visibility !== 'hidden';
                                const rect = btn.getBoundingClientRect();
                                const isLarge = rect.width > 100 && rect.height > 30;
                                
                                // Ищем акцентную кнопку с текстом, похожим на действие (Deposit, Submit, Continue, etc)
                                const isActionButton = text.includes('deposit') || 
                                                      text.includes('depositar') ||
                                                      text.includes('submit') ||
                                                      text.includes('continue') ||
                                                      text.includes('confirm') ||
                                                      text.includes('proceed');
                                
                                const isAccent = style.backgroundColor.includes('rgb') || 
                                               btn.className.toLowerCase().includes('accent') ||
                                               btn.className.toLowerCase().includes('primary') ||
                                               btn.className.toLowerCase().includes('green') ||
                                               btn.className.toLowerCase().includes('submit');
                                
                                return isVisible && isLarge && isNotCurrencySelector && isNotHeader && isNotPaymentMethodCard && 
                                       (isActionButton || (isAccent && !text.includes('select') && !text.includes('pay') && text !== 'astropay' && text !== 'airtm' && text !== 'binance pay' && text !== 'claro pay'));
                            });
                            
                            if (largeButtons.length > 0) {
                                const btn = largeButtons[0];
                                btn.scrollIntoView({behavior: 'smooth', block: 'center'});
                                setTimeout(() => {
                                    btn.click();
                                }, 200);
                                return {
                                    found: true, 
                                    text: (btn.innerText || btn.textContent || '').trim().substring(0, 50),
                                    testid: btn.getAttribute('data-testid') || '',
                                    className: btn.className || '',
                                    method: 'large_accent_button'
                                };
                            }
                            
                            return {found: false, reason: 'no_deposit_button', buttons_checked: buttons.length};
                        }
                    """)
                    if deposit_found.get('found'):
                        deposit_button_clicked = True
                        await page.wait_for_timeout(2500)
                        logger.info("payment_parser_deposit_button_clicked", method=deposit_found.get('method', 'js_in_modal'), 
                                   text=deposit_found.get('text'), 
                                   testid=deposit_found.get('testid'),
                                   className=deposit_found.get('className'))
                    else:
                        logger.warning("payment_parser_deposit_not_found_via_js", 
                                      reason=deposit_found.get('reason'),
                                      buttons_checked=deposit_found.get('buttons_checked'))
                except Exception as e:
                    logger.debug("payment_parser_deposit_button_js_in_modal_failed", error=str(e)[:100])
            
            # Метод 3: Ищем большую зеленую кнопку Deposit
            if not deposit_button_clicked:
                try:
                    # Ищем зеленую кнопку с текстом Deposit
                    green_deposit = page.locator('button:has-text("Deposit")').filter(has=page.locator('[style*="green"], [class*="green"], [class*="primary"]'))
                    if await green_deposit.count() > 0:
                        await green_deposit.first.click(timeout=5000)
                        deposit_button_clicked = True
                        logger.info("payment_parser_deposit_button_clicked", method="green_button")
                except Exception as e:
                    logger.debug("payment_parser_green_deposit_failed", error=str(e))
            
            if not deposit_button_clicked:
                logger.warning("payment_parser_deposit_button_not_found_after_all_methods")
                # Делаем финальный скриншот и диагностику
                try:
                    await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "deposit_button_not_found.png"))
                    logger.info("payment_parser_screenshot_deposit_not_found")
                    
                    # Финальная диагностика - ищем все элементы с текстом Deposit
                    final_diagnosis = await page.evaluate("""
                        () => {
                            const allElements = Array.from(document.querySelectorAll('*'));
                            const depositElements = [];
                            
                            for (const el of allElements) {
                                const text = (el.innerText || el.textContent || '').toLowerCase().trim();
                                if (text.includes('deposit') || text.includes('depositar')) {
                                    const style = window.getComputedStyle(el);
                                    const rect = el.getBoundingClientRect();
                                    const isVisible = style.display !== 'none' && 
                                                     style.visibility !== 'hidden' && 
                                                     rect.width > 0 && 
                                                     rect.height > 0;
                                    
                                    const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], div[role="dialog"]');
                                    const isInModal = modal && modal.contains(el);
                                    
                                    depositElements.push({
                                        tag: el.tagName.toLowerCase(),
                                        text: text.substring(0, 50),
                                        isVisible: isVisible,
                                        isInModal: isInModal,
                                        width: rect.width,
                                        height: rect.height,
                                        x: rect.x,
                                        y: rect.y,
                                        className: (el.className || '').substring(0, 100),
                                        id: el.id || '',
                                        dataTestId: el.getAttribute('data-testid') || ''
                                    });
                                }
                            }
                            
                            return {
                                total: depositElements.length,
                                visible: depositElements.filter(e => e.isVisible).length,
                                inModal: depositElements.filter(e => e.isInModal).length,
                                elements: depositElements.slice(0, 10)
                            };
                        }
                    """)
                    logger.warning("payment_parser_deposit_diagnosis", 
                                 total=final_diagnosis.get('total'),
                                 visible=final_diagnosis.get('visible'),
                                 inModal=final_diagnosis.get('inModal'),
                                 elements=final_diagnosis.get('elements'))
                except Exception as e:
                    logger.debug("payment_parser_deposit_diagnosis_failed", error=str(e)[:100])
            else:
                logger.info("payment_parser_deposit_button_clicked_successfully")
            
            # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: Если кнопка Deposit была кликнута, но форма не появилась через 5 секунд - повторяем клик
            if deposit_button_clicked:
                logger.info("payment_parser_verifying_deposit_click_result")
                await page.wait_for_timeout(5000)  # Ждем 5 секунд после клика
                
                # Проверяем, появилась ли форма
                form_check_after_click = await page.evaluate("""
                    () => {
                        const bodyText = document.body.innerText || document.body.textContent || '';
                        const hasCopyBankDetails = bodyText.includes('Copy bank details');
                        const hasWaitingText = bodyText.includes("We're waiting for your transfer");
                        const hasCvu = /CVU[\\s:]+[0-9]{20,25}/i.test(bodyText);
                        return hasCopyBankDetails || (hasWaitingText && hasCvu);
                    }
                """)
                
                if not form_check_after_click:
                    logger.warning("payment_parser_form_not_appeared_after_deposit_click_retrying")
                    # Форма не появилась - пробуем кликнуть еще раз более агрессивно
                    try:
                        deposit_retry_result = await page.evaluate("""
                            () => {
                                // Ищем все кнопки Deposit и кликаем на самую большую
                                const buttons = Array.from(document.querySelectorAll('button, [role="button"], div[onclick]'));
                                let bestButton = null;
                                let bestSize = 0;
                                
                                for (const btn of buttons) {
                                    const text = (btn.innerText || btn.textContent || '').toLowerCase().trim();
                                    if (text === 'deposit' || text.includes('deposit')) {
                                        const rect = btn.getBoundingClientRect();
                                        const style = window.getComputedStyle(btn);
                                        if (style.display !== 'none' && rect.width > 0 && rect.height > 0) {
                                            const size = rect.width * rect.height;
                                            if (size > bestSize) {
                                                bestSize = size;
                                                bestButton = btn;
                                            }
                                        }
                                    }
                                }
                                
                                if (bestButton) {
                                    try {
                                        bestButton.click();
                                        return { clicked: true, size: bestSize };
                                    } catch (e) {
                                        return { clicked: false, error: e.message };
                                    }
                                }
                                return { clicked: false };
                            }
                        """)
                        
                        if deposit_retry_result.get('clicked'):
                            logger.info("payment_parser_deposit_clicked_retry_success", size=deposit_retry_result.get('size'))
                            await page.wait_for_timeout(3000)
                        else:
                            logger.warning("payment_parser_deposit_click_retry_failed", error=deposit_retry_result.get('error', 'not found'))
                    except Exception as e:
                        logger.debug("payment_parser_deposit_retry_exception", error=str(e)[:100])
                else:
                    logger.info("payment_parser_form_appeared_after_deposit_click_verification_success")
            
            # Шаг 8.3: Ожидание появления формы с данными платежа (второе модальное окно)
            logger.info("payment_parser_waiting_for_payment_form_modal", deposit_button_clicked=deposit_button_clicked)
            
            # Если Deposit кнопка была кликнута, даем дополнительное время на загрузку формы
            if deposit_button_clicked:
                logger.info("payment_parser_deposit_was_clicked_waiting_for_form", wait_seconds=20)
                
                # Делаем скриншот сразу после клика на Deposit
                try:
                    await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "after_deposit_button_click.png"))
                    logger.info("payment_parser_screenshot_after_deposit_button_click")
                except:
                    pass
                
                # Ждем появления нового модального окна или изменения DOM
                logger.info("payment_parser_waiting_for_new_modal_or_form_after_deposit")
                
                # УВЕЛИЧИВАЕМ начальное ожидание после первого клика на Deposit
                # Даем больше времени на загрузку платежной формы (30 секунд вместо 10)
                logger.info("payment_parser_initial_wait_after_deposit_click", wait_seconds=30)
                await page.wait_for_timeout(30000)  # Ждем 30 секунд перед началом проверок
                
                form_started_loading = False
                
                # Проверяем каждую секунду в течение 20 секунд, появилась ли форма (было 10)
                for check in range(20):
                    await page.wait_for_timeout(1000)
                    try:
                        # Проверяем, появилось ли новое модальное окно или форма с данными
                        form_check = await page.evaluate("""
                            () => {
                                const bodyText = document.body.innerText || document.body.textContent || '';
                                const hasCvu = /CVU[\\s:]+[0-9]{20,25}/i.test(bodyText);
                                const hasRecipient = /Recipient[\\s:]+[A-Za-z\\s]+/i.test(bodyText);
                                const hasWaitingText = bodyText.includes("We're waiting for your transfer");
                                const hasLongNumber = /[0-9]{20,25}/.test(bodyText);
                                
                                // Проверяем наличие нового модального окна
                                const modal = document.querySelector('div.paywidget-app, [class*="paywidget"], [class*="payment-modal"], div[role="dialog"]');
                                const modalVisible = modal && window.getComputedStyle(modal).display !== 'none';
                                
                                return {
                                    formLoaded: hasCvu || hasRecipient || hasWaitingText || hasLongNumber,
                                    hasCvu: hasCvu,
                                    hasRecipient: hasRecipient,
                                    modalVisible: modalVisible,
                                    textLength: bodyText.length
                                };
                            }
                        """)
                        
                        if form_check.get('formLoaded'):
                            logger.info("payment_parser_form_started_loading_after_deposit", 
                                      check=check+1,
                                      hasCvu=form_check.get('hasCvu'),
                                      hasRecipient=form_check.get('hasRecipient'),
                                      modalVisible=form_check.get('modalVisible'))
                            form_started_loading = True
                            break
                    except:
                        pass
                
                # Если форма начала загружаться, даем еще время на полную загрузку
                if form_started_loading:
                    logger.info("payment_parser_form_loading_waiting_additional", wait_seconds=20)
                    await page.wait_for_timeout(20000)  # Увеличено с 10 до 20 секунд
                else:
                    logger.info("payment_parser_form_not_detected_yet_waiting_additional", wait_seconds=20)
                    await page.wait_for_timeout(20000)  # Увеличено с 10 до 20 секунд
                
                # Делаем скриншот после ожидания
                try:
                    await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "after_deposit_wait.png"))
                    logger.info("payment_parser_screenshot_after_deposit_wait")
                except:
                    pass
                
                # Проверяем, что URL или DOM изменился (форма начала загружаться)
                current_url = page.url
                logger.debug("payment_parser_url_after_deposit_click", url=current_url[:80])
            
            # Упрощенное ожидание формы: ждем и проверяем появление формы с CVU/Recipient
            # После клика на Deposit форма должна появиться через 20-30 секунд
            if deposit_button_clicked or deposit_button_clicked_early:
                # СНАЧАЛА проверяем, появилась ли форма сразу после клика (может быть быстрая загрузка)
                logger.info("payment_parser_checking_form_immediately_after_deposit_click")
                form_appeared_quick = False
                for quick_check in range(5):  # Проверяем 5 раз (5 секунд)
                    await page.wait_for_timeout(1000)
                    try:
                        quick_form_check = await page.evaluate("""
                            () => {
                                const bodyText = document.body.innerText || document.body.textContent || '';
                                const hasCopyBankDetails = bodyText.includes('Copy bank details');
                                const hasWaitingText = bodyText.includes("We're waiting for your transfer");
                                const hasCvu = /CVU[\\s:]+[0-9]{20,25}/i.test(bodyText);
                                return hasCopyBankDetails || (hasWaitingText && hasCvu);
                            }
                        """)
                        if quick_form_check:
                            form_appeared_quick = True
                            logger.info("payment_parser_form_appeared_quickly_after_deposit", check=quick_check+1)
                            break
                    except:
                        pass
                
                # Если форма не появилась быстро, ждем дольше и проверяем снова
                if not form_appeared_quick:
                    # УВЕЛИЧИВАЕМ время ожидания до 60 секунд для более надежного обнаружения
                    logger.info("payment_parser_simple_form_wait_after_deposit", wait_seconds=60)
                    # Вместо фиксированного ожидания - делаем проверку каждые 3 секунды (более частые проверки)
                    form_found_during_wait = False
                    for wait_cycle in range(20):  # 20 циклов по 3 секунды = 60 секунд
                        await page.wait_for_timeout(3000)
                        try:
                            # Улучшенная проверка: ищем форму в разных местах
                            cycle_check = await page.evaluate("""
                                () => {
                                    const bodyText = document.body.innerText || document.body.textContent || '';
                                    const hasCopyBankDetails = bodyText.includes('Copy bank details') || bodyText.includes('Copy the CVU');
                                    const hasWaitingText = bodyText.includes("We're waiting for your transfer") || bodyText.includes("waiting for your transfer");
                                    const hasCvu = /CVU[\\s:]+[0-9]{20,25}/i.test(bodyText) || /[0-9]{20,25}/.test(bodyText);
                                    const hasRecipient = /Recipient[\\s:]+[A-Z][A-Za-z\\s]{2,}/i.test(bodyText);
                                    const hasConfirmTransfer = bodyText.includes('Confirm transfer');
                                    const hasClaroPayLogo = bodyText.includes('Claro Pay Claro Pay');
                                    
                                    // Проверяем все модальные окна и диалоги
                                    const modals = document.querySelectorAll('[role="dialog"], .modal, [class*="modal"], [class*="dialog"], [class*="overlay"]');
                                    let modalHasForm = false;
                                    for (const modal of modals) {
                                        const style = window.getComputedStyle(modal);
                                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                                            const modalText = modal.textContent || modal.innerText || '';
                                            if (modalText.includes('CVU') || modalText.includes('Recipient') || modalText.includes('Copy bank details')) {
                                                modalHasForm = true;
                                                break;
                                            }
                                        }
                                    }
                                    
                                    return hasCopyBankDetails || (hasWaitingText && hasCvu) || (hasCvu && hasRecipient) || hasConfirmTransfer || modalHasForm;
                                }
                            """)
                            if cycle_check:
                                form_found_during_wait = True
                                logger.info("payment_parser_form_found_during_wait", cycle=wait_cycle+1, wait_seconds=(wait_cycle+1)*3)
                                break
                        except:
                            pass
                        
                        # Каждые 15 секунд (5 циклов) делаем прокрутку страницы (форма может быть ниже)
                        if (wait_cycle + 1) % 5 == 0:
                            try:
                                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                                await page.wait_for_timeout(500)
                                await page.evaluate("window.scrollTo(0, 0)")
                                logger.debug("payment_parser_scrolled_page_during_wait", cycle=wait_cycle+1)
                            except:
                                pass
                    
                    if not form_found_during_wait:
                        logger.info("payment_parser_form_not_found_during_60s_wait_continuing")
                else:
                    # Если форма появилась быстро, даем еще немного времени на полную загрузку
                    logger.info("payment_parser_form_appeared_quickly_waiting_additional", wait_seconds=5)
                    await page.wait_for_timeout(5000)
                
                # Проверяем, появилась ли форма с CVU/Recipient после ожидания
                logger.info("payment_parser_checking_form_after_wait")
                try:
                    # Проверка 1: Проверяем через JavaScript - наличие CVU и Recipient
                    form_check_after_wait = await page.evaluate("""
                        () => {
                            const bodyText = document.body.innerText || document.body.textContent || '';
                            const hasCvu = /CVU[\\s:]+[0-9]{20,25}/i.test(bodyText) || 
                                          /CVU[\\s:]*[0]{5,}[0-9]{15,20}/i.test(bodyText);
                            const hasRecipient = /Recipient[\\s:]+[A-Z][A-Za-z\\s]{2,}/i.test(bodyText);
                            const hasCopyBankDetails = bodyText.includes('Copy bank details') || 
                                                      bodyText.includes('Copy the CVU') ||
                                                      bodyText.includes('Copy bank');
                            const hasWaitingText = bodyText.includes("We're waiting for your transfer") ||
                                                  bodyText.includes("waiting for your transfer");
                            const hasLongNumber = /[0-9]{20,25}/.test(bodyText) || 
                                                 /[0]{5,}[0-9]{15,20}/.test(bodyText);
                            
                            // Дополнительные индикаторы формы из скриншота
                            const hasConfirmTransfer = bodyText.includes('Confirm transfer') || 
                                                      bodyText.includes('Confirm');
                            const hasClaroPayLogo = bodyText.includes('Claro Pay Claro Pay') || 
                                                    (bodyText.match(/Claro Pay/g) && bodyText.match(/Claro Pay/g).length >= 2);
                            const hasTimer = /\\d{1,2}m\\s*:\\s*\\d{1,2}s/.test(bodyText) || 
                                           /\\d{1,2}\\s*m\\s*:\\s*\\d{1,2}\\s*s/.test(bodyText);
                            
                            // Форма найдена если есть ключевые элементы
                            const formFound = hasCopyBankDetails || 
                                            (hasCvu && hasRecipient) || 
                                            (hasWaitingText && hasLongNumber) ||
                                            (hasConfirmTransfer && hasLongNumber) ||
                                            (hasCopyBankDetails && hasWaitingText) ||
                                            (hasConfirmTransfer && hasWaitingText);
                            
                            return {
                                hasCvu: hasCvu,
                                hasRecipient: hasRecipient,
                                hasCopyBankDetails: hasCopyBankDetails,
                                hasWaitingText: hasWaitingText,
                                hasLongNumber: hasLongNumber,
                                hasConfirmTransfer: hasConfirmTransfer,
                                hasClaroPayLogo: hasClaroPayLogo,
                                hasTimer: hasTimer,
                                formFound: formFound,
                                textLength: bodyText.length
                            };
                        }
                    """)
                    
                    if form_check_after_wait.get('formFound'):
                        form_appeared = True
                        logger.info("payment_parser_form_found_after_wait",
                                  hasCvu=form_check_after_wait.get('hasCvu'),
                                  hasRecipient=form_check_after_wait.get('hasRecipient'),
                                  hasCopyBankDetails=form_check_after_wait.get('hasCopyBankDetails'),
                                  hasWaitingText=form_check_after_wait.get('hasWaitingText'),
                                  hasConfirmTransfer=form_check_after_wait.get('hasConfirmTransfer'),
                                  hasClaroPayLogo=form_check_after_wait.get('hasClaroPayLogo'),
                                  hasTimer=form_check_after_wait.get('hasTimer'),
                                  textLength=form_check_after_wait.get('textLength'))
                        
                        # Делаем скриншот формы СРАЗУ после обнаружения
                        try:
                            screenshot_path = SCREENSHOTS_DIR / f"payment_form_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                            await page.screenshot(full_page=True, path=str(screenshot_path))
                            logger.info("payment_parser_form_screenshot_saved", path=str(screenshot_path))
                        except Exception as e:
                            logger.debug("payment_parser_form_screenshot_failed", error=str(e)[:100])
                    else:
                        logger.warning("payment_parser_form_not_found_after_wait",
                                     hasCvu=form_check_after_wait.get('hasCvu'),
                                     hasRecipient=form_check_after_wait.get('hasRecipient'),
                                     textLength=form_check_after_wait.get('textLength'))
                        # Все равно переходим к извлечению - возможно, форма загружается дольше
                        form_appeared = True
                    
                    # Проверка 2: Проверяем через DOM селекторы
                    try:
                        # Проверяем ключевые текстовые элементы формы
                        if await page.locator('*:has-text("Copy bank details"), *:has-text("Copy the CVU")').first.is_visible(timeout=2000):
                            form_appeared = True
                            logger.info("payment_parser_form_found_via_copy_bank_details")
                        elif await page.locator("*:has-text(\"We're waiting for your transfer\")").first.is_visible(timeout=2000):
                            form_appeared = True
                            logger.info("payment_parser_form_found_via_waiting_text")
                        elif await page.locator('*:has-text("Confirm transfer")').first.is_visible(timeout=2000):
                            form_appeared = True
                            logger.info("payment_parser_form_found_via_confirm_button")
                        
                        if form_appeared:
                            # Делаем скриншот формы
                            try:
                                screenshot_path = SCREENSHOTS_DIR / f"payment_form_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                                await page.screenshot(full_page=True, path=str(screenshot_path))
                                logger.info("payment_parser_form_screenshot_saved_dom", path=str(screenshot_path))
                            except Exception as e:
                                logger.debug("payment_parser_form_screenshot_failed_dom", error=str(e)[:100])
                    except:
                        pass
                    
                    # Проверка 3: Проверяем iframe (если форма в iframe)
                    form_found_in_iframe = False
                    try:
                        frames = page.frames
                        for frame in frames:
                            if frame != page.main_frame:
                                try:
                                    frame_text = await frame.evaluate("() => document.body.innerText || document.body.textContent || ''")
                                    if re.search(r'CVU[:\s]+[0-9]{20,25}', frame_text, re.IGNORECASE) or \
                                       re.search(r'Recipient[:\s]+[A-Z][A-Za-z\s]{2,}', frame_text, re.IGNORECASE):
                                        form_appeared = True
                                        form_found_in_iframe = True
                                        logger.info("payment_parser_form_found_in_iframe", frame_url=frame.url[:80])
                                        # Если форма найдена в iframe, нужно будет использовать frame для извлечения данных
                                        # Это будет обработано позже в коде извлечения данных
                                        break
                                except:
                                    continue
                    except Exception as e:
                        logger.debug("payment_parser_iframe_check_failed", error=str(e)[:100])
                        
                except Exception as e:
                    logger.debug("payment_parser_form_check_after_wait_failed", error=str(e)[:100])
                    # Все равно переходим к извлечению
                    form_appeared = True
                
                logger.info("payment_parser_form_wait_completed_proceeding_to_extraction", form_appeared=form_appeared)
                elapsed_total = 30
            else:
                # Дополнительная проверка формы (только если Deposit еще не был кликнут)
                wait_time = 60  # Увеличиваем время ожидания до 60 секунд
                start_time = datetime.now().timestamp()
                check_interval = 2000  # Проверяем каждые 2 секунды (реже, но точнее)
                elapsed_total = 0
                
                logger.info("payment_parser_starting_form_detection_loop", wait_time=wait_time, interval=check_interval)
                
                while (datetime.now().timestamp() - start_time) < wait_time:
                    elapsed = int(datetime.now().timestamp() - start_time)
                    try:
                        # Метод 1: Проверяем через JavaScript evaluate - более точный поиск
                        form_check_result = await page.evaluate("""
                        () => {
                            const bodyText = document.body.innerText || document.body.textContent || '';
                            
                            // Проверяем наличие ключевых индикаторов формы
                            // Улучшенная проверка для формы Claro Pay
                            const hasCopyBankDetails = bodyText.includes('Copy bank details') || 
                                                      bodyText.includes('Copy the CVU') ||
                                                      bodyText.includes('Copy bank');
                            // CVU может начинаться с нулей (0000085700204607998573)
                            const hasCvuLabel = /CVU[\\s:]+[0-9]{20,25}/i.test(bodyText) || 
                                               /CVU[\\s:]*[0]{5,}[0-9]{15,20}/i.test(bodyText);
                            // Recipient может быть длинным именем
                            const hasRecipientLabel = /Recipient[\\s:]+[A-Z][A-Za-z\\s]{2,}/i.test(bodyText);
                            const hasWaitingText = bodyText.includes("We're waiting for your transfer") ||
                                                  bodyText.includes("waiting for your transfer");
                            // CVU обычно 20-25 цифр, может начинаться с нулей
                            const hasLongNumber = /[0-9]{20,25}/.test(bodyText) || 
                                                 /[0]{5,}[0-9]{15,20}/.test(bodyText);
                            
                            // Проверяем наличие всех трех полей: CVU, Recipient, Bank
                            // Улучшенная проверка - учитываем, что данные могут быть в секции "Copy bank details"
                            const hasAllFields = (hasCvuLabel && hasRecipientLabel && (bodyText.includes('Bank') || bodyText.includes('Claro Pay'))) ||
                                                (hasCopyBankDetails && hasCvuLabel && hasRecipientLabel);
                            
                            return {
                                hasCopyBankDetails,
                                hasCvuLabel,
                                hasRecipientLabel,
                                hasWaitingText,
                                hasLongNumber,
                                hasAllFields,
                                textLength: bodyText.length,
                                sample: bodyText.substring(0, 200) // Первые 200 символов для отладки
                            };
                        }
                        """)
                        
                        logger.debug("payment_parser_form_check_result",
                               elapsed=elapsed,
                               hasCopyBankDetails=form_check_result.get('hasCopyBankDetails'),
                               hasCvuLabel=form_check_result.get('hasCvuLabel'),
                               hasRecipientLabel=form_check_result.get('hasRecipientLabel'),
                               hasWaitingText=form_check_result.get('hasWaitingText'),
                               hasLongNumber=form_check_result.get('hasLongNumber'),
                               hasAllFields=form_check_result.get('hasAllFields'),
                               textLength=form_check_result.get('textLength'),
                               sample=form_check_result.get('sample', '')[:100])
                        
                        # Если нашли все необходимые поля - форма появилась!
                        # Улучшенная проверка: учитываем даже частичное наличие данных
                        has_any_data = form_check_result.get('hasCvuLabel') or \
                                      form_check_result.get('hasRecipientLabel') or \
                                      form_check_result.get('hasLongNumber') or \
                                      form_check_result.get('hasWaitingText')
                        
                        if form_check_result.get('hasAllFields') or \
                           (form_check_result.get('hasCvuLabel') and form_check_result.get('hasRecipientLabel')) or \
                           (form_check_result.get('hasCopyBankDetails') and form_check_result.get('hasLongNumber')) or \
                           (has_any_data and form_check_result.get('textLength', 0) > 1200):  # Если есть данные и текст длинный
                            logger.info("payment_parser_payment_form_detected_via_evaluate",
                                       hasAllFields=form_check_result.get('hasAllFields'),
                                       hasCvuLabel=form_check_result.get('hasCvuLabel'),
                                       hasRecipientLabel=form_check_result.get('hasRecipientLabel'),
                                       hasLongNumber=form_check_result.get('hasLongNumber'),
                                       hasWaitingText=form_check_result.get('hasWaitingText'),
                                       textLength=form_check_result.get('textLength'))
                            form_appeared = True
                            # Делаем скриншот при обнаружении формы
                            try:
                                await page.screenshot(full_page=True, path=str(SCREENSHOTS_DIR / "form_detected.png"))
                                logger.info("payment_parser_screenshot_form_detected")
                            except:
                                pass
                            break
                        
                        # Метод 2: Проверяем через DOM селекторы (дополнительная проверка)
                        # Улучшенная проверка - ищем несколько индикаторов формы
                        try:
                            # Индикатор 1: "Copy bank details" - самый надежный признак
                            if await page.locator('*:has-text("Copy bank details"), *:has-text("Copy the CVU")').first.is_visible(timeout=500):
                                logger.info("payment_parser_payment_form_detected_via_copy_text_dom")
                                form_appeared = True
                                break
                        except:
                            pass
                        
                        try:
                            # Индикатор 2: "We're waiting for your transfer" - показывает, что форма активна
                            if await page.locator("*:has-text(\"We're waiting for your transfer\"), *:has-text(\"waiting for your transfer\")").first.is_visible(timeout=500):
                                logger.info("payment_parser_waiting_for_transfer_detected_dom")
                                form_appeared = True
                                break
                        except:
                            pass
                        
                        try:
                            # Индикатор 3: Наличие CVU с числом рядом (более точная проверка)
                            cvu_with_number = await page.locator('*:has-text("CVU")').first.is_visible(timeout=500)
                            if cvu_with_number:
                                # Проверяем, что рядом есть число (20+ цифр)
                                page_text_sample = await page.evaluate("() => document.body.innerText || document.body.textContent || ''")
                                if re.search(r'CVU[:\s]+[0-9]{20,25}', page_text_sample, re.IGNORECASE):
                                    logger.info("payment_parser_payment_form_detected_via_cvu_with_number")
                                    form_appeared = True
                                    break
                        except:
                            pass
                        
                        # Проверяем ошибки
                        try:
                            if await page.locator('*:has-text("Error")').first.is_visible(timeout=500):
                                logger.warning("payment_parser_error_detected_dom")
                                break
                        except:
                            pass
                        
                        try:
                            if await page.locator('*:has-text("Payment failed")').first.is_visible(timeout=500):
                                logger.warning("payment_parser_payment_failed_detected_dom")
                                break
                        except:
                            pass
                            
                    except Exception as e:
                        logger.debug("payment_parser_form_check_exception", elapsed=elapsed, error=str(e)[:100])
                        pass
                    
                    await page.wait_for_timeout(check_interval)
                    
                    elapsed_total = int(datetime.now().timestamp() - start_time)
                    if form_appeared:
                        break
            
            if form_appeared or deposit_button_clicked or deposit_button_clicked_early:
                logger.info("payment_parser_payment_form_modal_appeared", elapsed=elapsed_total)
                await page.wait_for_timeout(2000)  # Минимальное ожидание на полную загрузку всех данных
                
                # ВАЖНО: Извлекаем данные СРАЗУ после обнаружения формы, пока она не закрылась
                # Финальная проверка и извлечение данных в одном месте
                final_check = await page.evaluate("""
                    () => {
                        const text = document.body.innerText || document.body.textContent || '';
                        
                        // Ищем CVU - улучшенный поиск для формы Claro Pay
                        // CVU может начинаться с нескольких нулей (0000085700204607998573)
                        const cvuMatch = text.match(/CVU[\\s:]+([0-9\\s\\-]{20,30})/i);
                        let cvu = null;
                        if (cvuMatch) {
                            cvu = cvuMatch[1].replace(/[\\s\\-]/g, '');
                            // Проверяем длину (CVU обычно 20-25 символов, может быть 22)
                            if (cvu.length < 20 || cvu.length > 25) cvu = null;
                        }
                        // Если CVU не найден через паттерн, ищем длинное число
                        if (!cvu) {
                            const longNumbers = text.match(/[0-9]{20,25}/g);
                            if (longNumbers && longNumbers.length > 0) {
                                // Приоритет 1: Число, начинающееся с нескольких нулей (00000...)
                                for (const num of longNumbers) {
                                    if (num.startsWith('00000') && num.length >= 20) {
                                        cvu = num;
                                        break;
                                    }
                                }
                                // Приоритет 2: Число, начинающееся с нуля
                                if (!cvu) {
                                    for (const num of longNumbers) {
                                        if (num.startsWith('0') && num.length >= 20) {
                                            cvu = num;
                                            break;
                                        }
                                    }
                                }
                                // Приоритет 3: Первое длинное число
                                if (!cvu) cvu = longNumbers[0];
                            }
                        }
                        
                        // Ищем Recipient - улучшенный поиск для полных имен
                        // Recipient может быть длинным (например: "Ramon Ramon Victor Aguirre")
                        const recipientMatch = text.match(/Recipient[\\s:]+([A-Za-z\\s]+?)(?:\\n|Bank|CVU|Amount|We're|Confirm|$)/i);
                        let recipient = null;
                        if (recipientMatch) {
                            recipient = recipientMatch[1].trim();
                            // Удаляем лишние пробелы
                            recipient = recipient.replace(/\\s+/g, ' ').trim();
                            // Проверяем, что это похоже на имя (только буквы и пробелы, длина 3-100)
                            if (recipient.length < 3 || recipient.length > 100 || !/^[A-Za-z\\s]+$/.test(recipient)) {
                                recipient = null;
                            }
                        }
                        
                        // Дополнительный поиск - альтернативный паттерн
                        if (!recipient) {
                            const recipientAltMatch = text.match(/Recipient[\\s:]*\\n?([A-Z][A-Za-z\\s]+?)(?:\\n\\n|Bank|CVU|Amount)/);
                            if (recipientAltMatch) {
                                recipient = recipientAltMatch[1].trim();
                                recipient = recipient.replace(/\\s+/g, ' ').trim();
                                if (recipient.length < 3 || recipient.length > 100 || !/^[A-Za-z\\s]+$/.test(recipient)) {
                                    recipient = null;
                                }
                            }
                        }
                        
                        // Ищем Bank
                        let bank = null;
                        const bankMatch = text.match(/Bank[\\s:]+([A-Za-z\\s\\-]+?)(?:\\n|Recipient|CVU|Amount|$)/i);
                        if (bankMatch) {
                            bank = bankMatch[1].trim();
                        } else if (text.includes('Claro Pay')) {
                            bank = 'Claro Pay';
                        }
                        
                        // Ищем Amount
                        const amountMatch = text.match(/\\$\\s*([\\d,]+(?:\\.\\d{2})?)/);
                        let amount = null;
                        if (amountMatch) {
                            amount = '$' + amountMatch[1];
                        }
                        
                        return {
                            cvu: cvu,
                            recipient: recipient,
                            bank: bank || 'Claro Pay',
                            amount: amount,
                            hasCvu: !!cvu,
                            hasRecipient: !!recipient,
                            hasBank: !!bank || text.includes('Claro Pay'),
                            textLength: text.length,
                            fullText: text.substring(0, 500) // Первые 500 символов для отладки
                        };
                    }
                """)
                
                logger.info("payment_parser_final_form_check",
                           hasCvu=final_check.get('hasCvu'),
                           hasRecipient=final_check.get('hasRecipient'),
                           hasBank=final_check.get('hasBank'),
                           textLength=final_check.get('textLength'),
                           cvu=final_check.get('cvu', '')[:10] + '...' if final_check.get('cvu') else 'NOT FOUND',
                           recipient=final_check.get('recipient', '')[:30] if final_check.get('recipient') else 'NOT FOUND',
                           bank=final_check.get('bank') or 'NOT FOUND',
                           amount=final_check.get('amount') or 'NOT FOUND')
                
                # Сохраняем извлеченные данные сразу в result, если они найдены
                if final_check.get('cvu'):
                    result["cvu"] = final_check.get('cvu')
                    logger.info("payment_parser_cvu_extracted_immediately", cvu=result["cvu"][:10] + "...")
                
                if final_check.get('recipient'):
                    result["recipient"] = final_check.get('recipient')
                    logger.info("payment_parser_recipient_extracted_immediately", recipient=result["recipient"][:30])
                
                if final_check.get('bank'):
                    result["bank"] = final_check.get('bank')
                    logger.info("payment_parser_bank_extracted_immediately", bank=result["bank"])
                
                if final_check.get('amount'):
                    result["amount"] = final_check.get('amount')
                    logger.info("payment_parser_amount_extracted_immediately", amount=result["amount"])
            else:
                logger.warning("payment_parser_payment_form_modal_timeout", elapsed=elapsed_total, deposit_clicked=deposit_button_clicked)
                
                # Делаем скриншот для отладки
                try:
                    debug_screenshot = await page.screenshot(full_page=True)
                    debug_path = SCREENSHOTS_DIR / f"debug_form_timeout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    debug_path.write_bytes(debug_screenshot)
                    logger.info("payment_parser_debug_screenshot_saved", path=str(debug_path))
                except:
                    pass
        else:
            logger.warning("payment_parser_claro_pay_not_clicked_skipping_steps")
        
        # Дополнительное ожидание после выбора метода и типа
        await page.wait_for_timeout(2000)
        logger.debug("payment_parser_final_url_before_extraction", url=page.url)

        # Шаг 9: Извлечение данных платежной формы
        # form_appeared инициализирована выше на строке 2204, поэтому она всегда определена
        logger.info("payment_parser_extracting_data", form_appeared=form_appeared)
        
        # Если форма не была обнаружена, пробуем еще раз подождать и проверить
        if not form_appeared:
            logger.warning("payment_parser_form_not_detected_retrying", wait_seconds=5)
            await page.wait_for_timeout(5000)  # Дополнительное ожидание
            
            # Финальная проверка - может форма появилась за это время
            final_check = await page.evaluate("""
                () => {
                    const text = document.body.innerText || '';
                    const hasCvu = /CVU[\\s:]+[0-9]{20,25}/i.test(text);
                    const hasRecipient = /Recipient[\\s:]+[A-Za-z\\s]+/i.test(text);
                    const hasAll = hasCvu && hasRecipient && (text.includes('Bank') || text.includes('Claro Pay'));
                    return { hasAll, hasCvu, hasRecipient, textLength: text.length };
                }
            """)
            
            if final_check.get('hasAll') or (final_check.get('hasCvu') and final_check.get('hasRecipient')):
                form_appeared = True
                logger.info("payment_parser_form_detected_on_retry", 
                           hasCvu=final_check.get('hasCvu'),
                           hasRecipient=final_check.get('hasRecipient'),
                           textLength=final_check.get('textLength'))
            else:
                logger.warning("payment_parser_form_still_not_detected_after_retry",
                             hasCvu=final_check.get('hasCvu'),
                             hasRecipient=final_check.get('hasRecipient'),
                             textLength=final_check.get('textLength'))
        
        # Если форма появилась, даем дополнительное время на полную загрузку данных
        if form_appeared:
            logger.info("payment_parser_form_appeared_waiting_for_data", wait_seconds=3)
            await page.wait_for_timeout(3000)  # Дополнительное время для загрузки всех данных
        else:
            # Если форма не появилась, все равно ждем и пытаемся извлечь данные
            logger.warning("payment_parser_form_not_detected_but_extracting_anyway", wait_seconds=3)
            await page.wait_for_timeout(3000)

        result["url"] = page.url

        # Сохраняем скриншот формы оплаты (второе модальное окно с CVU, Recipient, Bank, Amount)
        # Делаем скриншот ДО извлечения данных, чтобы видеть состояние формы
        try:
            logger.info("payment_parser_taking_payment_form_screenshot")
            screenshot = await page.screenshot(full_page=True)
            result["debug_screenshot"] = base64.b64encode(screenshot).decode('utf-8')
            
            # Сохраняем скриншот в файл
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_filename = f"payment_form_{timestamp}.png"
            screenshot_path = SCREENSHOTS_DIR / screenshot_filename
            screenshot_path.write_bytes(screenshot)
            result["screenshot_path"] = str(screenshot_path)
            
            logger.info("payment_parser_payment_form_screenshot_saved", path=str(screenshot_path))
            
            # Проверяем, есть ли данные на скриншоте
            page_text_check = await page.inner_text('body')
            has_cvu_in_text = "CVU" in page_text_check and len(re.findall(r'\d{20,25}', page_text_check)) > 0
            has_recipient_in_text = "Recipient" in page_text_check
            logger.info("payment_parser_form_content_check", 
                       has_cvu=has_cvu_in_text, 
                       has_recipient=has_recipient_in_text,
                       text_length=len(page_text_check))
        except Exception as e:
            logger.warning("payment_parser_screenshot_failed", error=str(e))

        # Извлекаем CVU и Recipient - улучшенная логика с учетом структуры формы
        # Проверяем, были ли данные уже извлечены сразу после обнаружения формы
        data_already_extracted = bool(result.get("cvu") and result.get("recipient"))
        logger.debug("payment_parser_extracting_cvu_and_recipient", 
                    cvu_already_found=bool(result.get("cvu")),
                    recipient_already_found=bool(result.get("recipient")),
                    bank_already_found=bool(result.get("bank")),
                    amount_already_found=bool(result.get("amount")),
                    data_already_extracted=data_already_extracted)
        
        # Если данные уже были извлечены сразу после обнаружения формы - не перезаписываем
        if data_already_extracted:
            logger.info("payment_parser_data_already_extracted_skipping_duplicate_extraction",
                       cvu=result.get("cvu")[:10] + "...",
                       recipient=result.get("recipient")[:30],
                       bank=result.get("bank") or "NOT FOUND",
                       amount=result.get("amount") or "NOT FOUND")
        else:
            # Сначала ждем, пока форма действительно загрузится и данные появятся
            # УВЕЛИЧИВАЕМ ожидание для более надежной загрузки данных
            await page.wait_for_timeout(5000)
            
            # Метод 1: Извлечение через JavaScript - ищем структуру "Copy bank details"
            try:
                payment_data = await page.evaluate("""
                () => {
                    const result = { cvu: null, recipient: null, bank: null, amount: null };
                    
                    // Ищем блок "Copy bank details" или похожий контейнер
                    const allText = document.body.innerText || document.body.textContent || '';
                    
                    // Ищем CVU - улучшенный паттерн для формы Claro Pay
                    // CVU может начинаться с нескольких нулей (например: 0000085700204607998573)
                    const cvuMatch = allText.match(/CVU[\\s:]*([0-9\\s\\-]{20,30})/i);
                    if (cvuMatch) {
                        let cvu = cvuMatch[1].replace(/[\\s\\-]/g, '');
                        // Проверяем длину (CVU обычно 20-25 символов, может быть 22 как на скриншоте)
                        if (cvu.length >= 20 && cvu.length <= 25) {
                            result.cvu = cvu;
                        }
                    }
                    
                    // Если CVU не найден через паттерн, ищем длинное число (20-25 цифр)
                    if (!result.cvu) {
                        // Ищем все числа длиной 20-25 цифр
                        const longNumbers = allText.match(/[0-9]{20,25}/g);
                        if (longNumbers && longNumbers.length > 0) {
                            // Приоритет 1: Число, начинающееся с нескольких нулей (00000...)
                            for (const num of longNumbers) {
                                if (num.startsWith('00000') && num.length >= 20) {
                                    result.cvu = num;
                                    break;
                                }
                            }
                            // Приоритет 2: Число, начинающееся с одного или нескольких нулей
                            if (!result.cvu) {
                                for (const num of longNumbers) {
                                    if (num.startsWith('0') && num.length >= 20) {
                                        result.cvu = num;
                                        break;
                                    }
                                }
                            }
                            // Приоритет 3: Первое длинное число
                            if (!result.cvu) {
                                result.cvu = longNumbers[0];
                            }
                        }
                    }
                    
                    // Ищем Recipient - улучшенный паттерн для полных имен
                    // Recipient может быть длинным именем (например: "Ramon Ramon Victor Aguirre")
                    // Ищем до следующего поля (Bank, CVU, Amount) или до конца строки
                    const recipientMatch = allText.match(/Recipient[\\s:]+([A-Za-z\\s]+?)(?:\\n|Bank|CVU|Amount|We're|Confirm|$)/i);
                    if (recipientMatch) {
                        let recipient = recipientMatch[1].trim();
                        // Удаляем лишние пробелы и переносы строк
                        recipient = recipient.replace(/\\s+/g, ' ').trim();
                        // Проверяем, что это похоже на имя (содержит буквы, пробелы, длина > 3)
                        // Допускаем длинные имена (до 100 символов)
                        if (recipient.length >= 3 && recipient.length <= 100 && /^[A-Za-z\\s]+$/.test(recipient)) {
                            result.recipient = recipient;
                        }
                    }
                    
                    // Дополнительный поиск - ищем текст после "Recipient:" до следующего поля
                    if (!result.recipient) {
                        const recipientAltMatch = allText.match(/Recipient[\\s:]*\\n?([A-Z][A-Za-z\\s]+?)(?:\\n\\n|Bank|CVU|Amount)/);
                        if (recipientAltMatch) {
                            let recipient = recipientAltMatch[1].trim();
                            recipient = recipient.replace(/\\s+/g, ' ').trim();
                            if (recipient.length >= 3 && recipient.length <= 100 && /^[A-Za-z\\s]+$/.test(recipient)) {
                                result.recipient = recipient;
                            }
                        }
                    }
                    
                    // Ищем Bank - паттерн: "Bank:" или "Bank" + текст
                    const bankMatch = allText.match(/Bank[\\s:]+([A-Za-z\\s\\-]+?)(?:\\n|Recipient|CVU|Amount|$)/i);
                    if (bankMatch) {
                        result.bank = bankMatch[1].trim();
                    } else if (allText.includes('Claro Pay')) {
                        result.bank = 'Claro Pay';
                    }
                    
                    // Ищем Amount - паттерн: "$" + число
                    const amountMatch = allText.match(/\\$\\s*([\\d,]+(?:\\.\\d{2})?)/);
                    if (amountMatch) {
                        result.amount = '$' + amountMatch[1];
                    }
                    
                    return result;
                }
                """)
                
                if payment_data.get('cvu'):
                    result["cvu"] = payment_data['cvu']
                    logger.info("payment_parser_cvu_found_via_evaluate", cvu=result["cvu"][:10] + "...")
                
                if payment_data.get('recipient'):
                    result["recipient"] = payment_data['recipient']
                    logger.info("payment_parser_recipient_found_via_evaluate", recipient=result["recipient"][:30])
                
                if payment_data.get('bank'):
                    result["bank"] = payment_data['bank']
                    logger.info("payment_parser_bank_found_via_evaluate", bank=result["bank"])
                
                if payment_data.get('amount'):
                    result["amount"] = payment_data['amount']
                    logger.info("payment_parser_amount_found_via_evaluate", amount=result["amount"])
                    
            except Exception as e:
                logger.debug("payment_parser_evaluate_extraction_failed", error=str(e)[:100])
        
        # Метод 2: Если CVU не найден, пробуем через DOM селекторы (улучшенный поиск)
        if not result["cvu"]:
            logger.debug("payment_parser_searching_cvu_via_dom_selectors")
            try:
                # Ищем элемент с текстом "CVU" и получаем следующий элемент или родителя
                cvu_elements = await page.locator('*:has-text("CVU")').all()
                for cvu_elem in cvu_elements[:5]:  # Проверяем первые 5 элементов
                    try:
                        # Пробуем получить текст из родительского контейнера
                        parent_container = await cvu_elem.evaluate_handle("""el => {
                            let parent = el.closest("div, li, tr, td");
                            // Если не нашли контейнер, берем родителя
                            if (!parent) parent = el.parentElement;
                            return parent;
                        }""")
                        if parent_container:
                            parent_text = await parent_container.as_element().inner_text() if hasattr(parent_container, 'as_element') else None
                            if parent_text:
                                # Ищем CVU в тексте родителя - улучшенный паттерн
                                # Поддерживаем CVU с нулями в начале (0000085700204607998573)
                                cvu_match = re.search(r'CVU[:\s]*([0-9\s\-]{20,30})', parent_text, re.IGNORECASE)
                                if cvu_match:
                                    cvu_value = re.sub(r'[\s\-]+', '', cvu_match.group(1))
                                    if len(cvu_value) >= 20 and len(cvu_value) <= 25:
                                        result["cvu"] = cvu_value
                                        logger.info("payment_parser_cvu_found_via_dom_parent", cvu=result["cvu"][:10] + "...")
                                        break
                    except:
                        continue
                    
                # Альтернативный метод: поиск через evaluate с более точным поиском
                if not result["cvu"]:
                    cvu_from_dom = await page.evaluate("""
                        () => {
                            // Ищем элемент с текстом "CVU"
                            const cvuElements = Array.from(document.querySelectorAll('*')).filter(el => {
                                const text = (el.textContent || el.innerText || '').toLowerCase();
                                return text.includes('cvu') && text.length < 100;
                            });
                            
                            for (const el of cvuElements.slice(0, 5)) {
                                // Ищем родительский контейнер
                                let container = el.closest('div, li, tr, td, section, article');
                                if (!container) container = el.parentElement;
                                
                                if (container) {
                                    const containerText = container.textContent || container.innerText || '';
                                    // Ищем CVU с числом (20-25 цифр, может начинаться с нулей)
                                    const cvuMatch = containerText.match(/CVU[\\s:]*([0-9\\s\\-]{20,30})/i);
                                    if (cvuMatch) {
                                        const cvu = cvuMatch[1].replace(/[\\s\\-]/g, '');
                                        if (cvu.length >= 20 && cvu.length <= 25) {
                                            return cvu;
                                        }
                                    }
                                }
                            }
                            return null;
                        }
                    """)
                    if cvu_from_dom:
                        result["cvu"] = cvu_from_dom
                        logger.info("payment_parser_cvu_found_via_dom_evaluate", cvu=result["cvu"][:10] + "...")
            except Exception as e:
                logger.debug("payment_parser_cvu_dom_selector_failed", error=str(e)[:100])
        
        # Метод 3: Если Recipient не найден, пробуем через DOM селекторы (улучшенный поиск)
        if not result["recipient"]:
            logger.debug("payment_parser_searching_recipient_via_dom_selectors")
            try:
                recipient_elements = await page.locator('*:has-text("Recipient")').all()
                for recipient_elem in recipient_elements[:5]:
                    try:
                        # Пробуем получить текст из родительского контейнера
                        parent_container = await recipient_elem.evaluate_handle("""el => {
                            let parent = el.closest("div, li, tr, td, section, article");
                            if (!parent) parent = el.parentElement;
                            return parent;
                        }""")
                        if parent_container:
                            parent_text = await parent_container.as_element().inner_text() if hasattr(parent_container, 'as_element') else None
                            if parent_text:
                                # Ищем Recipient в тексте родителя - улучшенный паттерн для длинных имен
                                recipient_match = re.search(r'Recipient[:\s]+([A-Za-z\s]+?)(?:\n|Bank|CVU|Amount|We\'re|Confirm|$)', parent_text, re.IGNORECASE)
                                if recipient_match:
                                    recipient = recipient_match.group(1).strip()
                                    recipient = re.sub(r'\s+', ' ', recipient)  # Удаляем лишние пробелы
                                    if len(recipient) >= 3 and len(recipient) <= 100 and re.match(r'^[A-Za-z\s]+$', recipient):
                                        result["recipient"] = recipient
                                        logger.info("payment_parser_recipient_found_via_dom_parent", recipient=result["recipient"][:30])
                                        break
                    except:
                        continue
                    
                # Альтернативный метод: поиск через evaluate с более точным поиском
                if not result["recipient"]:
                    recipient_from_dom = await page.evaluate("""
                        () => {
                            // Ищем элемент с текстом "Recipient"
                            const recipientElements = Array.from(document.querySelectorAll('*')).filter(el => {
                                const text = (el.textContent || el.innerText || '').toLowerCase();
                                return text.includes('recipient') && text.length < 150;
                            });
                            
                            for (const el of recipientElements.slice(0, 5)) {
                                // Ищем родительский контейнер
                                let container = el.closest('div, li, tr, td, section, article');
                                if (!container) container = el.parentElement;
                                
                                if (container) {
                                    const containerText = container.textContent || container.innerText || '';
                                    // Ищем Recipient с именем (3-100 символов, только буквы и пробелы)
                                    const recipientMatch = containerText.match(/Recipient[\\s:]+([A-Z][A-Za-z\\s]{2,}?)(?:\\n|Bank|CVU|Amount|We're|Confirm|$)/i);
                                    if (recipientMatch) {
                                        let recipient = recipientMatch[1].trim().replace(/\\s+/g, ' ');
                                        if (recipient.length >= 3 && recipient.length <= 100 && /^[A-Za-z\\s]+$/.test(recipient)) {
                                            return recipient;
                                        }
                                    }
                                }
                            }
                            return null;
                        }
                    """)
                    if recipient_from_dom:
                        result["recipient"] = recipient_from_dom
                        logger.info("payment_parser_recipient_found_via_dom_evaluate", recipient=result["recipient"][:30])
            except Exception as e:
                logger.debug("payment_parser_recipient_dom_selector_failed", error=str(e)[:100])
        
        # Метод 4: Fallback - поиск в HTML контенте (улучшенный)
        if not result["cvu"]:
            logger.debug("payment_parser_searching_cvu_in_html_fallback")
            try:
                page_content = await page.content()
                cvu_patterns = [
                    r'CVU[:\s]*([0-9]{20,25})',
                    r'CVU[:\s]*([\d\s\-]{20,30})',
                    r'CVU[:\s]*([0]{5,}[0-9]{15,20})',  # CVU начинающийся с 5+ нулей
                    r'data-cvu[=:][\s"\']*([0-9]{20,25})',  # data-атрибуты
                ]
                for pattern in cvu_patterns:
                    matches = re.findall(pattern, page_content, re.IGNORECASE)
                    if matches:
                        for match in matches:
                            cvu_found = re.sub(r'[\s\-"\']+', '', str(match))
                            if len(cvu_found) >= 20 and len(cvu_found) <= 25:
                                result["cvu"] = cvu_found
                                logger.info("payment_parser_cvu_found_via_html_fallback", cvu=result["cvu"][:10] + "...")
                                break
                        if result["cvu"]:
                            break
            except Exception as e:
                logger.debug("payment_parser_cvu_html_fallback_failed", error=str(e)[:100])
        
        # Метод 4.5: Дополнительный поиск - ищем все длинные числа в тексте страницы
        if not result["cvu"]:
            logger.debug("payment_parser_searching_cvu_all_long_numbers")
            try:
                page_text = await page.inner_text('body')
                # Ищем все числа длиной 20-25 цифр
                long_numbers = re.findall(r'\b[0-9]{20,25}\b', page_text)
                if long_numbers:
                    # Приоритет 1: Число начинающееся с 00000
                    for num in long_numbers:
                        if num.startswith('00000') and len(num) >= 20:
                            result["cvu"] = num
                            logger.info("payment_parser_cvu_found_via_long_number_prefix", cvu=result["cvu"][:10] + "...")
                            break
                    # Приоритет 2: Число начинающееся с 0
                    if not result["cvu"]:
                        for num in long_numbers:
                            if num.startswith('0') and len(num) >= 20:
                                result["cvu"] = num
                                logger.info("payment_parser_cvu_found_via_long_number_zero", cvu=result["cvu"][:10] + "...")
                                break
                    # Приоритет 3: Первое длинное число
                    if not result["cvu"]:
                        result["cvu"] = long_numbers[0]
                        logger.info("payment_parser_cvu_found_via_long_number_first", cvu=result["cvu"][:10] + "...")
            except Exception as e:
                logger.debug("payment_parser_cvu_long_number_search_failed", error=str(e)[:100])
        
        # Метод 5: Fallback - поиск Recipient в HTML (улучшенный)
        if not result["recipient"]:
            logger.debug("payment_parser_searching_recipient_in_html_fallback")
            try:
                page_content = await page.content()
                recipient_patterns = [
                    r'Recipient[:\s>]+([A-Z][A-Za-z\s]{2,}?)(?:</|Bank|CVU|Amount|We\'re|Confirm|\\n|</)',
                    r'Recipient[:\s>]+([^<\\n]{3,100})',
                    r'data-recipient[=:][\s"\']*([A-Za-z\s]{3,100})',  # data-атрибуты
                    r'>Recipient[:\s]*<[^>]*>([A-Z][A-Za-z\s]{2,}?)</',  # HTML структура
                ]
                for pattern in recipient_patterns:
                    matches = re.findall(pattern, page_content, re.IGNORECASE)
                    if matches:
                        for match in matches:
                            recipient = str(match).strip()
                            # Очищаем от HTML тегов и лишних символов
                            recipient = re.sub(r'<[^>]+>', '', recipient).strip()
                            recipient = re.sub(r'["\']+', '', recipient).strip()
                            recipient = re.sub(r'\s+', ' ', recipient)
                            if len(recipient) >= 3 and len(recipient) <= 100 and re.match(r'^[A-Za-z\s]+$', recipient):
                                result["recipient"] = recipient
                                logger.info("payment_parser_recipient_found_via_html_fallback", recipient=result["recipient"][:30])
                                break
                        if result["recipient"]:
                            break
            except Exception as e:
                logger.debug("payment_parser_recipient_html_fallback_failed", error=str(e)[:100])
        
        # Метод 5.5: Дополнительная попытка - ждем еще и проверяем снова (форма может загрузиться позже)
        if not result["cvu"] or not result["recipient"]:
            logger.info("payment_parser_final_extraction_attempt_waiting", 
                       cvu_found=bool(result.get("cvu")), 
                       recipient_found=bool(result.get("recipient")))
            await page.wait_for_timeout(5000)  # Ждем еще 5 секунд
            
            # Финальная попытка извлечения
            try:
                final_extraction = await page.evaluate("""
                    () => {
                        const allText = document.body.innerText || document.body.textContent || '';
                        
                        let cvu = null;
                        let recipient = null;
                        
                        // Финальный поиск CVU - более агрессивный
                        const cvuMatch = allText.match(/CVU[\\s:]*([0-9\\s\\-]{20,30})/i);
                        if (cvuMatch) {
                            cvu = cvuMatch[1].replace(/[\\s\\-]/g, '');
                            if (cvu.length < 20 || cvu.length > 25) cvu = null;
                        }
                        
                        // Если не найден, ищем все длинные числа
                        if (!cvu) {
                            const numbers = allText.match(/[0-9]{20,25}/g);
                            if (numbers && numbers.length > 0) {
                                for (const num of numbers) {
                                    if (num.startsWith('00000') || num.startsWith('0')) {
                                        cvu = num;
                                        break;
                                    }
                                }
                                if (!cvu) cvu = numbers[0];
                            }
                        }
                        
                        // Финальный поиск Recipient - более агрессивный
                        const recipientMatch = allText.match(/Recipient[\\s:]+([A-Z][A-Za-z\\s]{2,}?)(?:\\n|Bank|CVU|Amount|We're|Confirm|$)/i);
                        if (recipientMatch) {
                            recipient = recipientMatch[1].trim().replace(/\\s+/g, ' ');
                            if (recipient.length < 3 || recipient.length > 100 || !/^[A-Za-z\\s]+$/.test(recipient)) {
                                recipient = null;
                            }
                        }
                        
                        return { cvu, recipient };
                    }
                """)
                
                if final_extraction.get('cvu') and not result.get("cvu"):
                    result["cvu"] = final_extraction['cvu']
                    logger.info("payment_parser_cvu_found_final_attempt", cvu=result["cvu"][:10] + "...")
                
                if final_extraction.get('recipient') and not result.get("recipient"):
                    result["recipient"] = final_extraction['recipient']
                    logger.info("payment_parser_recipient_found_final_attempt", recipient=result["recipient"][:30])
            except Exception as e:
                logger.debug("payment_parser_final_extraction_failed", error=str(e)[:100])

        # Извлекаем Bank (только если не был найден через evaluate)
        if not result.get("bank"):
            logger.debug("payment_parser_searching_bank_via_selectors")
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

            if not result.get("bank"):
                result["bank"] = "Claro Pay"  # По умолчанию

        # Извлекаем Amount (только если не был найден через evaluate)
        if not result.get("amount"):
            logger.debug("payment_parser_searching_amount_via_selectors")
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

        # Финальное логирование извлеченных данных
        logger.info("payment_parser_extraction_result",
                   cvu=result.get("cvu", "")[:10] + "..." if result.get("cvu") else "NOT FOUND",
                   recipient=result.get("recipient", "")[:30] + "..." if result.get("recipient") else "NOT FOUND",
                   bank=result.get("bank", "NOT FOUND"),
                   amount=result.get("amount", "NOT FOUND"),
                   method=result.get("method", "NOT FOUND"),
                   payment_type=result.get("payment_type", "NOT FOUND"))
        
        # Проверяем успешность - теперь без требования CVU
        # Успех определяется тем, что мы дошли до страницы депозита и выбрали метод оплаты
        if result.get("method") == "Claro Pay" and result.get("url"):
            result["success"] = True
            logger.info("payment_parser_success", 
                       domain=result.get("domain"), 
                       method=result.get("method"),
                       url=result.get("url"),
                       has_cvu=bool(result.get("cvu")),
                       has_recipient=bool(result.get("recipient")))
        else:
            result["success"] = False
            result["error"] = "Failed to select payment method or navigate to deposit page"
            logger.warning("payment_parser_failed", 
                          method=result.get("method"), 
                          url=result.get("url"),
                          has_cvu=bool(result.get("cvu")),
                          has_recipient=bool(result.get("recipient")))

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
                    await browser_context_manager.__aexit__(None, None, None)
                except:
                    pass
    
    # Финальная проверка перед возвратом - убеждаемся, что данные сохранены
    logger.info("payment_parser_final_result_check",
               cvu=result.get("cvu")[:10] + "..." if result.get("cvu") else "None",
               recipient=result.get("recipient")[:30] if result.get("recipient") else "None",
               bank=result.get("bank") or "None",
               amount=result.get("amount") or "None",
               method=result.get("method") or "None",
               payment_type=result.get("payment_type") or "None",
               success=result.get("success", False),
               has_cvu=bool(result.get("cvu")),
               has_recipient=bool(result.get("recipient")))

    return result
