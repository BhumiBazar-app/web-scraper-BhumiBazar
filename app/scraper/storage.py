from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree
try:
    from openpyxl import Workbook
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    Workbook = None
from app.models import CrawlResult, ProjectRecord
from app.scraper.utils import slugify


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def write_project_xlsx(path: Path, project: ProjectRecord) -> None:
    rows = [[key, ", ".join(value) if isinstance(value, list) else json.dumps(value) if isinstance(value, dict) else value] for key, value in asdict(project).items()]
    _write_xlsx(path, "Project", rows)


def write_master_xlsx(path: Path, projects: list[ProjectRecord]) -> None:
    rows = [["Project Name", "Builder", "Status", "RERA", "Starting Price", "Possession", "Unit Types", "Sizes", "Source Pages"]]
    for project in projects:
        rows.append([project.project_name, project.builder_name, project.status, project.rera_number, project.starting_price, project.possession_date, ", ".join(project.unit_types), ", ".join(project.sizes), ", ".join(project.source_pages)])
    _write_xlsx(path, "Projects", rows)


def _write_xlsx(path: Path, sheet_name: str, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if Workbook is not None:
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name
        for row in rows:
            ws.append(row)
        wb.save(path)
        return
    # Fallback keeps the pipeline operational when optional Excel dependency is absent.
    import csv
    fallback = path.with_suffix(".csv")
    with fallback.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def write_sitemap(path: Path, urls: list[str]) -> None:
    urlset = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for loc in urls:
        node = SubElement(urlset, "url")
        SubElement(node, "loc").text = loc
    path.parent.mkdir(parents=True, exist_ok=True)
    ElementTree(urlset).write(path, encoding="utf-8", xml_declaration=True)


def _txt_value(value: object) -> str:
    if value in (None, "", [], {}):
        return "Not found"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "Not found"
    if isinstance(value, dict):
        lines = []
        for key, items in value.items():
            rendered = ", ".join(str(item) for item in items) if isinstance(items, list) else str(items)
            lines.append(f"{key}: {rendered}")
        return "; ".join(lines) if lines else "Not found"
    return str(value)


def write_crawl_txt(path: Path, result: CrawlResult) -> None:
    """Write a human-readable TXT export containing the complete crawl summary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "BhumiBazar Scraped Data",
        "=======================",
        f"Generated At: {datetime.now(timezone.utc).isoformat()}",
        f"Website ID: {result.website_id}",
        f"Builder Name: {result.builder_name}",
        f"Domain: {result.domain}",
        f"Crawl ID: {result.crawl_id}",
        f"Status: {result.status}",
        f"Started At: {result.started_at}",
        f"Finished At: {result.finished_at}",
        f"Total Pages: {len(result.pages)}",
        f"Total Projects: {len(result.projects)}",
        f"Total Downloads: {len(result.downloads)}",
        f"Total Errors: {len(result.errors)}",
        "",
        "Pages",
        "-----",
    ]
    if result.pages:
        lines.extend(f"- {page}" for page in result.pages)
    else:
        lines.append("- Not found")
    lines.extend(["", "Projects", "--------"])
    if result.projects:
        for index, project in enumerate(result.projects, start=1):
            lines.extend([
                f"Project {index}: {project.project_name}",
                f"  Builder: {_txt_value(project.builder_name)}",
                f"  City: {_txt_value(project.city)}",
                f"  State: {_txt_value(project.state)}",
                f"  Country: {_txt_value(project.country)}",
                f"  Address: {_txt_value(project.address)}",
                f"  Status: {_txt_value(project.status)}",
                f"  RERA Number: {_txt_value(project.rera_number)}",
                f"  Starting Price: {_txt_value(project.starting_price)}",
                f"  Price Range: {_txt_value(project.price_range)}",
                f"  Possession Date: {_txt_value(project.possession_date)}",
                f"  Unit Types: {_txt_value(project.unit_types)}",
                f"  Sizes: {_txt_value(project.sizes)}",
                f"  Amenities: {_txt_value(project.amenities)}",
                f"  Specifications: {_txt_value(project.specifications)}",
                f"  Downloads: {_txt_value(project.downloads)}",
                f"  Source Pages: {_txt_value(project.source_pages)}",
                f"  Description: {_txt_value(project.description)}",
                "",
            ])
    else:
        lines.append("- Not found")
    lines.extend(["", "Downloads", "---------"])
    if result.downloads:
        for asset in result.downloads:
            lines.append(f"- [{asset.category}] {asset.url} (source: {asset.source_page}, path: {_txt_value(asset.path)})")
    else:
        lines.append("- Not found")
    lines.extend(["", "Errors", "------"])
    if result.errors:
        for error in result.errors:
            lines.append(f"- {error.get('url', 'unknown')}: {error.get('error_type', 'Error')} - {error.get('error', '')}")
    else:
        lines.append("- Not found")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def persist_result(result: CrawlResult) -> None:
    root = result.output_path
    versions = root / "versions" / result.crawl_id
    write_json(root / "latest.json", result.latest_payload())
    write_crawl_txt(root / "all_scraped_data.txt", result)
    write_json(root / "website.json", {"website_id": result.website_id, "builder_name": result.builder_name, "domain": result.domain})
    history_path = root / "crawl_history.json"
    history = []
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    history.append(result.latest_payload())
    write_json(history_path, history)
    write_json(versions / "crawl.json", {**result.latest_payload(), "pages": result.pages, "downloads": [asdict(d) for d in result.downloads]})
    write_sitemap(root / "sitemap.xml", result.pages)
    write_master_xlsx(root / "master.xlsx", result.projects)
    for project in result.projects:
        project_dir = root / "projects" / slugify(project.project_name, "project")
        write_json(project_dir / "project.json", asdict(project))
        project_txt_result = CrawlResult(
            result.website_id,
            result.builder_name,
            result.domain,
            result.crawl_id,
            result.started_at,
            result.finished_at,
            project.source_pages,
            [],
            [project],
            project_dir,
            status=result.status,
        )
        write_crawl_txt(project_dir / "scraped_data.txt", project_txt_result)
        (project_dir / "description.txt").write_text(project.description or "", encoding="utf-8")
        write_json(project_dir / "metadata.json", {"source_pages": project.source_pages, "crawl_id": result.crawl_id})
        write_json(project_dir / "images.json", [])
        write_project_xlsx(project_dir / "project.xlsx", project)
        for subdir in ("raw_html", "brochures", "floor_plans", "master_plans", "layouts", "documents"):
            (project_dir / subdir).mkdir(parents=True, exist_ok=True)
