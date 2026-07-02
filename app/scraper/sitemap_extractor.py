from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from app.models import ProjectRecord

SKIP_LABELS = {
    "home", "all projects", "ready to move", "under construction", "new launch", "locations",
    "about us", "blogs", "contact us", "site map", "privacy policy", "developer",
}
SKIP_PREFIXES = (
    "apartments ", "developers ", "duplex ", "flats ", "floors ", "homes ", "houses ",
    "penthouses ", "properties ", "villas ", "projects in sector", "luxury apartments",
    "luxury flats", "luxury houses", "luxury projects", "luxury properties", "luxury homes",
    "builder floors", "3 bhk", "bangalore", "delhi", "mumbai", "pune", "dubai", "gurgaon",
)


def extract_sitemap_projects(page_url: str, soup: Any, builder_name: str) -> list[ProjectRecord]:
    """Extract project directory entries from HTML site-map pages."""

    text = soup.get_text(" ", strip=True).lower()
    if "site map" not in text:
        return []
    projects: list[ProjectRecord] = []
    for link in soup.find_all("a", href=True):
        label = link.get_text(" ", strip=True).strip()
        if not _looks_like_project_label(label):
            continue
        href = urljoin(page_url, link.get("href"))
        projects.append(ProjectRecord(
            project_name=label,
            builder_name=builder_name,
            source_pages=[href],
            description=f"Project discovered from site map: {page_url}",
        ))
    return _dedupe(projects)


def _looks_like_project_label(label: str) -> bool:
    normalized = " ".join(label.lower().split())
    if not normalized or normalized in SKIP_LABELS:
        return False
    if normalized.startswith(SKIP_PREFIXES):
        return False
    return any(token in normalized for token in (" ", "m3m", "dlf", "sobha", "emaar", "godrej", "tata", "azizi", "binghatti"))


def _dedupe(projects: list[ProjectRecord]) -> list[ProjectRecord]:
    seen: set[str] = set()
    unique: list[ProjectRecord] = []
    for project in projects:
        key = project.project_name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(project)
    return unique
