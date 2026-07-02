import gzip
from urllib.error import HTTPError

from app.config import settings
from app.scraper.fetcher import FetchAccessBlockedError, FetchResult, PageFetcher, RobotsDisallowedError


def test_fetcher_decodes_gzip_response_body():
    fetcher = PageFetcher()
    body = gzip.compress(b"<html><body>Rendered</body></html>")

    assert fetcher._decode_body(body, "gzip") == b"<html><body>Rendered</body></html>"


def test_fetcher_marks_access_blocks_without_retrying(monkeypatch):
    fetcher = PageFetcher()
    calls = []
    monkeypatch.setattr(settings, "fetch_retry_count", 3)

    def blocked(url: str, retry_attempts: int):
        calls.append(retry_attempts)
        raise FetchAccessBlockedError("Access blocked by the website or current network")

    monkeypatch.setattr(fetcher, "_fetch_http", blocked)

    try:
        fetcher._fetch_http_with_retries("https://example.com")
    except FetchAccessBlockedError:
        pass

    assert calls == [0]


def test_fetcher_detects_http_403_as_access_block():
    fetcher = PageFetcher()
    error = HTTPError("https://example.com", 403, "Forbidden", hdrs=None, fp=None)

    assert fetcher._is_access_blocked_error(error)


def test_fetcher_detects_javascript_heavy_pages_for_rendering(monkeypatch):
    fetcher = PageFetcher()
    monkeypatch.setattr(settings, "render_script_threshold", 2)
    body = b'<html><body><div id="root"></div><script></script><script></script></body></html>'
    result = FetchResult("https://example.com", "https://example.com", "text/html", body, 200)

    assert fetcher._should_render(result)


def test_robots_disallowed_is_not_retryable(monkeypatch):
    fetcher = PageFetcher()
    calls = []
    monkeypatch.setattr(settings, "fetch_retry_count", 2)

    def disallowed(url: str, retry_attempts: int):
        calls.append(retry_attempts)
        raise RobotsDisallowedError("robots.txt disallows crawling this URL")

    monkeypatch.setattr(fetcher, "_fetch_http", disallowed)

    try:
        fetcher._fetch_http_with_retries("https://example.com/private")
    except RobotsDisallowedError:
        pass

    assert calls == [0]
