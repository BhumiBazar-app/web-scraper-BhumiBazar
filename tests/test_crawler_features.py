from pathlib import Path

from app.scraper.crawler import RealEstateCrawler
from app.scraper.google_sheets import sync_crawl_to_google_sheets
from app.models import CrawlResult, ProjectRecord


class DummyLink:
    def __init__(self, href: str, text: str = "", rel: str = "", css_class: str = "") -> None:
        self.values = {"rel": rel, "class": css_class}
        self.href = href
        self.text = text

    def get(self, key: str, default=None):
        if key == "href":
            return self.href
        return self.values.get(key, default)

    def get_text(self, separator: str = " ", strip: bool = False) -> str:
        return self.text.strip() if strip else self.text


def test_request_headers_are_browser_like():
    headers = RealEstateCrawler()._request_headers("https://example.com")

    assert "Mozilla/5.0" in headers["User-Agent"]
    assert "text/html" in headers["Accept"]
    assert headers["Accept-Language"]
    assert headers["Referer"].startswith("https://")


def test_pagination_detection_and_candidate_generation():
    crawler = RealEstateCrawler()

    assert crawler._is_pagination_link(DummyLink("/projects?page=2", text="Next"), "https://example.com/projects?page=2")
    assert crawler._pagination_candidates("https://example.com/projects?page=2&city=goa") == [
        "https://example.com/projects?page=3&city=goa"
    ]
    assert crawler._pagination_candidates("https://example.com/projects") == []


def test_google_sheets_writes_pending_payload_when_not_configured(tmp_path: Path):
    result = CrawlResult(
        website_id="example_com",
        builder_name="Example Builder",
        domain="example.com",
        crawl_id="crawl_001",
        started_at="2026-07-01T00:00:00+00:00",
        finished_at="2026-07-01T00:01:00+00:00",
        pages=["https://example.com"],
        downloads=[],
        projects=[ProjectRecord(project_name="Example Project", city="Gurgaon")],
        output_path=tmp_path,
    )

    status = sync_crawl_to_google_sheets(result)

    assert status["status"] == "not_configured"
    assert (tmp_path / "google_sheets_pending.json").exists()


def test_google_sheets_only_download_metadata_does_not_write_file(tmp_path: Path):
    crawler = RealEstateCrawler(data_root=tmp_path)

    asset = crawler._store_download(None, "https://example.com/brochure.pdf", "https://example.com", b"pdf", "brochure")

    assert asset.path == ""
    assert asset.content_hash
    assert not any(tmp_path.iterdir())


def test_google_sheets_can_skip_local_pending_file(tmp_path: Path):
    result = CrawlResult(
        website_id="example_com",
        builder_name="Example Builder",
        domain="example.com",
        crawl_id="crawl_001",
        started_at="2026-07-01T00:00:00+00:00",
        finished_at="2026-07-01T00:01:00+00:00",
        pages=["https://example.com"],
        downloads=[],
        projects=[],
        output_path=tmp_path,
    )

    status = sync_crawl_to_google_sheets(result, write_pending=False)

    assert status["status"] == "not_configured"
    assert not (tmp_path / "google_sheets_pending.json").exists()


def test_placeholder_google_sheet_id_is_treated_as_not_configured(tmp_path: Path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "google_sheets_spreadsheet_id", "your-spreadsheet-id")
    monkeypatch.setattr(settings, "google_service_account_json", '{"client_email":"agent@example.com"}')
    result = CrawlResult(
        website_id="example_com",
        builder_name="Example Builder",
        domain="example.com",
        crawl_id="crawl_001",
        started_at="2026-07-01T00:00:00+00:00",
        finished_at="2026-07-01T00:01:00+00:00",
        pages=[],
        downloads=[],
        projects=[],
        output_path=tmp_path,
    )

    status = sync_crawl_to_google_sheets(result, write_pending=False)

    assert status["status"] == "not_configured"


def test_seed_fetch_errors_return_failed_crawl_instead_of_raising(tmp_path: Path, monkeypatch):
    crawler = RealEstateCrawler(data_root=tmp_path, max_pages=1)

    def fail_fetch(url: str):
        raise OSError("network unreachable")

    monkeypatch.setattr(crawler, "_fetch", fail_fetch)

    result = crawler.crawl("https://builderwebsite.com")

    assert result.status == "failed"
    assert result.pages == []
    error_logs = list((tmp_path / "builderwebsite_com" / "logs").glob("*_errors.json"))
    assert error_logs
    assert "OSError" in error_logs[0].read_text(encoding="utf-8")


def test_download_fetch_errors_do_not_fail_entire_crawl(tmp_path: Path, monkeypatch):
    crawler = RealEstateCrawler(data_root=tmp_path, max_pages=1)

    def fake_fetch(url: str):
        if url.endswith("brochure.pdf"):
            raise OSError("download blocked")
        return (
            url,
            "text/html; charset=utf-8",
            b'<html><head><title>Builder</title></head><body><a href="/brochure.pdf">Brochure</a></body></html>',
        )

    monkeypatch.setattr(crawler, "_fetch", fake_fetch)

    result = crawler.crawl("https://builderwebsite.com")

    assert result.status == "completed"
    assert result.pages == ["https://builderwebsite.com"]
    assert result.downloads == []
    error_logs = list((tmp_path / "builderwebsite_com" / "logs").glob("*_errors.json"))
    assert error_logs
    assert "download blocked" in error_logs[0].read_text(encoding="utf-8")
