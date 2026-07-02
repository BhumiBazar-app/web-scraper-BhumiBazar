from app.scraper.html import parse_html
from app.scraper.sitemap_extractor import extract_sitemap_projects


def test_extracts_luxury_residences_site_map_projects():
    soup = parse_html("""
    <html><body><h1>Site Map</h1><h2>Gurugram</h2>
    <ul><li><a href="/emaar-serenity-hills/">Emaar Serenity Hills</a></li>
    <li><a href="/projects">All Projects</a></li>
    <li><a href="/paras-quartier/">Paras Quartier</a></li></ul></body></html>
    """)

    projects = extract_sitemap_projects("https://www.luxuryresidences.in/site-map/", soup, "Luxury Residences")

    assert [project.project_name for project in projects] == ["Emaar Serenity Hills", "Paras Quartier"]
    assert projects[0].source_pages == ["https://www.luxuryresidences.in/emaar-serenity-hills/"]
