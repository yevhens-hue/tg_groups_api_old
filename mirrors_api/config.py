# config.py

from __future__ import annotations

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ключ для Serper.dev
    SERPER_API_KEY: str

    # URL к базе данных (из .env: DATABASE_URL=...)
    DATABASE_URL: str = "sqlite:///./mirrors.db"

    # Окружение (development, staging, production)
    ENVIRONMENT: str = "development"

    # Keep-alive настройки
    KEEPALIVE_ENABLED: bool = False
    KEEPALIVE_INTERVAL: int = 60  # секунды
    KEEPALIVE_URL: str = "http://localhost:8011/health"

    # Логирование
    LOG_LEVEL: str = "INFO"

    # Server настройки
    HOST: str = "0.0.0.0"
    PORT: int = 8011
    WORKERS: int = 4

    # Google Sheets (опционально)
    GOOGLE_SHEETS_ACCESS_TOKEN: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """
        Удобное свойство, чтобы в коде можно было обращаться как
        settings.database_url, хотя поле называется DATABASE_URL.
        """
        return self.DATABASE_URL


_settings = Settings()


def get_settings() -> Settings:
    """
    Единая точка доступа к настройкам.
    """
    return _settings
