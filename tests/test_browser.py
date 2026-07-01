from app.scraper.browser import _browser_headers


def test_browser_headers_include_chromium_fetch_metadata():
    headers = _browser_headers({"User-Agent": "UA", "Accept-Language": "en-IN,en;q=0.9"})

    assert "User-Agent" not in headers
    assert headers["sec-ch-ua-platform"] == '"Windows"'
    assert headers["Sec-Fetch-Mode"] == "navigate"
    assert headers["Sec-Fetch-User"] == "?1"
