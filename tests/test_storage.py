from app.scraper.utils import domain_slug, slugify


def test_slugify_normalizes_project_names():
    assert slugify("Skyline Residency - Phase 1") == "skyline_residency_phase_1"


def test_domain_slug_removes_www_and_protocol():
    assert domain_slug("https://www.builder-example.com/projects") == "builder_example_com"
