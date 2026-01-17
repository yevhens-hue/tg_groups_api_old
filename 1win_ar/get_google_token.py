#!/usr/bin/env python3
"""
Скрипт для получения OAuth2 access token для Google Sheets API.
Использует client_secret.json для авторизации.
"""
import json
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes для Google Sheets и Drive API
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

# Путь к файлу с credentials
CLIENT_SECRET_FILE = Path(__file__).parent / "client_secret.json"
TOKEN_FILE = Path(__file__).parent / "token.json"


def get_access_token():
    """
    Получить access token для Google Sheets API.
    Если token.json существует и валиден, использует его.
    Иначе запускает OAuth2 flow для получения нового токена.
    """
    creds = None
    
    # Проверяем, есть ли сохраненный токен
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE, 'r') as token:
                token_data = json.load(token)
                # Используем refresh token если есть
                from google.oauth2.credentials import Credentials
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        except Exception as e:
            print(f"⚠️  Ошибка при загрузке сохраненного токена: {e}")
            creds = None
    
    # Если нет валидных credentials, запускаем OAuth2 flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Обновляем токен
            print("🔄 Обновление access token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️  Ошибка при обновлении токена: {e}")
                creds = None
        
        if not creds:
            # Запускаем OAuth2 flow
            if not CLIENT_SECRET_FILE.exists():
                raise FileNotFoundError(
                    f"Файл {CLIENT_SECRET_FILE} не найден. "
                    "Убедитесь, что client_secret.json находится в директории проекта."
                )
            
            print("🔐 Запуск OAuth2 авторизации...")
            print("📋 Откроется браузер для авторизации.")
            print("   Пожалуйста, войдите в свой Google аккаунт и разрешите доступ к Google Sheets.")
            print()
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_FILE),
                SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Сохраняем токен для будущего использования
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        
        with open(TOKEN_FILE, 'w') as token:
            json.dump(token_data, token)
        
        print(f"✅ Токен сохранен в {TOKEN_FILE}")
    
    return creds.token


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Получение OAuth2 access token для Google Sheets API")
        print("=" * 60)
        print()
        
        access_token = get_access_token()
        
        print()
        print("✅ Access token получен успешно!")
        print()
        print("Используйте этот токен одним из способов:")
        print()
        print("1. Установите переменную окружения:")
        print(f"   export GOOGLE_SHEETS_ACCESS_TOKEN='{access_token}'")
        print()
        print("2. Или используйте токен напрямую в API запросах")
        print()
        print(f"Токен (первые 50 символов): {access_token[:50]}...")
        print()
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
