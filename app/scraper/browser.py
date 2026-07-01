from __future__ import annotations

from dataclasses import dataclass
import importlib.util


@dataclass(slots=True)
class BrowserFetchResult:
    final_url: str
    content_type: str
    body: bytes


class PlaywrightUnavailableError(RuntimeError):
    """Raised when Playwright is requested but not installed in the runtime."""


def fetch_with_playwright(url: str, headers: dict[str, str], timeout_seconds: int, headless: bool = True) -> BrowserFetchResult:
    """Fetch a URL through Playwright so JavaScript-heavy sites can render before parsing."""

    if importlib.util.find_spec("playwright") is None:
        raise PlaywrightUnavailableError("Playwright is not installed. Run `pip install -e .` and `playwright install chromium`.")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            context = browser.new_context(
                user_agent=headers.get("User-Agent"),
                extra_http_headers={key: value for key, value in headers.items() if key.lower() != "user-agent"},
                locale=_locale_from_accept_language(headers.get("Accept-Language", "en-IN")),
            )
            page = context.new_page()
            response = page.goto(url, wait_until="networkidle", timeout=timeout_seconds * 1000)
            if response is None:
                html = page.content().encode("utf-8")
                return BrowserFetchResult(page.url, "text/html", html)
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type:
                body = page.content().encode("utf-8")
            else:
                body = response.body()
            return BrowserFetchResult(page.url, content_type, body)
        finally:
            browser.close()


def _locale_from_accept_language(value: str) -> str:
    return value.split(",", 1)[0].strip() or "en-IN"
