from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.config import settings
from app.models import CrawlResult, ProjectRecord
from app.scraper.storage import write_json

PROJECT_HEADERS = [
    "Website ID", "Crawl ID", "Project Name", "Builder", "City", "State", "Country",
    "Status", "RERA Number", "Starting Price", "Price Range", "Possession Date",
    "Address", "Amenities", "Source Pages",
]
DOWNLOAD_HEADERS = ["Website ID", "Crawl ID", "Category", "URL", "Source Page", "Local Path", "Content Hash"]
PAGE_HEADERS = ["Website ID", "Crawl ID", "Page URL"]
SUMMARY_HEADERS = ["Website ID", "Builder", "Domain", "Crawl ID", "Status", "Pages", "Projects", "Downloads", "Started", "Finished"]


def sync_crawl_to_google_sheets(result: CrawlResult, write_pending: bool = True) -> dict[str, Any]:
    """Sync crawl outputs to Google Sheets when credentials are configured.

    If credentials or optional dependencies are missing, a pending payload is written locally
    so operators can replay the sync without losing organization-ready rows.
    """

    payload = _payload(result)
    if _missing_google_sheet_config():
        if write_pending:
            pending_path = result.output_path / "google_sheets_pending.json"
            write_json(pending_path, {"status": "not_configured", "payload": payload})
            return {"status": "not_configured", "path": str(pending_path)}
        return {"status": "not_configured", "reason": "Set BHUMI_GOOGLE_SHEETS_SPREADSHEET_ID and BHUMI_GOOGLE_SERVICE_ACCOUNT_JSON"}

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional packages
        if write_pending:
            pending_path = result.output_path / "google_sheets_pending.json"
            write_json(pending_path, {"status": "missing_dependency", "error": str(exc), "payload": payload})
            return {"status": "missing_dependency", "path": str(pending_path), "error": str(exc)}
        return {"status": "missing_dependency", "error": str(exc)}

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials_info = _load_credentials(settings.google_service_account_json)
    credentials = Credentials.from_service_account_info(credentials_info, scopes=scopes)
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(settings.google_sheets_spreadsheet_id)

    _upsert_worksheet(spreadsheet, "Crawl Summary", [SUMMARY_HEADERS, payload["summary"]])
    _upsert_worksheet(spreadsheet, "Projects", [PROJECT_HEADERS, *payload["projects"]])
    _upsert_worksheet(spreadsheet, "Pages", [PAGE_HEADERS, *payload["pages"]])
    _upsert_worksheet(spreadsheet, "Downloads", [DOWNLOAD_HEADERS, *payload["downloads"]])
    return {"status": "synced", "spreadsheet_id": settings.google_sheets_spreadsheet_id}


def _missing_google_sheet_config() -> bool:
    return (
        not settings.google_sheets_spreadsheet_id
        or settings.google_sheets_spreadsheet_id == "your-spreadsheet-id"
        or not settings.google_service_account_json
    )


def _payload(result: CrawlResult) -> dict[str, Any]:
    return {
        "summary": [
            result.website_id, result.builder_name, result.domain, result.crawl_id, result.status,
            len(result.pages), len(result.projects), len(result.downloads), result.started_at, result.finished_at,
        ],
        "projects": [_project_row(result, project) for project in result.projects],
        "pages": [[result.website_id, result.crawl_id, page] for page in result.pages],
        "downloads": [[result.website_id, result.crawl_id, d.category, d.url, d.source_page, d.path, d.content_hash] for d in result.downloads],
    }


def _project_row(result: CrawlResult, project: ProjectRecord) -> list[Any]:
    data = asdict(project)
    return [
        result.website_id, result.crawl_id, data["project_name"], data["builder_name"], data["city"],
        data["state"], data["country"], data["status"], data["rera_number"], data["starting_price"],
        data["price_range"], data["possession_date"], data["address"], ", ".join(data["amenities"]),
        ", ".join(data["source_pages"]),
    ]


def _load_credentials(raw: str) -> dict[str, Any]:
    candidate = Path(raw)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(raw)


def _upsert_worksheet(spreadsheet: Any, title: str, rows: list[list[Any]]) -> None:
    try:
        worksheet = spreadsheet.worksheet(title)
        worksheet.clear()
    except Exception:  # gspread raises WorksheetNotFound; avoid tight dependency in fallback envs.
        worksheet = spreadsheet.add_worksheet(title=title, rows=max(len(rows), 100), cols=max(len(rows[0]), 20))
    worksheet.update(rows, value_input_option="USER_ENTERED")
