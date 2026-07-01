from app.scraper.classifier import classify_document, looks_like_project
from app.scraper.html import parse_html


def test_classifies_project_page_from_content_signals():
    soup = parse_html("""
    <html><h1>Skyline Residency</h1><p>Residential project with RERA ABC12345,
    possession December 2028, floor plan, clubhouse and 2 BHK homes.</p></html>
    """)
    assert looks_like_project("https://example.com/projects/skyline", soup)


def test_classifies_download_category():
    assert classify_document("https://example.com/files/Skyline-Brochure.pdf") == "brochure"
    assert classify_document("https://example.com/files/tower-floor-plan.pdf") == "floor_plans"
