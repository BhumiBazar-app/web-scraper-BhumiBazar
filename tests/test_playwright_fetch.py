from app.config import settings
from app.scraper.browser import BrowserFetchResult
from app.scraper.crawler import RealEstateCrawler


def test_crawler_fetch_uses_playwright_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "use_playwright", True)
    monkeypatch.setattr(settings, "playwright_headless", True)

    def fake_fetch(url, headers, timeout_seconds, headless, proxy, slow_mo_ms):
        assert url == "https://example.com"
        assert headers["User-Agent"]
        assert headless is True
        assert proxy is None
        assert slow_mo_ms == 0
        return BrowserFetchResult("https://example.com/rendered", "text/html", b"<html>rendered</html>")

    monkeypatch.setattr("app.scraper.scrapy_playwright_fetcher.ScrapyPlaywrightFetcher._ensure_scrapy_available", lambda self: None)
    monkeypatch.setattr("app.scraper.scrapy_playwright_fetcher.ScrapyPlaywrightFetcher._scrapy_normalized_body", lambda self, body, content_type: body)
    monkeypatch.setattr("app.scraper.scrapy_playwright_fetcher.fetch_with_playwright", fake_fetch)

    final_url, content_type, body = RealEstateCrawler()._fetch("https://example.com")

    assert final_url == "https://example.com/rendered"
    assert content_type == "text/html"
    assert body == b"<html>rendered</html>"


def test_crawler_treats_playwright_access_block_as_blocked(monkeypatch):
    monkeypatch.setattr(settings, "use_playwright", True)

    def fake_fetch(url, headers, timeout_seconds, headless, proxy, slow_mo_ms):
        return BrowserFetchResult(
            "https://example.com/blocked",
            "text/html",
            b"<html>Forbidden</html>",
            status_code=403,
            failure_reason="access_blocked",
        )

    monkeypatch.setattr("app.scraper.scrapy_playwright_fetcher.ScrapyPlaywrightFetcher._ensure_scrapy_available", lambda self: None)
    monkeypatch.setattr("app.scraper.scrapy_playwright_fetcher.ScrapyPlaywrightFetcher._scrapy_normalized_body", lambda self, body, content_type: body)
    monkeypatch.setattr("app.scraper.scrapy_playwright_fetcher.fetch_with_playwright", fake_fetch)

    try:
        RealEstateCrawler()._fetch("https://example.com")
    except Exception as exc:
        assert RealEstateCrawler().fetcher._is_access_blocked_error(exc)
    else:
        raise AssertionError("Expected blocked Playwright response to raise")
