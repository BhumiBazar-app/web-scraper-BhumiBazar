from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class DownloadedAsset:
    url: str
    source_page: str
    path: str
    category: str
    content_hash: str | None = None


@dataclass(slots=True)
class ImageReference:
    url: str
    source_page: str
    image_type: str
    alt_text: str | None
    file_extension: str | None
    crawl_timestamp: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class ProjectRecord:
    project_name: str
    builder_name: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "India"
    sector: str | None = None
    address: str | None = None
    google_maps_url: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    description: str | None = None
    status: str | None = None
    launch_date: str | None = None
    possession_date: str | None = None
    rera_number: str | None = None
    rera_link: str | None = None
    phase_information: str | None = None
    unit_types: list[str] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)
    carpet_area: list[str] = field(default_factory=list)
    built_up_area: list[str] = field(default_factory=list)
    super_area: list[str] = field(default_factory=list)
    starting_price: str | None = None
    price_range: str | None = None
    price_per_sq_ft: str | None = None
    amenities: list[str] = field(default_factory=list)
    specifications: list[str] = field(default_factory=list)
    downloads: dict[str, list[str]] = field(default_factory=dict)
    source_pages: list[str] = field(default_factory=list)
    images_manifest: str | None = None


@dataclass(slots=True)
class CrawlResult:
    website_id: str
    builder_name: str
    domain: str
    crawl_id: str
    started_at: str
    finished_at: str
    pages: list[str]
    downloads: list[DownloadedAsset]
    projects: list[ProjectRecord]
    output_path: Path
    status: str = "completed"

    def latest_payload(self) -> dict[str, Any]:
        return {
            "website_id": self.website_id,
            "builder_name": self.builder_name,
            "domain": self.domain,
            "crawl_id": self.crawl_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "total_pages": len(self.pages),
            "total_downloads": len(self.downloads),
            "total_projects": len(self.projects),
        }
