# Bhumi AI Real Estate Scraper Engine

A production-grade, dynamic web crawler for Indian real estate builder websites. It accepts a builder website URL, discovers internal pages, detects project pages, archives HTML, downloads public documents, creates image manifests, and writes project/website outputs under `SCRAPED_DATA/`.

## Version 1 Capabilities

- Dynamic URL input through FastAPI (`POST /crawl`), the Python crawler API, or the terminal script (`scrape_to_txt.py`).
- Internal-only website crawling with sitemap generation.
- Dynamic project detection from URL, metadata, navigation, and page-content signals.
- Download support for PDFs, spreadsheets, documents, presentations, ZIP, and RAR files.
- HTML archiving for every crawled page.
- Image manifest creation without downloading image binaries.
- Project JSON, Excel, description, metadata, and folder creation.
- Website-level `website.json`, `latest.json`, `crawl_history.json`, `sitemap.xml`, `master.xlsx`, and `all_scraped_data.txt`.
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
    ├── all_scraped_data.txt
    ├── images.json
    ├── pages/
    ├── downloads/
    ├── versions/crawl_001/
    └── projects/project_name/
        ├── project.json
        ├── project.xlsx
        ├── description.txt
        ├── scraped_data.txt
        ├── images.json
        ├── metadata.json
        ├── raw_html/
        ├── brochures/
        ├── floor_plans/
        ├── master_plans/
        ├── layouts/
        └── documents/
```


## Command-Line TXT Scraper

Use this method when you want to run the scraper directly from your terminal instead of starting the FastAPI server. The script asks for, or receives, one website URL and then writes the usual `SCRAPED_DATA/` folder plus TXT files that are easy to open locally.

### 1. Prepare your local environment

Run these commands from the repository root after cloning or pulling the latest branch:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

On Windows PowerShell, activate the virtual environment with:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e '.[dev]'
```

If you want browser rendering for JavaScript-heavy websites, install Chromium for Playwright once:

```bash
playwright install chromium
```

### 2. Run the script with a URL

Pass the builder or project website URL directly on the command line:

```bash
python scrape_to_txt.py https://builderwebsite.com
```

Example with a custom output folder and a smaller crawl limit for quick local testing:

```bash
python scrape_to_txt.py https://builderwebsite.com --data-root SCRAPED_DATA --max-pages 25
```

You can also run the script without a URL. It will prompt you to enter one:

```bash
python scrape_to_txt.py
# Enter website URL to scrape: https://builderwebsite.com
```

After installing the package with `pip install -e '.[dev]'`, you can use the console command instead of the Python file path:

```bash
bhumi-scrape https://builderwebsite.com --max-pages 25
```

### 3. Read the generated TXT output

When the command finishes, it prints a summary similar to this:

```text
Scrape status: completed
Pages scraped: 12
Projects found: 3
Downloads found: 5
TXT output: SCRAPED_DATA/builderwebsite_com/all_scraped_data.txt
```

Open the printed TXT file to inspect all scraped data in one place:

```bash
cat SCRAPED_DATA/builderwebsite_com/all_scraped_data.txt
```

Each detected project also receives its own TXT file:

```text
SCRAPED_DATA/builderwebsite_com/projects/project_name/scraped_data.txt
```

### 4. Useful local testing commands

Limit the crawl while checking that the script works:

```bash
python scrape_to_txt.py https://builderwebsite.com --max-pages 5
```

Use a throwaway output directory so test runs do not mix with existing data:

```bash
python scrape_to_txt.py https://builderwebsite.com --data-root LOCAL_TEST_SCRAPED_DATA --max-pages 5
```

Disable Playwright if your local machine does not have browser dependencies installed and you only want to test basic HTTP fetching:

```bash
BHUMI_USE_PLAYWRIGHT=false python scrape_to_txt.py https://builderwebsite.com --max-pages 5
```

On Windows PowerShell, set that environment variable for the current command like this:

```powershell
$env:BHUMI_USE_PLAYWRIGHT = "false"
python scrape_to_txt.py https://builderwebsite.com --max-pages 5
Remove-Item Env:\BHUMI_USE_PLAYWRIGHT
```

### 5. What files should you expect?

For `https://builderwebsite.com`, the output folder will usually look like this:

```text
SCRAPED_DATA/
└── builderwebsite_com/
    ├── all_scraped_data.txt      # Full crawl summary in TXT format
    ├── latest.json               # Machine-readable summary
    ├── website.json              # Website metadata
    ├── sitemap.xml               # URLs discovered during crawling
    ├── master.xlsx               # Project spreadsheet
    ├── pages/                    # Archived HTML pages
    ├── downloads/                # Downloaded brochures/documents
    └── projects/
        └── project_name/
            ├── scraped_data.txt  # Project-specific TXT data
            ├── description.txt
            ├── project.json
            └── project.xlsx
```

If the command exits with `Scrape status: blocked` or `Scrape status: failed`, check `SCRAPED_DATA/<domain>/logs/` for detailed fetch or error logs. Some websites block datacenter IPs, headless browsers, or automated requests; in those cases, try a smaller `--max-pages` value, enable Playwright, or configure an approved proxy as described below.

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
 
