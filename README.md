# Bhumi AI Real Estate Scraper Engine

A production-grade, dynamic web crawler for Indian real estate builder websites. It accepts a builder website URL, discovers internal pages, detects project pages, archives HTML, downloads public documents, creates image manifests, and writes project/website outputs under `SCRAPED_DATA/`.

## Version 1 Capabilities

- Dynamic URL input through FastAPI (`POST /crawl`) or the Python crawler API.
- Internal-only website crawling with sitemap generation.
- Dynamic project detection from URL, metadata, navigation, and page-content signals.
- Download support for PDFs, spreadsheets, documents, presentations, ZIP, and RAR files.
- HTML archiving for every crawled page.
- Image manifest creation without downloading image binaries.
- Project JSON, Excel, description, metadata, and folder creation.
- Website-level `website.json`, `latest.json`, `crawl_history.json`, `sitemap.xml`, and `master.xlsx`.
- Crawl version snapshots in `versions/crawl_###/` for historical comparison.

## Technology Stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.12 |
| Backend | FastAPI |
| Browser Automation | Playwright-ready dependency |
| HTML Parser | BeautifulSoup + lxml |
| Database | PostgreSQL-ready SQLAlchemy/Alembic dependencies |
| Background Jobs | Redis-ready dependency plus FastAPI background endpoint |
| PDF Processing | PyMuPDF + pdfplumber dependencies |
| Excel | OpenPyXL |
| Config | Pydantic Settings |

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.api:app --reload
```

Start a crawl:

```bash
curl -X POST http://127.0.0.1:8000/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://builderwebsite.com"}'
```

## Output Layout

```text
SCRAPED_DATA/
└── builder-domain/
    ├── website.json
    ├── latest.json
    ├── crawl_history.json
    ├── sitemap.xml
    ├── master.xlsx
    ├── images.json
    ├── pages/
    ├── downloads/
    ├── versions/crawl_001/
    └── projects/project_name/
        ├── project.json
        ├── project.xlsx
        ├── description.txt
        ├── images.json
        ├── metadata.json
        ├── raw_html/
        ├── brochures/
        ├── floor_plans/
        ├── master_plans/
        ├── layouts/
        └── documents/
```

## Python API

```python
from app.scraper.crawler import RealEstateCrawler

result = RealEstateCrawler().crawl("https://builderwebsite.com")
print(result.latest_payload())
```

## Anti-Blocking Headers, Pagination, and Google Sheets

The crawler sends browser-like request headers by default, including `User-Agent`, `Accept`, `Accept-Language`, `Referer`, cache-control headers, DNT, and upgrade hints. Override them with environment variables such as `BHUMI_USER_AGENT`, `BHUMI_ACCEPT_LANGUAGE`, and `BHUMI_REQUEST_REFERER`.

Pagination is discovered dynamically from internal links that look like `next`, `pagination`, `/page/2`, `?page=2`, `?paged=2`, or `?p=2`. Paginated pages are archived separately under `pages/paginated/`, regular pages are archived under `pages/standard/`, and discovered pagination links are written to `pagination.json`.

Google Sheets export is optional and organization-ready. Set these environment variables to sync crawl results into three worksheets: `Crawl Summary`, `Projects`, and `Downloads`.

```bash
export BHUMI_GOOGLE_SHEETS_SPREADSHEET_ID="your-spreadsheet-id"
export BHUMI_GOOGLE_SERVICE_ACCOUNT_JSON='/path/to/service-account.json'
```

If Google Sheets is not configured, the scraper writes `google_sheets_pending.json` with the same organized rows so the sync can be replayed later.

### Store Data in Google Sheets Instead of Local Folders

Set `BHUMI_STORAGE_BACKEND=google_sheets` to send crawl summaries, pages, projects, and download metadata to Google Sheets without writing the `SCRAPED_DATA/` folder tree. Binary downloads and archived HTML are represented as metadata rows in this mode because Google Sheets cannot store file binaries.

```bash
export BHUMI_STORAGE_BACKEND="google_sheets"
export BHUMI_GOOGLE_SHEETS_SPREADSHEET_ID="your-spreadsheet-id"
export BHUMI_GOOGLE_SERVICE_ACCOUNT_JSON='/path/to/service-account.json'
```

Use `BHUMI_STORAGE_BACKEND=both` when you want both Google Sheets sync and full filesystem archives/download folders.

## Playwright Rendering

The crawler uses Playwright by default (`BHUMI_USE_PLAYWRIGHT=true`) so JavaScript-heavy sites can render before extraction. Install the browser runtime before production crawls:

```bash
pip install -e '.[dev]'
playwright install chromium
```

Set `BHUMI_PLAYWRIGHT_HEADLESS=false` for visual debugging. If Playwright is unavailable in a minimal environment, the crawler falls back to the standard-library fetcher so tests and basic HTML sites still work.

### Reducing 403 Blocks with Playwright

For sites that block headless browsers, keep Playwright enabled and use the hardened Chromium context. The scraper now adds Chromium client hints, navigation `Sec-Fetch-*` headers, a realistic viewport/timezone/locale, HTTPS-error tolerance, and stealth JavaScript for common automation checks. If a target still blocks datacenter IPs, configure a residential or approved proxy:

```bash
export BHUMI_PLAYWRIGHT_PROXY="http://user:pass@host:port"
export BHUMI_PLAYWRIGHT_SLOW_MO_MS="50"
```
