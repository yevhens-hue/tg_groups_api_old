#!/usr/bin/env python3
"""
Утилита для получения Google OAuth2 access token из client_secret файла.
Использует google-auth-oauthlib для получения токена.
"""

import os
import sys
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes для Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Путь к credentials файлу
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"


def get_access_token():
    """
    Получить access token используя OAuth2 flow.
    
    Returns:
        Access token (str) или None если не удалось получить
    """
    if not CREDENTIALS_FILE.exists():
        print(f"❌ Файл credentials не найден: {CREDENTIALS_FILE}")
        print(f"   Поместите client_secret файл в: {CREDENTIALS_FILE}")
        return None
    
    # Проверяем, есть ли сохраненный токен
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, 'r') as f:
                token_data = json.load(f)
                access_token = token_data.get('access_token')
                if access_token:
                    print(f"✅ Использован сохраненный токен из {TOKEN_FILE}")
                    return access_token
        except Exception as e:
            print(f"⚠️  Ошибка чтения сохраненного токена: {e}")
    
    # Запускаем OAuth flow
    try:
        print(f"🔐 Запускаю OAuth2 flow...")
        print(f"   Credentials файл: {CREDENTIALS_FILE}")
        print(f"   Scopes: {', '.join(SCOPES)}")
        print(f"\n📝 Браузер откроется автоматически для авторизации...")
        print(f"   (если не откроется, откройте ссылку вручную)")
        
        flow = InstalledAppFlow.from_client_secrets_file(
            str(CREDENTIALS_FILE),
            SCOPES
        )
        
        # Запускаем локальный сервер для получения кода
        creds = flow.run_local_server(port=0, open_browser=True)
        
        # Сохраняем токен для повторного использования
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes,
        }
        
        # Также сохраняем access_token отдельно для удобства
        token_data['access_token'] = creds.token
        
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        print(f"\n✅ Токен получен и сохранен в {TOKEN_FILE}")
        print(f"📋 Access Token: {creds.token[:50]}...")
        print(f"\n💡 Теперь можно использовать:")
        print(f"   export GOOGLE_SHEETS_ACCESS_TOKEN='{creds.token}'")
        print(f"   или указать в .env файле:")
        print(f"   GOOGLE_SHEETS_ACCESS_TOKEN={creds.token}")
        
        return creds.token
        
    except Exception as e:
        print(f"❌ Ошибка при получении токена: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("=" * 70)
    print("🔐 ПОЛУЧЕНИЕ GOOGLE OAUTH2 ACCESS TOKEN")
    print("=" * 70)
    print()
    
    token = get_access_token()
    
    if token:
        print()
        print("=" * 70)
        print("✅ УСПЕШНО ПОЛУЧЕН ACCESS TOKEN")
        print("=" * 70)
        sys.exit(0)
    else:
        print()
        print("=" * 70)
        print("❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ ACCESS TOKEN")
        print("=" * 70)
        sys.exit(1)
