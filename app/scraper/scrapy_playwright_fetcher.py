from __future__ import annotations

import importlib.util
import time
from urllib.error import HTTPError
from urllib.parse import urlparse

from app.config import settings
from app.scraper.browser import PlaywrightUnavailableError, fetch_with_playwright
from app.scraper.fetcher import FetchAccessBlockedError, FetchResult


class ScrapyPlaywrightFetcher:
    """Fetch pages through Playwright and normalize HTML with Scrapy selectors.

    This fetcher intentionally avoids urllib/httpx network scraping. Playwright is
    responsible for browser navigation; Scrapy is used as the scraping/parsing
    layer for the rendered response body.
    """

    def fetch(self, url: str) -> FetchResult:
        self._ensure_scrapy_available()
        start = time.monotonic()
        browser_result = fetch_with_playwright(
            url,
            self.request_headers(url),
            settings.request_timeout_seconds,
            settings.playwright_headless,
            settings.playwright_proxy,
            settings.playwright_slow_mo_ms,
        )
        body = self._scrapy_normalized_body(browser_result.body, browser_result.content_type)
        result = FetchResult(
            url=url,
            final_url=browser_result.final_url,
            content_type=browser_result.content_type,
            body=body,
            status_code=browser_result.status_code,
            redirect_chain=[] if browser_result.final_url == url else [url, browser_result.final_url],
            response_time_seconds=time.monotonic() - start,
            rendered=True,
            rendering_error=browser_result.rendering_error,
            failure_reason=browser_result.failure_reason,
        )
        if result.failure_reason == "access_blocked":
            raise FetchAccessBlockedError("Access blocked by the website or current network")
        return result

    def _ensure_scrapy_available(self) -> None:
        if importlib.util.find_spec("scrapy") is None:
            raise PlaywrightUnavailableError("Scrapy is not installed. Run `pip install -e .` with project dependencies.")

    def _scrapy_normalized_body(self, body: bytes, content_type: str) -> bytes:
        if "text/html" not in content_type:
            return body
        from scrapy import Selector

        html = body.decode("utf-8", errors="replace")
        return (Selector(text=html).get() or html).encode("utf-8")

    def _is_access_blocked_error(self, exc: Exception) -> bool:
        if isinstance(exc, FetchAccessBlockedError):
            return True
        if isinstance(exc, HTTPError) and exc.code in {401, 403, 407, 451}:
            return True
        message = str(exc).lower()
        return "403" in message or "forbidden" in message or "tunnel connection failed" in message or "access blocked" in message

    def request_headers(self, url: str) -> dict[str, str]:
        return {
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": settings.accept_language,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self._referer_for(url),
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "sec-ch-ua": '"Chromium";v="126", "Google Chrome";v="126", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

    def _referer_for(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/"
        return settings.request_referer
