from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse
from typing import Any
from app.models import ImageReference, ProjectRecord
from app.scraper.classifier import page_text


def extract_builder_name(base_url: str, soup: Any | None = None) -> str:
    if soup:
        og = soup.find("meta", property="og:site_name")
        if og and og.get("content"):
            return og.get("content").strip()
        if soup.title and soup.title.string:
            return soup.title.string.split("|")[0].split("-")[0].strip()
    host = urlparse(base_url).netloc.replace("www.", "")
    return host.split(".")[0].replace("-", " ").title()


def extract_images(page_url: str, soup: Any) -> list[ImageReference]:
    images: list[ImageReference] = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        absolute = urljoin(page_url, src)
        path = urlparse(absolute).path
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else None
        alt = img.get("alt")
        image_type = "gallery" if "gallery" in page_url.lower() else "project"
        images.append(ImageReference(absolute, page_url, image_type, alt, ext))
    return images


def extract_project(page_url: str, soup: Any, builder_name: str) -> ProjectRecord:
    text = page_text(soup)
    heading = soup.find(["h1", "h2"])
    title = (heading.get_text(" ", strip=True) if heading else None) or (soup.title.string if soup.title else "Project")
    title = re.sub(r"\s+", " ", title).strip()
    rera_values = re.findall(r"[A-Z]{2,5}/P/\d{4}/\d+|[A-Z]\d{6,}|P\d{10,}", text, re.I)
    rera = re.search(r"(?:RERA\s*(?:No\.?|Number|ID|Registration No\.)?\s*[:#-]?\s*)([A-Z0-9/,\s-]{6,})", text, re.I)
    price = re.search(r"(?:₹|Rs\.?|INR)\s*[\d,.]+\s*(?:Lakhs|Lakh|Crore|Cr|L)?(?:\s*-\s*(?:₹|Rs\.?|INR)?\s*[\d,.]+\s*(?:Lakhs|Lakh|Crore|Cr|L)?)?", text, re.I)
    if not rera_values and rera:
        rera_values = [item.strip() for item in re.split(r",|\s+and\s+", rera.group(1)) if item.strip()]
    possession = re.search(r"possession\s*(?:date)?\s*[:\-]?\s*([A-Za-z]+\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text, re.I)
    amenities = sorted(set(re.findall(r"\b(?:clubhouse|gym|fitness center|pool|security|cctv|garden|gardens|park|parking|lift|spa|play area|jogging track|cafe|café|power backup|wi-?fi|fire fighting|yoga lounge|laundry|housekeeping|concierge|business lounge|reception lobby|indoor recreational room)\b", text, re.I)), key=str.lower)
    unit_types = sorted(set(re.findall(r"\b\d\s*BHK\b|\bStudio\b", text, re.I)), key=str.lower)
    sizes = sorted(set(re.findall(r"\b\d{2,5}\s*(?:sq\.?\s*ft|sqft|sq\.\s*yd|sqyd)\b", text, re.I)), key=str.lower)
    city = _first_match(text, [r"Luxury Apartment in ([A-Za-z ]+?)(?:\s+Starting|\s+RERA|$)", r"Tehsil-\s*([A-Za-z ]+)"])
    state = "Rajasthan" if re.search(r"\bRajasthan\b", text, re.I) else None
    address = _first_match(text, [r"Registered Office\s*:\s*(.+?\d{6})", r"Corporate Office\s*:\s*(.+?\d{6})"])
    status = "RERA Approved" if re.search(r"RERA Approved|RERA Registration", text, re.I) else None
    description = text[:1200]
    maps = soup.find("a", href=re.compile(r"google\.[^/]+/maps|maps\.app\.goo\.gl", re.I))
    return ProjectRecord(
        project_name=title,
        builder_name=builder_name,
        city=city.strip() if city else None,
        state=state,
        address=address.strip() if address else None,
        description=description,
        status=status,
        rera_number=", ".join(dict.fromkeys(rera_values)) if rera_values else (rera.group(1).strip() if rera else None),
        google_maps_url=maps.get("href") if maps else None,
        possession_date=possession.group(1) if possession else None,
        starting_price=price.group(0) if price else None,
        price_range=price.group(0) if price else None,
        unit_types=unit_types,
        sizes=sizes,
        amenities=amenities,
        source_pages=[page_url],
    )


def _first_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return None
