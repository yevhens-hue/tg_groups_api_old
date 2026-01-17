# merchants_config.py

MERCHANTS = {
    "1xbet": {
        "brand": "1xbet",
        "brand_variants": ["1xbet", "1x bet", "1xBet"],
        "official_domains": [
            "1xbet.com",
            "1xbet.xyz",
            "1x-bet.com",
            "indian.1xbet.com",
        ],
        # Креденшиалы для входа
        "credentials": {
            "username": "314971373",
            "password": "ty24wwr3",
        },
        # Селекторы для логина
        "selectors": {
            "login_button": "a[href*='login'], button.login, .login-btn, .auth-button, [data-test='login-button']",
            "username_input": "input[name='login'], input[name='username'], input[name='phone'], input[type='text'][placeholder*='login'], input[placeholder*='Login'], input[placeholder*='phone'], input[placeholder*='Phone'], input[id*='login'], input[id*='username'], input[id*='phone'], input[class*='login'], input[class*='username']",
            "password_input": "input[name='password'], input[type='password'], input[id*='password'], input[class*='password']",
            "submit_button": "button[type='submit'], button.login-submit, .submit-btn, button[class*='submit'], button[class*='enter'], [data-test='submit-button']",
            # Навигация к кэширу
            "cashier_link": "a[href*='cashier'], a[href*='deposit'], a[href*='payment'], a[href*='payments'], .cashier, .deposit, [data-test='deposit'], [data-test='cashier']",
            "cashier_button": "button[class*='cashier'], button[class*='deposit'], button[class*='payment']",
            # Кнопка "Make Deposit" (CSS селекторы без :contains)
            "make_deposit_button": "[class*='make-deposit'], [class*='deposit-button'], button[class*='deposit']",
            # Секция E-WALLETS
            "ewallets_section": "[class*='e-wallet'], [class*='ewallet'], [class*='E-WALLET'], [class*='E-WALLETS'], [id*='ewallet'], [id*='e-wallet']",
            # Селекторы провайдеров на странице кэшира
            "provider_buttons": "button[class*='provider'], button[class*='payment'], .payment-method, .provider-item, [data-provider], [data-payment], img[alt*='payment'], img[alt*='Payment'], .payment-option, .payment-provider, [class*='payment-method'], [class*='provider']",
            "provider_links": "a[href*='provider'], a[class*='provider'], a[class*='payment'], .provider-link, a[data-provider], a[data-payment]",
        },
        # Тип аккаунта: admin/agent/player/merchant-ops
        "account_type": "player",
    },

    "dafabet": {
        "brand": "dafabet",
        "brand_variants": ["dafabet", "dafa bet"],
        "official_domains": [
            "dafabet.com",
            "dafabet.net"
        ],
        "credentials": {
            "username": "",  # Заполнить при необходимости
            "password": "",  # Заполнить при необходимости
        },
        "selectors": {
            "login_button": "a[href*='login'], button.login, .login-btn",
            "username_input": "input[name='username'], input[name='login'], input[type='text'][placeholder*='username']",
            "password_input": "input[name='password'], input[type='password']",
            "submit_button": "button[type='submit'], button.login-submit, .submit-btn",
            "cashier_link": "a[href*='cashier'], a[href*='deposit'], a[href*='payment'], .cashier, .deposit",
            "cashier_button": "button[class*='cashier'], button[class*='deposit']",
            "provider_buttons": "button[class*='provider'], .payment-method, .provider-item, [data-provider]",
            "provider_links": "a[href*='provider'], a[class*='provider'], .provider-link",
        },
        "account_type": "player",
    }
}

