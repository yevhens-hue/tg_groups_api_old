# provider_parser_playwright.py
# Парсер провайдеров на Playwright с обработкой iframe, popup, network requests

import asyncio
import time
import os
from urllib.parse import urlparse
from typing import Optional, List, Dict
from playwright.async_api import async_playwright, Page, Frame, BrowserContext
import tldextract

from storage import Storage
from merchants_config import MERCHANTS


class ProviderParserPlaywright:
    def __init__(self, headless: bool = False, screenshot_dir: str = "screenshots", storage_state_dir: str = "storage_states", trace_dir: str = "traces"):
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        self.storage_state_dir = storage_state_dir
        self.trace_dir = trace_dir
        self.storage = Storage()
        
        # Создаём директории
        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs(self.storage_state_dir, exist_ok=True)
        os.makedirs(self.trace_dir, exist_ok=True)
        
    def get_storage_state_path(self, merchant_id: str) -> str:
        """Путь к файлу storageState для мерчанта"""
        return os.path.join(self.storage_state_dir, f"{merchant_id}_storage_state.json")
    
    def get_trace_path(self, merchant_id: str) -> str:
        """Путь к файлу trace для мерчанта"""
        return os.path.join(self.trace_dir, f"{merchant_id}_trace.zip")
    
    async def detect_captcha(self, page: Page) -> bool:
        """Обнаружение капчи на странице"""
        captcha_indicators = [
            "//iframe[contains(@src, 'recaptcha')]",
            "//iframe[contains(@src, 'captcha')]",
            "//div[contains(@class, 'captcha')]",
            "//div[contains(@class, 'recaptcha')]",
            "//div[contains(@id, 'captcha')]",
            "//div[contains(@id, 'recaptcha')]",
            "//*[contains(text(), 'captcha')]",
            "//*[contains(text(), 'CAPTCHA')]",
            "//*[contains(text(), 'Verify')]",
            "//*[contains(text(), 'verify')]",
        ]
        
        for xpath in captcha_indicators:
            try:
                element = page.locator(f"xpath={xpath}").first
                if await element.is_visible(timeout=2000):
                    return True
            except:
                continue
        
        # Проверяем iframe с капчей
        for frame in page.frames:
            if frame != page.main_frame:
                frame_url = frame.url.lower()
                if any(keyword in frame_url for keyword in ["recaptcha", "captcha", "hcaptcha", "turnstile"]):
                    return True
        
        return False
    
    async def wait_for_manual_login(self, page: Page, merchant_id: str, context: BrowserContext) -> bool:
        """Ожидание ручного решения капчи и логина"""
        print("\n" + "="*60)
        print("🔐 HUMAN-IN-THE-LOOP: Требуется ручное вмешательство")
        print("="*60)
        print(f"Мерчант: {merchant_id}")
        print(f"URL: {page.url}")
        print(f"\n📋 Инструкции:")
        print("1. Решите капчу в открытом браузере (если есть)")
        print("2. Введите креденшиалы и войдите в систему")
        print("3. После успешного входа нажмите Enter в этом терминале")
        print("\n⏸️  Ожидание ручного логина...")
        print("="*60 + "\n")
        
        # Сохраняем trace для отладки
        trace_path = self.get_trace_path(merchant_id)
        try:
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
            print(f"📹 Trace запись начата: {trace_path}")
        except Exception as e:
            print(f"⚠️  Не удалось начать trace: {e}")
        
        # Создаём файл уведомления
        notification_file = f"notification_{merchant_id}_{int(time.time())}.txt"
        with open(notification_file, "w") as f:
            f.write(f"HUMAN-IN-THE-LOOP: Требуется ручное вмешательство\n")
            f.write(f"Мерчант: {merchant_id}\n")
            f.write(f"URL: {page.url}\n")
            f.write(f"Trace: {trace_path}\n")
            f.write(f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        print(f"📄 Уведомление сохранено: {notification_file}")
        
        # Ждём ввода от пользователя
        try:
            input("Нажмите Enter после успешного логина...")
        except KeyboardInterrupt:
            print("\n⚠️  Прервано пользователем")
            return False
        
        # Останавливаем trace
        try:
            await context.tracing.stop(path=trace_path)
            print(f"✓ Trace сохранён: {trace_path}")
            print(f"  Просмотр: playwright show-trace {trace_path}")
        except Exception as e:
            print(f"⚠️  Ошибка при сохранении trace: {e}")
        
        # Проверяем, что логин успешен
        current_url = page.url
        if "login" not in current_url.lower() and "signin" not in current_url.lower():
            print("✓ Логин выполнен успешно")
            return True
        else:
            print("⚠️  Возможно, логин не выполнен. Проверьте URL.")
            return True  # Продолжаем в любом случае
    
    
    def get_domain(self, url: str) -> str:
        """Извлечение домена из URL (eTLD+1)"""
        if not url or not url.startswith(("http://", "https://")):
            return ""
        try:
            extracted = tldextract.extract(url)
            if extracted.domain and extracted.suffix:
                return f"{extracted.domain}.{extracted.suffix}".lower()
            return extracted.domain.lower() if extracted.domain else ""
        except Exception:
            return ""
    
    async def login(self, page: Page, merchant_id: str, config: dict) -> bool:
        """Логин на сайт мерчанта"""
        try:
            credentials = config.get("credentials", {})
            username = credentials.get("username", "")
            password = credentials.get("password", "")
            
            if not username or not password:
                print(f"⚠️  Креденшиалы не указаны для {merchant_id}. Пропускаем логин.")
                return False
            
            print(f"Попытка входа с username: {username[:3]}***")
            
            selectors = config.get("selectors", {})
            
            # Пробуем прямой переход на страницу логина
            current_url = page.url
            login_urls = [
                f"{urlparse(current_url).scheme}://{urlparse(current_url).netloc}/login",
                f"{urlparse(current_url).scheme}://{urlparse(current_url).netloc}/signin",
                f"{urlparse(current_url).scheme}://{urlparse(current_url).netloc}/auth",
            ]
            
            # Если уже на странице логина, пропускаем переход
            if "login" not in current_url.lower() and "signin" not in current_url.lower() and "auth" not in current_url.lower():
                for login_url in login_urls:
                    try:
                        await page.goto(login_url, wait_until="domcontentloaded", timeout=10000)
                        # Ждём загрузки JavaScript
                        await page.wait_for_timeout(5000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        except:
                            await page.wait_for_load_state("load", timeout=5000)
                        if "login" in page.url.lower() or "signin" in page.url.lower():
                            print(f"✓ Переход на страницу логина: {login_url}")
                            break
                    except:
                        continue
            
            # Поиск и клик по кнопке логина
            login_selectors = selectors.get("login_button", "").split(", ")
            login_clicked = False
            
            # Пробуем CSS селекторы
            for selector in login_selectors:
                if not selector.strip():
                    continue
                try:
                    login_btn = page.locator(selector).first
                    if await login_btn.is_visible(timeout=3000):
                        await login_btn.click()
                        login_clicked = True
                        print(f"✓ Нажата кнопка логина: {selector}")
                        await page.wait_for_timeout(2000)
                        break
                except Exception:
                    continue
            
            # Если не нашли через CSS, пробуем поиск по тексту
            if not login_clicked:
                text_selectors = [
                    "//a[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'LOGIN')]",
                    "//button[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'LOGIN')]",
                    "//a[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'SIGN IN')]",
                    "//button[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'SIGN IN')]",
                    "//a[contains(text(), 'Вход')]",
                    "//button[contains(text(), 'Вход')]",
                ]
                for xpath in text_selectors:
                    try:
                        login_btn = page.locator(f"xpath={xpath}").first
                        if await login_btn.is_visible(timeout=3000):
                            await login_btn.click()
                            login_clicked = True
                            print(f"✓ Нажата кнопка логина через XPath: {xpath}")
                            await page.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue
            
            if not login_clicked:
                print("⚠️  Кнопка логина не найдена. Возможно, уже на странице логина.")
            
            # Ждём появления формы логина (может быть модальное окно или iframe)
            await page.wait_for_timeout(5000)
            
            # Проверяем, не появился ли iframe с формой логина
            login_frame = None
            for frame in page.frames:
                if frame != page.main_frame:
                    try:
                        # Проверяем наличие полей ввода в iframe
                        username_in_frame = frame.locator("input[type='text'], input[name*='login'], input[name*='username']").first
                        if await username_in_frame.is_visible(timeout=2000):
                            login_frame = frame
                            print("✓ Найдена форма логина в iframe")
                            break
                    except:
                        continue
            
            # Если не нашли iframe, проверяем все фреймы более тщательно
            if not login_frame:
                print(f"  Проверка iframe: найдено {len(page.frames)} фреймов")
                for i, frame in enumerate(page.frames):
                    if frame != page.main_frame:
                        try:
                            frame_url = frame.url
                            print(f"    Frame {i}: {frame_url}")
                            # Пробуем найти любые input в этом фрейме
                            inputs = await frame.locator("input").all()
                            if inputs:
                                print(f"      Найдено {len(inputs)} input полей в iframe")
                                login_frame = frame
                                break
                        except:
                            continue
            
            # Ввод username - используем нужный контекст (iframe или main page)
            target_page = login_frame if login_frame else page
            username_selectors = selectors.get("username_input", "").split(", ")
            username_entered = False
            
            for selector in username_selectors:
                if not selector.strip():
                    continue
                try:
                    username_input = target_page.locator(selector).first
                    if await username_input.is_visible(timeout=3000):
                        await username_input.fill(username)
                        username_entered = True
                        print(f"✓ Введён username: {selector}")
                        await page.wait_for_timeout(1000)
                        break
                except Exception:
                    continue
            
            # Если не нашли через CSS, пробуем XPath
            if not username_entered:
                xpath_selectors = [
                    "//input[@type='text' and not(@type='password')]",
                    "//input[contains(@placeholder, 'login') or contains(@placeholder, 'Login') or contains(@placeholder, 'phone') or contains(@placeholder, 'Phone')]",
                    "//input[contains(@name, 'login') or contains(@name, 'username') or contains(@name, 'phone')]",
                    "//input[contains(@id, 'login') or contains(@id, 'username') or contains(@id, 'phone')]",
                    "//input[@type='text'][1]",
                ]
                for xpath in xpath_selectors:
                    try:
                        username_input = target_page.locator(f"xpath={xpath}").first
                        if await username_input.is_visible(timeout=3000):
                            await username_input.fill(username)
                            username_entered = True
                            print(f"✓ Введён username через XPath: {xpath}")
                            await page.wait_for_timeout(1000)
                            break
                    except Exception:
                        continue
            
            # Последняя попытка - ищем все input[type='text'] и берём первый
            if not username_entered:
                try:
                    all_text_inputs = await target_page.locator("input[type='text']").all()
                    if all_text_inputs:
                        # Берём первый видимый input
                        for inp in all_text_inputs:
                            try:
                                if await inp.is_visible(timeout=1000):
                                    await inp.fill(username)
                                    username_entered = True
                                    print(f"✓ Введён username в первый видимый input[type='text']")
                                    await page.wait_for_timeout(1000)
                                    break
                            except:
                                continue
                except Exception as e:
                    print(f"⚠️  Ошибка при поиске всех text inputs: {e}")
            
            if not username_entered:
                print("❌ Поле username не найдено")
                # Логируем все input поля на странице для отладки
                try:
                    all_inputs = await target_page.locator("input").all()
                    print(f"  Найдено input полей на странице: {len(all_inputs)}")
                    for i, inp in enumerate(all_inputs[:5]):  # Показываем первые 5
                        try:
                            inp_type = await inp.get_attribute("type")
                            inp_name = await inp.get_attribute("name")
                            inp_id = await inp.get_attribute("id")
                            print(f"    Input {i+1}: type={inp_type}, name={inp_name}, id={inp_id}")
                        except:
                            pass
                except:
                    pass
                return False
            
            # Ввод password - используем тот же контекст
            password_selectors = selectors.get("password_input", "").split(", ")
            password_entered = False
            
            for selector in password_selectors:
                if not selector.strip():
                    continue
                try:
                    password_input = target_page.locator(selector).first
                    if await password_input.is_visible(timeout=3000):
                        await password_input.fill(password)
                        password_entered = True
                        print(f"✓ Введён password: {selector}")
                        await page.wait_for_timeout(1000)
                        break
                except Exception:
                    continue
            
            # Если не нашли через CSS, пробуем XPath
            if not password_entered:
                xpath = "//input[@type='password']"
                try:
                    password_input = target_page.locator(f"xpath={xpath}").first
                    if await password_input.is_visible(timeout=3000):
                        await password_input.fill(password)
                        password_entered = True
                        print(f"✓ Введён password через XPath")
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass
            
            if not password_entered:
                print("❌ Поле password не найдено")
                return False
            
            # Нажатие кнопки submit - используем тот же контекст
            submit_selectors = selectors.get("submit_button", "").split(", ")
            submitted = False
            
            for selector in submit_selectors:
                if not selector.strip():
                    continue
                try:
                    submit_btn = target_page.locator(selector).first
                    if await submit_btn.is_visible(timeout=3000):
                        await submit_btn.click()
                        submitted = True
                        print(f"✓ Нажата кнопка submit: {selector}")
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        except:
                            await page.wait_for_load_state("load", timeout=5000)
                        break
                except Exception:
                    continue
            
            if not submitted:
                print("⚠️  Кнопка submit не найдена, пробуем Enter")
                try:
                    await password_input.press("Enter")
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        await page.wait_for_load_state("load", timeout=5000)
                except:
                    pass
            
            # Проверка на капчу
            captcha_detected = await self.detect_captcha(target_page)
            if captcha_detected:
                print("🔐 Обнаружена капча!")
                return "captcha"  # Возвращаем специальный статус
            
            # Проверка успешности логина
            current_url = page.url
            if "login" not in current_url.lower() or "dashboard" in current_url.lower() or "account" in current_url.lower():
                print("✓ Логин выполнен успешно")
                return True
            else:
                print("⚠️  Возможно, логин не выполнен. Продолжаем...")
                return True
                
        except Exception as e:
            print(f"❌ Ошибка при логине: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def navigate_to_cashier(self, page: Page, config: dict) -> Optional[str]:
        """Переход на страницу кэшира"""
        try:
            selectors = config.get("selectors", {})
            
            # Пробуем найти ссылку на кэшир
            cashier_selectors = (selectors.get("cashier_link", "") + ", " + 
                               selectors.get("cashier_button", "")).split(", ")
            
            for selector in cashier_selectors:
                if not selector.strip():
                    continue
                try:
                    cashier_element = page.locator(selector).first
                    if await cashier_element.is_visible(timeout=3000):
                        await cashier_element.click()
                        print(f"✓ Переход на кэшир: {selector}")
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        except:
                            await page.wait_for_load_state("load", timeout=5000)
                        return page.url
                except Exception:
                    continue
            
            # Если не нашли по селекторам, пробуем прямой переход
            current_url = page.url
            base_url = f"{urlparse(current_url).scheme}://{urlparse(current_url).netloc}"
            
            cashier_urls = [
                f"{base_url}/cashier",
                f"{base_url}/deposit",
                f"{base_url}/payment",
                f"{base_url}/payments",
            ]
            
            for cashier_url in cashier_urls:
                try:
                    await page.goto(cashier_url, wait_until="domcontentloaded", timeout=10000)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        await page.wait_for_load_state("load", timeout=5000)
                    if "cashier" in page.url.lower() or "deposit" in page.url.lower():
                        print(f"✓ Переход на кэшир через прямой URL: {cashier_url}")
                        return page.url
                except Exception:
                    continue
            
            print("⚠️  Не удалось найти кэшир. Продолжаем на текущей странице.")
            return page.url
            
        except Exception as e:
            print(f"❌ Ошибка при переходе на кэшир: {e}")
            return page.url
    
    async def click_make_deposit(self, page: Page, config: dict) -> bool:
        """Нажатие на кнопку 'Make Deposit'"""
        try:
            selectors = config.get("selectors", {})
            make_deposit_selectors = selectors.get("make_deposit_button", "").split(", ")
            
            # Пробуем CSS селекторы
            for selector in make_deposit_selectors:
                if not selector.strip():
                    continue
                try:
                    button = page.locator(selector).first
                    if await button.is_visible(timeout=3000):
                        await button.click()
                        print(f"✓ Нажата кнопка 'Make Deposit': {selector}")
                        await page.wait_for_timeout(3000)
                        return True
                except Exception:
                    continue
            
            # Пробуем XPath селекторы по тексту
            xpath_selectors = [
                "//button[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'MAKE A DEPOSIT')]",
                "//button[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'MAKE DEPOSIT')]",
                "//a[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'MAKE A DEPOSIT')]",
            ]
            
            for xpath in xpath_selectors:
                try:
                    button = page.locator(f"xpath={xpath}").first
                    if await button.is_visible(timeout=3000):
                        await button.click()
                        print(f"✓ Нажата кнопка 'Make Deposit' через XPath")
                        await page.wait_for_timeout(3000)
                        return True
                except Exception:
                    continue
            
            print("⚠️  Кнопка 'Make Deposit' не найдена. Продолжаем...")
            return False
            
        except Exception as e:
            print(f"⚠️  Ошибка при поиске кнопки 'Make Deposit': {e}")
            return False
    
    async def find_ewallets_providers(self, page: Page, config: dict) -> List[Dict]:
        """Поиск всех провайдеров в секции E-WALLETS"""
        providers = []
        
        try:
            # Ищем заголовок E-WALLETS
            header_xpaths = [
                "//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'E-WALLETS')]",
                "//*[contains(text(), 'E-WALLETS')]",
                "//*[contains(text(), 'E-Wallets')]",
            ]
            
            header = None
            for xpath in header_xpaths:
                try:
                    header = page.locator(f"xpath={xpath}").first
                    if await header.is_visible(timeout=2000):
                        print(f"✓ Найден заголовок E-WALLETS")
                        break
                except Exception:
                    continue
            
            if not header:
                print("⚠️  Заголовок E-WALLETS не найден. Ищем все провайдеры на странице.")
                return await self.find_all_providers(page, config)
            
            # Находим родительский контейнер секции
            try:
                section = header.locator("xpath=./ancestor::div[contains(@class, 'payment') or contains(@class, 'method') or contains(@class, 'section')][1]")
                if not await section.is_visible(timeout=1000):
                    section = header.locator("xpath=./ancestor::div[@class][1]")
            except:
                section = header.locator("xpath=./ancestor::div[@class][1]")
            
            # Ищем все кликабельные элементы в секции
            clickable_selectors = [
                "button",
                "a",
                "div[role='button']",
                "div[onclick]",
                "div[class*='payment']",
                "div[class*='provider']",
                "div[class*='method']",
            ]
            
            all_elements = []
            for selector in clickable_selectors:
                try:
                    elements = await section.locator(selector).all()
                    for elem in elements:
                        if elem not in all_elements:
                            all_elements.append(elem)
                except:
                    pass
            
            # Также ищем элементы с изображениями провайдеров
            try:
                images = await section.locator("img").all()
                for img in images:
                    try:
                        parent = img.locator("xpath=./ancestor::button[1] | ./ancestor::a[1] | ./ancestor::div[@onclick][1] | ./ancestor::div[contains(@class, 'payment')][1]").first
                        if parent not in all_elements:
                            all_elements.append(parent)
                    except:
                        pass
            except:
                pass
            
            print(f"Найдено кликабельных элементов в E-WALLETS: {len(all_elements)}")
            
            # Обрабатываем каждый элемент
            seen_texts = set()
            for elem in all_elements:
                try:
                    # Получаем текст элемента
                    elem_text = (await elem.inner_text()).strip().lower()[:100]
                    if not elem_text or elem_text in seen_texts:
                        continue
                    
                    # Пропускаем элементы, которые не являются провайдерами
                    if any(skip in elem_text for skip in ["all methods", "recommended", "count:", "payment systems", "e-wallets"]):
                        continue
                    
                    seen_texts.add(elem_text)
                    
                    # Получаем имя провайдера
                    provider_name = elem_text if elem_text else "unknown"
                    
                    providers.append({
                        "element": elem,
                        "name": provider_name,
                        "button_text": elem_text,
                    })
                    
                except Exception:
                    continue
            
            print(f"✓ Найдено провайдеров в E-WALLETS: {len(providers)}")
            return providers
            
        except Exception as e:
            print(f"❌ Ошибка при поиске провайдеров в E-WALLETS: {e}")
            import traceback
            traceback.print_exc()
            return await self.find_all_providers(page, config)
    
    async def find_all_providers(self, page: Page, config: dict) -> List[Dict]:
        """Поиск всех провайдеров на странице (fallback)"""
        providers = []
        selectors = config.get("selectors", {})
        
        provider_button_selectors = selectors.get("provider_buttons", "").split(", ")
        provider_link_selectors = selectors.get("provider_links", "").split(", ")
        
        all_selectors = provider_button_selectors + provider_link_selectors
        
        for selector in all_selectors:
            if not selector.strip():
                continue
            try:
                elements = await page.locator(selector).all()
                for elem in elements:
                    try:
                        elem_text = (await elem.inner_text()).strip()[:100]
                        if elem_text:
                            providers.append({
                                "element": elem,
                                "name": elem_text.lower(),
                                "button_text": elem_text,
                            })
                    except:
                        pass
            except:
                continue
        
        return providers
    
    async def process_provider_button(
        self, 
        page: Page, 
        provider_info: Dict, 
        merchant_domain: str,
        cashier_url: str,
        idx: int,
        total: int
    ) -> Optional[Dict]:
        """Обработка одной кнопки провайдера с перехватом popup, iframe, network"""
        elem = provider_info["element"]
        provider_name = provider_info.get("name", "unknown")
        button_text = provider_info.get("button_text", "")
        
        print(f"\n[{idx+1}/{total}] Обработка провайдера: {provider_name}")
        
        # Переменные для перехвата
        popup_page = None
        provider_frame = None
        entry_url = ""
        final_url = ""
        detected_in = "button_text"
        is_iframe = False
        network_requests = []
        
        # Обработчики событий
        async def on_popup(popup: Page):
            nonlocal popup_page
            popup_page = popup
            print(f"  → Открыт popup: {popup.url}")
        
        async def on_request(request):
            url = request.url
            if url.startswith(("http://", "https://")):
                req_domain = self.get_domain(url)
                merchant_domain_check = self.get_domain(page.url)
                # Если это внешний домен
                if req_domain and req_domain != merchant_domain_check and req_domain not in ["1xbet.com", "dafabet.com"]:
                    network_requests.append(url)
        
        async def on_framenavigated(frame: Frame):
            nonlocal provider_frame, entry_url, is_iframe
            if frame != page.main_frame and frame.url.startswith(("http://", "https://")):
                frame_domain = self.get_domain(frame.url)
                merchant_domain_check = self.get_domain(page.url)
                if frame_domain and frame_domain != merchant_domain_check:
                    provider_frame = frame
                    entry_url = frame.url
                    is_iframe = True
                    detected_in = "iframe src"
                    print(f"  → Найден iframe провайдера: {frame.url}")
        
        # Подписываемся на события
        page.once("popup", on_popup)
        page.on("request", on_request)
        page.on("framenavigated", on_framenavigated)
        
        try:
            # Скроллим к элементу
            await elem.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
            
            # Кликаем
            await elem.click(timeout=5000)
            print(f"  ✓ Клик по провайдеру: {provider_name}")
            
            # Ждём появления popup, iframe или навигации
            await page.wait_for_timeout(2000)
            
            # Если открылся popup
            if popup_page:
                try:
                    await popup_page.wait_for_load_state("domcontentloaded", timeout=7000)
                    final_url = popup_page.url
                    entry_url = final_url if not entry_url else entry_url
                    detected_in = "popup"
                    
                    # Проверяем iframe в popup
                    for frame in popup_page.frames:
                        if frame != popup_page.main_frame and frame.url.startswith(("http://", "https://")):
                            frame_domain = self.get_domain(frame.url)
                            merchant_domain_check = self.get_domain(popup_page.url)
                            if frame_domain and frame_domain != merchant_domain_check:
                                provider_frame = frame
                                entry_url = frame.url
                                final_url = frame.url
                                is_iframe = True
                                detected_in = "popup iframe"
                                break
                except Exception as e:
                    print(f"  ⚠️  Ошибка при обработке popup: {e}")
            
            # Если найден iframe
            elif provider_frame:
                final_url = provider_frame.url
                entry_url = entry_url if entry_url else final_url
            
            # Если навигация на главной странице
            else:
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    current_url = page.url
                    current_domain = self.get_domain(current_url)
                    merchant_domain_check = self.get_domain(cashier_url)
                    
                    if current_domain and current_domain != merchant_domain_check:
                        final_url = current_url
                        entry_url = entry_url if entry_url else final_url
                        detected_in = "navigation"
                except:
                    pass
            
            # Если не нашли URL через события, используем network requests
            if not final_url and network_requests:
                final_url = network_requests[0]
                entry_url = entry_url if entry_url else final_url
                detected_in = "network request"
            
            # Определяем домен провайдера
            if final_url:
                provider_domain = self.get_domain(final_url)
            else:
                # Если URL не найден, используем имя провайдера
                provider_domain = provider_name.replace(" ", "_").lower()[:50]
            
            # Проверяем на дубликаты
            if self.storage.provider_exists(merchant_domain, provider_domain):
                print(f"  ⏭️  Провайдер {provider_domain} уже в БД, пропускаем")
                return None
            
            # Делаем скриншот
            screenshot_filename = f"{merchant_domain}_{provider_domain}_{int(time.time())}.png"
            screenshot_path = os.path.join(self.screenshot_dir, screenshot_filename)
            
            try:
                if provider_frame:
                    # Скриншот iframe
                    await provider_frame.locator("body").screenshot(path=screenshot_path, timeout=5000)
                elif popup_page:
                    # Скриншот popup
                    await popup_page.screenshot(path=screenshot_path, full_page=False, timeout=5000)
                else:
                    # Скриншот главной страницы
                    await page.screenshot(path=screenshot_path, full_page=False, timeout=5000)
                
                print(f"  ✓ Скриншот сохранён: {screenshot_path}")
            except Exception as e:
                print(f"  ⚠️  Ошибка при создании скриншота: {e}")
                screenshot_path = ""
            
            # Определяем payment method
            payment_method = None
            provider_name_lower = provider_name.lower()
            if any(x in provider_name_lower for x in ["upi", "phonepe", "paytm", "gpay"]):
                payment_method = "UPI"
            elif any(x in provider_name_lower for x in ["card", "visa", "mastercard"]):
                payment_method = "Card"
            elif any(x in provider_name_lower for x in ["netbanking", "bank"]):
                payment_method = "NetBanking"
            elif any(x in provider_name_lower for x in ["wallet", "skrill", "neteller"]):
                payment_method = "Wallet"
            
            result = {
                "merchant_domain": merchant_domain,
                "provider_domain": provider_domain,
                "provider_name": provider_name,
                "provider_entry_url": entry_url,
                "final_url": final_url,
                "cashier_url": cashier_url,
                "screenshot_path": screenshot_path,
                "detected_in": detected_in,
                "payment_method": payment_method,
                "is_iframe": is_iframe,
                "button_text": button_text,
            }
            
            return result
            
        except Exception as e:
            print(f"  ❌ Ошибка при обработке провайдера: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        finally:
            # Закрываем popup если открыт
            if popup_page:
                try:
                    await popup_page.close()
                except:
                    pass
            
                # Возвращаемся на страницу депозита
            try:
                if page.url != cashier_url:
                    await page.goto(cashier_url, wait_until="domcontentloaded", timeout=10000)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        await page.wait_for_load_state("load", timeout=5000)
            except:
                pass
    
    async def parse_providers(self, merchant_id: str, merchant_url: str, config: dict) -> List[Dict]:
        """Основной метод парсинга провайдеров"""
        results = []
        merchant_domain = self.get_domain(merchant_url)
        account_type = config.get("account_type") or "player"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            
            # Пробуем загрузить сохранённый storageState
            storage_state_path = self.get_storage_state_path(merchant_id)
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            if os.path.exists(storage_state_path):
                try:
                    context_options["storage_state"] = storage_state_path
                    print(f"✓ Загружен сохранённый storageState: {storage_state_path}")
                except Exception as e:
                    print(f"⚠️  Не удалось загрузить storageState: {e}")
            
            context = await browser.new_context(**context_options)
            page = await context.new_page()
            
            try:
                # Шаг 1: Логин
                print("\n=== Шаг 1: Вход в систему ===")
                await page.goto(merchant_url, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_load_state("load", timeout=10000)
                except:
                    await page.wait_for_timeout(3000)
                
                login_result = await self.login(page, merchant_id, config)
                
                # Обработка капчи - human-in-the-loop
                if login_result == "captcha" or not login_result:
                    # Проверяем, действительно ли есть капча или просто не удалось залогиниться
                    captcha_detected = await self.detect_captcha(page)
                    if captcha_detected or not login_result:
                        # Запускаем human-in-the-loop
                        manual_login_success = await self.wait_for_manual_login(page, merchant_id, context)
                        if manual_login_success:
                            # Сохраняем storageState после успешного логина
                            await context.storage_state(path=storage_state_path)
                            print(f"✓ StorageState сохранён: {storage_state_path}")
                
                # Если логин успешен, сохраняем storageState
                if login_result is True:
                    await context.storage_state(path=storage_state_path)
                    print(f"✓ StorageState сохранён: {storage_state_path}")
                
                await page.wait_for_timeout(3000)
                
                # Шаг 2: Переход на кэшир
                print("\n=== Шаг 2: Переход на страницу депозита ===")
                cashier_url = await self.navigate_to_cashier(page, config)
                await page.wait_for_timeout(3000)
                
                # Шаг 3: Нажатие на кнопку "Make Deposit"
                print("\n=== Шаг 3: Нажатие на кнопку 'Make Deposit' ===")
                await self.click_make_deposit(page, config)
                await page.wait_for_timeout(3000)
                
                # Шаг 4: Поиск провайдеров в секции E-WALLETS
                print("\n=== Шаг 4: Поиск провайдеров в секции E-WALLETS ===")
                provider_elements = await self.find_ewallets_providers(page, config)
                print(f"Найдено провайдеров: {len(provider_elements)}")
                
                if not provider_elements:
                    print("⚠️  Провайдеры не найдены")
                    return results
                
                # Шаг 5: Обработка каждого провайдера
                print(f"\n=== Шаг 5: Обработка {len(provider_elements)} провайдеров ===")
                
                for idx, provider_info in enumerate(provider_elements):
                    result = await self.process_provider_button(
                        page, provider_info, merchant_domain, cashier_url, idx + 1, len(provider_elements)
                    )
                    
                    if result:
                        # Сохраняем в БД
                        saved = self.storage.save_provider(
                            merchant=merchant_id,
                            merchant_domain=merchant_domain,
                            provider_domain=result["provider_domain"],
                            account_type=account_type,
                            provider_name=result["provider_name"],
                            provider_entry_url=result["provider_entry_url"],
                            final_url=result["final_url"],
                            cashier_url=result["cashier_url"],
                            screenshot_path=result["screenshot_path"],
                            detected_in=result["detected_in"],
                            payment_method=result["payment_method"],
                            is_iframe=result["is_iframe"],
                        )
                        
                        if saved:
                            print(f"  ✓ Провайдер {result['provider_domain']} сохранён в БД")
                            results.append(result)
                    
                    await page.wait_for_timeout(2000)  # Пауза между провайдерами
                
            finally:
                await browser.close()
        
        return results
    
    async def parse_merchant(self, merchant_id: str, merchant_url: str, headless: bool = False):
        """Парсинг одного мерчанта"""
        if merchant_id not in MERCHANTS:
            print(f"❌ Мерчант {merchant_id} не найден в конфигурации")
            return
        
        config = MERCHANTS[merchant_id]
        self.headless = headless
        
        results = await self.parse_providers(merchant_id, merchant_url, config)
        print(f"\n✓ Парсинг завершён. Найдено провайдеров: {len(results)}")
        
        # Экспортируем в XLSX
        self.storage.export_to_xlsx()
        
        return results

