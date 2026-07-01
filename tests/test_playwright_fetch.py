from app.config import settings
from app.scraper.browser import BrowserFetchResult
from app.scraper.crawler import RealEstateCrawler


def test_crawler_fetch_uses_playwright_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "use_playwright", True)
    monkeypatch.setattr(settings, "playwright_headless", True)

    def fake_fetch(url, headers, timeout_seconds, headless):
        assert url == "https://example.com"
        assert headers["User-Agent"]
        assert headless is True
        return BrowserFetchResult("https://example.com/rendered", "text/html", b"<html>rendered</html>")

    monkeypatch.setattr("app.scraper.crawler.fetch_with_playwright", fake_fetch)

    final_url, content_type, body = RealEstateCrawler()._fetch("https://example.com")

    assert final_url == "https://example.com/rendered"
    assert content_type == "text/html"
    assert body == b"<html>rendered</html>"
