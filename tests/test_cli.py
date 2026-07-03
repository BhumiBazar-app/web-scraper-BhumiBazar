from app.models import CrawlResult
import scrape_to_txt


def test_cli_runs_crawler_with_url_and_prints_txt_output(monkeypatch, tmp_path, capsys):
    captured = {}

    class FakeCrawler:
        def __init__(self, data_root=None, max_pages=None):
            captured["data_root"] = data_root
            captured["max_pages"] = max_pages

        def crawl(self, url):
            captured["url"] = url
            return CrawlResult(
                website_id="example_com",
                builder_name="Example Builder",
                domain="example.com",
                crawl_id="crawl_001",
                started_at="2026-07-01T00:00:00+00:00",
                finished_at="2026-07-01T00:01:00+00:00",
                pages=[url],
                downloads=[],
                projects=[],
                output_path=tmp_path / "example_com",
            )

    monkeypatch.setattr(scrape_to_txt, "RealEstateCrawler", FakeCrawler)

    exit_code = scrape_to_txt.main(["https://example.com", "--data-root", str(tmp_path), "--max-pages", "3"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert captured == {"data_root": tmp_path, "max_pages": 3, "url": "https://example.com"}
    assert "TXT output:" in output


def test_cli_prompts_for_url_when_argument_is_missing(monkeypatch, tmp_path):
    class FakeCrawler:
        def __init__(self, data_root=None, max_pages=None):
            pass

        def crawl(self, url):
            return CrawlResult("example_com", "Example", "example.com", "crawl_001", "start", "finish", [url], [], [], tmp_path)

    monkeypatch.setattr(scrape_to_txt, "RealEstateCrawler", FakeCrawler)
    monkeypatch.setattr("builtins.input", lambda prompt: "https://example.com")

    assert scrape_to_txt.main([]) == 0
