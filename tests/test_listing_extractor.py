from app.scraper.html import parse_html
from app.scraper.listing_extractor import extract_listing_projects


def test_extracts_housing_noida_listing_table_projects():
    soup = parse_html("""
    <html><body>
    <p>Capital Hometech Pride 2 (650 sq.ft)</p><p>₹28.0 L - 56.0 L</p><p>Sector 74, Noida</p>
    <p>Capital Metro Height (650 sq.ft)</p><p>₹25.0 L - 58.0 L</p><p>Sector 72, Noida</p>
    </body></html>
    """)

    projects = extract_listing_projects("https://housing.com/in/buy/noida/projects/", soup, "Housing.com")

    assert [project.project_name for project in projects] == ["Capital Hometech Pride 2", "Capital Metro Height"]
    assert projects[0].price_range == "₹28.0 L - 56.0 L"
    assert projects[0].address == "Sector 74, Noida"
    assert projects[0].state == "Uttar Pradesh"
