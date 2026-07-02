from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
from urllib.parse import urlparse


@dataclass(slots=True)
class BrowserFetchResult:
    final_url: str
    content_type: str
    body: bytes
    status_code: int | None = None
    response_headers: dict[str, str] = field(default_factory=dict)
    failure_reason: str | None = None
    rendering_error: str | None = None


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
    """Fetch a URL through a real Playwright browser page with browser-like headers.

    The browser context, not urllib/httpx, performs navigation. This lets the
    target site set cookies, run JavaScript, and see Chromium navigation headers
    before the scraper reads the rendered DOM.
    """

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
            "--disable-web-security",
            "--no-default-browser-check",
            "--no-first-run",
            "--no-sandbox",
            "--start-maximized",
            "--window-size=1366,768",
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
                screen={"width": 1366, "height": 768},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                ignore_https_errors=True,
                java_script_enabled=True,
            )
            context.add_init_script(STEALTH_INIT_SCRIPT)
            page = context.new_page()
            page.set_default_navigation_timeout(timeout_seconds * 1000)
            _warm_up_origin(page, url, timeout_seconds)
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_seconds * 1000, 15_000))
            except PlaywrightTimeoutError:
                pass
            _human_like_scroll(page)

            final_url = page.url
            status_code = response.status if response else None
            response_headers = dict(response.headers) if response else {}
            content_type = response_headers.get("content-type", "text/html; charset=utf-8")
            if "text/html" in content_type or not content_type:
                body = page.content().encode("utf-8")
            else:
                body = response.body() if response else b""
            return BrowserFetchResult(
                final_url=final_url,
                content_type=content_type,
                body=body,
                status_code=status_code,
                response_headers=response_headers,
                failure_reason=_detect_failure_reason(status_code, body, content_type),
            )
        finally:
            browser.close()


def _warm_up_origin(page: object, url: str, timeout_seconds: int) -> None:
    parsed = urlparse(url)
    if parsed.path in {"", "/"}:
        return
    origin = f"{parsed.scheme}://{parsed.netloc}/"
    try:
        page.goto(origin, wait_until="domcontentloaded", timeout=min(timeout_seconds * 1000, 10_000))
        page.wait_for_timeout(750)
    except Exception:
        # Warm-up is best-effort. The real target navigation below is authoritative.
        return


def _human_like_scroll(page: object) -> None:
    for pixels in (450, 900, 1350):
        try:
            page.mouse.wheel(0, pixels)
            page.wait_for_timeout(350)
        except Exception:
            return


def _browser_headers(headers: dict[str, str]) -> dict[str, str]:
    excluded = {"user-agent", "connection", "host", "content-length", "accept-encoding"}
    enriched = {key: value for key, value in headers.items() if key.lower() not in excluded}
    enriched.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8")
    enriched.setdefault("Accept-Language", headers.get("Accept-Language", "en-IN,en;q=0.9"))
    enriched.setdefault("sec-ch-ua", '"Chromium";v="126", "Google Chrome";v="126", "Not-A.Brand";v="99"')
    enriched.setdefault("sec-ch-ua-mobile", "?0")
    enriched.setdefault("sec-ch-ua-platform", '"Windows"')
    enriched.setdefault("Sec-Fetch-Dest", "document")
    enriched.setdefault("Sec-Fetch-Mode", "navigate")
    enriched.setdefault("Sec-Fetch-Site", "none")
    enriched.setdefault("Sec-Fetch-User", "?1")
    enriched.setdefault("Upgrade-Insecure-Requests", "1")
    return enriched


def _locale_from_accept_language(value: str) -> str:
    return value.split(",", 1)[0].strip() or "en-IN"


def _detect_failure_reason(status_code: int | None, body: bytes, content_type: str) -> str | None:
    if status_code in {401, 403, 407, 451}:
        return "access_blocked"
    if status_code == 429:
        return "rate_limited"
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


STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
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
