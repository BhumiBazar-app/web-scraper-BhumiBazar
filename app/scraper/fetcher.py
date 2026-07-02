from __future__ import annotations

import gzip
import importlib.util
import time
import zlib
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener
from urllib.robotparser import RobotFileParser

from app.config import settings


class FetchAccessBlockedError(RuntimeError):
    """Raised when the remote site or network blocks crawler access."""


class RobotsDisallowedError(RuntimeError):
    """Raised when robots.txt disallows crawling a URL."""


@dataclass(slots=True)
class FetchResult:
    url: str
    final_url: str
    content_type: str
    body: bytes
    status_code: int | None
    redirect_chain: list[str] = field(default_factory=list)
    response_time_seconds: float = 0.0
    retry_attempts: int = 0
    rendered: bool = False
    rendering_error: str | None = None
    failure_reason: str | None = None


class PageFetcher:
    """Fetch pages with a polite HTTP session and optional JS rendering fallback."""

    def __init__(self) -> None:
        self.cookie_jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar))
        self._last_request_at_by_domain: dict[str, float] = {}
        self._robots_cache: dict[str, RobotFileParser] = {}

    def fetch(self, url: str) -> FetchResult:
        self._respect_robots(url)
        result = self._fetch_http_with_retries(url)
        if self._should_render(result):
            rendered = self._fetch_with_browser(url)
            if rendered is not None:
                return rendered
        return result

    def _fetch_http_with_retries(self, url: str) -> FetchResult:
        attempts = max(settings.fetch_retry_count, 0) + 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            if attempt:
                time.sleep(settings.fetch_retry_backoff_seconds * (2 ** (attempt - 1)))
            try:
                return self._fetch_http(url, attempt)
            except Exception as exc:
                last_exc = exc
                if isinstance(exc, (FetchAccessBlockedError, RobotsDisallowedError)) or not self._is_retryable(exc):
                    raise
        assert last_exc is not None
        raise last_exc

    def _fetch_http(self, url: str, retry_attempts: int) -> FetchResult:
        self._wait_for_domain(url)
        request = Request(url, headers=self.request_headers(url))
        start = time.monotonic()
        try:
            with self.opener.open(request, timeout=settings.request_timeout_seconds) as response:
                raw_body = response.read()
                body = self._decode_body(raw_body, response.headers.get("content-encoding", ""))
                final_url = response.geturl()
                return FetchResult(
                    url=url,
                    final_url=final_url,
                    content_type=response.headers.get("content-type", ""),
                    body=body,
                    status_code=getattr(response, "status", None) or response.getcode(),
                    redirect_chain=[] if final_url == url else [url, final_url],
                    response_time_seconds=time.monotonic() - start,
                    retry_attempts=retry_attempts,
                    failure_reason=self._detect_failure_reason(body, response.headers.get("content-type", "")),
                )
        except HTTPError as exc:
            if self._is_access_blocked_error(exc):
                raise FetchAccessBlockedError("Access blocked by the website or current network") from exc
            raise
        except URLError as exc:
            if self._is_access_blocked_error(exc):
                raise FetchAccessBlockedError("Access blocked by the website or current network") from exc
            raise

    def _fetch_with_browser(self, url: str) -> FetchResult | None:
        if not settings.enable_browser_rendering or importlib.util.find_spec("playwright") is None:
            return None
        from playwright.sync_api import sync_playwright

        start = time.monotonic()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(user_agent=settings.user_agent, locale=settings.accept_language.split(",")[0])
                page = context.new_page()
                response = page.goto(url, wait_until="domcontentloaded", timeout=settings.browser_timeout_seconds * 1000)
                page.wait_for_load_state("networkidle", timeout=settings.browser_timeout_seconds * 1000)
                for _ in range(settings.lazy_load_scroll_steps):
                    page.mouse.wheel(0, settings.lazy_load_scroll_pixels)
                    page.wait_for_timeout(settings.lazy_load_scroll_delay_ms)
                html = page.content().encode("utf-8")
                final_url = page.url
                status_code = response.status if response else None
                browser.close()
                return FetchResult(
                    url=url,
                    final_url=final_url,
                    content_type="text/html; charset=utf-8",
                    body=html,
                    status_code=status_code,
                    redirect_chain=[] if final_url == url else [url, final_url],
                    response_time_seconds=time.monotonic() - start,
                    rendered=True,
                    failure_reason=self._detect_failure_reason(html, "text/html"),
                )
        except Exception as exc:
            return FetchResult(
                url=url,
                final_url=url,
                content_type="",
                body=b"",
                status_code=None,
                response_time_seconds=time.monotonic() - start,
                rendered=True,
                rendering_error=str(exc),
                failure_reason="rendering_error",
            )

    def _respect_robots(self, url: str) -> None:
        if not settings.respect_robots_txt:
            return
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._robots_cache.get(base_url)
        if parser is None:
            parser = RobotFileParser()
            parser.set_url(f"{base_url}/robots.txt")
            try:
                parser.read()
            except Exception:
                return
            self._robots_cache[base_url] = parser
        if not parser.can_fetch(settings.user_agent, url):
            raise RobotsDisallowedError("robots.txt disallows crawling this URL")

    def _wait_for_domain(self, url: str) -> None:
        delay = max(settings.request_delay_seconds, 0.0)
        if delay == 0:
            return
        domain = urlparse(url).netloc
        now = time.monotonic()
        last_request_at = self._last_request_at_by_domain.get(domain)
        if last_request_at is not None:
            sleep_for = delay - (now - last_request_at)
            if sleep_for > 0:
                time.sleep(sleep_for)
        self._last_request_at_by_domain[domain] = time.monotonic()

    def _should_render(self, result: FetchResult) -> bool:
        if result.failure_reason in {"captcha", "access_blocked", "rate_limited"}:
            return False
        if "text/html" not in result.content_type:
            return False
        html = result.body.decode("utf-8", errors="ignore").lower()
        if len(html.strip()) < settings.render_min_html_chars:
            return True
        app_markers = ("id=\"__next\"", "id=\"root\"", "data-reactroot", "window.__initial_state__")
        return any(marker in html for marker in app_markers) and html.count("<script") >= settings.render_script_threshold

    def _detect_failure_reason(self, body: bytes, content_type: str) -> str | None:
        if "text/html" not in content_type and content_type:
            return None
        text = body[:10000].decode("utf-8", errors="ignore").lower()
        if "captcha" in text or "recaptcha" in text or "hcaptcha" in text:
            return "captcha"
        if "too many requests" in text or "rate limit" in text:
            return "rate_limited"
        if "access denied" in text or "forbidden" in text:
            return "access_blocked"
        return None

    def _decode_body(self, body: bytes, content_encoding: str) -> bytes:
        encoding = content_encoding.lower()
        if "gzip" in encoding:
            return gzip.decompress(body)
        if "deflate" in encoding:
            return zlib.decompress(body)
        return body

    def _is_retryable(self, exc: Exception) -> bool:
        if isinstance(exc, HTTPError):
            return exc.code in {408, 425, 429, 500, 502, 503, 504}
        return isinstance(exc, (TimeoutError, URLError))

    def _is_access_blocked_error(self, exc: Exception) -> bool:
        if isinstance(exc, FetchAccessBlockedError):
            return True
        if isinstance(exc, HTTPError) and exc.code in {401, 403, 407, 451}:
            return True
        message = str(exc).lower()
        return "403" in message or "forbidden" in message or "tunnel connection failed" in message

    def request_headers(self, url: str) -> dict[str, str]:
        return {
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": settings.accept_language,
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": settings.request_referer,
            "Connection": "keep-alive",
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
