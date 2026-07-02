from __future__ import annotations

import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    BaseSettings = object
    SettingsConfigDict = None


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseSettings):
    """Runtime configuration for the scraper service."""

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_prefix="BHUMI_", env_file=".env", extra="ignore")

    data_root: Path = Path(os.getenv("BHUMI_DATA_ROOT", "SCRAPED_DATA"))
    request_timeout_seconds: int = _env_int("BHUMI_REQUEST_TIMEOUT_SECONDS", 30)
    max_pages_per_crawl: int = _env_int("BHUMI_MAX_PAGES_PER_CRAWL", 500)
    user_agent: str = os.getenv("BHUMI_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36 BhumiAIRealEstateScraper/1.0")
    accept_language: str = os.getenv("BHUMI_ACCEPT_LANGUAGE", "en-IN,en;q=0.9")
    request_referer: str = os.getenv("BHUMI_REQUEST_REFERER", "https://www.google.com/")
    max_pagination_pages: int = _env_int("BHUMI_MAX_PAGINATION_PAGES", 25)
    request_delay_seconds: float = _env_float("BHUMI_REQUEST_DELAY_SECONDS", 1.0)
    fetch_retry_count: int = _env_int("BHUMI_FETCH_RETRY_COUNT", 2)
    fetch_retry_backoff_seconds: float = _env_float("BHUMI_FETCH_RETRY_BACKOFF_SECONDS", 0.75)
    max_concurrent_requests_per_domain: int = _env_int("BHUMI_MAX_CONCURRENT_REQUESTS_PER_DOMAIN", 1)
    enable_browser_rendering: bool = _env_bool("BHUMI_ENABLE_BROWSER_RENDERING", True)
    browser_timeout_seconds: int = _env_int("BHUMI_BROWSER_TIMEOUT_SECONDS", 30)
    render_min_html_chars: int = _env_int("BHUMI_RENDER_MIN_HTML_CHARS", 800)
    render_script_threshold: int = _env_int("BHUMI_RENDER_SCRIPT_THRESHOLD", 8)
    lazy_load_scroll_steps: int = _env_int("BHUMI_LAZY_LOAD_SCROLL_STEPS", 3)
    lazy_load_scroll_pixels: int = _env_int("BHUMI_LAZY_LOAD_SCROLL_PIXELS", 1200)
    lazy_load_scroll_delay_ms: int = _env_int("BHUMI_LAZY_LOAD_SCROLL_DELAY_MS", 750)
    respect_robots_txt: bool = _env_bool("BHUMI_RESPECT_ROBOTS_TXT", True)

    max_pagination_pages: int = int(os.getenv("BHUMI_MAX_PAGINATION_PAGES", "25")
    use_playwright: bool = os.getenv("BHUMI_USE_PLAYWRIGHT", "true").lower() in {"1", "true", "yes", "on"}
    playwright_headless: bool = os.getenv("BHUMI_PLAYWRIGHT_HEADLESS", "true").lower() in {"1", "true", "yes", "on"}
    playwright_proxy: str | None = os.getenv("BHUMI_PLAYWRIGHT_PROXY")
    playwright_slow_mo_ms: int = int(os.getenv("BHUMI_PLAYWRIGHT_SLOW_MO_MS", "0"))

    storage_backend: str = os.getenv("BHUMI_STORAGE_BACKEND", "filesystem")
    google_sheets_spreadsheet_id: str | None = os.getenv("BHUMI_GOOGLE_SHEETS_SPREADSHEET_ID")
    google_service_account_json: str | None = os.getenv("BHUMI_GOOGLE_SERVICE_ACCOUNT_JSON")
    database_url: str = os.getenv("BHUMI_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/bhumi_scraper")
    redis_url: str = os.getenv("BHUMI_REDIS_URL", "redis://localhost:6379/0")


settings = Settings()
