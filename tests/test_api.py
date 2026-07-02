from pathlib import Path

from fastapi.testclient import TestClient

from app.api import app
from app.models import CrawlResult


def test_crawl_api_reports_blocked_status_with_non_success_http_code(monkeypatch, tmp_path: Path):
    def fake_crawl(self, url: str):
        return CrawlResult(
            website_id="blocked_builder_com",
            builder_name="Blocked Builder",
            domain="blocked-builder.com",
            crawl_id="crawl_001",
            started_at="2026-07-01T00:00:00+00:00",
            finished_at="2026-07-01T00:01:00+00:00",
            pages=[],
            downloads=[],
            projects=[],
            output_path=tmp_path,
            status="blocked",
            errors=[{"url": url, "error_type": "FetchAccessBlockedError", "blocked": "true"}],
        )

    monkeypatch.setattr("app.api.RealEstateCrawler.crawl", fake_crawl)

    response = TestClient(app).post("/crawl", json={"url": "https://blocked-builder.com"})

    assert response.status_code == 502
    payload = response.json()
    assert payload["status"] == "blocked"
    assert payload["blocked"] is True
    assert payload["total_errors"] == 1
