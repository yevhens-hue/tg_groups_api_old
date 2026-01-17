# storage.py
# Хранение данных провайдеров в XLSX и SQLite

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict
from pathlib import Path
import pandas as pd
import tldextract


class Storage:
    def __init__(self, db_path: str = "providers_data.db", xlsx_path: str = "providers_data.xlsx"):
        self.db_path = db_path
        self.xlsx_path = xlsx_path
        self.init_database()

    def init_database(self):
        """Инициализация базы данных с расширенными полями"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant TEXT NOT NULL,
                merchant_domain TEXT NOT NULL,
                account_type TEXT,
                provider_domain TEXT NOT NULL,
                provider_name TEXT,
                provider_entry_url TEXT,
                final_url TEXT,
                cashier_url TEXT,
                screenshot_path TEXT,
                detected_in TEXT,
                payment_method TEXT,
                is_iframe INTEGER DEFAULT 0,
                requires_otp INTEGER DEFAULT 0,
                blocked_by_geo INTEGER DEFAULT 0,
                captcha_present INTEGER DEFAULT 0,
                timestamp_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(merchant_domain, provider_domain, account_type)
            )
        """)
        
        conn.commit()
        conn.close()

    def normalize_domain(self, url: str) -> str:
        """Нормализация домена (eTLD+1)"""
        if not url or not url.startswith(("http://", "https://")):
            return ""
        try:
            extracted = tldextract.extract(url)
            if extracted.domain and extracted.suffix:
                return f"{extracted.domain}.{extracted.suffix}".lower()
            return extracted.domain.lower() if extracted.domain else ""
        except Exception:
            return ""

    def save_provider(
        self,
        merchant: str,
        merchant_domain: str,
        provider_domain: str,
        account_type: Optional[str] = None,
        provider_name: Optional[str] = None,
        provider_entry_url: Optional[str] = None,
        final_url: Optional[str] = None,
        cashier_url: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        detected_in: Optional[str] = None,
        payment_method: Optional[str] = None,
        is_iframe: bool = False,
        requires_otp: bool = False,
        blocked_by_geo: bool = False,
        captcha_present: bool = False,
    ) -> bool:
        """Сохранение данных провайдера в БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO providers 
                (merchant, merchant_domain, account_type, provider_domain, provider_name,
                 provider_entry_url, final_url, cashier_url, screenshot_path, detected_in,
                 payment_method, is_iframe, requires_otp, blocked_by_geo, captcha_present,
                 timestamp_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                merchant, merchant_domain, account_type, provider_domain, provider_name,
                provider_entry_url, final_url, cashier_url, screenshot_path, detected_in,
                payment_method, int(is_iframe), int(requires_otp), int(blocked_by_geo), 
                int(captcha_present), datetime.now(timezone.utc).isoformat()
            ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка при сохранении в БД: {e}")
            return False
        finally:
            conn.close()

    def get_all_providers(self, merchant: Optional[str] = None) -> List[Dict]:
        """Получение всех записей о провайдерах"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if merchant:
            cursor.execute("""
                SELECT * FROM providers WHERE merchant = ? ORDER BY timestamp_utc DESC
            """, (merchant,))
        else:
            cursor.execute("SELECT * FROM providers ORDER BY timestamp_utc DESC")
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def export_to_xlsx(self, output_path: Optional[str] = None):
        """Экспорт данных в XLSX"""
        if output_path is None:
            output_path = self.xlsx_path
        
        rows = self.get_all_providers()
        if not rows:
            print("Нет данных для экспорта")
            return
        
        # Преобразуем в DataFrame
        df = pd.DataFrame(rows)
        
        # Удаляем служебные колонки
        df = df.drop(columns=['id'], errors='ignore')
        
        # Сохраняем в XLSX
        df.to_excel(output_path, index=False, engine='openpyxl')
        print(f"✓ Данные экспортированы в {output_path} ({len(rows)} записей)")

    def provider_exists(self, merchant_domain: str, provider_domain: str, account_type: Optional[str] = None) -> bool:
        """Проверка существования записи"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if account_type:
            cursor.execute("""
                SELECT COUNT(*) FROM providers 
                WHERE merchant_domain = ? AND provider_domain = ? AND account_type = ?
            """, (merchant_domain, provider_domain, account_type))
        else:
            cursor.execute("""
                SELECT COUNT(*) FROM providers 
                WHERE merchant_domain = ? AND provider_domain = ?
            """, (merchant_domain, provider_domain))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0



