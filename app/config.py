from __future__ import annotations

import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    BaseSettings = object
    SettingsConfigDict = None


class Settings(BaseSettings):
    """Runtime configuration for the scraper service."""

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_prefix="BHUMI_", env_file=".env", extra="ignore")

    data_root: Path = Path(os.getenv("BHUMI_DATA_ROOT", "SCRAPED_DATA"))
    request_timeout_seconds: int = int(os.getenv("BHUMI_REQUEST_TIMEOUT_SECONDS", "30"))
    max_pages_per_crawl: int = int(os.getenv("BHUMI_MAX_PAGES_PER_CRAWL", "500"))
    user_agent: str = os.getenv("BHUMI_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 BhumiAIRealEstateScraper/1.0")
    accept_language: str = os.getenv("BHUMI_ACCEPT_LANGUAGE", "en-IN,en;q=0.9")
    request_referer: str = os.getenv("BHUMI_REQUEST_REFERER", "https://www.google.com/")
    max_pagination_pages: int = int(os.getenv("BHUMI_MAX_PAGINATION_PAGES", "25"))
    storage_backend: str = os.getenv("BHUMI_STORAGE_BACKEND", "filesystem")
    google_sheets_spreadsheet_id: str | None = os.getenv("BHUMI_GOOGLE_SHEETS_SPREADSHEET_ID")
    google_service_account_json: str | None = os.getenv("BHUMI_GOOGLE_SERVICE_ACCOUNT_JSON")
    database_url: str = os.getenv("BHUMI_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/bhumi_scraper")
    redis_url: str = os.getenv("BHUMI_REDIS_URL", "redis://localhost:6379/0")


settings = Settings()
