from __future__ import annotations

import re
from typing import Any

PROJECT_KEYWORDS = {
    "residential", "commercial", "villa", "villas", "plot", "plots", "township",
    "project", "projects", "apartment", "apartments", "homes", "estate", "residency",
}
DOCUMENT_CATEGORIES = {
    "brochure": ("brochure", "catalogue"),
    "floor_plans": ("floor", "unit plan", "floorplan"),
    "master_plans": ("master plan", "site plan"),
    "layouts": ("layout", "plot plan"),
    "documents": ("price", "payment", "legal", "rera", "form", "inventory", "construction", "download"),
}
DOWNLOAD_EXTENSIONS = {".pdf", ".xls", ".xlsx", ".doc", ".docx", ".pptx", ".zip", ".rar"}


def page_text(soup: Any) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def looks_like_project(url: str, soup: Any) -> bool:
    text = page_text(soup).lower()
    url_lower = url.lower()
    keyword_hits = sum(1 for word in PROJECT_KEYWORDS if word in url_lower or word in text)
    signal_hits = sum(1 for pattern in ("rera", "possession", "amenit", "floor plan", "sq.ft", "sq ft", "price") if pattern in text)
    return keyword_hits >= 2 or (keyword_hits >= 1 and signal_hits >= 2)


def classify_document(url: str, label: str = "") -> str:
    haystack = f"{url} {label}".lower()
    for category, needles in DOCUMENT_CATEGORIES.items():
        if any(needle in haystack for needle in needles):
            return category
    return "documents"
