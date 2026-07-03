from app.models import CrawlResult, DownloadedAsset, ProjectRecord
from app.scraper.storage import persist_result, write_crawl_txt
from app.scraper.utils import domain_slug, slugify


def test_slugify_normalizes_project_names():
    assert slugify("Skyline Residency - Phase 1") == "skyline_residency_phase_1"


def test_domain_slug_removes_www_and_protocol():
    assert domain_slug("https://www.builder-example.com/projects") == "builder_example_com"


def test_write_crawl_txt_exports_complete_human_readable_summary(tmp_path):
    result = CrawlResult(
        website_id="example_com",
        builder_name="Example Builder",
        domain="example.com",
        crawl_id="crawl_001",
        started_at="2026-07-01T00:00:00+00:00",
        finished_at="2026-07-01T00:01:00+00:00",
        pages=["https://example.com/project"],
        downloads=[
            DownloadedAsset(
                "https://example.com/brochure.pdf",
                "https://example.com/project",
                "downloads/brochure.pdf",
                "brochures",
            )
        ],
        projects=[
            ProjectRecord(
                project_name="Example Heights",
                city="Gurgaon",
                description="Luxury homes",
                source_pages=["https://example.com/project"],
            )
        ],
        output_path=tmp_path,
    )

    txt_path = tmp_path / "all_scraped_data.txt"
    write_crawl_txt(txt_path, result)

    content = txt_path.read_text(encoding="utf-8")
    assert "BhumiBazar Scraped Data" in content
    assert "Project 1: Example Heights" in content
    assert "https://example.com/brochure.pdf" in content
    assert "Luxury homes" in content


def test_persist_result_writes_website_and_project_txt_exports(tmp_path):
    result = CrawlResult(
        website_id="example_com",
        builder_name="Example Builder",
        domain="example.com",
        crawl_id="crawl_001",
        started_at="2026-07-01T00:00:00+00:00",
        finished_at="2026-07-01T00:01:00+00:00",
        pages=["https://example.com/project"],
        downloads=[],
        projects=[ProjectRecord(project_name="Example Heights", city="Gurgaon", source_pages=["https://example.com/project"])],
        output_path=tmp_path,
    )

    persist_result(result)

    assert (tmp_path / "all_scraped_data.txt").exists()
    project_txt = tmp_path / "projects" / "example_heights" / "scraped_data.txt"
    assert project_txt.exists()
    assert "Example Heights" in project_txt.read_text(encoding="utf-8")
