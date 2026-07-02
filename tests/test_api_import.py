from app.api import app


def test_uvicorn_app_imports_successfully():
    assert app.title == "Bhumi AI Real Estate Scraper Engine"
