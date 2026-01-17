# database.py

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path


class Database:
    def __init__(self, db_path: str = "providers_data.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Инициализация базы данных и создание таблицы"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id TEXT NOT NULL,
                merchant_domain TEXT NOT NULL,
                account_type TEXT,
                provider_domain TEXT NOT NULL,
                provider_url TEXT,
                screenshot_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(merchant_domain, provider_domain)
            )
        """)
        
        conn.commit()
        conn.close()

    def save_provider(
        self,
        merchant_id: str,
        merchant_domain: str,
        provider_domain: str,
        provider_url: str,
        account_type: Optional[str] = None,
        screenshot_path: Optional[str] = None
    ) -> bool:
        """Сохранение данных провайдера в БД"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO providers 
                (merchant_id, merchant_domain, account_type, provider_domain, provider_url, screenshot_path)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (merchant_id, merchant_domain, account_type, provider_domain, provider_url, screenshot_path))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка при сохранении в БД: {e}")
            return False
        finally:
            conn.close()

    def get_all_providers(self, merchant_id: Optional[str] = None) -> List[Dict]:
        """Получение всех записей о провайдерах"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if merchant_id:
            cursor.execute("""
                SELECT * FROM providers WHERE merchant_id = ? ORDER BY created_at DESC
            """, (merchant_id,))
        else:
            cursor.execute("SELECT * FROM providers ORDER BY created_at DESC")
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def provider_exists(self, merchant_domain: str, provider_domain: str) -> bool:
        """Проверка существования записи"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM providers 
            WHERE merchant_domain = ? AND provider_domain = ?
        """, (merchant_domain, provider_domain))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0



