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


def fetch_with_playwright(
    url: str,
    headers: dict[str, str],
    timeout_seconds: int,
    headless: bool = True,
    proxy: str | None = None,
    slow_mo_ms: int = 0,
) -> BrowserFetchResult:
    """Fetch a URL through Playwright with a realistic Chromium context."""

    if importlib.util.find_spec("playwright") is None:
        raise PlaywrightUnavailableError("Playwright is not installed. Run `pip install -e .` and `playwright install chromium`.")

    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

    launch_options = {
        "headless": headless,
        "slow_mo": slow_mo_ms,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-gpu",
            "--disable-infobars",
            "--no-default-browser-check",
            "--no-first-run",
            "--no-sandbox",
            "--start-maximized",
        ],
    }
    if proxy:
        launch_options["proxy"] = {"server": proxy}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_options)
        try:
            context = browser.new_context(
                user_agent=headers.get("User-Agent"),
                extra_http_headers=_browser_headers(headers),
                locale=_locale_from_accept_language(headers.get("Accept-Language", "en-IN")),
                timezone_id="Asia/Kolkata",
                viewport={"width": 1366, "height": 768},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                ignore_https_errors=True,
            )
            context.add_init_script(STEALTH_INIT_SCRIPT)
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_seconds * 1000, 15_000))
            except PlaywrightTimeoutError:
                pass
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


def _browser_headers(headers: dict[str, str]) -> dict[str, str]:
    enriched = {key: value for key, value in headers.items() if key.lower() != "user-agent"}
    enriched.setdefault("sec-ch-ua", '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"')
    enriched.setdefault("sec-ch-ua-mobile", "?0")
    enriched.setdefault("sec-ch-ua-platform", '"Windows"')
    enriched.setdefault("Sec-Fetch-Dest", "document")
    enriched.setdefault("Sec-Fetch-Mode", "navigate")
    enriched.setdefault("Sec-Fetch-Site", "none")
    enriched.setdefault("Sec-Fetch-User", "?1")
    return enriched


def _locale_from_accept_language(value: str) -> str:
    return value.split(",", 1)[0].strip() or "en-IN"


STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : originalQuery(parameters)
  );
}
"""
