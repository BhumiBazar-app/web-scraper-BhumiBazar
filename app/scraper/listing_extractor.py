from __future__ import annotations

import re
from typing import Any

from app.models import ProjectRecord
from app.scraper.classifier import page_text

PROJECT_NAME_PATTERN = re.compile(r"^(.+?)\s*\(([^()]+(?:sq\.ft|sqft|sq yd|sqyd)[^()]*)\)$", re.I)
PRICE_PATTERN = re.compile(r"^(?:₹)?\d[\d,.]*(?:\s*(?:L|Lac|Lacs|Cr|Crore))?(?:\s*-\s*(?:₹)?\d[\d,.]*(?:\s*(?:L|Lac|Lacs|Cr|Crore))?)?$", re.I)
ADDRESS_PATTERN = re.compile(r"\b(Noida|Greater Noida|Sector\s+\d+|Noida Extension|Greater Noida West)\b", re.I)
CONFIG_PATTERN = re.compile(r"\b\d(?:\.\d)?\s*BHK\b|\bStudio\b|\bPenthouse\b|\bVilla\b|\bDuplex\b|\bApartment\b|\bFlat\b", re.I)


def extract_listing_projects(page_url: str, soup: Any, builder_name: str) -> list[ProjectRecord]:
    """Extract project cards/tables from listing pages such as Housing.com Noida results."""

    lines = [line.strip() for line in page_text(soup).split(" ") if line.strip()]
    text = soup.get_text("\n", strip=True)
    compact_lines = _meaningful_lines(text)
    projects: list[ProjectRecord] = []
    projects.extend(_extract_inline_price_table(text, page_url, builder_name))
    projects.extend(_extract_price_table(compact_lines, page_url, builder_name))
    projects.extend(_extract_card_blocks(compact_lines, page_url, builder_name))
    return _dedupe(projects)


def _meaningful_lines(text: str) -> list[str]:
    raw = re.split(r"\n+|(?<=\))\s+(?=₹)|(?<=L)\s+(?=Sector|Noida)|(?<=Cr)\s+(?=Sector|Noida)", text)
    lines: list[str] = []
    for item in raw:
        item = re.sub(r"\s+", " ", item).strip()
        if item:
            lines.append(item)
    return lines


def _extract_inline_price_table(text: str, page_url: str, builder_name: str) -> list[ProjectRecord]:
    pattern = re.compile(
        r"([A-Z][A-Za-z0-9 .&'-]+?)\s*\(([^()]*?(?:sq\.ft|sqft|sq yd|sqyd)[^()]*)\)\s*"
        r"(₹\s*\d[\d,.]*\s*(?:L|Lac|Lacs|Cr|Crore)(?:\s*-\s*\d[\d,.]*\s*(?:L|Lac|Lacs|Cr|Crore))?)\s*"
        r"((?:Sector\s+\d+|Noida Extension|Greater Noida West|[^₹]{0,40}?Noida)[^₹]{0,60})",
        re.I,
    )
    projects: list[ProjectRecord] = []
    for match in pattern.finditer(text):
        address = re.split(r"\s+[A-Z][A-Za-z0-9 .&'-]+?\s*\(", match.group(4).strip())[0].strip()
        projects.append(ProjectRecord(
            project_name=match.group(1).strip(),
            builder_name=builder_name,
            city="Noida",
            state="Uttar Pradesh",
            address=address,
            price_range=match.group(3).strip(),
            starting_price=match.group(3).split("-")[0].strip(),
            sizes=[match.group(2).strip()],
            source_pages=[page_url],
        ))
    return projects


def _extract_price_table(lines: list[str], page_url: str, builder_name: str) -> list[ProjectRecord]:
    projects: list[ProjectRecord] = []
    for index, line in enumerate(lines):
        match = PROJECT_NAME_PATTERN.match(line)
        if not match or index + 2 >= len(lines):
            continue
        price = lines[index + 1]
        address = lines[index + 2]
        if not PRICE_PATTERN.match(price) or not ADDRESS_PATTERN.search(address):
            continue
        projects.append(ProjectRecord(
            project_name=match.group(1).strip(),
            builder_name=builder_name,
            city="Noida" if "Noida" in address else None,
            state="Uttar Pradesh",
            address=address,
            price_range=price,
            starting_price=price.split("-")[0].strip(),
            sizes=[match.group(2).strip()],
            source_pages=[page_url],
        ))
    return projects


def _extract_card_blocks(lines: list[str], page_url: str, builder_name: str) -> list[ProjectRecord]:
    projects: list[ProjectRecord] = []
    for index, line in enumerate(lines):
        if not (line.startswith("₹") and index + 2 < len(lines)):
            continue
        price = line
        name = lines[index + 1]
        config = lines[index + 2] if index + 2 < len(lines) else ""
        address = lines[index + 3] if index + 3 < len(lines) else ""
        if not name or len(name) > 100 or not ADDRESS_PATTERN.search(address + " " + config):
            continue
        unit_types = sorted(set(CONFIG_PATTERN.findall(config)), key=str.lower)
        projects.append(ProjectRecord(
            project_name=name,
            builder_name=builder_name,
            city="Noida" if "Noida" in f"{address} {config}" else None,
            state="Uttar Pradesh",
            address=address if ADDRESS_PATTERN.search(address) else None,
            price_range=price,
            starting_price=price.split("-")[0].strip(),
            unit_types=unit_types,
            source_pages=[page_url],
        ))
    return projects


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
