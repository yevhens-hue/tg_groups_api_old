# provider_parser.py

import time
import os
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from database import Database
from merchants_config import MERCHANTS


class ProviderParser:
    def __init__(self, headless: bool = False, screenshot_dir: str = "screenshots"):
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        self.db = Database()
        self.driver = None
        
        # Создаём директорию для скриншотов
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
    def init_driver(self):
        """Инициализация Selenium WebDriver"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--window-size=1920,1080")
        
        # User agent для имитации реального браузера
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)
        
    def close_driver(self):
        """Закрытие браузера"""
        if self.driver:
            self.driver.quit()
            
    def get_domain(self, url: str) -> str:
        """Извлечение домена из URL"""
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    
    def login(self, merchant_id: str, merchant_url: str, config: dict) -> bool:
        """Логин на сайт мерчанта"""
        try:
            print(f"Переход на {merchant_url}")
            self.driver.get(merchant_url)
            time.sleep(3)
            
            credentials = config.get("credentials", {})
            username = credentials.get("username", "")
            password = credentials.get("password", "")
            
            if not username or not password:
                print(f"⚠️  Креденшиалы не указаны для {merchant_id}. Пропускаем логин.")
                return False
            
            selectors = config.get("selectors", {})
            
            # Поиск и клик по кнопке логина
            login_selectors = selectors.get("login_button", "").split(", ")
            login_clicked = False
            
            for selector in login_selectors:
                try:
                    login_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    login_btn.click()
                    login_clicked = True
                    print(f"✓ Нажата кнопка логина: {selector}")
                    time.sleep(2)
                    break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            if not login_clicked:
                print("⚠️  Кнопка логина не найдена. Возможно, уже на странице логина.")
            
            # Ввод username - пробуем разные стратегии
            username_selectors = selectors.get("username_input", "").split(", ")
            username_entered = False
            
            # Сначала пробуем CSS селекторы
            for selector in username_selectors:
                if not selector.strip():
                    continue
                try:
                    username_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    username_input.clear()
                    username_input.send_keys(username)
                    username_entered = True
                    print(f"✓ Введён username: {selector}")
                    time.sleep(1)
                    break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            # Если не нашли через CSS, пробуем XPath
            if not username_entered:
                xpath_selectors = [
                    "//input[@type='text']",
                    "//input[contains(@placeholder, 'login') or contains(@placeholder, 'Login') or contains(@placeholder, 'phone') or contains(@placeholder, 'Phone')]",
                    "//input[contains(@class, 'login') or contains(@class, 'username') or contains(@class, 'phone')]",
                    "//input[@id and (contains(@id, 'login') or contains(@id, 'username') or contains(@id, 'phone'))]",
                ]
                for xpath in xpath_selectors:
                    try:
                        username_input = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, xpath))
                        )
                        username_input.clear()
                        username_input.send_keys(username)
                        username_entered = True
                        print(f"✓ Введён username через XPath: {xpath}")
                        time.sleep(1)
                        break
                    except (TimeoutException, NoSuchElementException):
                        continue
            
            if not username_entered:
                print("❌ Поле username не найдено")
                return False
            
            # Ввод password
            password_selectors = selectors.get("password_input", "").split(", ")
            password_entered = False
            
            # Сначала пробуем CSS селекторы
            for selector in password_selectors:
                if not selector.strip():
                    continue
                try:
                    password_input = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    password_input.clear()
                    password_input.send_keys(password)
                    password_entered = True
                    print(f"✓ Введён password: {selector}")
                    time.sleep(1)
                    break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            # Если не нашли через CSS, пробуем XPath
            if not password_entered:
                xpath_selectors = [
                    "//input[@type='password']",
                    "//input[contains(@name, 'password')]",
                    "//input[contains(@id, 'password')]",
                    "//input[contains(@class, 'password')]",
                    "//input[@name='password']",
                ]
                for xpath in xpath_selectors:
                    try:
                        password_input = WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, xpath))
                        )
                        password_input.clear()
                        password_input.send_keys(password)
                        password_entered = True
                        print(f"✓ Введён password через XPath: {xpath}")
                        time.sleep(1)
                        break
                    except (TimeoutException, NoSuchElementException):
                        continue
            
            if not password_entered:
                print("❌ Поле password не найдено")
                return False
            
            # Нажатие кнопки submit
            submit_selectors = selectors.get("submit_button", "").split(", ")
            submitted = False
            
            for selector in submit_selectors:
                try:
                    submit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    submit_btn.click()
                    submitted = True
                    print(f"✓ Нажата кнопка submit: {selector}")
                    time.sleep(5)  # Ждём загрузки после логина
                    break
                except NoSuchElementException:
                    continue
            
            if not submitted:
                print("⚠️  Кнопка submit не найдена, пробуем Enter")
                password_input.send_keys("\n")
                time.sleep(5)
            
            # Проверка успешности логина (можно улучшить)
            current_url = self.driver.current_url
            if "login" not in current_url.lower() or "dashboard" in current_url.lower() or "account" in current_url.lower():
                print("✓ Логин выполнен успешно")
                return True
            else:
                print("⚠️  Возможно, логин не выполнен. Продолжаем...")
                return True  # Продолжаем в любом случае
                
        except Exception as e:
            print(f"❌ Ошибка при логине: {e}")
            return False
    
    def navigate_to_cashier(self, config: dict) -> bool:
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
                    cashier_element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    cashier_element.click()
                    print(f"✓ Переход на кэшир: {selector}")
                    time.sleep(5)  # Ждём загрузки страницы кэшира
                    return True
                except (TimeoutException, NoSuchElementException):
                    continue
            
            # Если не нашли по селекторам, пробуем прямой переход
            current_url = self.driver.current_url
            base_url = f"{urlparse(current_url).scheme}://{urlparse(current_url).netloc}"
            
            cashier_urls = [
                f"{base_url}/cashier",
                f"{base_url}/deposit",
                f"{base_url}/payment",
                f"{base_url}/payments",
            ]
            
            for cashier_url in cashier_urls:
                try:
                    self.driver.get(cashier_url)
                    time.sleep(3)
                    if "cashier" in self.driver.current_url.lower() or "deposit" in self.driver.current_url.lower():
                        print(f"✓ Переход на кэшир через прямой URL: {cashier_url}")
                        return True
                except Exception:
                    continue
            
            print("⚠️  Не удалось найти кэшир. Продолжаем на текущей странице.")
            return False
            
        except Exception as e:
            print(f"❌ Ошибка при переходе на кэшир: {e}")
            return False
    
    def click_make_deposit(self, config: dict) -> bool:
        """Нажатие на кнопку 'Make Deposit'"""
        try:
            selectors = config.get("selectors", {})
            make_deposit_selectors = selectors.get("make_deposit_button", "").split(", ")
            
            # Также пробуем найти по тексту
            xpath_selectors = [
                "//button[contains(text(), 'Make Deposit')]",
                "//button[contains(text(), 'MAKE A DEPOSIT')]",
                "//button[contains(., 'Make Deposit')]",
                "//button[contains(., 'MAKE A DEPOSIT')]",
                "//a[contains(text(), 'Make Deposit')]",
                "//a[contains(text(), 'MAKE A DEPOSIT')]",
            ]
            
            # Пробуем CSS селекторы
            for selector in make_deposit_selectors:
                if not selector.strip():
                    continue
                try:
                    button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    button.click()
                    print(f"✓ Нажата кнопка 'Make Deposit': {selector}")
                    time.sleep(3)
                    return True
                except (TimeoutException, NoSuchElementException):
                    continue
            
            # Пробуем XPath селекторы
            for xpath in xpath_selectors:
                try:
                    button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    button.click()
                    print(f"✓ Нажата кнопка 'Make Deposit' через XPath: {xpath}")
                    time.sleep(3)
                    return True
                except (TimeoutException, NoSuchElementException):
                    continue
            
            print("⚠️  Кнопка 'Make Deposit' не найдена. Продолжаем...")
            return False
            
        except Exception as e:
            print(f"⚠️  Ошибка при поиске кнопки 'Make Deposit': {e}")
            return False
    
    def find_ewallets_providers(self, config: dict) -> list:
        """Поиск всех провайдеров в секции E-WALLETS"""
        providers = []
        selectors = config.get("selectors", {})
        
        try:
            # Ищем секцию E-WALLETS
            ewallets_section_selectors = selectors.get("ewallets_section", "").split(", ")
            section = None
            
            # Пробуем найти секцию по селекторам
            for selector in ewallets_section_selectors:
                if not selector.strip():
                    continue
                try:
                    section = self.driver.find_element(By.CSS_SELECTOR, selector)
                    print(f"✓ Найдена секция E-WALLETS: {selector}")
                    break
                except NoSuchElementException:
                    continue
            
            # Если не нашли по селекторам, ищем по тексту
            if not section:
                xpath_selectors = [
                    "//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'E-WALLETS')]",
                    "//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'E-WALLET')]",
                    "//*[contains(text(), 'E-WALLETS')]",
                    "//*[contains(text(), 'E-WALLET')]",
                    "//*[contains(text(), 'E-Wallets')]",
                    "//*[contains(text(), 'E-Wallet')]",
                    "//*[contains(@class, 'e-wallet')]",
                    "//*[contains(@class, 'E-WALLET')]",
                    "//*[contains(@id, 'e-wallet')]",
                    "//*[contains(@id, 'ewallet')]",
                ]
                
                for xpath in xpath_selectors:
                    try:
                        header = self.driver.find_element(By.XPATH, xpath)
                        # Находим родительский контейнер секции - ищем ближайший div/section
                        try:
                            section = header.find_element(By.XPATH, "./ancestor::div[contains(@class, 'payment') or contains(@class, 'method') or contains(@class, 'section')][1]")
                        except:
                            try:
                                section = header.find_element(By.XPATH, "./ancestor::section[1]")
                            except:
                                try:
                                    section = header.find_element(By.XPATH, "./ancestor::div[@class][1]")
                                except:
                                    # Если не нашли родителя, используем следующий sibling или родительский div
                                    section = header.find_element(By.XPATH, "./following-sibling::div[1] | ./parent::div[1]")
                        
                        print(f"✓ Найдена секция E-WALLETS через XPath: {xpath}")
                        break
                    except (NoSuchElementException, Exception) as e:
                        continue
            
            if not section:
                print("⚠️  Секция E-WALLETS не найдена. Ищем все провайдеры на странице.")
                return self.find_provider_elements(config)
            
            # Ищем все кликабельные элементы внутри секции E-WALLETS
            # Сначала пробуем найти все элементы, которые могут быть провайдерами
            clickable_elements = []
            
            # Ищем кнопки, ссылки, div'ы с провайдерами
            try:
                clickable_elements = section.find_elements(By.CSS_SELECTOR, 
                    "button, a, div[onclick], div[class*='payment'], div[class*='provider'], div[class*='method'], [data-provider], [data-payment], [role='button']")
            except:
                pass
            
            # Также ищем элементы с изображениями провайдеров (логотипы)
            try:
                images = section.find_elements(By.TAG_NAME, "img")
                for img in images:
                    try:
                        # Находим родительский кликабельный элемент
                        parent_xpaths = [
                            "./ancestor::button[1]",
                            "./ancestor::a[1]",
                            "./ancestor::div[@onclick][1]",
                            "./ancestor::div[contains(@class, 'payment')][1]",
                            "./ancestor::div[contains(@class, 'method')][1]",
                            "./ancestor::div[contains(@class, 'provider')][1]",
                            "./parent::div[1]",
                            "./parent::button[1]",
                        ]
                        for xpath in parent_xpaths:
                            try:
                                parent = img.find_element(By.XPATH, xpath)
                                if parent not in clickable_elements:
                                    clickable_elements.append(parent)
                                break
                            except:
                                continue
                    except:
                        pass
            except:
                pass
            
            # Если не нашли в секции, ищем все элементы на странице после заголовка E-WALLETS
            if len(clickable_elements) == 0:
                try:
                    # Находим заголовок E-WALLETS и берём все элементы после него до следующего заголовка
                    header = self.driver.find_element(By.XPATH, "//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'E-WALLETS')]")
                    # Находим все элементы после заголовка
                    following_elements = self.driver.find_elements(By.XPATH, 
                        "//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'E-WALLETS')]/following::*[self::button or self::a or self::div[@onclick] or self::div[contains(@class, 'payment')]]")
                    clickable_elements = following_elements[:20]  # Ограничиваем до 20 элементов
                except:
                    pass
            
            print(f"Найдено кликабельных элементов в E-WALLETS: {len(clickable_elements)}")
            
            # Обрабатываем каждый элемент
            seen_texts = set()
            for elem in clickable_elements:
                try:
                    # Получаем текст элемента для идентификации
                    elem_text = elem.text.strip().lower()
                    if not elem_text or elem_text in seen_texts:
                        continue
                    
                    # Пропускаем элементы, которые не являются провайдерами
                    if any(skip in elem_text for skip in ["all methods", "recommended", "count:", "payment systems"]):
                        continue
                    
                    seen_texts.add(elem_text)
                    
                    # Получаем URL или определяем, что это провайдер
                    provider_url = None
                    provider_name = elem_text
                    
                    if elem.tag_name == "a":
                        provider_url = elem.get_attribute("href")
                    elif elem.tag_name == "button" or elem.tag_name == "div":
                        provider_url = (elem.get_attribute("data-url") or 
                                      elem.get_attribute("data-href") or
                                      elem.get_attribute("onclick"))
                    
                    # Если URL не найден, это может быть кнопка, которая открывает форму
                    # В этом случае provider_url будет None, но мы всё равно обработаем элемент
                    
                    providers.append({
                        "element": elem,
                        "url": provider_url,
                        "name": provider_name,
                        "selector": "ewallets-section"
                    })
                    
                except Exception as e:
                    continue
            
            print(f"✓ Найдено провайдеров в E-WALLETS: {len(providers)}")
            return providers
            
        except Exception as e:
            print(f"❌ Ошибка при поиске провайдеров в E-WALLETS: {e}")
            # Fallback на обычный поиск
            return self.find_provider_elements(config)
    
    def find_provider_elements(self, config: dict) -> list:
        """Поиск элементов провайдеров на странице"""
        providers = []
        selectors = config.get("selectors", {})
        seen_urls = set()  # Для избежания дубликатов
        
        # Ищем кнопки провайдеров
        provider_button_selectors = selectors.get("provider_buttons", "").split(", ")
        provider_link_selectors = selectors.get("provider_links", "").split(", ")
        
        all_selectors = provider_button_selectors + provider_link_selectors
        
        for selector in all_selectors:
            if not selector.strip():
                continue
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    try:
                        # Получаем URL провайдера
                        provider_url = None
                        if elem.tag_name == "a":
                            provider_url = elem.get_attribute("href")
                        elif elem.tag_name == "button" or elem.tag_name == "div" or elem.tag_name == "img":
                            # Пробуем найти data-атрибуты или родительскую ссылку
                            provider_url = (elem.get_attribute("data-url") or 
                                          elem.get_attribute("data-href") or
                                          elem.get_attribute("data-link") or
                                          elem.get_attribute("onclick"))
                            
                            # Если не нашли, ищем родительскую ссылку
                            if not provider_url:
                                try:
                                    parent_link = elem.find_element(By.XPATH, "./ancestor::a[1]")
                                    if parent_link:
                                        provider_url = parent_link.get_attribute("href")
                                except:
                                    pass
                        
                        # Если это изображение, пробуем найти родительский кликабельный элемент
                        if elem.tag_name == "img" and not provider_url:
                            try:
                                parent = elem.find_element(By.XPATH, "./ancestor::a[1] | ./ancestor::button[1] | ./ancestor::div[@onclick][1]")
                                if parent:
                                    provider_url = (parent.get_attribute("href") or 
                                                  parent.get_attribute("data-url") or
                                                  parent.get_attribute("onclick"))
                            except:
                                pass
                        
                        if provider_url and provider_url not in seen_urls:
                            # Очищаем URL от javascript: и других протоколов
                            if provider_url.startswith("javascript:"):
                                continue
                            if provider_url.startswith(("http://", "https://")):
                                seen_urls.add(provider_url)
                                providers.append({
                                    "element": elem,
                                    "url": provider_url,
                                    "selector": selector
                                })
                    except Exception:
                        continue
            except NoSuchElementException:
                continue
        
        # Если не нашли через селекторы, ищем все кликабельные элементы с упоминанием payment/provider
        if not providers:
            try:
                # Ищем все ссылки
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                for link in all_links:
                    href = link.get_attribute("href") or ""
                    text = link.text.lower()
                    alt_text = link.get_attribute("alt") or ""
                    title_text = link.get_attribute("title") or ""
                    
                    if href and href.startswith(("http://", "https://")):
                        # Проверяем, не является ли это внешним доменом провайдера
                        link_domain = self.get_domain(href)
                        merchant_domain = self.get_domain(self.driver.current_url)
                        
                        # Если это внешний домен и не мерчант - возможно провайдер
                        if link_domain != merchant_domain and link_domain not in ["1xbet.com", "dafabet.com"]:
                            if any(keyword in href.lower() or keyword in text or keyword in alt_text or keyword in title_text 
                                  for keyword in ["payment", "gateway", "method", "upi", "paytm", "phonepe", "gpay", 
                                                 "razorpay", "payu", "ccavenue", "instamojo", "cashfree"]):
                                if href not in seen_urls:
                                    seen_urls.add(href)
                                    providers.append({
                                        "element": link,
                                        "url": href,
                                        "selector": "auto-detected-link"
                                    })
                
                # Ищем кнопки и div'ы с текстом провайдеров
                clickable_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    "button, div[onclick], div[class*='payment'], div[class*='provider'], div[data-provider]")
                
                for elem in clickable_elements:
                    text = elem.text.lower()
                    onclick = elem.get_attribute("onclick") or ""
                    data_url = elem.get_attribute("data-url") or elem.get_attribute("data-href") or ""
                    
                    if any(keyword in text or keyword in onclick or keyword in data_url
                          for keyword in ["upi", "paytm", "phonepe", "gpay", "razorpay", "payu", "ccavenue", 
                                         "instamojo", "cashfree", "payment", "deposit"]):
                        # Пробуем найти URL в onclick или data-атрибутах
                        provider_url = data_url
                        if not provider_url and onclick:
                            # Извлекаем URL из onclick
                            import re
                            url_match = re.search(r'https?://[^\s\'"]+', onclick)
                            if url_match:
                                provider_url = url_match.group(0)
                        
                        if provider_url and provider_url.startswith(("http://", "https://")) and provider_url not in seen_urls:
                            seen_urls.add(provider_url)
                            providers.append({
                                "element": elem,
                                "url": provider_url,
                                "selector": "auto-detected-button"
                            })
            except Exception as e:
                print(f"⚠️  Ошибка при автоопределении провайдеров: {e}")
        
        return providers
    
    def take_screenshot(self, merchant_domain: str, provider_domain: str) -> str:
        """Создание скриншота текущей страницы"""
        try:
            filename = f"{merchant_domain}_{provider_domain}_{int(time.time())}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            self.driver.save_screenshot(filepath)
            print(f"✓ Скриншот сохранён: {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ Ошибка при создании скриншота: {e}")
            return ""
    
    def parse_providers(self, merchant_id: str, merchant_url: str, config: dict) -> list:
        """Основной метод парсинга провайдеров"""
        results = []
        merchant_domain = self.get_domain(merchant_url)
        
        try:
            # Шаг 1: Логин
            print("\n=== Шаг 1: Вход в систему ===")
            self.login(merchant_id, merchant_url, config)
            time.sleep(3)
            
            # Шаг 2: Переход на кэшир (Deposit)
            print("\n=== Шаг 2: Переход на страницу депозита ===")
            self.navigate_to_cashier(config)
            time.sleep(3)
            
            # Шаг 3: Нажатие на кнопку "Make Deposit"
            print("\n=== Шаг 3: Нажатие на кнопку 'Make Deposit' ===")
            self.click_make_deposit(config)
            time.sleep(3)
            
            # Шаг 4: Поиск провайдеров в секции E-WALLETS
            print("\n=== Шаг 4: Поиск провайдеров в секции E-WALLETS ===")
            provider_elements = self.find_ewallets_providers(config)
            print(f"Найдено элементов провайдеров в E-WALLETS: {len(provider_elements)}")
            
            if not provider_elements:
                print("⚠️  Провайдеры не найдены в секции E-WALLETS. Пробуем общий поиск...")
                provider_elements = self.find_provider_elements(config)
                print(f"Найдено элементов провайдеров (общий поиск): {len(provider_elements)}")
            
            if not provider_elements:
                print("⚠️  Провайдеры не найдены на странице")
                return results
            
            # Шаг 5: Обработка каждого провайдера из E-WALLETS
            print(f"\n=== Шаг 5: Обработка {len(provider_elements)} провайдеров ===")
            
            # Сохраняем текущий URL для возврата
            deposit_page_url = self.driver.current_url
            
            for idx, provider_info in enumerate(provider_elements):
                try:
                    elem = provider_info["element"]
                    provider_url = provider_info.get("url")
                    provider_name = provider_info.get("name", "unknown")
                    
                    print(f"\n[{idx+1}/{len(provider_elements)}] Обработка провайдера: {provider_name}")
                    
                    # Определяем домен провайдера
                    if provider_url and provider_url.startswith(("http://", "https://")):
                        provider_domain = self.get_domain(provider_url)
                    else:
                        # Если URL нет, используем имя провайдера как идентификатор
                        provider_domain = provider_name.replace(" ", "_").lower()[:50]
                    
                    # Проверяем, не обрабатывали ли уже этот провайдер
                    if self.db.provider_exists(merchant_domain, provider_domain):
                        print(f"⏭️  Провайдер {provider_domain} уже в БД, пропускаем")
                        continue
                    
                    # Кликаем на элемент провайдера
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                        time.sleep(1)
                        elem.click()
                        print(f"✓ Клик по провайдеру: {provider_name}")
                        time.sleep(5)  # Ждём загрузки формы провайдера
                    except Exception as e:
                        print(f"⚠️  Не удалось кликнуть на элемент: {e}")
                        # Пробуем через JavaScript
                        try:
                            self.driver.execute_script("arguments[0].click();", elem)
                            time.sleep(5)
                        except:
                            print(f"❌ Не удалось кликнуть через JavaScript")
                            continue
                    
                    # Определяем тип аккаунта
                    account_type = config.get("account_type") or "standard"
                    
                    # Получаем текущий URL (может быть форма провайдера или iframe)
                    current_url = self.driver.current_url
                    
                    # Делаем скриншот платёжной формы
                    screenshot_path = self.take_screenshot(merchant_domain, provider_domain)
                    
                    # Сохраняем в БД
                    saved = self.db.save_provider(
                        merchant_id=merchant_id,
                        merchant_domain=merchant_domain,
                        provider_domain=provider_domain,
                        provider_url=current_url,
                        account_type=account_type,
                        screenshot_path=screenshot_path
                    )
                    
                    if saved:
                        print(f"✓ Провайдер {provider_domain} сохранён в БД")
                        results.append({
                            "merchant_domain": merchant_domain,
                            "provider_domain": provider_domain,
                            "provider_url": current_url,
                            "account_type": account_type,
                            "screenshot_path": screenshot_path,
                            "provider_name": provider_name
                        })
                    
                    # Возвращаемся на страницу депозита
                    try:
                        if deposit_page_url != current_url:
                            self.driver.back()
                            time.sleep(3)
                        else:
                            # Если URL не изменился, возможно форма открылась в модальном окне
                            # Пробуем закрыть модальное окно или вернуться на страницу депозита
                            self.driver.get(deposit_page_url)
                            time.sleep(3)
                    except Exception as e:
                        print(f"⚠️  Ошибка при возврате на страницу депозита: {e}")
                        # Пробуем прямой переход
                        self.driver.get(deposit_page_url)
                        time.sleep(3)
                    
                except Exception as e:
                    print(f"❌ Ошибка при обработке провайдера: {e}")
                    import traceback
                    traceback.print_exc()
                    # Пробуем вернуться на страницу депозита
                    try:
                        self.driver.get(deposit_page_url)
                        time.sleep(3)
                    except:
                        pass
                    continue
            
            return results
            
        except Exception as e:
            print(f"❌ Критическая ошибка при парсинге: {e}")
            import traceback
            traceback.print_exc()
            return results
    
    def parse_merchant(self, merchant_id: str, merchant_url: str, headless: bool = False):
        """Парсинг одного мерчанта"""
        if merchant_id not in MERCHANTS:
            print(f"❌ Мерчант {merchant_id} не найден в конфигурации")
            return
        
        config = MERCHANTS[merchant_id]
        self.headless = headless
        
        try:
            self.init_driver()
            results = self.parse_providers(merchant_id, merchant_url, config)
            print(f"\n✓ Парсинг завершён. Найдено провайдеров: {len(results)}")
            return results
        finally:
            self.close_driver()

