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

Tip: run the commands from the repository root so `uvicorn` can import `app.api` and the scraper writes outputs to the expected `SCRAPED_DATA/` directory.

## Sync Your Local Branch With the Git Repo

If your local files do not match the code shown on the Git repo branch or PR, fetch the remote branch and check out the exact branch before running the app:

```bash
git fetch origin
git branch -r
git checkout <branch-name>
git pull --ff-only origin <branch-name>
git log -1 --oneline
```

If you already have local edits, either commit them or stash them before pulling:

```bash
git status
git stash push -m "save local changes before syncing"
git pull --ff-only origin <branch-name>
```

After syncing, rerun `python -m compileall app tests` and `pytest -q` to confirm the checked-out code is runnable locally.

## Crawler Politeness and Rendering Configuration

The crawler starts with a lightweight HTTP session that preserves cookies and follows redirects. Pages that appear JavaScript-heavy can be rendered with Playwright when `BHUMI_ENABLE_BROWSER_RENDERING=true`. Keep crawling compliant: respect each site's `robots.txt`, Terms of Service, and any available official APIs. The scraper classifies blocked, rate-limited, or CAPTCHA pages for manual review rather than repeatedly retrying them.

Useful environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BHUMI_REQUEST_DELAY_SECONDS` | `1.0` | Delay between requests to the same domain. |
| `BHUMI_FETCH_RETRY_COUNT` | `2` | Retry count for retryable transient failures. |
| `BHUMI_FETCH_RETRY_BACKOFF_SECONDS` | `0.75` | Exponential backoff base delay. |
| `BHUMI_MAX_CONCURRENT_REQUESTS_PER_DOMAIN` | `1` | Per-domain concurrency limit; the current crawler runs serially by default. |
| `BHUMI_ENABLE_BROWSER_RENDERING` | `true` | Enable Playwright fallback for JavaScript-heavy pages. |
| `BHUMI_BROWSER_TIMEOUT_SECONDS` | `30` | Browser navigation and network-idle timeout. |
| `BHUMI_RESPECT_ROBOTS_TXT` | `true` | Respect robots.txt before fetching pages. |

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
